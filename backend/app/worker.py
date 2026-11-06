"""Durable database queue worker. Run separately: python -m backend.app.worker."""
import hashlib
import json
import logging
import os
import signal
import time
import uuid
from pathlib import Path
from sqlalchemy import select, update
from .database import DATA_DIR, SessionLocal, Job, Resource, Notice, Lease, init_db
from . import artifacts

log=logging.getLogger('pricemesh.worker')
class Cancelled(Exception): pass

def artifact_folder(identifier):
    return artifacts.folder(identifier)

def save_json(path,data):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,allow_nan=False),encoding='utf-8')
    temporary.replace(path)

def process(job_id,worker_id='local-worker'):
    from pricing.environment import Market,baseline_actions
    from pricing.evaluation import evaluate,rollout
    from pricing.learning import train,load_policy
    with SessionLocal() as db:
        job=db.get(Job,job_id)
        config=job.config
        owner_id=job.owner_id
    folder=artifact_folder(job_id)
    def progress(completed,total,metrics=None):
        with SessionLocal() as db:
            job=db.get(Job,job_id)
            if job.cancel_requested: raise Cancelled()
            job.completed,job.total,job.heartbeat=completed,total,time.time()
            history=job.details.get('history',[])
            if metrics: history=(history+[metrics])[-1000:]
            job.details={'latest':metrics or {},'history':history}
            lease=db.get(Lease,worker_id)
            if lease: lease.heartbeat=time.time()
            db.commit()
    progress(0,1)
    scenario=config['scenario']
    settings=config['settings']
    result={};kind=''
    if config['type']=='training':
        _,history,metadata=train(scenario,settings,folder,progress)
        checksum=hashlib.sha256((folder/'weights.npz').read_bytes()).hexdigest()
        kind='policy';result={'history':history,'metadata':metadata,'artifact_id':job_id,'checksum':checksum,
                             'scenario':scenario,'settings':settings,'training_seed':settings['seed']}
    elif config['type']=='dataset':
        rows=[]
        for episode in range(settings['episodes']):
            metrics,records=rollout(scenario,settings['seed']+episode,None,settings['strategy'])
            for row in records: row.update(episode=episode,seed=settings['seed']+episode)
            rows.extend(records)
            progress(episode+1,settings['episodes'])
        save_json(folder/'records.json',rows)
        kind='dataset';result={'row_count':len(rows),'artifact_id':job_id,'settings':settings,'scenario':scenario,
            'quality':{'missing_values':sum(v is None for row in rows for v in row.values()),
                       'negative_inventory':sum(r['inventory']<0 for r in rows),
                       'invalid_accounting':sum(abs(r['revenue']-r['units']*r['price'])>1e-6 for r in rows)},
            'checksum':hashlib.sha256((folder/'records.json').read_bytes()).hexdigest()}
    elif config['type'] in ('evaluation','simulation','sensitivity'):
        policy=None
        if config.get('policy_artifact'):
            policy,_=load_policy(artifacts.policy_folder(config['policy_artifact']))
        if config['type'] in ('evaluation','sensitivity'):
            kind='evaluation';result=evaluate(scenario,settings,policy,progress)
            result.update(scenario=scenario,policy_id=settings.get('policy_id'))
            save_json(folder/'evaluation.json',result)
        else:
            kind='simulation'
            env=Market(scenario,settings['seed'])
            while env.t<env.horizon:
                with SessionLocal() as db:
                    running=db.get(Job,job_id)
                    if running.cancel_requested: raise Cancelled()
                    running.heartbeat=time.time()
                    lease=db.get(Lease,worker_id)
                    if lease: lease.heartbeat=time.time()
                    paused=running.control=='paused' and running.step_requests==0
                    if running.control=='paused' and running.step_requests>0:
                        running.step_requests-=1
                    db.commit()
                if paused:
                    time.sleep(.25);continue
                actions=policy.actions(env.observe()) if policy is not None else baseline_actions(env,settings['strategy'])
                env.step(actions)
                metrics=env.metrics()
                progress(env.t,env.horizon,{'step':env.t,**metrics,'records':env.records[-env.n:]})
                time.sleep(settings.get('step_delay',.25))
            metrics,records=env.metrics(),env.records
            save_json(folder/'records.json',records)
            result={'metrics':metrics,'artifact_id':job_id,'row_count':len(records),'scenario':scenario,'settings':settings}
    else: raise ValueError('Unsupported job type')
    from .tracking import mirror
    result['tracking']=mirror(job_id,kind,settings,result,folder)
    artifacts.publish(job_id)
    with SessionLocal() as db:
        job=db.get(Job,job_id)
        if job.cancel_requested: raise Cancelled()
        resource=Resource(owner_id=owner_id,kind=kind,name=settings.get('name',config['name']),
                          source_id=config.get('source_id'),data=result)
        db.add(resource);db.flush()
        job.status='completed';job.result_id=resource.id;job.completed=job.total;job.heartbeat=time.time()
        db.add(Notice(owner_id=owner_id,job_id=job.id,message=f'{kind.title()} completed: {resource.name}'))
        db.commit()

def run_once(worker_id='local-worker'):
    now=time.time()
    with SessionLocal() as db:
        lease=db.get(Lease,worker_id)
        if lease: lease.heartbeat=now
        else: db.add(Lease(id=worker_id,heartbeat=now))
        # Recover abandoned work honestly as failed, never report false success.
        db.execute(update(Job).where(Job.status=='running',Job.heartbeat<now-600).values(status='failed',error='Worker lease expired; submit a new run to retry.'))
        candidate=db.scalar(select(Job.id).where(Job.status=='queued').order_by(Job.created_at).limit(1))
        db.commit()
        if not candidate: return False
        changed=db.execute(update(Job).where(Job.id==candidate,Job.status=='queued').values(status='running',heartbeat=now))
        db.commit()
        if changed.rowcount!=1: return True
    try: process(candidate,worker_id)
    except Exception as exc:
        log.exception('Job failed: %s',candidate)
        with SessionLocal() as db:
            job=db.get(Job,candidate)
            job.status='cancelled' if isinstance(exc,Cancelled) else 'failed'
            job.error=None if isinstance(exc,Cancelled) else f'{type(exc).__name__}: {str(exc)[:500]}'
            job.heartbeat=time.time()
            db.add(Notice(owner_id=job.owner_id,job_id=job.id,message=f'{job.kind.title()} {job.status}'))
            db.commit()
    return True

def main():
    logging.basicConfig(level=logging.INFO)
    if os.getenv('AUTO_MIGRATE')=='1':
        from .database import migrate_db
        migrate_db()
    else:init_db()
    worker_id=f'worker-{os.getpid()}'
    stop=False
    def shutdown(*_):
        nonlocal stop
        stop=True
    signal.signal(signal.SIGINT,shutdown);signal.signal(signal.SIGTERM,shutdown)
    while not stop:
        if not run_once(worker_id): time.sleep(float(os.getenv('WORKER_POLL_SECONDS','1')))

if __name__=='__main__': main()
