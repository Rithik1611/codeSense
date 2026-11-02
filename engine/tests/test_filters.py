from pathlib import Path

import pytest
from conftest import MakeRepo

from codesense.config import IndexConfig
from codesense.ingest.filters import read_source
from codesense.models import SkippedFile, SkipReason, SourceFile

CODE = "export function add(a: number, b: number) {\n  return a + b;\n}\n"


def read(root: Path, path: str, config: IndexConfig | None = None) -> SourceFile | SkippedFile:
    return read_source(root, path, config or IndexConfig())


def test_reads_utf8_source_with_its_language(make_repo: MakeRepo) -> None:
    root = make_repo({"src/math.ts": CODE})

    assert read(root, "src/math.ts") == SourceFile("src/math.ts", "typescript", CODE)


def test_non_ascii_utf8_is_kept(make_repo: MakeRepo) -> None:
    text = 'const greeting = "héllo 👋";\n'
    root = make_repo({"i18n.js": text})

    assert read(root, "i18n.js") == SourceFile("i18n.js", "javascript", text)


def test_utf8_byte_order_mark_is_stripped(make_repo: MakeRepo) -> None:
    # Windows editors often write a BOM; left in, it would become part of the first chunk.
    root = make_repo({"bom.ts": b"\xef\xbb\xbf" + CODE.encode()})

    assert read(root, "bom.ts") == SourceFile("bom.ts", "typescript", CODE)


def test_empty_file_is_read_not_skipped(make_repo: MakeRepo) -> None:
    # Nothing is wrong with it; the chunker simply produces no chunks.
    root = make_repo({"empty.ts": ""})

    assert read(root, "empty.ts") == SourceFile("empty.ts", "typescript", "")


def test_file_at_the_size_limit_is_read(make_repo: MakeRepo) -> None:
    root = make_repo({"a.ts": "x" * 10})

    assert isinstance(read(root, "a.ts", IndexConfig(max_file_bytes=10)), SourceFile)


def test_file_over_the_size_limit_is_skipped(make_repo: MakeRepo) -> None:
    root = make_repo({"bundle.js": "x" * 11})

    result = read(root, "bundle.js", IndexConfig(max_file_bytes=10))

    assert result == SkippedFile("bundle.js", SkipReason.OVERSIZED)


def test_nul_byte_means_binary(make_repo: MakeRepo) -> None:
    root = make_repo({"image.js": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"})

    assert read(root, "image.js") == SkippedFile("image.js", SkipReason.BINARY)


def test_binary_detection_only_sniffs_the_first_8000_bytes(make_repo: MakeRepo) -> None:
    # Same heuristic as git: cheap, and good enough for real binaries, which have NULs early.
    root = make_repo({"late.js": b"x" * 8000 + b"\x00"})

    assert isinstance(read(root, "late.js"), SourceFile)


@pytest.mark.parametrize(
    "content",
    [
        "const café = 1;\n".encode("latin-1"),
        b"const x = '\xff';\n",
    ],
)
def test_non_utf8_file_is_skipped(make_repo: MakeRepo, content: bytes) -> None:
    root = make_repo({"legacy.js": content})

    assert read(root, "legacy.js") == SkippedFile("legacy.js", SkipReason.NOT_UTF8)


def test_file_that_disappeared_after_discovery_is_unreadable(make_repo: MakeRepo) -> None:
    root = make_repo({})

    assert read(root, "deleted.ts") == SkippedFile("deleted.ts", SkipReason.UNREADABLE)


def test_unsupported_path_is_a_bug_not_a_skip(make_repo: MakeRepo) -> None:
    root = make_repo({"notes.md": "# hi\n"})

    with pytest.raises(ValueError, match="unsupported"):
        read(root, "notes.md")
