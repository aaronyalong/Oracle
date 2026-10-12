---
tags: [scala]
---
# Enums

Scala 3 added a proper `enum` keyword.

```scala
enum Color:
  case Red, Green, Blue
```

## Enums with parameters
```scala
enum Planet(val mass: Double):
  case Earth extends Planet(5.97e24)
```

## Algebraic data types
Enum cases can carry different fields, which replaces most sealed-trait-plus-[[Case Classes]] hierarchies with less code. [[Pattern Matching]] on an enum is checked for exhaustiveness.
