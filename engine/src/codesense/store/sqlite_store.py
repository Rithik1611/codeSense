"""SQLite + sqlite-vec implementation of the vector store (ADR-0003).

Metadata lives in ordinary tables; vectors live in a ``vec0`` virtual table with the
same rowid as their chunk. Search is exact (every vector is compared), which measured
15 ms for 10k vectors (docs/experiments/level1-vector-store.md).

The index is derived data: an index built with another schema, model or repository is
refused (IndexMismatchError) and rebuilt by the caller, never migrated or mixed.
"""

import itertools
import sqlite3
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

import numpy as np
import sqlite_vec

from codesense.embedding.base import Vectors, embedding_key
from codesense.errors import IndexMismatchError, StoreError
from codesense.models import CodeChunk, SymbolKind

SCHEMA_VERSION = 1
_KEY_BATCH = 500  # stay well under SQLite's limit on ? parameters per statement


def _schema(dimensions: int) -> list[str]:
    return [
        "CREATE TABLE index_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        """CREATE TABLE files (
            path TEXT PRIMARY KEY,
            language TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            indexed_at TEXT NOT NULL
        )""",
        """CREATE TABLE chunks (
            id INTEGER PRIMARY KEY,  -- also the rowid of the chunk's vector
            chunk_id TEXT NOT NULL UNIQUE,
            path TEXT NOT NULL REFERENCES files(path),
            symbol_name TEXT,
            symbol_kind TEXT NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            embedding_key TEXT NOT NULL,
            model_id TEXT NOT NULL
        )""",
        "CREATE INDEX chunks_by_path ON chunks(path)",
        "CREATE INDEX chunks_by_embedding_key ON chunks(embedding_key)",
        # `dimensions` cannot be a ? parameter here; open() has checked it is a positive int.
        f"CREATE VIRTUAL TABLE chunk_vectors USING vec0("
        f"embedding float[{dimensions}] distance_metric=cosine)",
    ]


class SqliteVectorStore:
    def __init__(
        self, connection: sqlite3.Connection, model_id: str, dimensions: int, repo_id: str
    ) -> None:
        """Use ``open()``; this only wraps an already prepared connection."""
        self._db = connection
        self._model_id = model_id
        self._dimensions = dimensions
        self._repo_id = repo_id

    @classmethod
    def open(cls, path: Path, model_id: str, dimensions: int, repo_id: str) -> Self:
        """Create a new index file, or open an existing one built the same way."""
        if isinstance(dimensions, bool) or not isinstance(dimensions, int) or dimensions < 1:
            raise ValueError(f"dimensions must be a positive int, got {dimensions!r}")
        identity = {
            "schema_version": str(SCHEMA_VERSION),
            "model_id": model_id,
            "dimensions": str(dimensions),
            "repo_id": repo_id,
        }
        try:
            # isolation_level=None: no hidden BEGINs; transactions are explicit (_transaction).
            connection = sqlite3.connect(path, isolation_level=None)
        except sqlite3.Error as error:
            raise StoreError(f"cannot open index {path}: {error}") from error
        try:
            cls._prepare(connection, identity, dimensions)
        except sqlite3.DatabaseError as error:
            connection.close()
            raise StoreError(
                f"cannot open index {path}: {error}; delete the file to rebuild the index"
            ) from error
        except BaseException:
            connection.close()
            raise
        return cls(connection, model_id, dimensions, repo_id)

    @staticmethod
    def _prepare(connection: sqlite3.Connection, identity: dict[str, str], dimensions: int) -> None:
        connection.enable_load_extension(True)
        sqlite_vec.load(connection)
        connection.enable_load_extension(False)  # no other extension may be loaded later
        connection.execute("PRAGMA journal_mode = WAL")  # readers never block the writer
        connection.execute("PRAGMA foreign_keys = ON")

        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
        if not tables:
            with _transaction(connection):
                for statement in _schema(dimensions):
                    connection.execute(statement)
                created = datetime.now(UTC).isoformat(timespec="seconds")
                connection.executemany(
                    "INSERT INTO index_meta (key, value) VALUES (?, ?)",
                    [*identity.items(), ("created_at", created)],
                )
            return
        if "index_meta" not in tables:
            raise StoreError("this database is not a CodeSense index; refusing to modify it")
        stored = dict(connection.execute("SELECT key, value FROM index_meta").fetchall())
        for key, expected in identity.items():  # schema_version first: other keys may move
            if stored.get(key) != expected:
                raise IndexMismatchError(
                    f"the index was built with {key}={stored.get(key)!r} but this engine uses "
                    f"{expected!r}; rebuild the index"
                )

    def replace_file(
        self,
        path: str,
        language: str,
        file_hash: str,
        chunks: Sequence[CodeChunk],
        vectors: Vectors,
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(f"{len(chunks)} chunks but {len(vectors)} vectors")
        if vectors.shape != (len(chunks), self._dimensions) or vectors.dtype != np.float32:
            raise ValueError(
                f"vectors must be float32 with shape ({len(chunks)}, {self._dimensions}), "
                f"got {vectors.dtype} {vectors.shape}"
            )
        for chunk in chunks:
            if chunk.path != path:
                raise ValueError(f"chunk {chunk.chunk_id} belongs to {chunk.path}, not {path}")

        indexed_at = datetime.now(UTC).isoformat(timespec="seconds")
        with _transaction(self._db):  # the old version is deleted only if the new one is complete
            self._delete(path)
            self._db.execute(
                "INSERT INTO files (path, language, content_hash, indexed_at) VALUES (?, ?, ?, ?)",
                (path, language, file_hash, indexed_at),
            )
            for chunk, vector in zip(chunks, vectors, strict=True):
                cursor = self._db.execute(
                    """INSERT INTO chunks (chunk_id, path, symbol_name, symbol_kind, start_line,
                        end_line, content, content_hash, embedding_key, model_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        chunk.chunk_id,
                        chunk.path,
                        chunk.symbol_name,
                        chunk.symbol_kind.value,
                        chunk.start_line,
                        chunk.end_line,
                        chunk.content,
                        chunk.content_hash,
                        embedding_key(chunk),
                        self._model_id,
                    ),
                )
                self._db.execute(
                    "INSERT INTO chunk_vectors (rowid, embedding) VALUES (?, ?)",
                    (cursor.lastrowid, vector.tobytes()),  # raw float32: 4 bytes per number
                )

    def delete_file(self, path: str) -> None:
        with _transaction(self._db):
            self._delete(path)

    def _delete(self, path: str) -> None:
        # Vectors first, explicitly: virtual tables do not cascade, and an orphaned vector
        # would keep matching queries as a result that points at nothing.
        self._db.execute(
            "DELETE FROM chunk_vectors WHERE rowid IN (SELECT id FROM chunks WHERE path = ?)",
            (path,),
        )
        self._db.execute("DELETE FROM chunks WHERE path = ?", (path,))
        self._db.execute("DELETE FROM files WHERE path = ?", (path,))

    def file_hashes(self) -> dict[str, str]:
        return dict(self._db.execute("SELECT path, content_hash FROM files").fetchall())

    def existing_vectors(self, keys: Iterable[str]) -> dict[str, Vectors]:
        found: dict[str, Vectors] = {}
        for batch in itertools.batched(set(keys), _KEY_BATCH):
            placeholders = ", ".join("?" * len(batch))  # only "?" is interpolated, never values
            rows = self._db.execute(
                f"""SELECT c.embedding_key, v.embedding
                FROM chunks c JOIN chunk_vectors v ON v.rowid = c.id
                WHERE c.embedding_key IN ({placeholders})""",
                batch,
            )
            for key, blob in rows:
                found[key] = np.frombuffer(blob, dtype=np.float32)
        return found

    def search(self, query: Vectors, k: int) -> list[tuple[CodeChunk, float]]:
        if query.shape != (self._dimensions,):
            raise ValueError(f"query must have shape ({self._dimensions},), got {query.shape}")
        if k < 1:
            raise ValueError(f"k must be >= 1, got {k}")
        rows = self._db.execute(
            """WITH nearest AS (
                SELECT rowid, distance FROM chunk_vectors WHERE embedding MATCH ? AND k = ?
            )
            SELECT c.chunk_id, c.path, f.language, c.symbol_name, c.symbol_kind,
                c.start_line, c.end_line, c.content, c.content_hash, nearest.distance
            FROM nearest
            JOIN chunks c ON c.id = nearest.rowid
            JOIN files f ON f.path = c.path
            ORDER BY nearest.distance""",
            (np.asarray(query, dtype=np.float32).tobytes(), k),
        )
        return [
            (
                CodeChunk(
                    chunk_id=chunk_id,
                    repo_id=self._repo_id,
                    path=path,
                    language=language,
                    symbol_name=symbol_name,
                    symbol_kind=SymbolKind(symbol_kind),
                    start_line=start_line,
                    end_line=end_line,
                    content=content,
                    content_hash=content_hash,
                ),
                1.0 - distance,  # the one place distance becomes similarity
            )
            for (
                chunk_id,
                path,
                language,
                symbol_name,
                symbol_kind,
                start_line,
                end_line,
                content,
                content_hash,
                distance,
            ) in rows
        ]

    def clear(self) -> None:
        with _transaction(self._db):
            self._db.execute("DELETE FROM chunk_vectors")
            self._db.execute("DELETE FROM chunks")
            self._db.execute("DELETE FROM files")

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


@contextmanager
def _transaction(connection: sqlite3.Connection) -> Iterator[None]:
    """All statements inside commit together, or none do."""
    connection.execute("BEGIN")
    try:
        yield
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    connection.execute("COMMIT")
