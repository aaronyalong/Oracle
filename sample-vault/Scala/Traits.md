---
tags: [scala]
---
# Traits

Traits are like Java interfaces that can also contain concrete methods and fields.

## Mixins
A class can extend one class and mix in many traits: `class Duck extends Animal with Swimmer with Flyer`.

## Linearization
When several traits override the same method, Scala orders them right to left, and `super` calls go to the next trait in that order. This avoids the diamond problem.

## Scala 3
Traits can now take parameters: `trait Greeter(name: String)`.

A `sealed trait` is the usual base for [[Case Classes]] hierarchies.
