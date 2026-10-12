---
tags: [databases]
---
# SQLite

SQLite is an embedded database stored in a single file. There is no server: the library runs inside your application.

## Strengths
Zero setup, very fast for reads, and ideal for local apps, tests, and mobile.

## Concurrency
SQLite allows only one writer at a time; a write locks the whole database. WAL mode lets readers continue during a write, but writes are still serialized, so many simultaneous writers queue up or time out.
