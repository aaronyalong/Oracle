---
tags: [ai, search, algorithms]
---
# HNSW

Hierarchical Navigable Small World (Malkov & Yashunin, 2016) is a graph-based index for approximate nearest neighbour search.

## Structure
Vectors are nodes in a multi-layer graph. Upper layers are sparse and allow long jumps; the bottom layer contains every vector. A search starts at the top, greedily moves toward the query, and drops down a layer at a time.

## Parameters
- **M** — the number of links per node. Higher means better recall and more memory.
- **ef_construction** — how many candidates are considered while building. Higher means a better graph and slower inserts.
- **ef_search** — how many candidates are kept during a query. It trades speed for recall at query time.
