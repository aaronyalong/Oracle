---
tags: [ai, nlp]
---
# Tokenization

Language models don't read characters or whole words; they read tokens.

## Subword methods
- **Byte-pair encoding (BPE)** — repeatedly merges the most frequent pair of symbols. Used by GPT and Llama models.
- **WordPiece** — similar idea, used by [[BERT]].
- **SentencePiece** — works directly on raw text, including spaces.

## Rules of thumb
In English, one token is roughly 4 characters or three quarters of a word. Code, numbers, and non-English text usually take more tokens per character.
