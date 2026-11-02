"""Core data types shared by every engine layer."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath


class SymbolKind(StrEnum):
    FUNCTION = "function"  # declarations, and arrow/function expressions bound to a name
    METHOD = "method"
    CLASS = "class"
    WINDOW = "window"  # fixed-size line window: fallback when no symbol was extracted


@dataclass(frozen=True, slots=True)
class CodeChunk:
    """One searchable unit of source code, traceable to its exact location.

    Lines are 1-based and inclusive, as shown in an editor. ``path`` is relative
    to the repository root and always uses forward slashes.

    Model id and indexing time are not stored here: they describe how a chunk
    was indexed, not what the code is, and are attached by the store (Step 6).
    """

    chunk_id: str
    repo_id: str
    path: str
    language: str
    symbol_name: str | None
    symbol_kind: SymbolKind
    start_line: int
    end_line: int
    content: str
    content_hash: str

    def __post_init__(self) -> None:
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError(
                f"invalid line range {self.start_line}-{self.end_line}: "
                "lines are 1-based and end_line must be >= start_line"
            )
        if not self.content.strip():
            raise ValueError(f"empty content for chunk at {self.path}:{self.start_line}")
        _check_relative_posix_path(self.path)


def _check_relative_posix_path(path: str) -> None:
    posix = PurePosixPath(path)
    if (
        not path
        or "\\" in path
        or posix.is_absolute()
        or PureWindowsPath(path).drive
        or ".." in posix.parts
    ):
        raise ValueError(
            f"invalid path {path!r}: must be relative to the repository root, "
            "use forward slashes and stay inside the repository"
        )
