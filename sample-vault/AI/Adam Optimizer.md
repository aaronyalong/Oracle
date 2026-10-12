---
tags: [ai, optimization]
aliases: [Adam]
---
# Adam Optimizer

Adam (Kingma & Ba, 2014) combines momentum with per-parameter adaptive step sizes. It is the default optimizer for most deep learning work.

## How it works
Adam keeps two running averages for every parameter: the mean of recent gradients (first moment) and the mean of their squares (second moment). Each step is the first moment divided by the square root of the second, so parameters with consistently large gradients take smaller steps.

## Default hyperparameters
The paper recommends learning rate 0.001, beta1 = 0.9, beta2 = 0.999, and epsilon = 1e-8. These defaults work surprisingly often without tuning.

## AdamW
Plain Adam applies L2 regularization through the gradient, which interacts badly with the adaptive scaling. AdamW (Loshchilov & Hutter) decouples weight decay from the update and is now preferred for training transformers.

Compare with plain [[Gradient Descent]]. Often combined with [[Learning Rate Schedules]].
