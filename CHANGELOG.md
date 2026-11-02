# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Development environment: uv-managed Python 3.12 engine package with PyTorch (CPU), sentence-transformers, sqlite-vec, tree-sitter and pathspec.
- Repository foundation: README, MIT license, changelog, architecture overview and Level 1 agenda.
- Architecture Decision Records 0001–0004.
- Python quality tooling: ruff, strict mypy, pytest.
- GitHub Actions CI for the engine.
- `.gitattributes` enforcing LF line endings.
- `CodeChunk` and `SymbolKind` core data types with validated, 1-based line ranges and repository-relative POSIX paths.
- Deterministic SHA-256 identifiers: `content_hash` (line-ending insensitive), position-based `chunk_id`, and case-normalized `repo_id`.
- `CodeSenseError` / `ConfigError` for expected failures, and stderr-only logging configured by `CODESENSE_LOG_LEVEL`.
- `IndexConfig` with validated indexing limits and `from_dict` parsing of untrusted settings (unknown keys and wrong types rejected).
- Language registry mapping `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs` and `.cjs` to language ids.
- Repository discovery that prunes default exclusions, honours root and nested `.gitignore` files and user `exclude_globs`, does not follow symlinks, and enforces `max_files`.
- Defensive file reading that skips oversized, binary, non-UTF-8 and unreadable files with a recorded reason.
