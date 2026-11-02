"""Indexing settings the user can change.

Settings arrive as untrusted JSON from VS Code. ``IndexConfig.from_dict`` turns them
into a validated, immutable object once, at the boundary; code after that trusts it.

Deliberately not settings: supported file extensions (owned by the language
registry, Step 3) and built-in exclusions such as node_modules (constants).
Search ``top_k`` is per query and validated by the retriever (Step 8).
"""

from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any, Self

from codesense.errors import ConfigError

_LIMITS = ("max_file_bytes", "max_files", "max_chunk_tokens", "window_lines")


@dataclass(frozen=True, slots=True)
class IndexConfig:
    exclude_globs: tuple[str, ...] = ()  # gitignore-style patterns, on top of .gitignore
    max_file_bytes: int = 1024 * 1024  # larger files are almost always generated or minified
    max_files: int = 20_000  # safety cap for accidentally opening a huge folder
    max_chunk_tokens: int = 512  # embedder input cap; covers 93% of chunks (docs/experiments)
    window_lines: int = 40  # fallback chunker window size
    window_overlap: int = 10  # lines shared by consecutive windows

    def __post_init__(self) -> None:
        for name in _LIMITS:
            value = getattr(self, name)
            if value < 1:
                raise ConfigError(f"{name} must be >= 1, got {value}")
        if not 0 <= self.window_overlap < self.window_lines:
            raise ConfigError(
                f"window_overlap must be >= 0 and < window_lines ({self.window_lines}), "
                f"got {self.window_overlap}"
            )
        if any(not glob.strip() for glob in self.exclude_globs):
            raise ConfigError("exclude_globs must not contain empty patterns")

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> Self:
        """Build a config from JSON-like settings; missing keys keep their defaults."""
        known = {field.name for field in fields(cls)}
        unknown = sorted(raw.keys() - known)
        if unknown:
            raise ConfigError(
                f"unknown setting(s): {', '.join(unknown)}; "
                f"valid settings: {', '.join(sorted(known))}"
            )

        values: dict[str, Any] = {}
        for name, value in raw.items():
            if name == "exclude_globs":
                if not isinstance(value, list) or not all(isinstance(g, str) for g in value):
                    raise ConfigError(f"exclude_globs must be a list of strings, got {value!r}")
                values[name] = tuple(value)
            elif isinstance(value, bool) or not isinstance(value, int):
                # bool is checked first: True is an int in Python and would pass as 1.
                raise ConfigError(f"{name} must be an integer, got {value!r}")
            else:
                values[name] = value
        return cls(**values)
