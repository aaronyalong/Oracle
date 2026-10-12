---
tags: [databases]
---
# Redis

Redis is an in-memory key-value store, mostly used for caching, sessions, rate limiting, and queues.

## Data types
Strings, lists, sets, sorted sets, hashes, and streams.

## Expiry
Any key can have a TTL so it's deleted automatically — the basis of most caching.

## Persistence
RDB snapshots and an append-only file (AOF) can be enabled, but Redis is usually treated as a cache rather than the source of truth.
