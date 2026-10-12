---
tags: [ai, deep-learning]
---
# Backpropagation

Backpropagation computes the gradient of the loss with respect to every weight by applying the chain rule backwards through the network, layer by layer.

## Vanishing gradients
Multiplying many small derivatives makes gradients in early layers shrink toward zero, so those layers stop learning. Sigmoid activations make this worse because their derivative is at most 0.25. ReLU, residual connections, and careful initialization help.

## Exploding gradients
The opposite problem: gradients grow huge. Common in recurrent networks; fixed with gradient clipping.

The gradients are then used by [[Gradient Descent]].
