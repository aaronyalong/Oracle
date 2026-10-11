---
tags: [ai, nlp]
---
# Attention Mechanism

Attention lets each token build its representation by looking at every other token and weighting them by relevance.

## Scaled dot-product attention
`Attention(Q, K, V) = softmax(Q Kᵀ / √d_k) V`

Queries (Q) are compared with keys (K) by dot product, scaled by √d_k so that the softmax doesn't saturate, and the resulting weights are used to average the values (V).

## Multi-head attention
Several attention operations run in parallel with different learned projections, so each head can focus on a different kind of relationship (syntax, coreference, etc.).

## Cost
Self-attention is **O(n²)** in sequence length, which is why long context windows are expensive.

Used in [[Transformers]]. The dot-product comparison is closely related to [[Cosine Similarity]].
