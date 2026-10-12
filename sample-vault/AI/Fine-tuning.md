---
tags: [ai, llm]
---
# Fine-tuning

Fine-tuning continues training a pre-trained model on a smaller, task-specific dataset.

## Full fine-tuning
Updates every weight. Best quality but needs a lot of GPU memory and stores a full copy of the model per task.

## LoRA
Low-Rank Adaptation freezes the original weights and trains small low-rank matrices added to selected layers. It trains a tiny fraction of the parameters, and the adapters are only a few megabytes.

## Catastrophic forgetting
Training too long on narrow data can make the model lose general abilities. Mix in general data or keep training short.

Fine-tuning changes what the model knows; [[Retrieval-Augmented Generation|RAG]] instead gives it documents at question time.
