---
tags: [ai, rag, databases]
---
# Vector Databases

A vector database stores [[Embeddings]] and finds the nearest neighbours of a query vector.

## Options
- **Chroma** — embedded Python library, persists to a local folder, no server. Good for single-user local apps.
- **pgvector** — a [[PostgreSQL]] extension; good if you already run Postgres.
- **FAISS** — a library from Meta for very fast similarity search; no persistence or metadata filtering out of the box.
- **Pinecone** — fully managed cloud service.

## Approximate nearest neighbour
Exact search compares the query against every vector, which is O(n). Large stores use approximate indexes instead — most commonly **[[HNSW]]** (Hierarchical Navigable Small World graphs), which Chroma uses by default.

## Metadata filtering
Most vector stores let you filter by metadata (e.g. `tag == "scala"`) before or during the similarity search.

Similarity is usually [[Cosine Similarity]].
