---
tags: [scala, concurrency]
---
# Akka

Akka is a toolkit for concurrent and distributed systems based on the actor model.

## Actors
An actor has private state and a mailbox. Others send it messages; it processes them one at a time, so its state needs no locks.

## Supervision
Parent actors decide what happens when a child fails: restart it, stop it, or escalate.

## License change
In 2022 Lightbend moved Akka to the Business Source License. The Apache-licensed community fork is Apache Pekko.
