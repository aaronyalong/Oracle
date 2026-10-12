---
tags: [ai]
---
# Regularization

Regularization adds a penalty to the loss so the model prefers simpler solutions.

## L1 (lasso)
Penalizes the sum of absolute weights. Pushes many weights to exactly zero, which acts as feature selection.

## L2 (ridge)
Penalizes the sum of squared weights. Shrinks all weights smoothly toward zero without making them exactly zero. In neural networks this is usually called weight decay.

## Elastic net
A weighted mix of L1 and L2, useful when features are correlated.

## Choosing the strength
The penalty strength (often called lambda) is a hyperparameter; pick it with [[Cross-Validation]].
