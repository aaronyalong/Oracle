---
tags: [scala, hub]
---
# Scala

Scala is a JVM language that combines object-oriented and functional programming. These notes are from my Scala 3 coursework.

## Key features
- Immutable data by default with [[Case Classes]].
- Powerful [[Pattern Matching]].
- Contextual abstractions: [[Implicits and Givens]].
- Concurrency with [[Futures]].

## Tooling
- **sbt** is the standard build tool; `sbt ~compile` recompiles on every save.
- **scala-cli** is handy for single-file scripts.
- Scala 3 is also called **Dotty** (its compiler's original name).

## Scala 2 vs Scala 3
Scala 3 added optional braces (significant indentation), `enum`, `given`/`using`, and extension methods.

#scala
