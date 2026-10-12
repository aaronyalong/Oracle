---
tags: [ai, nlp]
---
# BERT

BERT (Google, 2018) is an encoder-only [[Transformers|transformer]] pre-trained on large text corpora.

## Pre-training
- **Masked language modeling** — hide 15% of tokens and predict them from both sides of the context.
- **Next sentence prediction** — later work showed this task adds little.

## Sizes
BERT-base has 110M parameters; BERT-large has 340M.

## Uses
Fine-tuned for classification, named-entity recognition, and question answering. Sentence-embedding models are often BERT variants.

Uses WordPiece [[Tokenization]].
