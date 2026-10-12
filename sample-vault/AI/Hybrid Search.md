---
tags: [ai, rag, search]
---
# Hybrid Search

Hybrid search combines keyword search with vector search.

## Why
Vector search handles paraphrases well but can miss exact terms such as error codes, names, or rare words. Keyword search (BM25) is the opposite.

## BM25
The standard keyword ranking function. It rewards terms that are frequent in the document but rare across the collection, with diminishing returns for repeated terms and a correction for document length.

## Combining rankings
Reciprocal Rank Fusion (RRF) merges the two ranked lists: each document scores the sum of 1 / (60 + rank) over the lists it appears in. It only uses ranks, so the two systems' scores don't need to be on the same scale.
