---
tags: [scala]
---
# Pattern Matching

`match` is like a much more powerful `switch`:

```scala
shape match
  case Circle(r)        => math.Pi * r * r
  case Rect(w, h)       => w * h
  case _                => 0.0
```

## Kinds of patterns
- Constant patterns: `case 0 =>`
- Constructor patterns on [[Case Classes]]: `case Point(x, y) =>`
- Type patterns: `case s: String =>`
- Guards: `case n if n > 0 =>`
- Sequence patterns: `case List(first, _*) =>`

## Exhaustiveness
When matching on a `sealed` type, the compiler warns about missing cases. A non-exhaustive match on an unsealed type throws a `MatchError` at runtime.

#scala
