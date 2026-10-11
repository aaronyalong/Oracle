---
tags: [ai]
---
# Overfitting

A model overfits when it memorizes the training data, including its noise, and generalizes poorly. The tell-tale sign is training loss that keeps falling while validation loss starts rising.

## Remedies
- **More data** or data augmentation.
- **Regularization** — L2 weight decay penalizes large weights; L1 encourages sparsity.
- **Dropout** — randomly zero activations during training (common rate: 0.1–0.5). See [[Neural Networks#Training tricks]].
- **Early stopping** — stop when validation loss hasn't improved for a set number of epochs (the "patience").

## Underfitting
The opposite problem: the model is too simple to capture the pattern, so both training and validation loss stay high.

Back to [[Machine Learning|ML overview]].
