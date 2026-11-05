# Learning and evaluation methodology

## Environment

One agent per retailer-owned product; eight observed features: normalized inventory, price/reference, cost/reference, last sales/base demand, episode time, seasonality, mean relative product price and stock availability. Actors do not receive future shocks or latent unfulfilled demand. Demand and rounding tapes are generated before actions so comparisons share exogenous randomness.

Demand intensity scales base demand by own price elasticity, cross-price interactions and seasonality. Integer-rounded lognormal demand is capped by inventory to produce fulfilled sales. This is an artificial market assumption and not a calibrated model of customer behavior. Constraints enforce price bounds and maximum movement; interventions are logged.

## Algorithms

Discrete price changes: −10%, −5%, 0%, +5%, +10%. Sold-out agents hold. Separate 64-unit tanh actors; IPPO and shared PPO use local critics; MAPPO critics observe concatenated current observations. IPPO rewards use own margin less configured penalties. MAPPO/shared PPO use the summed portfolio reward. A fixed reference-margin scale normalizes rewards.

PPO uses clipping 0.2, discount 0.99, GAE λ=0.95, entropy coefficient 0.01, critic coefficient 0.5 and gradient norm 0.5. Episodes terminate at the finite selling horizon; terminal bootstrap is zero. Update epochs and learning rate are configurable. The final predetermined-budget checkpoint is saved; tests verify finite optimization and checkpoint/action equivalence, not guaranteed convergence.

## Evaluation

Frozen policies and fixed-price baselines use matching scenario snapshots and episode seeds. Methods include fixed price, inventory-aware rule, privileged myopic elasticity heuristic, IPPO, MAPPO and shared PPO. Myopic pricing is not a true optimal-control oracle.

Seven conditions: unshifted, elasticity increase, demand collapse, demand spike, half supply, doubled noise and missing sales observations. Report portfolio margin, revenue, sales, sell-through, lost sales, inventory, safety interventions, constraints and explicitly separated penalties. Episode-bootstrap 95% intervals use 1,000 samples. Paired comparisons reject non-matching snapshots or seed lists.

Relative degradation = (reference profit − shifted profit) / abs(reference profit); return undefined near zero. Absolute differences are always retained. Single-policy episode intervals do not describe training-seed uncertainty.

For independent training-seed comparisons, export a scenario as JSON and run from the root:

```powershell
python -m scripts.research_study --scenario my-scenario.json --seeds 5 --episodes 100 --test-episodes 30
```

The runner freezes a manifest before training, evaluates all methods on the same held-out seeds, aggregates episodes within training seed and bootstraps training-seed means. It writes raw results, checkpoints and paired MAPPO-minus-IPPO intervals. Small runs only verify execution. Do not tune on final held-out results; define a separate validation suite before hyperparameter selection. No claimed performance improvement has been fabricated or assumed.
