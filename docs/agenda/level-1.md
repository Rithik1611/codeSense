# Level 1 Agenda: Single-Repository Semantic Search

**Goal:** open a TypeScript/JavaScript repo in VS Code, run *Index Workspace*, search in natural language, and click a result to jump to the exact lines. The index survives restarts.

**Build order:** engine → CLI → protocol → UI. Semantic search works in the terminal by Step 9, before any VS Code code exists.

**Workflow per feature:** explain → approve → code + tests → explain → commit → stop.

| Step | Name | Status |
|---|---|---|
| 0 | Planning and environment | ✅ Done |
| 1 | Repository foundation | ✅ Done |
| 2 | Core data types, configuration, logging | ✅ Done |
| 3 | Repository ingestion | ✅ Done |
| 4 | Code extraction and chunking | ⬜ Next |
| 5 | Embeddings | ⬜ |
| 6 | Vector store | ⬜ |
| 7 | Indexing pipeline | ⬜ |
| 8 | Similarity search and retrieval | ⬜ |
| 9 | Engine CLI (end-to-end milestone) | ⬜ |
| 10 | Engine protocol server (JSON-RPC over stdio) | ⬜ |
| 11 | VS Code extension scaffold | ⬜ |
| 12 | Engine client in the extension | ⬜ |
| 13 | Search UI | ⬜ |
| 14 | Extension tests | ⬜ |
| 15 | Documentation and Level 1 acceptance | ⬜ |
| 🎓 | Graduation | ⬜ |

---

## Step 1: Repository foundation ✅
**Goal:** a professional, CI-checked repository before the first engine code.
- **1.1** README, LICENSE (MIT), CHANGELOG, `docs/` structure, this agenda
- **1.2** ADRs 0001–0004
- **1.3** ruff, strict mypy, pytest config; `.vscode` recommendations
- **1.4** GitHub Actions CI (ruff, mypy, pytest)

**Learn:** ADRs; lint vs format vs type-check; what CI protects.
**Done when:** CI is green; you can explain each ADR.

## Step 2: Core data types, configuration, logging
**Goal:** define the system's shared types once.
- **2.1** ✅ `CodeChunk` frozen dataclass + `SymbolKind`. Model id and indexing time are attached by the store in Step 6
- **2.2** ✅ SHA-256 content hash (reuse embeddings) + chunk ID by **position** (decided: identity ≠ content) + path-based `repo_id`
- **2.3** ✅ `CodeSenseError` hierarchy; logging to **stderr only** (`log.py`, not `logging.py`)
- **2.4** ✅ `IndexConfig`: exclusions, size/file/token limits, window size/overlap; `from_dict` validates untrusted settings. Not settings: extensions (language registry, 3.5), `top_k` (per query, 8.2)

**Learn:** dataclasses, immutability, content hashing, stable identity.
**Files:** `models.py`, `ids.py`, `errors.py`, `log.py`, `config.py` + tests.
**Done when:** tests cover ID stability, hash determinism, config validation; mypy strict passes.

## Step 3: Repository ingestion (spec 5.1)
**Goal:** list exactly the source files worth indexing; never crash on a bad file.
- **3.1** ✅ Language registry: `.ts .tsx .js .jsx .mjs .cjs` → language id (the single source of supported extensions; `.tsx` is its own grammar)
- **3.2** ✅ `discover()`: a directory walk that prunes default exclusions (`node_modules`, `.git`, `dist`, `build`, `out`, `coverage`) and excludes `*.min.js` and `*.d.ts`. Symlinks are not followed; a symlinked source file is recorded as `symlink`. Output is sorted
- **3.3** ✅ Root and nested `.gitignore` files via `pathspec` (each relative to its own directory, the deepest decision wins), plus user `exclude_globs`. Defaults cannot be re-included
- **3.4** ✅ `read_source()` skips `oversized` (reads at most limit + 1 bytes), `binary` (NUL in the first 8000 bytes), `not_utf8` and `unreadable` files and strips a UTF-8 BOM. `max_files` keeps the first N sorted paths and records the rest as `file_cap`

**Two phases:** `discover()` lists names only (cheap). `read_source()` reads one file at a time, so memory stays flat. Only *supported* files that failed are recorded as skipped; ignored and unsupported files are out of scope.
**Limitations:** symlinks are not followed; `.git/info/exclude` and the global gitignore are not read; UTF-16 files count as binary.

**Learn:** gitignore semantics, binary detection, defensive I/O.
**Files:** `ingest/languages.py`, `ingest/discovery.py`, `ingest/filters.py`, tests.
**Tests:** each test builds its fake repo in `tmp_path`. Committed fixture repos would be filtered by our own `.gitignore`, and would break in CI.
**Done when:** tests prove every skip rule, with reasons recorded.

## Step 4: Code extraction and chunking (spec 5.2), core concept
**Goal:** meaningful, traceable code units. Chunk quality caps retrieval quality.
- **4.1** Fixed-window chunker with overlap (fallback + Level 3 baseline)
- **4.2** tree-sitter setup for TS/TSX/JS; AST exploration session
- **4.3** Extract functions, classes, methods, arrow/function expressions assigned to `const`, exports
- **4.4** Window fallback for files without symbols
- **4.5** Parse-failure fallback with recorded reason

**Learn:** ASTs, concrete syntax trees, why function-shaped chunks help, what Level 1 doesn't handle.
**Files:** `chunking/window.py`, `chunking/treesitter.py`, `chunking/extractors.py` + tests.
**Done when:** correct 1-based line ranges for every fixture symbol; clean fallbacks; no empty chunks.

## Step 5: Embeddings (spec 5.3), core concept
**Goal:** code and queries become vectors in one shared space.
- **5.1** Lab: tokens, pooling, normalization; a similarity matrix by hand
- **5.2** `Embedder` interface (`embed_documents`, `embed_query`, `model_id`, `dimensions`)
- **5.3** `JinaEmbedder`: load once, batch, normalize, validate dimensions, measured input-token cap
- **5.4** Experiment: raw code vs code with a contextual header (path + symbol)
- **5.5** `FakeEmbedder` so tests never download the model
- **5.6** Clear `EmbeddingError`s

**Learn:** what embeddings are, shared space, batching vs length cost, licensing.
**Files:** `embedding/base.py`, `embedding/jina.py`, `embedding/fake.py`, `scripts/embedding_lab.py` + tests.
**Done when:** shape, normalization and determinism tests pass; a `slow` real-model test passes; throughput recorded.

## Step 6: Vector store (spec 5.4), core concept
**Goal:** persist vectors + metadata and find nearest neighbours in one SQLite file.
- **6.1** Lesson: vector DBs, exact vs approximate nearest-neighbour search, `vec0`
- **6.2** Schema: `index_meta`, `files`, `chunks`, `vec0` (cosine)
- **6.3** `VectorStore` + SQLite implementation: add/update, delete by file, k-nearest-neighbour search, clear, close
- **6.4** One transaction per file
- **6.5** Model/dimension compatibility check on open
- **6.6** Look up existing vectors by content hash

**Learn:** virtual tables, cosine distance vs similarity, atomicity, index versioning.
**Files:** `store/base.py`, `store/sqlite_store.py`, `store/schema.sql` + tests.
**Done when:** round-trip, delete, reopen and model-mismatch tests pass, and the k-nearest-neighbour ordering is correct.

## Step 7: Indexing pipeline
**Goal:** one reliable `Indexer` connecting Steps 3–6.
- **7.1** discover → chunk → diff → embed only new content → write → remove deleted
- **7.2** Per-file error isolation
- **7.3** Progress callback + cancellation
- **7.4** `IndexReport` statistics

**Learn:** pipelines, idempotency, embedding reuse, cooperative cancellation.
**Done when:** re-indexing an unchanged repo computes **0** embeddings; edits and deletes are handled correctly.

## Step 8: Similarity search and retrieval (spec 5.5), core concepts
**Goal:** question in, ranked code out, honest scores.
- **8.1** Lesson: cosine vs dot product vs L2; top-K; scores are not probabilities
- **8.2** `Retriever`: validate query and per-query `top_k` (1–100) → embed → k-nearest-neighbour search → resolve metadata → `SearchResult`
- **8.3** Labelled sanity set (~10 queries) with the real model (`slow`)

**Done when:** unit tests pass; slow retrieval test passes; hit rate recorded.

## Step 9: Engine CLI, end-to-end milestone 🎯
- **9.1** `codesense index`, `codesense search`, `codesense stats` (argparse)
- **9.2** Try it on a real open-source TS repo; write `docs/experiments/level1-first-look.md`

## Step 10: Engine protocol server
- **10.1** Lesson: JSON-RPC 2.0 and newline-delimited message framing
- **10.2** `initialize`, `index`, `search`, `status`, `cancel`, `shutdown`, `progress` notifications
- **10.3** Indexing on a worker thread; model loaded once
- **10.4** Malformed input → JSON-RPC error; stdout carries protocol messages only

**Done when:** subprocess tests cover the full exchange, including cancellation and malformed input.

## Step 11: VS Code extension scaffold
- **11.1** `yo code` (TypeScript + esbuild), trimmed
- **11.2** Commands, view container, settings in `package.json`
- **11.3** ESLint, strict TS, `@vscode/test-cli`, CI job

## Step 12: Engine client
- **12.1** Start the engine; index stored in `storageUri`
- **12.2** JSON-RPC client: framing, request-ID matching, timeouts, progress
- **12.3** Crash detection, restart, clean shutdown

## Step 13: Search UI (spec 5.6)
- **13.1** Index command with cancellable progress + status bar
- **13.2** Search: InputBox → TreeView (symbol, `path:lines`, "similarity 0.67", snippet tooltip)
- **13.3** Click → open file at the exact range
- **13.4** Loading, empty, no-results, error and indexing states

## Step 14: Extension tests
- **14.1** Activation + command registration
- **14.2** End-to-end search with the real engine + fake embedder
- **14.3** Navigation test
- **14.4** Error states (missing Python, engine crash)

## Step 15: Documentation and acceptance
- **15.1** README with screenshots and limitations
- **15.2** `docs/retrieval-pipeline.md` (model card, metric, chunking, score semantics)
- **15.3** Measurements: indexing time, throughput, latency, index size, hardware
- **15.4** Spec Level 1 acceptance table with evidence
- **15.5** CHANGELOG 0.1.0, `v0.1.0` tag and release

## 🎓 Graduation
Explain without AI: source code → chunks → vectors → results; why the chunks are shaped as they are; what the 768 numbers mean; why cosine; how stale results are prevented; why the engine runs in its own process.

---

## Spec acceptance mapping

| Spec 5.7 criterion | Proven in |
|---|---|
| 1 Trigger indexing | 7, 13.1 |
| 2 Extract and index code units | 3, 4, 7 |
| 3 Embeddings generated and persisted | 5, 6 |
| 4 Natural-language retrieval works | 8.3, 9.2 |
| 5 Correct paths and lines | 4, 8 |
| 6 Results open in VS Code | 13.3, 14.3 |
| 7 Index survives restart | 6, 12.1 |
| 8 Graceful errors | 3.4, 4.5, 5.6, 10.4, 13.4 |
| 9 Test suite | every step, 14 |
| 10 Documented limitations and architecture | 1.2, 15 |

**Deferred:** file watchers (Level 2), keyword/hybrid search (Level 3), sub-chunking very large functions (Level 3), Python language support (later).
