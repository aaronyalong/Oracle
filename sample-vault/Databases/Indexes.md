---
tags: [databases]
---
# Indexes

An index is an extra data structure that makes lookups fast at the cost of slower writes and more disk space.

## Types in Postgres
- **B-tree** — the default; equality and range queries on sortable values.
- **Hash** — equality only.
- **GIN** — for values that contain many items: arrays, JSONB, and text search documents.
- **GiST** — geometric data and nearest-neighbour searches.
- **BRIN** — tiny indexes for huge tables whose rows are physically ordered, such as time series.

## When not to index
Small tables, columns with few distinct values, and write-heavy tables often don't benefit.
