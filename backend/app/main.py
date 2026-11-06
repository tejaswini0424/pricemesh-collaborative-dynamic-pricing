import asyncio
import csv
import html
import io
import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlalchemy import select, func, text, update
from sqlalchemy.exc import IntegrityError
from .database import (SessionLocal, User, LoginSession, Resource, Job, Notice, Audit, Lease,
                       get_db, init_db, public_resource, public_job, DATA_DIR)
from .security import current_user, hash_password, verify_password, access_token, digest, DUMMY_PASSWORD_HASH
from .schemas import Credentials, Catalog, Scenario, Experiment, Generate, Evaluate, Simulate, Report, Settings, Compare, Drift, Diagnostics, Sensitivity, Control, Profile, UserUpdate
from . import artifacts

logging.basicConfig(level=os.getenv('LOG_LEVEL','INFO'))
log=logging.getLogger('pricemesh.api')
ORIGINS=[x.strip() for x in os.getenv('CORS_ORIGINS','http://127.0.0.1:5173,http://localhost:5173').split(',') if x.strip()]
PRODUCTION=os.getenv('APP_ENV')=='production'

@asynccontextmanager
async def lifespan(app):
    if os.getenv('AUTO_MIGRATE')=='1':
        from .database import migrate_db
        await asyncio.to_thread(migrate_db)
    elif not PRODUCTION: init_db()
    yield

app=FastAPI(title='PriceMesh Research API',version='1.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=ORIGINS,allow_credentials=True,allow_methods=['GET','POST','PATCH','PUT'],allow_headers=['Content-Type','Authorization','X-Requested-With'])

@app.middleware('http')
async def security_headers(request,call_next):
    if request.method=='POST' and request.url.path.startswith('/api/v1/auth/'):
        origin=request.headers.get('origin')
        if origin and origin not in ORIGINS:
            return Response('Origin not permitted',status_code=403)
    try: content_length=int(request.headers.get('content-length','0') or 0)
    except ValueError: return Response('Invalid Content-Length',status_code=400)
    if content_length>1_000_000:
        return Response('Request too large',status_code=413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Cache-Control']='no-store'
    return response

def resource(db,identifier,owner,kind=None):
    row=db.get(Resource,identifier)
    if not row or row.owner_id!=owner or (kind and row.kind!=kind): raise HTTPException(404,'Resource not found')
    return row
def job_row(db,identifier,owner):
    row=db.get(Job,identifier)
    if not row or row.owner_id!=owner: raise HTTPException(404,'Job not found')
    return row
def create_resource(db,user,kind,name,data,source=None):
    row=Resource(owner_id=user.id,kind=kind,name=name,data=data,source_id=source)
    db.add(row);db.flush();db.add(Audit(owner_id=user.id,action=f'create:{kind}',target=row.id));db.commit()
    return public_resource(row)
def records_of(row):
    artifact=row.data.get('artifact_id')
    if not artifact: return []
    # Artifact IDs originate exclusively from server-generated UUID job IDs.
    try:return json.loads(artifacts.read(artifact,'records.json'))
    except FileNotFoundError:raise HTTPException(404,'Artifact is unavailable')
def csv_content(rows):
    out=io.StringIO()
    if rows:
        writer=csv.DictWriter(out,fieldnames=list(rows[0]),extrasaction='ignore');writer.writeheader()
        # Neutralize spreadsheet formula injection in string fields.
        for row in rows:
            writer.writerow({k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v) for k,v in row.items()})
    return out.getvalue()

@app.get('/api/v1/health/live')
def live(): return {'status':'alive'}
@app.get('/api/v1/health/ready')
def ready(db=Depends(get_db)):
    try: db.execute(select(User.id).limit(1))
    except Exception: raise HTTPException(503,'Database unavailable')
    return {'status':'ready','version':'1.0.0'}

def throttle(request,db,email):
    address=request.client.host if request.client else 'unknown'
    target=digest(f'{address}|{email}')
    cutoff=time.time()-300
    attempts=db.scalar(select(func.count()).select_from(Audit).where(Audit.action=='auth_attempt',Audit.target==target,Audit.created_at>cutoff))
    address_hash=digest(address)
    ip_attempts=db.scalar(select(func.count()).select_from(Audit).where(Audit.action=='auth_ip',Audit.target==address_hash,Audit.created_at>cutoff))
    if attempts>=12 or ip_attempts>=40: raise HTTPException(429,'Too many attempts; wait five minutes')
    db.add(Audit(action='auth_attempt',target=target));db.add(Audit(action='auth_ip',target=address_hash));db.commit()

def issue(user,db,response):
    token=secrets.token_urlsafe(48)
    session=LoginSession(user_id=user.id,token_hash=digest(token),expires_at=time.time()+7*86400)
    db.add(session);db.commit()
    response.set_cookie('pm_refresh',token,httponly=True,secure=PRODUCTION,samesite='strict',path='/api/v1/auth',max_age=7*86400)
    return {'access_token':access_token(user.id,session.id),'token_type':'bearer',
            'user':{'id':user.id,'email':user.email,'name':user.name,'role':user.role}}

@app.post('/api/v1/auth/register',status_code=201)
def register(body:Credentials,request:Request,response:Response,db=Depends(get_db)):
    throttle(request,db,body.email)
    user=User(email=body.email,name=body.name,password_hash=hash_password(body.password))
    try: db.add(user);db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Unable to register this email')
    return issue(user,db,response)
@app.post('/api/v1/auth/login')
def login(body:Credentials,request:Request,response:Response,db=Depends(get_db)):
    throttle(request,db,body.email)
    user=db.scalar(select(User).where(User.email==body.email))
    # Always execute the expensive hash, including for unknown users.
    valid=verify_password(body.password,user.password_hash if user else DUMMY_PASSWORD_HASH)
    if not user or not user.active or not valid: raise HTTPException(401,'Invalid email or password')
    return issue(user,db,response)
@app.post('/api/v1/auth/refresh')
def refresh(request:Request,response:Response,db=Depends(get_db)):
    if request.headers.get('x-requested-with')!='PriceMesh': raise HTTPException(403,'Missing refresh request header')
    token=request.cookies.get('pm_refresh','')
    session=db.scalar(select(LoginSession).where(LoginSession.token_hash==digest(token)))
    if not session or session.revoked or session.expires_at<=time.time(): raise HTTPException(401,'Sign in required')
    user=db.get(User,session.user_id)
    if not user or not user.active: raise HTTPException(401,'Account unavailable')
    rotated=db.execute(update(LoginSession).where(LoginSession.id==session.id,LoginSession.revoked==False).values(revoked=True))
    db.commit()
    if rotated.rowcount!=1: raise HTTPException(401,'Refresh token already used')
    return issue(user,db,response)
@app.post('/api/v1/auth/logout')
def logout(request:Request,response:Response,db=Depends(get_db)):
    if request.headers.get('x-requested-with')!='PriceMesh': raise HTTPException(403,'Missing logout request header')
    session=db.scalar(select(LoginSession).where(LoginSession.token_hash==digest(request.cookies.get('pm_refresh',''))))
    if session: session.revoked=True;db.commit()
    response.delete_cookie('pm_refresh',path='/api/v1/auth')
    return {'status':'logged_out'}
@app.get('/api/v1/auth/me')
def me(user=Depends(current_user)): return {'id':user.id,'name':user.name,'email':user.email,'role':user.role}
@app.patch('/api/v1/profile')
def profile(body:Profile,user=Depends(current_user),db=Depends(get_db)):
    row=db.get(User,user.id);row.name=body.name;db.commit()
    return {'id':row.id,'name':row.name,'email':row.email,'role':row.role}
@app.get('/api/v1/admin/users')
def admin_users(user=Depends(current_user),db=Depends(get_db)):
    if user.role!='admin': raise HTTPException(403,'Administrator role required')
    return {'items':[{'id':r.id,'name':r.name,'email':r.email,'role':r.role,'active':r.active} for r in db.scalars(select(User).limit(100)).all()]}
@app.patch('/api/v1/admin/users/{identifier}')
def update_user(identifier:str,body:UserUpdate,user=Depends(current_user),db=Depends(get_db)):
    if user.role!='admin': raise HTTPException(403,'Administrator role required')
    if identifier==user.id: raise HTTPException(409,'An administrator cannot change their own access')
    row=db.get(User,identifier)
    if not row: raise HTTPException(404,'User not found')
    row.role,row.active=body.role,body.active
    if not body.active: db.execute(update(LoginSession).where(LoginSession.user_id==row.id).values(revoked=True))
    db.add(Audit(owner_id=user.id,action='admin:update_user',target=row.id));db.commit()
    return {'id':row.id,'role':row.role,'active':row.active}
@app.get('/api/v1/settings')
def settings(user=Depends(current_user)): return user.settings
@app.put('/api/v1/settings')
def put_settings(body:Settings,user=Depends(current_user),db=Depends(get_db)):
    row=db.get(User,user.id);row.settings=body.model_dump();db.commit();return row.settings

@app.get('/api/v1/resources')
def list_resources(kind:str|None=None,q:str='',limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0),user=Depends(current_user),db=Depends(get_db)):
    query=select(Resource).where(Resource.owner_id==user.id)
    if kind: query=query.where(Resource.kind==kind)
    if q: query=query.where(Resource.name.ilike('%'+q[:100]+'%'))
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.scalars(query.order_by(Resource.created_at.desc()).offset(offset).limit(limit)).all()
    return {'items':[public_resource(r) for r in rows],'total':total,'offset':offset,'limit':limit}
@app.get('/api/v1/resources/{identifier}')
def get_resource(identifier:str,user=Depends(current_user),db=Depends(get_db)): return public_resource(resource(db,identifier,user.id))
@app.post('/api/v1/catalogs',status_code=201)
def catalog(body:Catalog,user=Depends(current_user),db=Depends(get_db)):
    return create_resource(db,user,'catalog',body.name,body.model_dump())
@app.post('/api/v1/scenarios',status_code=201)
def scenario(body:Scenario,user=Depends(current_user),db=Depends(get_db)):
    catalog=resource(db,body.catalog_id,user.id,'catalog')
    config=body.model_dump();config['products']=catalog.data['products'];config['currency']=catalog.data['currency'];config['version']=1
    return create_resource(db,user,'scenario',body.name,config,catalog.id)
@app.post('/api/v1/experiments',status_code=201)
def experiment(body:Experiment,user=Depends(current_user),db=Depends(get_db)):
    source=resource(db,body.scenario_id,user.id,'scenario')
    config=body.model_dump();config['scenario']=source.data
    return create_resource(db,user,'experiment',body.name,config,source.id)

def enqueue(db,user,kind,scenario,settings,name,source_id,policy=None):
    product_steps=scenario['horizon']*len(scenario['products'])*settings.get('episodes',1)*(settings.get('points',7 if settings.get('robustness') else 1))
    if product_steps>250000: raise HTTPException(422,'Job exceeds 250,000 product-step budget; reduce episodes, horizon or products')
    count=db.scalar(select(func.count()).select_from(Job).where(Job.owner_id==user.id,Job.status.in_(['queued','running'])))
    if count>=3: raise HTTPException(429,'At most three active jobs per researcher')
    row=Job(owner_id=user.id,kind=kind,total=settings.get('episodes',scenario['horizon']),config={
        'type':kind,'scenario':scenario,'settings':settings,'name':name,'source_id':source_id,
        'policy_artifact':policy.data['artifact_id'] if policy else None})
    db.add(row);db.flush();db.add(Audit(owner_id=user.id,action=f'enqueue:{kind}',target=row.id));db.commit()
    return public_job(row)

@app.post('/api/v1/experiments/{identifier}/runs',status_code=202)
def train_run(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    source=resource(db,identifier,user.id,'experiment')
    settings={k:v for k,v in source.data.items() if k!='scenario'}
    return enqueue(db,user,'training',source.data['scenario'],settings,source.name,source.id)
@app.post('/api/v1/datasets/generate',status_code=202)
def generate(body:Generate,user=Depends(current_user),db=Depends(get_db)):
    source=resource(db,body.scenario_id,user.id,'scenario')
    return enqueue(db,user,'dataset',source.data,body.model_dump(),body.name,source.id)
def validated_policy(db,user,identifier,scenario):
    if not identifier: return None
    policy=resource(db,identifier,user.id,'policy')
    trained=policy.data['scenario']
    if [p['sku'] for p in trained['products']] != [p['sku'] for p in scenario['products']]:
        raise HTTPException(422,'Policy product count, order and SKU assignments must match the evaluation scenario')
    return policy
@app.post('/api/v1/evaluations',status_code=202)
def evaluation(body:Evaluate,user=Depends(current_user),db=Depends(get_db)):
    source=resource(db,body.scenario_id,user.id,'scenario')
    policy=validated_policy(db,user,body.policy_id,source.data)
    return enqueue(db,user,'evaluation',source.data,body.model_dump(),body.name,source.id,policy)
@app.post('/api/v1/simulations',status_code=202)
def simulation(body:Simulate,user=Depends(current_user),db=Depends(get_db)):
    source=resource(db,body.scenario_id,user.id,'scenario')
    policy=validated_policy(db,user,body.policy_id,source.data)
    return enqueue(db,user,'simulation',source.data,body.model_dump(),body.name,source.id,policy)
@app.get('/api/v1/jobs')
def jobs(limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0),user=Depends(current_user),db=Depends(get_db)):
    rows=db.scalars(select(Job).where(Job.owner_id==user.id).order_by(Job.created_at.desc()).offset(offset).limit(limit)).all()
    return {'items':[public_job(j) for j in rows]}
@app.get('/api/v1/jobs/{identifier}')
def get_job(identifier:str,user=Depends(current_user),db=Depends(get_db)): return public_job(job_row(db,identifier,user.id))
@app.post('/api/v1/jobs/{identifier}/cancel')
def cancel(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    row=job_row(db,identifier,user.id)
    if row.status in ('queued','running'):
        row.cancel_requested=True
        if row.status=='queued': row.status='cancelled'
        db.commit()
    return public_job(row)
@app.post('/api/v1/jobs/{identifier}/control')
def simulation_control(identifier:str,body:Control,user=Depends(current_user),db=Depends(get_db)):
    row=job_row(db,identifier,user.id)
    if row.kind!='simulation' or row.status not in ('queued','running'): raise HTTPException(409,'Only active simulations can be controlled')
    if body.action=='pause': row.control='paused'
    elif body.action=='resume': row.control='running';row.step_requests=0
    else:
        if row.control!='paused': raise HTTPException(409,'Pause the simulation before stepping')
        row.step_requests=min(row.step_requests+1,10)
    db.commit();return public_job(row)
@app.get('/api/v1/jobs/{identifier}/events')
async def events(identifier:str,request:Request,user=Depends(current_user),db=Depends(get_db)):
    job_row(db,identifier,user.id)
    async def stream():
        previous=None
        while not await request.is_disconnected():
            with SessionLocal() as session:
                row=job_row(session,identifier,user.id)
                state=public_job(row)
            payload=json.dumps(state)
            if payload!=previous:
                yield f'data: {payload}\n\n';previous=payload
            else: yield ': heartbeat\n\n'
            if state['status'] in ('completed','cancelled','failed'): break
            await asyncio.sleep(1)
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'X-Accel-Buffering':'no'})

@app.get('/api/v1/resources/{identifier}/records')
def records(identifier:str,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=500),sku:str|None=None,user=Depends(current_user),db=Depends(get_db)):
    row=resource(db,identifier,user.id)
    if row.kind not in ('dataset','simulation'): raise HTTPException(422,'This resource has no transaction records')
    rows=records_of(row)
    if sku: rows=[r for r in rows if r['sku']==sku]
    return {'items':rows[offset:offset+limit],'total':len(rows)}
@app.get('/api/v1/resources/{identifier}/download')
def download(identifier:str,format:str=Query('json',pattern='^(json|csv|html)$'),user=Depends(current_user),db=Depends(get_db)):
    row=resource(db,identifier,user.id)
    if row.kind in ('dataset','simulation'): data=records_of(row)
    else: data=row.data
    if format=='csv':
        rows=data if isinstance(data,list) else data.get('summary',data.get('history',[data]))
        content=csv_content(rows);media='text/csv'
    elif format=='html':
        content=f'<!doctype html><meta charset="utf-8"><title>PriceMesh report</title><style>body{{font:14px system-ui;max-width:1000px;margin:40px auto;padding:20px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}@media print{{button{{display:none}}}}</style><h1>{html.escape(row.name)}</h1><p>Artificial single-retailer market. Results are not evidence of real-world profitability.</p><p>Use your browser print dialog to save a PDF.</p><pre>{html.escape(json.dumps(data,indent=2))}</pre>'
        media='text/html'
    else: content=json.dumps(data,indent=2);media='application/json'
    # Stream large exports instead of hitting Vercel's buffered response limit.
    return StreamingResponse((content[i:i+65536] for i in range(0,len(content),65536)),media_type=media,
        headers={'Content-Disposition':f'attachment; filename="pricemesh-{row.id}.{format}"'})

@app.post('/api/v1/reports',status_code=201)
def report(body:Report,user=Depends(current_user),db=Depends(get_db)):
    evaluation=resource(db,body.evaluation_id,user.id,'evaluation')
    return create_resource(db,user,'report',f'Report: {evaluation.name}',{**evaluation.data,'export_format':body.format},evaluation.id)
@app.get('/api/v1/dashboard')
def dashboard(user=Depends(current_user),db=Depends(get_db)):
    counts=dict(db.execute(select(Resource.kind,func.count()).where(Resource.owner_id==user.id).group_by(Resource.kind)).all())
    run_count=db.scalar(select(func.count()).select_from(Job).where(Job.owner_id==user.id,Job.kind=='training'))
    latest=db.scalar(select(Resource).where(Resource.owner_id==user.id,Resource.kind=='evaluation').order_by(Resource.created_at.desc()).limit(1))
    recent=db.scalars(select(Resource).where(Resource.owner_id==user.id,Resource.kind=='experiment').order_by(Resource.created_at.desc()).limit(5)).all()
    return {'counts':counts,'training_runs':run_count,'latest_evaluation':public_resource(latest) if latest else None,'experiments':[public_resource(r) for r in recent]}
@app.get('/api/v1/search')
def search(q:str=Query(min_length=1,max_length=100),user=Depends(current_user),db=Depends(get_db)):
    return {'items':[public_resource(r) for r in db.scalars(select(Resource).where(Resource.owner_id==user.id,Resource.name.ilike('%'+q+'%')).limit(20)).all()]}
@app.get('/api/v1/notifications')
def notifications(user=Depends(current_user),db=Depends(get_db)):
    return {'items':[{'id':r.id,'message':r.message,'read':r.read,'created_at':r.created_at} for r in db.scalars(select(Notice).where(Notice.owner_id==user.id).order_by(Notice.created_at.desc()).limit(30)).all()]}
@app.patch('/api/v1/notifications/{identifier}')
def mark_read(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    row=db.get(Notice,identifier)
    if not row or row.owner_id!=user.id: raise HTTPException(404,'Notification not found')
    row.read=True;db.commit();return {'read':True}
@app.get('/api/v1/system/status')
def status(user=Depends(current_user),db=Depends(get_db)):
    db.execute(text('SELECT 1'))
    recent=db.scalar(select(func.max(Lease.heartbeat)))
    return {'api':'ready','database':'ready','worker':'online' if recent and recent>time.time()-600 else 'offline',
            'storage':'private Vercel Blob' if artifacts.cloud_storage() else 'local persistent volume','mlflow':'configured' if os.getenv('MLFLOW_TRACKING_URI') else 'disabled','environment':os.getenv('APP_ENV','development')}

@app.post('/api/v1/analysis/sensitivity',status_code=202)
def sensitivity(body:Sensitivity,user=Depends(current_user),db=Depends(get_db)):
    source=resource(db,body.scenario_id,user.id,'scenario')
    policy=validated_policy(db,user,body.policy_id,source.data)
    return enqueue(db,user,'sensitivity',source.data,body.model_dump(),body.name,source.id,policy)

@app.post('/api/v1/analysis/drift')
def drift(body:Drift,user=Depends(current_user),db=Depends(get_db)):
    import numpy as np
    a=records_of(resource(db,body.dataset_a,user.id,'dataset'))
    b=records_of(resource(db,body.dataset_b,user.id,'dataset'))
    rows=[]
    for key in ['price','units','profit','inventory','requested_demand']:
        av=np.array([r[key] for r in a]);bv=np.array([r[key] for r in b])
        rows.append({'feature':key,'reference_mean':float(av.mean()),'comparison_mean':float(bv.mean()),
                     'reference_std':float(av.std()),'comparison_std':float(bv.std()),
                     'standardized_mean_shift':float((bv.mean()-av.mean())/max(av.std(),1e-6))})
    return {'features':rows,'note':'Descriptive drift; repeated trajectory rows are correlated, so no independence-based p-values are reported.'}

@app.post('/api/v1/analysis/compare')
def compare(body:Compare,user=Depends(current_user),db=Depends(get_db)):
    import numpy as np
    a=resource(db,body.evaluation_a,user.id,'evaluation')
    b=resource(db,body.evaluation_b,user.id,'evaluation')
    if a.data['scenario']!=b.data['scenario']: raise HTTPException(422,'Evaluations must have identical scenario snapshots')
    ae,be=a.data['episodes'],b.data['episodes']
    if set(ae)!=set(be): raise HTTPException(422,'Evaluations must contain matching market shifts')
    results=[]
    for name in ae:
        if [r['seed'] for r in ae[name]]!=[r['seed'] for r in be[name]]:
            raise HTTPException(422,'Evaluations must use matching episode seeds')
        differences=np.array([ar['profit']-br['profit'] for ar,br in zip(ae[name],be[name])])
        rng=np.random.default_rng(919)
        sample=differences[rng.integers(0,len(differences),size=(1000,len(differences)))].mean(1)
        results.append({'scenario':name,'mean_difference_A_minus_B':float(differences.mean()),
                        'ci_low':float(np.quantile(sample,.025)),'ci_high':float(np.quantile(sample,.975))})
    return {'evaluation_a':a.name,'evaluation_b':b.name,'paired_results':results,'note':'Episode uncertainty only; independent training seeds are still required.'}

@app.post('/api/v1/analysis/diagnostics')
def diagnostics(body:Diagnostics,user=Depends(current_user),db=Depends(get_db)):
    import numpy as np
    import torch
    from pricing.learning import load_policy
    from pricing.environment import Market,ACTIONS
    source=resource(db,body.policy_id,user.id,'policy')
    policy,_=load_policy(artifacts.policy_folder(source.data['artifact_id']))
    obs=Market(source.data['scenario']).observe()
    rows=[]
    for feature,index in [('initial',None),('inventory_low',0),('inventory_high',0),('last_sales_low',3),('last_sales_high',3)]:
        variant=obs.copy()
        if index is not None:
            delta=-.1 if feature.endswith('low') else .1
            variant[:,index]=np.clip(variant[:,index]+delta,0,1 if index==0 else 100)
        with torch.no_grad():
            logits,_=policy(torch.tensor(variant).unsqueeze(0))
            probabilities=torch.softmax(logits,dim=-1)[0].numpy()
        for i,product in enumerate(source.data['scenario']['products']):
            for j,action in enumerate(ACTIONS):
                rows.append({'sku':product['sku'],'condition':feature,'price_adjustment':float(action),'probability':float(probabilities[i,j])})
    return {'rows':rows,'note':'Controlled local actor sensitivity, not causal consumer behavior.'}
