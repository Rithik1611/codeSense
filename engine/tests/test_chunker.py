import logging

import pytest

from codesense.chunking.chunker import chunk_file
from codesense.config import IndexConfig
from codesense.ids import chunk_id, content_hash
from codesense.models import CodeChunk, SourceFile, SymbolKind

REPO = "repo-1"
FUNCTION, METHOD, CLASS, WINDOW = (
    SymbolKind.FUNCTION,
    SymbolKind.METHOD,
    SymbolKind.CLASS,
    SymbolKind.WINDOW,
)

MIXED = """\
import { db } from "./db";

export const ROUTES = [
  { path: "/users", handler: "listUsers" },
];

/** Loads one user. */
export async function getUser(id: string) {
  return db.get(id);
}

class Cache {
  store = new Map();

  get(key: string) {
    return this.store.get(key);
  }
}
"""


def chunks(
    text: str, language: str = "typescript", config: IndexConfig | None = None
) -> list[CodeChunk]:
    return chunk_file(SourceFile("src/a.ts", language, text), REPO, config or IndexConfig())


def summary(result: list[CodeChunk]) -> list[tuple[str | None, SymbolKind, int, int]]:
    return [(c.symbol_name, c.symbol_kind, c.start_line, c.end_line) for c in result]


# --- 4.4: symbols + gap windows ---------------------------------------------------------


def test_symbols_and_gap_windows_cover_the_file() -> None:
    assert summary(chunks(MIXED)) == [
        (None, WINDOW, 1, 5),  # import + ROUTES: code outside any symbol (D2)
        ("getUser", FUNCTION, 7, 10),  # doc comment included (D3)
        ("Cache", CLASS, 12, 13),  # header, trailing blank line trimmed (D1)
        ("Cache.get", METHOD, 15, 17),  # qualified name (D4)
        # line 18 is only "}": no letters or digits, so no chunk
    ]


def test_chunks_carry_ids_hashes_and_source_metadata() -> None:
    chunk = chunks(MIXED)[1]

    assert chunk.chunk_id == chunk_id(REPO, "src/a.ts", 7, 10)
    assert chunk.content_hash == content_hash(chunk.content)
    assert (chunk.repo_id, chunk.path, chunk.language) == (REPO, "src/a.ts", "typescript")
    assert chunk.content.startswith("/** Loads one user. */\nexport async function getUser")


def test_file_without_symbols_is_windowed() -> None:
    text = "".join(f"const x{n} = {n};\n" for n in range(1, 101))

    assert summary(chunks(text)) == [
        (None, WINDOW, 1, 40),
        (None, WINDOW, 31, 70),
        (None, WINDOW, 61, 100),
    ]


def test_window_size_and_overlap_come_from_the_config() -> None:
    text = "".join(f"const x{n} = {n};\n" for n in range(1, 6))
    config = IndexConfig(window_lines=3, window_overlap=1)

    assert [(c.start_line, c.end_line) for c in chunks(text, config=config)] == [(1, 3), (3, 5)]


def test_large_gap_between_symbols_is_windowed_in_place() -> None:
    config = IndexConfig(window_lines=3, window_overlap=0)
    text = (
        "function a() {}\n"
        + "".join(f"const x{n} = {n};\n" for n in range(5))
        + "function b() {}\n"
    )

    assert summary(chunks(text, config=config)) == [
        ("a", FUNCTION, 1, 1),
        (None, WINDOW, 2, 4),
        (None, WINDOW, 5, 6),
        ("b", FUNCTION, 7, 7),
    ]


@pytest.mark.parametrize("text", ["", "\n\n  \n", "}\n});\n"])
def test_files_without_meaningful_code_have_no_chunks(text: str) -> None:
    assert chunks(text) == []


def test_symbols_sharing_a_line_range_keep_one_chunk() -> None:
    # Same range means same chunk_id, so only the first one is kept.
    assert summary(chunks("function a() {} function b() {}\n")) == [("a", FUNCTION, 1, 1)]


def test_line_numbers_ignore_unicode_line_separators() -> None:
    # str.splitlines() would split on \u2028 and shift every line below it; editors don't.
    text = 'const s = "a\u2028b";\nfunction f() {}\n'

    assert summary(chunks(text))[-1] == ("f", FUNCTION, 2, 2)


def test_crlf_and_lf_files_give_identical_chunks() -> None:
    lf = "function f() {\n  return 1;\n}\n"

    assert chunks(lf.replace("\n", "\r\n")) == chunks(lf)


SAMPLES = {
    "mixed": MIXED,
    "jsx": "const App = () => (\n  <div>\n    hi\n  </div>\n);\n\nexport default App;\n",
    "windows": "".join(f"call{n}();\n\n" for n in range(60)),
    "broken": "function ok() {\n  return 1;\n}\nfunction broken( {\n  let x = ;\n}\n",
}


@pytest.mark.parametrize("name", SAMPLES)
def test_chunk_invariants(name: str) -> None:
    text = SAMPLES[name]
    lines = text.split("\n")
    language = "javascript" if name == "jsx" else "typescript"

    result = chunks(text, language)

    ranges = [(c.start_line, c.end_line) for c in result]
    assert ranges == sorted(ranges)
    assert len(set(ranges)) == len(ranges)  # unique ranges, so unique chunk ids
    for chunk in result:
        assert chunk.end_line <= len(lines)  # slicing alone would hide a bogus end line
        assert chunk.content == "\n".join(lines[chunk.start_line - 1 : chunk.end_line])
        assert chunk.content.strip()
    covered = {line for start, end in ranges for line in range(start, end + 1)}
    for number, line in enumerate(lines, start=1):
        if any(char.isalnum() for char in line):
            assert number in covered, f"line {number} is not searchable: {line!r}"


# --- 4.5: syntax errors -----------------------------------------------------------------


def test_broken_file_keeps_valid_symbols_and_windows_the_rest(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="codesense"):
        result = chunks(SAMPLES["broken"])

    assert summary(result)[0] == ("ok", FUNCTION, 1, 3)
    assert all(c.symbol_kind == WINDOW for c in result[1:])
    assert "src/a.ts has syntax errors" in caplog.text


def test_valid_file_logs_no_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="codesense"):
        chunks(MIXED)

    assert caplog.text == ""


def test_large_file_has_correct_line_numbers() -> None:
    # Regression: tree-sitter 0.26.0 returned garbage positions (row ~1e9) for files over
    # ~6 KB once other allocations reused its memory; our small samples never triggered it.
    text = "".join(f"function f{n}(a, b) {{\n  return a + b + {n};\n}}\n" for n in range(600))

    result = chunks(text, "javascript")
    churn = [bytearray(9000) for _ in range(2000)]  # reuse freed memory, as a real index run does

    assert len(churn) == 2000
    assert [(c.symbol_name, c.start_line, c.end_line) for c in result][-1] == ("f599", 1798, 1800)
    assert all(c.end_line <= 1800 for c in result)
