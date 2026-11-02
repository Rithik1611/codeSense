import sqlite3
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
import sqlite_vec

from codesense.embedding.base import Vectors, embedding_key
from codesense.errors import CodeSenseError, IndexMismatchError, StoreError
from codesense.ids import chunk_id, content_hash
from codesense.models import CodeChunk, SymbolKind
from codesense.store.base import VectorStore
from codesense.store.sqlite_store import SCHEMA_VERSION, SqliteVectorStore

MODEL, DIMS, REPO = "fake/hashing", 4, "repo-1"


def make_chunk(path: str, start: int, name: str, body: str = "return 1;") -> CodeChunk:
    content = f"function {name}() {{ {body} }}"
    return CodeChunk(
        chunk_id=chunk_id(REPO, path, start, start),
        repo_id=REPO,
        path=path,
        language="typescript",
        symbol_name=name,
        symbol_kind=SymbolKind.FUNCTION,
        start_line=start,
        end_line=start,
        content=content,
        content_hash=content_hash(content),
    )


def unit(*values: float) -> Vectors:
    vector = np.array(values, dtype=np.float32)
    return vector / np.linalg.norm(vector)


def vectors(*rows: Vectors) -> Vectors:
    return np.stack(rows)


def open_store(path: Path, **overrides: object) -> SqliteVectorStore:
    settings: dict[str, object] = {"model_id": MODEL, "dimensions": DIMS, "repo_id": REPO}
    settings.update(overrides)
    return SqliteVectorStore.open(path, **settings)  # type: ignore[arg-type]


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "index.db"


@pytest.fixture
def store(db_path: Path) -> Iterator[SqliteVectorStore]:
    with open_store(db_path) as opened:
        yield opened


def raw(db_path: Path) -> sqlite3.Connection:
    """A second connection that inspects the file directly, as a SQLite viewer would."""
    connection = sqlite3.connect(db_path)
    connection.enable_load_extension(True)
    sqlite_vec.load(connection)
    return connection


def assert_no_orphans(db_path: Path) -> None:
    # vec0 does not cascade deletes: a leftover vector would match queries as a ghost result.
    with raw(db_path) as connection:
        chunks = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]
        stored = connection.execute("SELECT count(*) FROM chunk_vectors").fetchone()[0]
    assert chunks == stored


A1, A2 = make_chunk("a.ts", 1, "alpha"), make_chunk("a.ts", 5, "beta")
B1 = make_chunk("b.ts", 1, "gamma")


# --- 6.2: schema, open, persistence -----------------------------------------------------


def test_satisfies_the_vector_store_protocol(store: SqliteVectorStore) -> None:
    protocol_view: VectorStore = store  # mypy checks the structure

    assert protocol_view.search(unit(1, 0, 0, 0), k=5) == []  # a new index is empty


def test_new_index_records_what_built_it(store: SqliteVectorStore, db_path: Path) -> None:
    with raw(db_path) as connection:
        meta = dict(connection.execute("SELECT key, value FROM index_meta").fetchall())
        journal = connection.execute("PRAGMA journal_mode").fetchone()[0]

    assert meta["schema_version"] == str(SCHEMA_VERSION)
    assert (meta["model_id"], meta["dimensions"], meta["repo_id"]) == (MODEL, str(DIMS), REPO)
    assert "created_at" in meta
    assert journal == "wal"  # readers and the writer do not block each other


def test_index_survives_close_and_reopen(db_path: Path) -> None:
    with open_store(db_path) as store:
        store.replace_file("a.ts", "typescript", "hash-a", [A1], vectors(unit(1, 0, 0, 0)))

    with open_store(db_path) as reopened:
        assert [chunk for chunk, _ in reopened.search(unit(1, 0, 0, 0), k=1)] == [A1]
        assert reopened.file_hashes() == {"a.ts": "hash-a"}


def test_garbage_file_is_a_store_error_with_a_rebuild_hint(db_path: Path) -> None:
    db_path.write_bytes(b"this is not a database" * 100)

    with pytest.raises(StoreError, match="delete the file to rebuild") as raised:
        open_store(db_path)
    assert isinstance(raised.value, CodeSenseError)


def test_other_sqlite_database_is_not_taken_over(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE notes (text TEXT)")

    with pytest.raises(StoreError, match="not a CodeSense index"):
        open_store(db_path)


def test_unreachable_location_is_a_store_error(tmp_path: Path) -> None:
    with pytest.raises(StoreError):
        open_store(tmp_path / "missing-folder" / "index.db")


@pytest.mark.parametrize("dimensions", [0, -1, True])
def test_dimensions_must_be_a_positive_int(db_path: Path, dimensions: object) -> None:
    with pytest.raises(ValueError, match="dimensions"):
        open_store(db_path, dimensions=dimensions)


# --- 6.3: add, update, remove, search ---------------------------------------------------


def test_search_returns_chunks_with_similarity_best_first(
    store: SqliteVectorStore, db_path: Path
) -> None:
    store.replace_file(
        "a.ts", "typescript", "h", [A1, A2], vectors(unit(1, 0, 0, 0), unit(0, 1, 0, 0))
    )
    store.replace_file("b.ts", "typescript", "h", [B1], vectors(unit(-1, 0, 0, 0)))

    results = store.search(unit(1, 0, 0, 0), k=3)

    assert [chunk for chunk, _ in results] == [A1, A2, B1]
    # Cosine similarity, not distance: same direction 1, unrelated 0, opposite -1.
    np.testing.assert_allclose([score for _, score in results], [1.0, 0.0, -1.0], atol=1e-6)
    assert_no_orphans(db_path)


def test_k_limits_results_and_may_exceed_the_index_size(store: SqliteVectorStore) -> None:
    store.replace_file(
        "a.ts", "typescript", "h", [A1, A2], vectors(unit(1, 0, 0, 0), unit(1, 1, 0, 0))
    )

    assert len(store.search(unit(1, 0, 0, 0), k=1)) == 1
    assert len(store.search(unit(1, 0, 0, 0), k=50)) == 2


def test_replace_file_removes_the_previous_version(store: SqliteVectorStore, db_path: Path) -> None:
    store.replace_file(
        "a.ts", "typescript", "v1", [A1, A2], vectors(unit(1, 0, 0, 0), unit(0, 1, 0, 0))
    )
    edited = make_chunk("a.ts", 1, "alpha", body="return 2;")

    store.replace_file("a.ts", "typescript", "v2", [edited], vectors(unit(0, 0, 1, 0)))

    assert [chunk for chunk, _ in store.search(unit(1, 1, 1, 1), k=10)] == [edited]
    assert store.file_hashes() == {"a.ts": "v2"}
    assert_no_orphans(db_path)


def test_delete_file_keeps_other_files(store: SqliteVectorStore, db_path: Path) -> None:
    store.replace_file(
        "a.ts", "typescript", "h", [A1, A2], vectors(unit(1, 0, 0, 0), unit(0, 1, 0, 0))
    )
    store.replace_file("b.ts", "typescript", "h", [B1], vectors(unit(0, 0, 1, 0)))

    store.delete_file("a.ts")

    assert [chunk for chunk, _ in store.search(unit(1, 0, 0, 0), k=10)] == [B1]
    assert store.file_hashes() == {"b.ts": "h"}
    assert_no_orphans(db_path)


def test_file_with_no_chunks_is_still_recorded(store: SqliteVectorStore) -> None:
    # An empty file was indexed; Step 7 must not re-read it on every run.
    store.replace_file("empty.ts", "typescript", "h", [], np.zeros((0, DIMS), dtype=np.float32))

    assert store.file_hashes() == {"empty.ts": "h"}


def test_clear_empties_the_index_but_keeps_its_identity(
    store: SqliteVectorStore, db_path: Path
) -> None:
    store.replace_file("a.ts", "typescript", "h", [A1], vectors(unit(1, 0, 0, 0)))

    store.clear()

    assert store.search(unit(1, 0, 0, 0), k=10) == []
    assert store.file_hashes() == {}
    assert_no_orphans(db_path)
    store.close()
    open_store(db_path).close()  # meta kept: same model still opens


def test_every_chunk_records_its_model(store: SqliteVectorStore, db_path: Path) -> None:
    store.replace_file(
        "a.ts", "typescript", "h", [A1, A2], vectors(unit(1, 0, 0, 0), unit(0, 1, 0, 0))
    )

    with raw(db_path) as connection:
        models = connection.execute("SELECT DISTINCT model_id FROM chunks").fetchall()
    assert models == [(MODEL,)]


@pytest.mark.parametrize(
    ("chunks", "rows", "message"),
    [
        ([A1, A2], vectors(unit(1, 0, 0, 0)), "2 chunks but 1 vectors"),
        ([A1], np.ones((1, 3), dtype=np.float32), r"got float32 \(1, 3\)"),
        ([A1], np.ones((1, DIMS), dtype=np.float64), "float32"),
        ([B1], vectors(unit(1, 0, 0, 0)), "belongs to b.ts"),
    ],
)
def test_replace_file_rejects_inconsistent_input(
    store: SqliteVectorStore, chunks: list[CodeChunk], rows: Vectors, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        store.replace_file("a.ts", "typescript", "h", chunks, rows)


@pytest.mark.parametrize(
    ("query", "k", "message"),
    [(unit(1, 0, 0), 5, "shape"), (unit(1, 0, 0, 0), 0, "k must be >= 1")],
)
def test_search_rejects_invalid_input(
    store: SqliteVectorStore, query: Vectors, k: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        store.search(query, k)


# --- 6.4: one transaction per file ------------------------------------------------------


def test_failed_replace_leaves_the_previous_version_intact(
    store: SqliteVectorStore, db_path: Path
) -> None:
    store.replace_file(
        "a.ts", "typescript", "v1", [A1, A2], vectors(unit(1, 0, 0, 0), unit(0, 1, 0, 0))
    )
    duplicate = make_chunk("a.ts", 1, "alpha")  # same chunk_id twice: the 2nd insert fails

    with pytest.raises(sqlite3.IntegrityError):
        store.replace_file(
            "a.ts",
            "typescript",
            "v2",
            [duplicate, duplicate],
            vectors(unit(0, 0, 1, 0), unit(0, 0, 0, 1)),
        )

    assert [chunk for chunk, _ in store.search(unit(1, 0, 0, 0), k=10)] == [A1, A2]
    assert store.file_hashes() == {"a.ts": "v1"}  # the delete of v1 was rolled back too
    assert_no_orphans(db_path)


# --- 6.5: compatibility check -----------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "overrides"),
    [
        ("model_id", {"model_id": "jinaai/other-model"}),
        ("dimensions", {"dimensions": 8}),
        ("repo_id", {"repo_id": "repo-2"}),
    ],
)
def test_incompatible_index_is_refused(
    db_path: Path, field: str, overrides: dict[str, object]
) -> None:
    open_store(db_path).close()

    with pytest.raises(IndexMismatchError, match=f"{field}.*rebuild") as raised:
        open_store(db_path, **overrides)
    assert isinstance(raised.value, StoreError)


def test_index_from_another_schema_version_is_refused(db_path: Path) -> None:
    open_store(db_path).close()
    with raw(db_path) as connection:
        connection.execute("UPDATE index_meta SET value = '0' WHERE key = 'schema_version'")

    with pytest.raises(IndexMismatchError, match="schema_version"):
        open_store(db_path)


# --- 6.6: embedding reuse ---------------------------------------------------------------


def test_existing_vectors_are_returned_byte_identical(store: SqliteVectorStore) -> None:
    stored = vectors(unit(1, 2, 3, 4), unit(4, 3, 2, 1))
    store.replace_file("a.ts", "typescript", "h", [A1, A2], stored)

    found = store.existing_vectors([embedding_key(A1), embedding_key(A2), "unknown-key"])

    assert found.keys() == {embedding_key(A1), embedding_key(A2)}
    assert found[embedding_key(A1)].tobytes() == stored[0].tobytes()
    assert found[embedding_key(A2)].tobytes() == stored[1].tobytes()


def test_vector_is_found_for_the_same_function_after_a_line_shift(store: SqliteVectorStore) -> None:
    store.replace_file("a.ts", "typescript", "h", [A1], vectors(unit(1, 2, 3, 4)))
    shifted = make_chunk("a.ts", 4, "alpha")  # 3 lines added above: new chunk_id, same text

    assert shifted.chunk_id != A1.chunk_id
    assert embedding_key(shifted) in store.existing_vectors([embedding_key(shifted)])


def test_no_keys_means_no_query(store: SqliteVectorStore) -> None:
    assert store.existing_vectors([]) == {}
