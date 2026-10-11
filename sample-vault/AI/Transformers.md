---
tags: [ai, deep-learning, nlp]
---
# Transformers

The transformer architecture was introduced in the 2017 paper "Attention Is All You Need" (Vaswani et al.). It replaced recurrence with [[Attention Mechanism|self-attention]], which lets training run in parallel across the whole sequence.

## Structure
- Token [[Embeddings]] plus positional encodings.
- Repeated blocks of multi-head self-attention and a feed-forward network.
- Residual connections and layer normalization around each sub-layer.

## Variants
- **Encoder-only** (BERT) — good for classification and producing embeddings.
- **Decoder-only** (GPT, Llama) — good for text generation.
- **Encoder-decoder** (T5) — good for translation and summarization.

## Context window
The model can only attend to a fixed number of tokens at once. This limit is a major reason [[Retrieval-Augmented Generation]] exists.

![[Attention Mechanism#Scaled dot-product attention]]
