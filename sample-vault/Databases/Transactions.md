---
tags: [databases]
---
# Transactions

A transaction groups statements so they succeed or fail together.

## ACID
Atomicity, consistency, isolation, durability.

## Isolation levels
- **Read Committed** — each statement sees data committed before it started. Read Committed is PostgreSQL's default.
- **Repeatable Read** — the whole transaction sees one snapshot.
- **Serializable** — behaves as if transactions ran one after another; may abort with serialization errors that the app must retry.
