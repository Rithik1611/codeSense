"""Language registry: the single source of truth for which files CodeSense can index.

The language id also selects the tree-sitter grammar in Step 4, which is why ``.tsx``
is its own language: in TSX, ``<T>x`` is a JSX element; in plain TypeScript it is a cast.
"""

from pathlib import PurePosixPath

_LANGUAGE_BY_EXTENSION = {
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",  # the JavaScript grammar already parses JSX
    ".mjs": "javascript",
    ".cjs": "javascript",
}


def language_for(path: str) -> str | None:
    """Return the language id for a repository-relative POSIX path, or None if unsupported."""
    return _LANGUAGE_BY_EXTENSION.get(PurePosixPath(path).suffix.lower())
