---
tags: [scala]
---
# For Comprehensions

```scala
for
  user  <- findUser(id)
  order <- latestOrder(user)
  if order.total > 0
yield order.total
```

## Desugaring
The compiler rewrites this into `flatMap`, `map`, and `withFilter` calls. Any type with those methods works: List, [[Option and Either|Option]], [[Futures|Future]], ZIO, and so on.

## Gotcha
All generators must be the same kind of container; you can't mix an Option and a List in one comprehension without converting.
