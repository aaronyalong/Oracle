---
tags: [ai]
---
# Loss Functions

The loss function measures how wrong a model's predictions are; training minimizes it.

## Regression
- **Mean squared error (MSE)** — squares errors, so large mistakes dominate.
- **Mean absolute error (MAE)** — more robust to outliers.

## Classification
- **Cross-entropy** — compares predicted probabilities with the true class; pairs with softmax outputs.
- **Hinge loss** — used by support vector machines.

The gradient of the loss drives [[Backpropagation]].
