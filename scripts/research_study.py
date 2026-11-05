"""Predeclared multi-training-seed study. Run from repository root as a module."""
import argparse
import json
from pathlib import Path
import numpy as np
from pricing.learning import train
from pricing.evaluation import evaluate

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario',required=True,help='Path to an exported scenario JSON (resource data only)')
    parser.add_argument('--output',default='artifacts/research-study')
    parser.add_argument('--seeds',type=int,default=5)
    parser.add_argument('--episodes',type=int,default=100)
    parser.add_argument('--test-episodes',type=int,default=30)
    args=parser.parse_args()
    if not 2<=args.seeds<=20 or not 2<=args.episodes<=1000 or not 2<=args.test_episodes<=100:
        parser.error('Require 2–20 seeds, 2–1000 training episodes, 2–100 evaluation episodes')
    # Validate exported scenario through the same schema used by the API.
    from backend.app.schemas import Product
    scenario=json.loads(Path(args.scenario).read_text())
    for product in scenario['products']:Product.model_validate(product)
    if not 1<=len(scenario['products'])<=20 or not 2<=scenario['horizon']<=365:
        parser.error('Invalid scenario dimensions')
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    # Frozen held-out seeds; never used for checkpoint selection or tuning.
    manifest={'training_seeds':[42+i*1000 for i in range(args.seeds)],'evaluation_seed':100000,
              'train_episodes':args.episodes,'test_episodes':args.test_episodes,'scenario':scenario,
              'algorithms':['ippo','mappo','shared_ppo'],'checkpoint_selection':'final fixed-budget checkpoint'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    results=[]
    for algorithm in manifest['algorithms']:
        means=[]
        for seed in manifest['training_seeds']:
            folder=output/f'{algorithm}-{seed}'
            policy,history,metadata=train(scenario,{'seed':seed,'episodes':args.episodes,'algorithm':algorithm},folder,
                                          lambda done,total,_:print(f'{algorithm} seed={seed} {done}/{total}',flush=True))
            result=evaluate(scenario,{'episodes':args.test_episodes,'seed':100000,'robustness':True},policy)
            (folder/'results.json').write_text(json.dumps(result,indent=2))
            means.append({row['scenario']:row['mean_profit'] for row in result['summary']})
        for scenario_name in means[0]:
            values=np.array([m[scenario_name] for m in means])
            indices=np.random.default_rng(919).integers(0,len(values),(2000,len(values)))
            low,high=np.quantile(values[indices].mean(1),[.025,.975])
            results.append({'algorithm':algorithm,'scenario':scenario_name,'training_seed_means':values.tolist(),
                            'mean_profit':float(values.mean()),'ci_low':float(low),'ci_high':float(high)})
    paired=[]
    for row in [r for r in results if r['algorithm']=='mappo']:
        baseline=next(r for r in results if r['algorithm']=='ippo' and r['scenario']==row['scenario'])
        differences=np.array(row['training_seed_means'])-baseline['training_seed_means']
        indices=np.random.default_rng(919).integers(0,len(differences),(2000,len(differences)))
        low,high=np.quantile(differences[indices].mean(1),[.025,.975])
        paired.append({'scenario':row['scenario'],'mappo_minus_ippo':float(differences.mean()),'ci_low':float(low),'ci_high':float(high)})
    (output/'summary.json').write_text(json.dumps({'manifest':manifest,'results':results,'paired_training_seed_comparison':paired,
        'uncertainty_scope':'Bootstrap across independent training-seed means. Artificial single-retailer market only.'},indent=2))
    print(f'Completed study: {output.resolve()/"summary.json"}')

if __name__=='__main__':main()
