# Level 1: Embedding measurements and experiments

Step 5 decisions (token cap, batch size, embedding text) come from these measurements.

**Hardware:** AMD Ryzen 7 PRO 8840HS (8 cores / 16 threads; PyTorch uses 8), 28 GB RAM, no GPU.
**Software:** Windows 11, Python 3.12, torch 2.15.0+cpu, sentence-transformers 5.7.0, transformers 4.49.0.
**Model:** `jinaai/jina-embeddings-v2-base-code` @ `516f4ba` (remote code @ `3baf9e3`), 768 dimensions, 311 MB on disk.
**Corpus:** chunks produced by Step 4 from npm packages `generator-code` 1.12.0 and `typescript-language-server` 5.3.0 (1,163 chunks).

Reproduce: `uv run python scripts/embedding_lab.py` and `uv run python scripts/header_experiment.py <npm global node_modules>` (from `engine/`).

## 1. Model facts
| Fact | Value |
|---|---|
| Load time | 46 s cold (first PyTorch import), ~15 s warm |
| Works offline after first download | yes (`HF_HUB_OFFLINE=1` tested) |
| Query/document prompts | none (`{'query': '', 'document': ''}`): the model is symmetric |
| Characters per token (median, real chunks) | 3.96 |

## 2. Chunk sizes in tokens
| p50 | p90 | p95 | p99 | max |
|---|---|---|---|---|
| 64 | 414 | 584 | 2,337 | 15,097 |

| Cap | Chunks truncated |
|---|---|
| 512 | 78 (6.7%) |
| 1,024 | 32 (2.7%) |

## 3. Cost per text vs. length (batch of 1)
| Tokens | Time |
|---|---|
| 128 | 158–205 ms |
| 512 | 756–829 ms |
| 1,024 | 1.8–2.1 s |
| 2,048 | 5.8–6.3 s |
| 4,096 | 22.1 s |

Doubling the length costs ~3×: attention compares every pair of tokens.

## 4. Batch size (50–200-token chunks)
| batch_size | 1 | 8 | 32 |
|---|---|---|---|
| chunks/s | 4.6 | 5.1 | 4.3 |

End to end on the 1,163-chunk corpus at a 512-token cap: **~4.5 chunks/s** (250–266 s).

**Decisions:** `max_chunk_tokens = 512` (93% of chunks embedded whole; worst case < 1 s instead of minutes); `batch_size = 8` (on CPU, batching barely helps; on a GPU it would).

## 5. Experiment: raw code vs. path/symbol header
Each chunk embedded two ways: the raw code, or with a header:
```
// path: generators/app/validator.js
// symbol: validatePublisher (function)
<code>
```
15 hand-labelled natural-language queries; each must find its chunk among all 1,163.

| Variant | hit@1 | hit@5 | MRR |
|---|---|---|---|
| raw | 0.67 | 0.87 | 0.762 |
| **header** | **0.73** | 0.87 | **0.805** |

Per query, the header helped 4 (8→2, 9→8, 5→3, 2→1) and hurt 1 ("let the user pick webpack or esbuild": 2→9).

**Decision:** embed with the header (`embedding.base.document_text`). Because the header contains the path, embedding reuse (Step 7) must be keyed on the hash of the embedded text, not on `content_hash`.

**Limits of this evidence:** 15 queries, written by someone who had seen the code, over two packages. The hit@1 gain is one query. Level 5's benchmark re-tests this.

## 6. Lab: similarity matrix (no shared words needed)
| query \ code | add | fetchUser | parseCsv | debounce | isEmail |
|---|---|---|---|---|---|
| sum two values | **0.58** | -0.00 | 0.03 | 0.08 | -0.02 |
| load a user from the server | 0.04 | **0.54** | 0.06 | -0.02 | 0.14 |
| split a comma separated row | -0.03 | -0.02 | **0.63** | -0.02 | 0.10 |
| wait until typing stops before calling | 0.09 | 0.14 | 0.05 | **0.29** | 0.18 |
| validate an email address | 0.09 | 0.08 | 0.11 | 0.06 | **0.73** |

The correct answer wins every row, but the winning score ranges from 0.29 to 0.73. Scores are only comparable within one query, so a fixed threshold would hide correct results.
