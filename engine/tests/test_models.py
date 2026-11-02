import dataclasses
import json
from typing import Any

import pytest

from codesense.models import CodeChunk, SymbolKind


def make_chunk(**overrides: Any) -> CodeChunk:
    fields: dict[str, Any] = {
        "chunk_id": "chunk-1",
        "repo_id": "repo-1",
        "path": "src/http/retry.ts",
        "language": "typescript",
        "symbol_name": "fetchWithRetry",
        "symbol_kind": SymbolKind.FUNCTION,
        "start_line": 12,
        "end_line": 31,
        "content": "async function fetchWithRetry() {}",
        "content_hash": "hash-1",
    }
    return CodeChunk(**(fields | overrides))


def test_valid_chunk_keeps_its_values() -> None:
    chunk = make_chunk()

    assert chunk.path == "src/http/retry.ts"
    assert (chunk.start_line, chunk.end_line) == (12, 31)


def test_single_line_chunk_is_valid() -> None:
    chunk = make_chunk(start_line=5, end_line=5)

    assert chunk.start_line == chunk.end_line == 5


def test_window_chunk_has_no_symbol_name() -> None:
    chunk = make_chunk(symbol_name=None, symbol_kind=SymbolKind.WINDOW)

    assert chunk.symbol_name is None


@pytest.mark.parametrize(
    ("start_line", "end_line"),
    [
        (0, 10),  # lines are 1-based: 0 is the classic off-by-one from 0-based parsers
        (-1, 10),
        (10, 9),  # end before start
    ],
)
def test_rejects_invalid_line_range(start_line: int, end_line: int) -> None:
    with pytest.raises(ValueError, match="line"):
        make_chunk(start_line=start_line, end_line=end_line)


@pytest.mark.parametrize("content", ["", "   ", "\n\t\n"])
def test_rejects_empty_content(content: str) -> None:
    with pytest.raises(ValueError, match="content"):
        make_chunk(content=content)


@pytest.mark.parametrize(
    "path",
    [
        "/home/me/repo/src/a.ts",  # absolute POSIX
        "C:/Users/me/repo/a.ts",  # absolute Windows (drive letter)
        "src\\http\\retry.ts",  # Windows separators must be normalized before this point
        "../outside/a.ts",  # escapes the repository
        "src/../../a.ts",
        "",
    ],
)
def test_rejects_paths_that_are_not_relative_posix_inside_repo(path: str) -> None:
    with pytest.raises(ValueError, match="path"):
        make_chunk(path=path)


def test_chunk_is_immutable() -> None:
    chunk = make_chunk()

    with pytest.raises(dataclasses.FrozenInstanceError):
        chunk.start_line = 1  # type: ignore[misc]


def test_chunks_with_equal_values_are_equal_and_hashable() -> None:
    assert make_chunk() == make_chunk()
    assert len({make_chunk(), make_chunk()}) == 1


def test_symbol_kind_serializes_as_plain_string() -> None:
    # StrEnum values go straight into JSON (Step 10) and SQLite (Step 6).
    assert json.dumps(SymbolKind.FUNCTION) == '"function"'
