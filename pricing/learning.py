"""Small explicit independent PPO / MAPPO implementation for CPU research runs."""
import json
import time
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.distributions import Categorical
from .environment import Market, ACTIONS

torch.set_num_threads(1)

class Policy(nn.Module):
    def __init__(self, n, algorithm='mappo', hidden=64):
        super().__init__()
        self.n, self.algorithm, self.hidden = n, algorithm, hidden
        self.actors = nn.ModuleList([nn.Sequential(nn.Linear(8,hidden),nn.Tanh(),nn.Linear(hidden,hidden),nn.Tanh(),nn.Linear(hidden,5)) for _ in range(n)])
        size = n*8 if algorithm == 'mappo' else 8
        self.critics = nn.ModuleList([nn.Sequential(nn.Linear(size,hidden),nn.Tanh(),nn.Linear(hidden,1)) for _ in range(n)])

    def forward(self, obs):
        logits = torch.stack([actor(obs[:,i]) for i,actor in enumerate(self.actors)],1)
        # A sold-out agent has exactly one legal action: no-op.
        mask = obs[:,:,7] == 0
        logits = logits.masked_fill(mask[:,:,None] & (torch.arange(5)[None,None,:] != 2), -1e9)
        state = obs.flatten(1)
        values = torch.stack([critic(state if self.algorithm == 'mappo' else obs[:,i]).squeeze(-1) for i,critic in enumerate(self.critics)],1)
        return logits, values

    def actions(self, obs, deterministic=True):
        with torch.no_grad():
            logits,_ = self(torch.tensor(obs).unsqueeze(0))
            return (logits.argmax(-1) if deterministic else Categorical(logits=logits).sample())[0].numpy()

def train(config, settings, folder, progress=lambda *_: None):
    seed, episodes = settings.get('seed',42), settings.get('episodes',24)
    torch.manual_seed(seed)
    np.random.seed(seed)
    policy = Policy(len(config['products']), settings.get('algorithm','mappo'))
    optimizer = torch.optim.Adam(policy.parameters(), lr=settings.get('learning_rate',.0003))
    history=[]
    start=time.time()
    for episode in range(episodes):
        env=Market(config,seed+episode)
        obs=env.observe()
        states=[]; actions=[]; logs=[]; rewards=[]; values=[]
        for _ in range(env.horizon):
            states.append(obs.copy())
            with torch.no_grad():
                logits,value=policy(torch.tensor(obs).unsqueeze(0))
                dist=Categorical(logits=logits)
                action=dist.sample()
                logs.append(dist.log_prob(action)[0])
                values.append(value[0])
            obs,reward,done=env.step(action[0].numpy())
            actions.append(action[0])
            if policy.algorithm != 'ippo':
                reward=np.full(env.n, float(reward.sum()), dtype=np.float32)
            rewards.append(torch.tensor(reward))
            if done: break
        old_values=torch.stack(values)
        advantages=torch.zeros_like(old_values)
        gae=torch.zeros(env.n)
        # Finite-horizon episode is a true terminal: terminal bootstrap is zero.
        next_value=torch.zeros(env.n)
        for t in reversed(range(len(rewards))):
            delta=rewards[t]+.99*next_value-old_values[t]
            gae=delta+.99*.95*gae
            advantages[t]=gae
            next_value=old_values[t]
        targets=advantages+old_values
        advantages=(advantages-advantages.mean())/(advantages.std(unbiased=False)+1e-8)
        states=torch.tensor(np.stack(states)); actions=torch.stack(actions); old_logs=torch.stack(logs)
        for _ in range(settings.get('epochs',4)):
            logits,value=policy(states)
            dist=Categorical(logits=logits)
            ratio=(dist.log_prob(actions)-old_logs).exp()
            actor_loss=-torch.minimum(ratio*advantages,ratio.clamp(.8,1.2)*advantages).mean()
            critic_loss=(value-targets).square().mean()
            entropy=dist.entropy().mean()
            loss=actor_loss+.5*critic_loss-.01*entropy
            if not torch.isfinite(loss): raise ValueError('Non-finite training loss')
            optimizer.zero_grad();loss.backward();nn.utils.clip_grad_norm_(policy.parameters(),.5);optimizer.step()
        metrics=env.metrics()
        metrics.update(episode=episode+1, steps=(episode+1)*env.horizon, loss=float(loss.detach()), entropy=float(entropy.detach()))
        history.append(metrics)
        progress(episode+1,episodes,metrics)
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    # NPZ + JSON avoids unpickling executable checkpoints.
    np.savez_compressed(folder/'weights.npz', **{k:v.detach().numpy() for k,v in policy.state_dict().items()})
    metadata=dict(n=policy.n,algorithm=policy.algorithm,hidden=policy.hidden,version=1,observation_schema=1,
                  action_grid=ACTIONS.tolist(),config=config,settings=settings,seconds=time.time()-start)
    (folder/'policy.json').write_text(json.dumps(metadata),encoding='utf-8')
    return policy,history,metadata

def load_policy(folder):
    folder=Path(folder)
    metadata=json.loads((folder/'policy.json').read_text(encoding='utf-8'))
    if metadata['version'] != 1: raise ValueError('Unsupported checkpoint version')
    model=Policy(metadata['n'],metadata['algorithm'],metadata['hidden'])
    with np.load(folder/'weights.npz',allow_pickle=False) as archive:
        model.load_state_dict({k:torch.from_numpy(archive[k].copy()) for k in model.state_dict()})
    model.eval()
    return model,metadata
