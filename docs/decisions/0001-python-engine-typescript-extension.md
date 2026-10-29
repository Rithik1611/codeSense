# ADR-0001: Use a Python engine behind a thin TypeScript extension, connected over stdio JSON-RPC

- **Status:** Accepted
- **Date:** 2026-10-29
- **Level:** 1

## Context
A VS Code extension must be written in TypeScript or JavaScript. The search engine, however, needs embedding models, AST parsing, a vector store and (in Level 5) evaluation tooling. The spec also requires that:

- the UI must not contain embedding, ranking or indexing logic;
- heavy indexing must not run on the extension host thread;
- there are no network services or microservices without a clear justification.

## Decision
The search engine is a **Python package** (`engine/`). The extension (`extension/`) launches it as a **child process** and talks to it with **JSON-RPC 2.0 messages over stdin/stdout**.

This is the same architecture VS Code uses for language servers (Pylance, the TypeScript server, rust-analyzer).

## Alternatives considered
| Option | Why not |
|---|---|
| Everything in TypeScript (transformers.js, Node SQLite bindings) | Smaller model ecosystem, weaker evaluation tooling for Level 5, and native SQLite modules must be rebuilt for VS Code's Electron runtime. |
| Python engine behind a local HTTP server (FastAPI) | Adds ports, port conflicts and a localhost attack surface. It is a network service the spec asks us to avoid. Stdio gives the same separation with fewer moving parts. |
| Python engine as a one-shot CLI per request | Would reload the ~300 MB model on every search (seconds of latency). A long-lived process loads it once. |

## Consequences
**Positive**
- The UI/engine separation required by the spec is enforced by a process boundary, not just by convention.
- Embedding work runs in another process, so the extension host stays responsive.
- The engine can be tested and used without VS Code (CLI in Step 9).
- Access to the best ML ecosystem for embeddings, rerankers (Level 3) and metrics (Level 5).

**Negative**
- Two languages, two toolchains, two test suites.
- Users need a Python 3.12 environment. Bundling Python is a Level 5 packaging problem.
- We must design and test a protocol (Step 10), and the engine must **never write anything except protocol messages to stdout**.

**Revisit when:** distribution to non-developer users becomes a goal (consider bundling a frozen Python runtime or ONNX in Node).
