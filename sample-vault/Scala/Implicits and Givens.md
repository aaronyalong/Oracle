---
tags: [scala]
aliases: [givens, implicits]
---
# Implicits and Givens

Scala lets the compiler fill in some arguments automatically from context.

## Scala 2: implicit
`implicit val`, `implicit def`, and `implicit` parameters. Powerful but confusing, because one keyword did several jobs (conversions, parameters, extension methods).

## Scala 3: given / using
```scala
given Ordering[Person] = Ordering.by(_.age)
def sorted[T](xs: List[T])(using ord: Ordering[T]) = xs.sorted
```
- `given` defines a value the compiler can supply.
- `using` marks a parameter the compiler should fill in.
- Extension methods replaced the old "implicit class" pattern.

## Typeclasses
Givens are how Scala 3 implements typeclasses (e.g. `Ordering`, `Show`), much like Haskell typeclasses.

[[Futures]] also rely on this: they need an `ExecutionContext` passed via `using`.
