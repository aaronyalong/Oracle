---
tags: [ai, optimization]
---
# Learning Rate Schedules

A schedule changes the learning rate during training instead of keeping it fixed.

## Warmup
Start with a very small learning rate and increase it linearly over the first few hundred or thousand steps. This avoids large, unstable updates while the optimizer's running statistics are still poor. Standard for [[Transformers]].

## Decay
- **Step decay** — divide the rate by 10 every N epochs.
- **Cosine annealing** — follow a cosine curve from the starting rate down to near zero.
- **Reduce on plateau** — lower the rate when validation loss stops improving.

## One-cycle
Raise the rate to a maximum and then lower it again within a single run. Often trains faster than a fixed rate.

Usually paired with the [[Adam Optimizer]].
