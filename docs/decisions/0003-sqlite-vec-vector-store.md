# ADR-0003: Use SQLite + sqlite-vec as the vector store

- **Status:** Accepted
- **Date:** 2026-10-29
- **Level:** 1

## Context
We need to persist chunk metadata and 768-dim vectors locally, update and delete them as files change, find nearest neighbours, and survive VS Code restarts. The spec says: do **not** build a vector database from scratch, and prefer a practical local solution. SQLite-based storage with a compatible vector index is explicitly acceptable.

Typical scale for one repository: thousands to tens of thousands of chunks.

## Decision
Use **SQLite** (Python's built-in `sqlite3`) with the **[sqlite-vec](https://github.com/asg017/sqlite-vec)** extension:

- Metadata lives in ordinary tables (`index_meta`, `files`, `chunks`).
- Vectors live in a `vec0` virtual table using **cosine distance**.
- Search is **exact** (brute-force) k-nearest-neighbour search.
- The whole index is **one file** in VS Code's per-workspace storage.
- Access is hidden behind a small `VectorStore` interface, so the backend stays replaceable.

## Alternatives considered
| Option | Why not (yet) |
|---|---|
| LanceDB | Strong embedded option with built-in ANN and full-text search, but it hides more of the mechanics we want to learn. |
| Chroma | Heavier, opinionated, brings its own embedding abstractions. |
| FAISS | An index only. We would hand-build metadata storage, persistence and deletes. |
| Qdrant / Weaviate / pgvector | Server processes. Overkill and against "no premature infrastructure". |
| Hand-written NumPy store | The spec forbids reimplementing a storage engine. |

## Consequences
**Positive**
- Exact search makes retrieval easy to reason about: it is just distances, sorted.
- Transactions give atomic per-file updates, the foundation for incremental indexing in Level 2.
- SQLite's **FTS5** full-text index is built in, so Level 3 hybrid search can live in the same database.
- One portable file, inspectable with any SQLite viewer.

**Negative**
- sqlite-vec is pre-1.0 (v0.1.x). Its API may change, so we pin it and wrap it.
- Brute-force search is O(N) per query. Fine for ~100k chunks, too slow for millions. **Measured in Step 6** ([experiments](../experiments/level1-vector-store.md)): top-10 search takes 48 ms at 10k chunks, 157 ms at 50k and 378 ms at 100k, on disk.
- Requires a Python build with SQLite extension loading enabled. The uv-managed CPython supports this, and it was verified in the smoke test.

**Revisit when:** a single index exceeds ~100k chunks and search latency becomes noticeable (approximate search is a Level 5 ablation), or sqlite-vec makes breaking changes.
