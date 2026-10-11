---
tags: [ai, deep-learning]
---
# Neural Networks

A neural network is a stack of layers, each computing a linear transformation followed by a nonlinear activation function.

## Activation functions
- **ReLU** — `max(0, x)`; the default for hidden layers.
- **Sigmoid** — squashes to (0, 1); used for binary outputs.
- **Softmax** — turns a vector into a probability distribution; used for multi-class outputs and inside [[Attention Mechanism|attention]].

## Training
Weights are learned with backpropagation (the chain rule) plus [[Gradient Descent]].

## Training tricks
- Dropout to fight [[Overfitting]].
- Batch normalization to stabilize training.
- Residual (skip) connections let very deep networks train; they are a key part of [[Transformers]].

#ai/deep-learning
