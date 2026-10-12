---
tags: [scala]
---
# Collections

Scala's default collections are immutable.

## List
A singly linked list. Prepending with `::` is O(1), but appending is O(n) because the whole list has to be copied. Build in reverse and call `.reverse`, or use a Vector.

## Vector
A wide tree with effectively constant-time indexing, append, and update. A good general-purpose default.

## Map and Set
Immutable hash-based by default. `map + (k -> v)` returns a new map.

## Mutable versions
`scala.collection.mutable.ArrayBuffer`, `HashMap`, and so on, for performance-sensitive local code.
