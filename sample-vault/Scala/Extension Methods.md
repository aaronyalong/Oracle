---
tags: [scala]
---
# Extension Methods

Add methods to a type you don't own:

```scala
extension (s: String)
  def shout: String = s.toUpperCase + "!"

"hi".shout  // "HI!"
```

## Replaces implicit classes
In Scala 2 this needed an `implicit class` wrapper. See [[Implicits and Givens]].

## Type class syntax
Extension methods are how [[Type Classes]] expose nice syntax, like `a.show`.
