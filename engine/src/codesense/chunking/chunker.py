"""Turn one source file into CodeChunks: a chunk per symbol, line windows for the rest.

Lines not covered by any symbol ("gaps") are windowed, so every line with code in it
is searchable: top-level config, interfaces, and regions the parser could not read.
"""

import logging

from codesense.chunking.symbols import extract_symbols, parse
from codesense.chunking.window import window_ranges
from codesense.config import IndexConfig
from codesense.ids import chunk_id, content_hash
from codesense.models import CodeChunk, SourceFile, SymbolKind

logger = logging.getLogger(__name__)


def chunk_file(source: SourceFile, repo_id: str, config: IndexConfig) -> list[CodeChunk]:
    text = source.text.replace("\r\n", "\n")  # one line-ending style: same code, same chunks
    # Not splitlines(): it also splits on \u2028, \x0c and others, which editors and
    # tree-sitter do not count as new lines, so every line number below would shift.
    lines = text.split("\n")

    tree = parse(text, source.language)
    if tree.root_node.has_error:
        logger.warning(
            "%s has syntax errors; code the parser could not read is indexed as line windows",
            source.path,
        )

    symbols = extract_symbols(tree)
    candidates: list[tuple[int, int, str | None, SymbolKind]] = [
        (s.start_line, s.end_line, s.name, s.kind) for s in symbols
    ]
    covered = {line for s in symbols for line in range(s.start_line, s.end_line + 1)}
    for run in _uncovered_runs(len(lines), covered):
        # Trim first: windowing blank edges (like the "" after a final newline) adds windows
        # that shrink into their neighbour once trimmed.
        trimmed_run = _trim_blank_lines(lines, *run)
        if trimmed_run is None:
            continue
        windows = window_ranges(*trimmed_run, config.window_lines, config.window_overlap)
        candidates += [(start, end, None, SymbolKind.WINDOW) for start, end in windows]

    chunks: dict[tuple[int, int], CodeChunk] = {}  # keyed by range: one chunk per chunk_id
    for start, end, name, kind in candidates:  # symbols first, so they win a shared range
        trimmed = _trim_blank_lines(lines, start, end)
        if trimmed is None or trimmed in chunks:
            continue
        start, end = trimmed
        content = "\n".join(lines[start - 1 : end])
        if not any(char.isalnum() for char in content):  # a lone "}" or "});" is noise
            continue
        chunks[trimmed] = CodeChunk(
            chunk_id=chunk_id(repo_id, source.path, start, end),
            repo_id=repo_id,
            path=source.path,
            language=source.language,
            symbol_name=name,
            symbol_kind=kind,
            start_line=start,
            end_line=end,
            content=content,
            content_hash=content_hash(content),
        )
    return sorted(chunks.values(), key=lambda c: (c.start_line, c.end_line))


def _uncovered_runs(line_count: int, covered: set[int]) -> list[tuple[int, int]]:
    """Maximal runs of consecutive line numbers that no symbol covers."""
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for line in range(1, line_count + 2):  # one past the end closes the final run
        if line <= line_count and line not in covered:
            start = line if start is None else start
        elif start is not None:
            runs.append((start, line - 1))
            start = None
    return runs


def _trim_blank_lines(lines: list[str], start: int, end: int) -> tuple[int, int] | None:
    while start <= end and not lines[start - 1].strip():
        start += 1
    while end >= start and not lines[end - 1].strip():
        end -= 1
    return (start, end) if start <= end else None
