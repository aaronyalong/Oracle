---
tags: [databases, search]
---
# Full-Text Search

PostgreSQL has built-in full-text search.

## tsvector and tsquery
`to_tsvector('english', body)` turns text into normalized lexemes (stemmed, with stop words removed). `to_tsquery('cats & dogs')` describes what to find, and `@@` matches them.

## Indexing
Create a GIN index on the tsvector column; without it every search scans the whole table.

## Ranking
`ts_rank` scores matches by term frequency. It is not BM25 — Postgres has no BM25 built in, so true BM25 needs an extension or a separate search engine.
