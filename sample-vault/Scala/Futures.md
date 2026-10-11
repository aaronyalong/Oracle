---
tags: [scala, concurrency]
---
# Futures

A `Future[T]` is a value of type `T` that will be available later, computed asynchronously.

```scala
import scala.concurrent.ExecutionContext.Implicits.global
val f: Future[Int] = Future { slowComputation() }
f.map(_ + 1)
```

## ExecutionContext
Every Future needs an `ExecutionContext` (a thread pool), supplied as a [[Implicits and Givens|given]]. The global one has as many threads as CPU cores, so **blocking calls should be wrapped in `blocking { }`** to let it grow the pool.

## Composing futures
- `map` / `flatMap` / for-comprehensions to chain steps.
- `Future.sequence` to turn `List[Future[T]]` into `Future[List[T]]`.
- `recover` to handle failures.

## Pitfall
Futures are **eager**: they start running as soon as they're created. Libraries like Cats Effect `IO` and ZIO are lazy instead, which makes them easier to reason about and retry.

Back to [[Scala]].
