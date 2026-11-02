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


class SkipReason(StrEnum):
    """Why a supported source file was not indexed."""

    SYMLINK = "symlink"  # not followed: could loop or point outside the repository
    FILE_CAP = "file_cap"  # beyond IndexConfig.max_files
    OVERSIZED = "oversized"  # larger than IndexConfig.max_file_bytes
    BINARY = "binary"
    NOT_UTF8 = "not_utf8"
    UNREADABLE = "unreadable"  # permission denied, deleted after discovery, ...


@dataclass(frozen=True, slots=True)
class SourceFile:
    """A supported file that passed every filter, ready for chunking."""

    path: str
    language: str
    text: str


@dataclass(frozen=True, slots=True)
class SkippedFile:
    """A supported source file that was not indexed, and why.

    Ignored files (.gitignore, default exclusions) and unsupported languages are
    out of scope, not skipped, so they are never recorded.
    """

    path: str
    reason: SkipReason


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
