---
tags: [ai, llm]
---
# Prompt Engineering

## Techniques
- **System prompt** — sets the model's role and rules for the whole conversation.
- **Few-shot examples** — show a few input/output pairs before the real input.
- **Chain of thought** — ask the model to reason step by step before answering.
- **Output format** — ask for JSON or a fixed template to make answers parseable.

## Pitfalls
Small models follow instructions too literally; an instruction like "only answer if the text says so" can make them refuse reasonable questions. Test prompts on real examples.

See also [[Hallucination]].
