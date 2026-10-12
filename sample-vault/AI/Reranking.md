---
tags: [ai, rag, search]
---
# Reranking

A reranker re-orders the candidates from a first-stage search using a slower but more accurate model.

## Cross-encoders
An embedding model (bi-encoder) encodes the query and each passage separately. A cross-encoder scores the query and passage together in one forward pass, so it can model their interaction directly. That makes it more accurate, but it must run once per candidate, so it's only used on the top 20–100 results.

## Typical pipeline
1. Retrieve the top 50 with vector or [[Hybrid Search|hybrid search]].
2. Rerank them with a cross-encoder.
3. Keep the top 5 for the prompt.
