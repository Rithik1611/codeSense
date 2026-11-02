"""Benchmark 6.1: what exact nearest-neighbour search costs, through the real store, on disk.

Usage (from engine/):  uv run python scripts/knn_benchmark.py
Random unit vectors stand in for embeddings: exact search cost depends only on how
many vectors there are, not on what they mean. Results: docs/experiments/level1-vector-store.md.
"""

import tempfile
import time
from pathlib import Path

import numpy as np

from codesense.ids import chunk_id, content_hash
from codesense.models import CodeChunk, SymbolKind
from codesense.store.sqlite_store import SqliteVectorStore

DIMENSIONS, CHUNKS_PER_FILE, QUERIES = 768, 50, 20
CONTENT = "export function handler(request) {\n  return service.process(request);\n}\n" * 4


def chunks_for(path: str) -> list[CodeChunk]:
    return [
        CodeChunk(
            chunk_id=chunk_id("bench", path, line, line + 3),
            repo_id="bench",
            path=path,
            language="typescript",
            symbol_name=f"handler{line}",
            symbol_kind=SymbolKind.FUNCTION,
            start_line=line,
            end_line=line + 3,
            content=CONTENT,
            content_hash=content_hash(CONTENT),
        )
        for line in range(1, CHUNKS_PER_FILE * 4, 4)
    ]


def run(total: int, folder: Path) -> None:
    rng = np.random.default_rng(0)
    db_path = folder / f"index-{total}.db"
    with SqliteVectorStore.open(db_path, "bench", DIMENSIONS, "bench") as store:
        started = time.perf_counter()
        for file_number in range(total // CHUNKS_PER_FILE):
            path = f"src/file{file_number}.ts"
            vectors = rng.standard_normal((CHUNKS_PER_FILE, DIMENSIONS), dtype=np.float32)
            vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
            store.replace_file(path, "typescript", "hash", chunks_for(path), vectors)
        write_seconds = time.perf_counter() - started

        queries = rng.standard_normal((QUERIES, DIMENSIONS), dtype=np.float32)
        queries /= np.linalg.norm(queries, axis=1, keepdims=True)
        store.search(queries[0], k=10)  # warm the page cache, as a second search would be
        started = time.perf_counter()
        for query in queries:
            store.search(query, k=10)
        search_ms = (time.perf_counter() - started) / QUERIES * 1000

    size_mb = sum(f.stat().st_size for f in folder.glob(f"index-{total}.db*")) / 1e6
    print(
        f"{total:7,d} chunks | write {write_seconds:5.1f} s ({total / write_seconds:6,.0f}/s)"
        f" | top-10 search {search_ms:6.1f} ms | file {size_mb:6.0f} MB"
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        for total in (1_000, 10_000, 50_000, 100_000):
            run(total, Path(folder))


if __name__ == "__main__":
    main()
