---
tags: [ai, optimization]
---
# Gradient Descent

Gradient descent updates parameters in the direction opposite the gradient of the loss: `θ ← θ − η ∇L(θ)`, where η is the learning rate.

## Learning rate
- Too high: the loss oscillates or diverges.
- Too low: training is very slow and can stall on plateaus.
- In my [[CS4100]] project a learning rate of **0.001 with Adam** was the most stable setting; 0.01 diverged after about 3 epochs.

## Variants
- **Batch** — uses the whole dataset per step; accurate but slow.
- **Stochastic (SGD)** — one example per step; noisy but fast.
- **Mini-batch** — the practical default, usually 32–256 examples.
- **[[Adam Optimizer|Adam]]** — adapts the step size per parameter using running averages of the gradient and its square.

Used to train [[Neural Networks]]. Related: [[Overfitting]].
