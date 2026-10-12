---
tags: [ai, deep-learning, vision]
aliases: [CNN]
---
# Convolutional Neural Networks

CNNs are built for grid data such as images.

## Convolution layers
Small learned filters (e.g. 3×3) slide across the image and respond to local patterns like edges and textures. The same filter is reused at every position (weight sharing), so there are far fewer parameters than in a fully connected layer.

## Pooling
Max pooling keeps the strongest response in each small window, shrinking the feature map and making the network tolerant to small shifts.

## Architectures
- LeNet (1998) — early digit recognizer.
- AlexNet (2012) — won ImageNet and started the deep learning boom.
- ResNet (2015) — residual connections allowed 100+ layer networks.
