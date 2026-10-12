---
tags: [scala, fp, concurrency]
---
# Cats Effect

Cats Effect provides `IO`, a lazy description of a side effect that runs only when executed.

## Fibers
`IO` runs on lightweight fibers rather than OS threads; you can start thousands of them. `.start` forks a fiber and `.join` waits for it.

## Blocking work
Wrap blocking calls in `IO.blocking(...)`, which moves them to a separate thread pool so the compute pool isn't starved.

## Resources
`Resource` acquires and releases things like files and connections safely, even when errors or cancellation happen.
