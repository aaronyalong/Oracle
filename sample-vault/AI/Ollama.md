---
tags: [ai, tools]
---
# Ollama

Ollama runs open-weight models locally. It uses llama.cpp underneath and serves an HTTP API on port 11434.

## Commands
- `ollama pull llama3.2` — download a model.
- `ollama run llama3.2` — chat in the terminal.
- `ollama list` — show downloaded models.

## Memory behaviour
Ollama unloads a model after 5 minutes without requests (the keep_alive setting), so the next request has to load it again and is noticeably slower.

## Model sizes
Models are usually [[Quantization|quantized]] to 4 bits; llama3.2 (3B) is about 2 GB on disk.
