"""Deterministic identifiers.

Two hashes, two jobs:
- ``content_hash`` answers "is this the same code?" and drives embedding reuse.
- ``chunk_id`` answers "which row is this?" and is derived from position only.
Line shifts give chunks new IDs, but unchanged code keeps its content hash,
so its embedding is reused instead of recomputed.

SHA-256, never the built-in ``hash()``: that is randomized per process.
"""

import hashlib
import os
from pathlib import Path

_SEPARATOR = "\0"  # cannot appear in paths or IDs, so ("src/ab", "c") != ("src/a", "bc")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_hash(content: str) -> str:
    """Hash source text, ignoring CRLF vs LF so line-ending style never forces re-embedding."""
    return _sha256(content.replace("\r\n", "\n"))


def chunk_id(repo_id: str, path: str, start_line: int, end_line: int) -> str:
    """Identify a chunk by where it is: repository, relative path and line span."""
    posix_path = path.replace("\\", "/")
    return _sha256(_SEPARATOR.join((repo_id, posix_path, str(start_line), str(end_line))))


def repo_id(root: Path) -> str:
    """Identify a repository by its absolute root path.

    shortcut: path-based, so moving the repo creates a new ID; Level 2 replaces this
    with registered repositories.
    """
    # normcase lowercases on Windows only, where C:\\repo and c:\\repo are the same folder.
    return _sha256(os.path.normcase(root.resolve()))
