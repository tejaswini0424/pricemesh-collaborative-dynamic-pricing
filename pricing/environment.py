"""Seeded artificial single-retailer market. No real customer data is used."""
from copy import deepcopy
import numpy as np

ACTIONS = np.array([-.10, -.05, 0., .05, .10], dtype=np.float32)

class Market:
    observation_size = 8

    def __init__(self, config, seed=0, shift=None):
        self.config = deepcopy(config)
        self.products = self.config['products']
        self.n = len(self.products)
        self.horizon = config.get('horizon', 30)
        self.shift = shift or {}
        self.reference = np.array([p['reference_price'] for p in self.products], dtype=float)
        self.cost = np.array([p['cost'] for p in self.products], dtype=float)
        self.floor = np.array([p['min_price'] for p in self.products], dtype=float)
        self.ceiling = np.array([p['max_price'] for p in self.products], dtype=float)
        self.initial = np.array([p['stock'] for p in self.products], dtype=float) * self.shift.get('supply', 1.)
        self.initial = np.floor(self.initial)
        self.base = np.array([p.get('base_demand', 8) for p in self.products], dtype=float)
        self.elasticity = np.array([p.get('elasticity', 1.6) for p in self.products]) * self.shift.get('elasticity', 1.)
        rng = np.random.default_rng(seed)
        # Exogenous tapes are fixed before actions, preserving paired evaluation.
        self.noise_tape = rng.normal(size=(self.horizon, self.n))
        self.round_tape = rng.uniform(size=(self.horizon, self.n))
        self.observation_mask = rng.uniform(size=(self.horizon + 1, self.n))
        self.price = self.reference.copy()
        self.stock = self.initial.copy()
        self.last_sales = np.zeros(self.n)
        self.t = 0
        self.records = []
        self.reward_scale = max(float(np.sum((self.reference - self.cost) * self.base)), 1.)

    def observe(self):
        season = np.sin(2 * np.pi * self.t / max(self.horizon, 1))
        sales = self.last_sales / np.maximum(self.base, 1)
        sales = np.where(self.observation_mask[self.t] < self.shift.get('missing', 0), 0., sales)
        return np.stack([self.stock / np.maximum(self.initial, 1), self.price / self.reference,
                         self.cost / self.reference, sales, np.full(self.n, self.t/self.horizon),
                         np.full(self.n, season), np.full(self.n, np.mean(self.price/self.reference)),
                         (self.stock > 0).astype(float)], axis=1).astype(np.float32)

    def step(self, actions):
        if self.t >= self.horizon:
            raise ValueError('Episode has already terminated')
        actions = np.asarray(actions, dtype=int)
        if actions.shape != (self.n,) or np.any(actions < 0) or np.any(actions >= len(ACTIONS)):
            raise ValueError('One valid discrete action per product is required')
        active = self.stock > 0
        old = self.price.copy()
        proposed = old * (1 + np.where(active, ACTIONS[actions], 0))
        movement = self.config.get('max_change', .1)
        applied = np.clip(proposed, np.maximum(self.floor, old*(1-movement)), np.minimum(self.ceiling, old*(1+movement)))
        interventions = (~np.isclose(proposed, applied)) & active
        relative = applied/self.reference
        others = (np.sum(np.log(relative))-np.log(relative))/max(self.n-1, 1) if self.n > 1 else np.zeros(1)
        season = self.config.get('seasonality', .2)*np.sin(2*np.pi*self.t/self.horizon)
        log_intensity = -self.elasticity*np.log(relative) + self.config.get('cross_elasticity', .25)*others + season
        demand_multiplier = self.shift.get('demand', 1.)
        if self.t >= self.horizon//2:
            demand_multiplier *= self.shift.get('shock', 1.)
        mean = self.base * np.exp(np.clip(log_intensity, -4, 4)) * demand_multiplier
        noise = self.config.get('noise', .25)*self.shift.get('noise', 1.)
        demand = np.floor(np.maximum(0, mean*np.exp(noise*self.noise_tape[self.t]-.5*noise**2)+self.round_tape[self.t]))
        sales = np.minimum(demand, self.stock)
        stock_before = self.stock.copy()
        self.stock -= sales
        margin = (applied-self.cost)*sales
        holding = self.config.get('holding_penalty', 0)*self.stock
        lost = self.config.get('stockout_penalty', 0)*np.maximum(demand-sales, 0)
        changes = self.config.get('change_penalty', 0)*np.abs(applied-old)
        reward = (margin-holding-lost-changes)/self.reward_scale
        for i,p in enumerate(self.products):
            self.records.append(dict(step=self.t, sku=p['sku'], price=float(applied[i]), proposed_price=float(proposed[i]),
                cost=float(self.cost[i]), inventory_before=int(stock_before[i]), inventory=int(self.stock[i]),
                requested_demand=int(demand[i]), units=int(sales[i]), lost_sales=int(demand[i]-sales[i]),
                revenue=float(applied[i]*sales[i]), profit=float(margin[i]), reward=float(reward[i]),
                penalty=float(holding[i]+lost[i]+changes[i]), intervention=bool(interventions[i]), action=int(actions[i])))
        self.price, self.last_sales = applied, sales
        self.t += 1
        return self.observe(), reward.astype(np.float32), self.t == self.horizon

    def metrics(self):
        rows = self.records
        return dict(profit=sum(r['profit'] for r in rows), revenue=sum(r['revenue'] for r in rows),
                    units=sum(r['units'] for r in rows), lost_sales=sum(r['lost_sales'] for r in rows),
                    remaining_inventory=int(self.stock.sum()), sell_through=float(1-self.stock.sum()/max(self.initial.sum(),1)),
                    stockout_rate=float(np.mean([r['inventory']==0 for r in rows])) if rows else 0.,
                    interventions=sum(r['intervention'] for r in rows), constraint_violations=sum(
                        not self.floor[i%self.n]-1e-6 <= r['price'] <= self.ceiling[i%self.n]+1e-6 for i,r in enumerate(rows)),
                    shaped_reward=sum(r['reward'] for r in rows), penalties=sum(r['penalty'] for r in rows))

def baseline_actions(env, strategy='fixed'):
    if strategy == 'fixed':
        target = env.reference
    elif strategy == 'inventory':
        expected_remaining = np.maximum(1-env.t/env.horizon, .05)
        stock_fraction = env.stock/np.maximum(env.initial, 1)
        target = env.reference*np.clip(1+.25*(expected_remaining-stock_fraction), .7, 1.3)
    elif strategy == 'myopic':
        # Privileged true elasticity, ignoring cross-product dynamics and future stock.
        e = env.elasticity
        target = np.where(e > 1.01, env.cost*e/np.maximum(e-1, .01), env.ceiling)
    else:
        raise ValueError('Unknown baseline')
    options = env.price[:,None]*(1+ACTIONS)
    return np.argmin(np.abs(options-target[:,None]), axis=1)
