---
tags: [scala, fp, concurrency]
---
# ZIO

ZIO is an effect system built around the type `ZIO[R, E, A]`: an effect that needs an environment `R`, may fail with an error `E`, or succeeds with an `A`.

## Typed errors
Because errors appear in the type, the compiler shows which failures you still have to handle.

## Blocking calls
Use `ZIO.attemptBlocking(...)` for blocking I/O such as JDBC calls. It runs on ZIO's dedicated blocking thread pool so the main pool keeps serving fibers.

## Dependency injection
`ZLayer` describes how to build services from other services; ZIO wires them together at startup.
