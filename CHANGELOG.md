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
