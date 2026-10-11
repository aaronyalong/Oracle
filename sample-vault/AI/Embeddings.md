---
tags: [ai, rag]
aliases: [vector embeddings]
---
# Embeddings

An embedding maps text (or images, etc.) to a dense vector so that similar meanings land close together in vector space.

## Embedding models
- **nomic-embed-text** — 768 dimensions, 8192-token context, runs locally through Ollama. This is what [[Retrieval-Augmented Generation|my RAG project]] uses.
- **all-MiniLM-L6-v2** — 384 dimensions; small and fast, but only a 256-token input limit.
- **OpenAI text-embedding-3-small** — 1536 dimensions; cloud only.

## Comparing embeddings
Vectors are usually compared with [[Cosine Similarity]].

## Gotcha
Query and document must be embedded with the **same model**. Vectors from different models live in different spaces and can't be compared. nomic-embed-text also expects task prefixes: `search_query: ` for questions and `search_document: ` for passages.

Stored and searched in a [[Vector Databases|vector database]].
