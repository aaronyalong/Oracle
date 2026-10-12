---
tags: [databases]
aliases: [Postgres]
---
# PostgreSQL

An open-source relational database known for correctness and extensibility. Default port 5432.

## MVCC
Readers never block writers: each transaction sees a snapshot, and old row versions are cleaned up later by VACUUM.

## Extensions
- **pgvector** — vector similarity search.
- **PostGIS** — geographic data.
- **pg_trgm** — trigram matching for fuzzy text search.

See also [[Indexes]], [[Transactions]], and [[Full-Text Search]].
