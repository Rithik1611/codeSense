# ADR-0002: Use `jinaai/jina-embeddings-v2-base-code` as the Level 1 embedding model

- **Status:** Accepted (Level 1; to be re-evaluated with benchmarks in Level 5)
- **Date:** 2026-10-29
- **Level:** 1

## Context
The quality of semantic search is bounded by the embedding model. Requirements:

- **Local:** runs on a developer laptop CPU, with no source code sent to an API.
- **Code-aware:** trained on code paired with natural-language descriptions, because general text models are not optimal for code.
- **Long context:** whole functions should fit without being cut off.
- **Licensing:** permissive enough for a public portfolio project.

## Decision
Use **`jinaai/jina-embeddings-v2-base-code`**, loaded with sentence-transformers on PyTorch (CPU).

| Property | Value |
|---|---|
| Parameters | ~161M |
| Output dimensions | 768 |
| Max input | 8192 tokens (ALiBi positional encoding) |
| License | Apache-2.0 |
| Training data | GitHub code + natural-language/code pairs, 30 programming languages |
| Download size | ~300 MB (one time, then offline) |

Vectors are **L2-normalized**, so cosine similarity equals the dot product.

## Alternatives considered
| Option | Why not (yet) |
|---|---|
| `BAAI/bge-small-en-v1.5` (384-dim) | General text model, not code-specific. Faster. A good **baseline** to compare against in Level 5. |
| `sentence-transformers/all-MiniLM-L6-v2` | 256-token limit truncates most functions. Not code-specific. |
| `nomic-ai/nomic-embed-code` | ~7B parameters, too heavy for CPU laptops. |
| Hosted APIs (OpenAI, Voyage, Cohere) | Violates the local-first and privacy principles. |
| `fastembed` (ONNX runtime) instead of PyTorch | Much lighter install. Kept as a fallback if PyTorch's footprint becomes a problem. |

## Consequences
**Positive**
- Code-specific training should align natural-language queries with implementations.
- The long context lets us embed whole functions. We still cap input length for speed (measured in Step 5).
- Apache-2.0 is compatible with this repository's MIT license.

**Negative**
- Requires `trust_remote_code=True`: we execute Jina's model code from Hugging Face. That code imports helpers removed in newer `transformers`, so we **pin `transformers>=4.44,<4.50`** (see `engine/pyproject.toml`). This is real version-drift risk to monitor.
- PyTorch adds ~1 GB to the environment.
- CPU attention cost grows with input length, so long chunks are slow.

**Revisit when:** Level 5 benchmarks show another model wins on our labelled queries, or the transformers pin blocks a needed upgrade.
