# ADR-0004: Use a two-package monorepo layout with no `docker/` directory

- **Status:** Accepted
- **Date:** 2026-10-29
- **Level:** 1

## Context
The bootcamp repository standard lists `README.md`, `docs/`, `src/`, `tests/`, `scripts/`, `docker/`, `.github/`, `LICENSE` and `CHANGELOG.md`. This project has two components in two languages (ADR-0001), each with its own build system, dependency manager and test runner.

## Decision
```
engine/      Python package: src/codesense/, tests/, pyproject.toml (uv)
extension/   VS Code extension: src/, test, package.json (npm)
docs/        architecture.md, decisions/, agenda/
scripts/     developer scripts (added when the first one exists)
.github/     CI workflows
README.md · LICENSE · CHANGELOG.md · CLAUDE.md
```

- **`src/` and `tests/` live inside each package** instead of at the root.
- **No `docker/` directory.**
- **Empty directories are not created in advance.** `scripts/` and `extension/` appear with their first real file.

## Alternatives considered
| Option | Why not |
|---|---|
| Root-level `src/` containing both Python and TypeScript | Mixes two toolchains. uv and npm would both need custom configuration, and tests become harder to run per component. |
| Two separate repositories | Engine and extension change together while the protocol is evolving. One repo keeps them in sync in a single commit. |
| `docker/` with a Dockerfile | CodeSense is a local desktop tool. A container would package nothing the user runs, and the extension needs the host's VS Code. A `.devcontainer/` may be added later for reproducible development setups. |

## Consequences
**Positive:** each package uses its ecosystem's standard layout and commands, and CI can run them as separate jobs.
**Negative:** this differs from the bootcamp standard, so it needs this ADR to explain it. Contributors must `cd` into the right package.
**Revisit when:** a third component appears, or a reproducible dev environment becomes necessary (add `.devcontainer/`).
