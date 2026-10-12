---
tags: [ai, llm]
---
# Hallucination

A hallucination is a fluent, confident statement that isn't supported by the model's input or by reality.

## Causes
The model predicts likely text, not true text. Gaps in training data, ambiguous prompts, and pressure to always answer all make it worse.

## Mitigations
- Ground answers in retrieved documents and require citations.
- Allow, and test for, "I don't know" answers.
- Check that each cited source actually supports the claim.
