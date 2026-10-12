---
tags: [ai, deep-learning, nlp]
aliases: [RNN]
---
# Recurrent Neural Networks

RNNs process a sequence one step at a time, carrying a hidden state from step to step.

## LSTM and GRU
- **LSTM** (Hochreiter & Schmidhuber, 1997) adds gates that decide what to keep, forget, and output, which helps with long-range dependencies.
- **GRU** (2014) is a simpler variant with two gates.

## Limitations
Because each step depends on the previous one, training can't be parallelized across the sequence, and very long dependencies are still hard. [[Transformers]] replaced RNNs for most language tasks.
