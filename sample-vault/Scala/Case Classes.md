---
tags: [scala]
---
# Case Classes

A case class is a class designed for immutable data:

```scala
case class Point(x: Int, y: Int)
val p = Point(1, 2)
val q = p.copy(y = 5)
```

## What you get for free
- An `apply` method, so no `new` is needed.
- Structural `equals` and `hashCode`.
- A readable `toString`.
- A `copy` method for making modified copies.
- An `unapply` method so it works with [[Pattern Matching]].

## Sealed traits
A `sealed trait` with case class subtypes forms an algebraic data type (ADT). Because the trait is sealed, the compiler can warn when a `match` doesn't cover every case.

Back to [[Scala]].
