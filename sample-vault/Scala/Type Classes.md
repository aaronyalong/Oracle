---
tags: [scala, fp]
---
# Type Classes

A type class defines behaviour that types can opt into without inheriting from anything.

```scala
trait Show[A]:
  extension (a: A) def show: String

given Show[Int] with
  extension (a: Int) def show = s"Int($a)"
```

## Derivation
Scala 3 can generate instances automatically with `derives`, e.g. `case class Point(x: Int, y: Int) derives Eq`.

## Common type classes
`Eq`, `Ordering`, `Show`, `Monoid`, `Functor`, `Monad` — the Cats library defines most of them.
