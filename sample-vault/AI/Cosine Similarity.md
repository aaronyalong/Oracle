---
tags: [ai, math]
---
# Cosine Similarity

Cosine similarity measures the angle between two vectors, ignoring their length:

`cos(a, b) = (a · b) / (‖a‖ ‖b‖)`

- **1** means same direction (very similar).
- **0** means orthogonal (unrelated).
- **−1** means opposite.

If vectors are normalized to unit length, cosine similarity equals the dot product, which is cheaper to compute. Many [[Vector Databases]] normalize on insert for this reason.

Cosine *distance* is `1 − cosine similarity`; Chroma reports distances, so lower is better.

Used to compare [[Embeddings]].
