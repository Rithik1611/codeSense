from dataclasses import replace

from codesense.embedding.base import document_text, embedding_key
from codesense.ids import chunk_id, content_hash
from codesense.models import CodeChunk, SymbolKind


def make_chunk(symbol_name: str | None, kind: SymbolKind, path: str = "src/users.ts") -> CodeChunk:
    content = "async getUser(id) {\n  return db.get(id);\n}"
    return CodeChunk(
        chunk_id=chunk_id("r", path, 3, 5),
        repo_id="r",
        path=path,
        language="typescript",
        symbol_name=symbol_name,
        symbol_kind=kind,
        start_line=3,
        end_line=5,
        content=content,
        content_hash=content_hash(content),
    )


def test_symbol_chunk_gets_path_and_symbol_header() -> None:
    text = document_text(make_chunk("UserService.getUser", SymbolKind.METHOD))

    assert text == (
        "// path: src/users.ts\n"
        "// symbol: UserService.getUser (method)\n"
        "async getUser(id) {\n  return db.get(id);\n}"
    )


def test_window_chunk_gets_path_only() -> None:
    text = document_text(make_chunk(None, SymbolKind.WINDOW))

    assert text.startswith("// path: src/users.ts\nasync getUser")


def test_same_code_at_another_path_is_different_embedding_input() -> None:
    # Why Step 7 must key embedding reuse on the hash of THIS text, not on content_hash.
    here = make_chunk("getUser", SymbolKind.FUNCTION, path="src/users.ts")
    moved = make_chunk("getUser", SymbolKind.FUNCTION, path="src/legacy/users.ts")

    assert here.content_hash == moved.content_hash
    assert document_text(here) != document_text(moved)


def test_embedding_key_survives_a_line_shift_but_not_a_move_or_an_edit() -> None:
    # The payoff of "two hashes, two jobs": an edit above a function shifts its lines
    # (new chunk_id) but not its text, so its stored vector can be reused.
    original = make_chunk("getUser", SymbolKind.FUNCTION)
    shifted = replace(
        original, start_line=13, end_line=15, chunk_id=chunk_id("r", "src/users.ts", 13, 15)
    )
    moved = replace(original, path="src/legacy/users.ts")
    edited = replace(original, content=original.content.replace("db.get", "cache.get"))

    assert shifted.chunk_id != original.chunk_id
    assert embedding_key(shifted) == embedding_key(original)
    assert embedding_key(moved) != embedding_key(original)
    assert embedding_key(edited) != embedding_key(original)
