import numpy as np
from .environment import Market, baseline_actions

SHIFTS={'baseline':{},'elasticity':{'elasticity':1.5},'demand_collapse':{'shock':.4},
        'demand_spike':{'shock':1.8},'supply_shortage':{'supply':.5},'noise':{'noise':2.},
        'observation_loss':{'missing':.3}}

def rollout(config, seed, policy=None, strategy='fixed', shift=None):
    env=Market(config,seed,shift)
    for _ in range(env.horizon):
        actions=policy.actions(env.observe()) if policy is not None else baseline_actions(env,strategy)
        env.step(actions)
    return env.metrics(),env.records

def paired_summary(results, seed=919):
    """Intervals quantify episode uncertainty for ONE trained policy, not training-seed variance."""
    values=np.array([r['profit'] for r in results])
    fixed=np.array([r['baseline_profit'] for r in results])
    rng=np.random.default_rng(seed)
    indices=rng.integers(0,len(values),size=(1000,len(values)))
    means=values[indices].mean(1)
    differences=(values-fixed)[indices].mean(1)
    low,high=np.quantile(means,[.025,.975])
    dl,dh=np.quantile(differences,[.025,.975])
    return dict(mean_profit=float(values.mean()),ci_low=float(low),ci_high=float(high),
                baseline_profit=float(fixed.mean()),paired_difference=float((values-fixed).mean()),
                difference_ci_low=float(dl),difference_ci_high=float(dh),
                mean_revenue=float(np.mean([r['revenue'] for r in results])),
                mean_sell_through=float(np.mean([r['sell_through'] for r in results])),
                constraint_violations=sum(r['constraint_violations'] for r in results),
                interventions=sum(r['interventions'] for r in results),episodes=len(results),
                uncertainty_scope='Episode bootstrap for one trained policy; not across independent training seeds.')

def evaluate(config, settings, policy=None, progress=lambda *_: None):
    if settings.get('parameter'):
        values=np.linspace(settings['minimum'],settings['maximum'],settings['points'])
        shifts={f"{settings['parameter']}={value:.3f}":{settings['parameter']:float(value)} for value in values}
    else:
        shifts=SHIFTS if settings.get('robustness') else {'baseline':{}}
    episodes=settings.get('episodes',10)
    all_results={};summary=[];completed=0
    for name,shift in shifts.items():
        rows=[]
        for episode in range(episodes):
            seed=settings.get('seed',100000)+episode
            metrics,_=rollout(config,seed,policy,settings.get('strategy','inventory'),shift)
            fixed,_=rollout(config,seed,None,'fixed',shift)
            metrics.update(seed=seed,baseline_profit=fixed['profit'])
            rows.append(metrics);completed+=1
            progress(completed,episodes*len(shifts),{'scenario':name})
        all_results[name]=rows
        summary.append({'scenario':name,**paired_summary(rows)})
    reference=summary[0]['mean_profit']
    for row in summary:
        row['absolute_change']=row['mean_profit']-reference
        row['degradation']=None if abs(reference)<1e-6 else (reference-row['mean_profit'])/abs(reference)
    return {'summary':summary,'episodes':all_results,'settings':settings,
            'limitations':['Artificial demand does not establish real-world profitability.','Five or more independent training seeds are recommended for research conclusions.']}
