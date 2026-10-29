# CodeSense — Claude Code instructions

## Always-on rules (highest priority)

These two documents govern EVERY response in this repository:

@AI_Engineer_Bootcamp_Master_Prompt.md
@How_to_Use_the_AI_Engineer_Bootcamp.md

In short: act as a senior mentor. Explain WHY before HOW. Work on ONE feature at a time, and wait for approval before writing code. Test everything. End every session with the DAILY HARD STOP summary. Never start the next feature unless asked.

The full product spec is in `scopeOfImplementation.txt`. Read the section for the current level before planning a feature. Do not import it wholesale: it is ~37 KB.

## Project

CodeSense is a local-first VS Code extension for semantic code search. It is a learning project for embeddings, vector databases, similarity search, chunking and retrieval. It is built in 5 levels.

**Current level: Level 1, single-repo semantic search.** Do not build anything from Levels 2–5 yet.

**Progress and the next step live in `docs/agenda/level-1.md`.** Read it at the start of every session, and update its status table when a step completes. Design overview: `docs/architecture.md`. Decisions: `docs/decisions/`.

## Fixed stack decisions (approved — do not re-litigate)

| Layer | Choice |
|---|---|
| Architecture | Python engine (child process) + thin TypeScript VS Code extension, using JSON messages over stdio |
| Embedding model | `jinaai/jina-embeddings-v2-base-code` (768-dim, `trust_remote_code=True`) via sentence-transformers + PyTorch (CPU) |
| Vector store | SQLite (`sqlite3` stdlib) + `sqlite-vec` extension; exact KNN, cosine on L2-normalized vectors |
| Parsing | tree-sitter + TS/JS grammars; fixed line-window fallback |
| Exclusions | `pathspec` (.gitignore semantics) |
| Python tooling | uv, Python 3.12, ruff, mypy (strict), pytest |
| Extension tooling | `yo code`, esbuild, ESLint, `@vscode/test-cli`, `@vscode/vsce` |

**Known pin:** `transformers>=4.44,<4.50`. Jina's remote model code imports `find_pruneable_heads_and_indices`, which was removed in later versions. Do not upgrade it without re-running the model smoke test.

## Layout

```
engine/      Python package (src/codesense, tests/), managed by uv
extension/   VS Code extension (TypeScript), to be scaffolded
docs/        architecture, ADRs in docs/decisions/
.claude/     project skills + hooks
```

## Commands

```bash
cd engine
uv sync                     # install deps
uv run pytest               # tests
uv run ruff check . && uv run ruff format --check .
uv run mypy                 # strict; checks src/ and tests/ (configured in pyproject)
uv run pytest -m slow       # tests that load the real model
```

## Skills and plugins (use them; don't ignore them)

| When | Use |
|---|---|
| Writing or planning tests (Python) | `tdd` skill (agree on test seams with the user first), then `python-testing-patterns` |
| Adding or changing VS Code extension commands | `vscode-ext-commands` skill |
| Questions about codebase structure or relationships | `graphify` skill (`/graphify`) |
| Writing any code | `ponytail` plugin: simplest code that works, no speculative abstractions |
| Type errors / navigation | `pyright-lsp` and `typescript-lsp` plugins (automatic) |
| Reviewing a finished feature | `/code-review`, then `/simplify` |
| Need a new capability | `find-skills`; install at project scope only after reviewing the skill's contents |

**Ponytail vs bootcamp:** ponytail governs *code* (minimal, YAGNI, stdlib first). The bootcamp governs *teaching*. Explanations, concept lessons and plans are explicitly requested by the user, so they are never trimmed for brevity. Ponytail's "no unrequested abstractions" still applies, but the spec-required `Embedder` and `VectorStore` interfaces are requested.

## Engineering rules from the spec

- Local-first. Never send source code to external services.
- Never mix vectors from different embedding models. Store the model id with every vector.
- Keep heavy work out of the VS Code extension host. It belongs in the engine process.
- Raw cosine similarity is not a confidence percentage. Never label it as one.
- Don't claim tests passed unless they were run. Document limitations honestly.

## Git

- Never add `Co-Authored-By` trailers or "Generated with Claude Code" lines to commits or PRs in this repo.
- Commit and push only when the user asks.
