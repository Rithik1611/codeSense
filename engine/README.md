# codesense (engine)

The Python search engine behind the CodeSense VS Code extension. It ingests a repository, chunks code into functions and classes, embeds the chunks, stores the vectors in SQLite + sqlite-vec, and answers similarity queries.

See the [root README](../README.md) for the project overview and [docs/architecture.md](../docs/architecture.md) for the design.

## Commands

```bash
uv sync                         # install dependencies into .venv
uv run pytest                   # tests
uv run ruff check .             # lint
uv run ruff format .            # format
uv run mypy                     # strict type check
```

## Layout

```
src/codesense/   package source (modules arrive step by step; see docs/agenda/level-1.md)
tests/           pytest suite
```
