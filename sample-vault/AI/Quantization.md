---
tags: [ai, llm]
---
# Quantization

Quantization stores weights with fewer bits — 8 or 4 instead of 16 — to cut memory and speed up inference, at a small cost in quality.

## GGUF formats
llama.cpp uses names like Q4_K_M (about 4.5 bits per weight, a common default) and Q8_0 (8 bits, nearly lossless).

## Rule of thumb
A model needs roughly (parameters × bits ÷ 8) bytes, plus some overhead: an 8B model at 4 bits is about 5 GB.
