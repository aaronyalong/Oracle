---
tags: [ai, llm, evaluation]
---
# LLM Evaluation

## Reference-based
Compare the output with a known correct answer using exact match, F1 over tokens, or a required key phrase.

## LLM-as-judge
Ask a strong model to grade answers against a rubric. Cheap and scalable, but judges favour longer answers and their own style.

## RAG-specific metrics
- **Faithfulness** — is every claim supported by the retrieved context?
- **Answer relevance** — does the answer address the question?
- **Context precision** — how much of the retrieved context was actually useful?

The RAGAS library implements these.
