---
tags: [ai, rag]
---
# Chunking Strategies

How you split documents strongly affects [[Retrieval-Augmented Generation|RAG]] quality. Chunks that are too large dilute the embedding; chunks that are too small lose context.

## Fixed-size
Split every N tokens (e.g. 512) with some overlap (e.g. 50 tokens). Simple, but it cuts sentences and sections in half.

## Structure-aware
Split on document structure such as Markdown headings. Works well for notes because each section is usually about one thing. Long sections still need a size cap.

## Semantic
Split where the embedding similarity between consecutive sentences drops. Higher quality, but slower and harder to debug.

## Tips
- Prefix each chunk with its document title and heading path so it makes sense on its own.
- Keep metadata (source file, heading, links) with each chunk so answers can cite sources.
