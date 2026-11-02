# Level 1: Vector store measurements

Checks that exact (brute-force) nearest-neighbour search is fast enough for one repository (ADR-0003).

**Hardware:** AMD Ryzen 7 PRO 8840HS (8 cores / 16 threads), 28 GB RAM, NVMe SSD.
**Software:** Windows 11, Python 3.12, SQLite 3.53.1, sqlite-vec v0.1.9.
**Method:** `uv run python scripts/knn_benchmark.py` (from `engine/`). Goes through `SqliteVectorStore` and a real file on disk, in WAL mode, with 50 chunks per file (one transaction each). Uses random unit vectors with 768 dimensions: exact search cost depends on how many vectors there are, not on their values. Search time is the mean of 20 top-10 queries after one warm-up.

| Chunks | Write (incl. metadata) | Top-10 search | File size |
|---|---|---|---|
| 1,000 | 0.9 s (1,133 chunks/s) | 4 ms | 4 MB |
| 10,000 | 13.3 s (751 chunks/s) | 48 ms | 40 MB |
| 50,000 | 78.8 s (635 chunks/s) | 157 ms | 195 MB |
| 100,000 | 197.0 s (508 chunks/s) | 378 ms | 389 MB |

## Conclusions
- **Search grows linearly** (exact search compares every vector). It is interactive (< 160 ms) up to ~50k chunks, the expected range for one repository. At 100k it still works (~0.4 s), which is the point where approximate search (HNSW/IVF) becomes worth evaluating (Level 5).
- **Storage is not the bottleneck:** writing is ~150× faster than embedding (~4.5 chunks/s, see [level1-embeddings.md](level1-embeddings.md)).
- **Size:** ~3.9 KB per chunk: 3,072 bytes of float32 vector plus code and metadata.
- An earlier in-memory probe (no metadata, no disk) measured 15 ms at 10k. The real path is ~3× slower, which is why the benchmark goes through the store itself.
