---
tags: [ai, rag, hub]
aliases: [RAG]
---
# Retrieval-Augmented Generation

RAG answers a question by first retrieving relevant passages from a document collection, then giving them to an LLM as context. It grounds answers in your own data and works around the [[Transformers#Context window|context window]] limit.

## Pipeline
1. Split documents into chunks — see [[Chunking Strategies]].
2. Embed each chunk — see [[Embeddings]].
3. Store the vectors in a [[Vector Databases|vector database]].
4. At query time, embed the question and retrieve the top-k most similar chunks.
5. Put those chunks in the prompt and ask the LLM to answer using only that context.

## Common failure modes
- **Retrieval miss** — the right chunk exists but isn't in the top-k. Fix with better chunking, hybrid keyword + vector search, or reranking.
- **Lost in the middle** — LLMs pay less attention to context in the middle of a long prompt.
- **Hallucinated citations** — the model cites a source that doesn't support the claim.

## Evaluation
Measure retrieval separately from generation. Common retrieval metrics are **recall@k** (is the right document in the top k?) and **MRR** (mean reciprocal rank of the first correct hit).

Idea for applying this to my own notes: [[Project Ideas#Oracle]].
