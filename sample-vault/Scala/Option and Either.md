---
tags: [scala]
---
# Option and Either

## Option
`Option[A]` is either `Some(a)` or `None`, replacing null. Use `map`, `getOrElse`, and `fold` instead of checking `isDefined`.

## Either
`Either[E, A]` is `Left(error)` or `Right(value)`. Since Scala 2.12 it is right-biased, so `map` and `flatMap` work on the Right side and errors short-circuit.

## Try
`Try[A]` is `Success(a)` or `Failure(exception)`, for wrapping code that throws.

All three work in [[For Comprehensions]].
