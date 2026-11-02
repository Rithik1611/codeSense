"""Experiment 5.4: embed raw code, or code with a path/symbol header? Decide with data.

Usage (from engine/):  uv run python scripts/header_experiment.py <npm global node_modules>
Corpus: generator-code 1.12.0 (labelled targets) + typescript-language-server 5.3.0
(about 1,000 distractor chunks). Results: docs/experiments/level1-embeddings.md.
"""

import sys
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from codesense.chunking.chunker import chunk_file
from codesense.config import IndexConfig
from codesense.embedding.base import document_text
from codesense.embedding.jina import JinaEmbedder
from codesense.ingest.discovery import discover
from codesense.ingest.filters import read_source
from codesense.models import CodeChunk, SourceFile

# (query, path of the expected chunk, its symbol). Written without the identifiers' words
# where possible, so the test is about meaning, not keyword overlap.
QUERIES = [
    (
        "convert a TextMate color theme into a VS Code theme",
        "generate-colortheme.js",
        "convertTheme",
    ),
    ("find the newest released version of the editor", "env.js", "getLatestVSCodeVersion"),
    ("check that the publisher name is allowed", "validator.js", "validatePublisher"),
    ("turn a string into a safe file name", "validator.js", "sanitizeFilename"),
    ("ask the user whether to use npm, yarn or pnpm", "prompts.js", "askForPackageManager"),
    ("ask whether to initialize a git repository", "prompts.js", "askForGit"),
    ("read a file's JSON content and collect errors", "generate-snippets.js", "getFileContent"),
    (
        "convert a TextMate grammar into a language definition",
        "generate-language.js",
        "convertGrammar",
    ),
    (
        "ask which file extensions the new language uses",
        "generate-language.js",
        "askForLanguageExtensions",
    ),
    ("webpack settings for a notebook renderer", "webpack.config.js", "makeConfig"),
    ("let the user pick webpack or esbuild", "prompts.js", "askForBundler"),
    ("name shown in the marketplace for the extension", "prompts.js", "askForExtensionDisplayName"),
    ("ask for the scope name of the grammar", "generate-language.js", "askForLanguageScopeName"),
    ("run mocha tests in the browser, bundled with esbuild", "esbuild-mochaTestRunner.ts", "run"),
    (
        "translated name of the language for a language pack",
        "generate-localization.js",
        "askForLocalizedLanguageName",
    ),
]


def raw(chunk: CodeChunk) -> str:
    return chunk.content


def load_chunks(node_modules: Path, package: str) -> list[CodeChunk]:
    root, config = node_modules / package, IndexConfig()
    chunks: list[CodeChunk] = []
    for path in discover(root, config).files:
        source = read_source(root, path, config)
        if isinstance(source, SourceFile):
            chunks += chunk_file(source, package, config)
    return chunks


def evaluate(
    embedder: JinaEmbedder, chunks: list[CodeChunk], text: Callable[[CodeChunk], str]
) -> list[int]:
    started = time.perf_counter()
    documents = embedder.embed_documents([text(chunk) for chunk in chunks])
    print(f"  embedded {len(chunks)} chunks in {time.perf_counter() - started:.0f} s", flush=True)
    ranks = []
    for query, path_end, symbol in QUERIES:
        target = next(
            i for i, c in enumerate(chunks) if c.path.endswith(path_end) and c.symbol_name == symbol
        )
        scores = documents @ embedder.embed_query(query)
        ranks.append(int((scores > scores[target]).sum()) + 1)  # 1 = best
    return ranks


def summary(ranks: list[int]) -> str:
    r = np.array(ranks)
    return f"hit@1 {np.mean(r <= 1):.2f} | hit@5 {np.mean(r <= 5):.2f} | MRR {np.mean(1 / r):.3f}"


def main() -> None:
    node_modules = Path(sys.argv[1])
    chunks = load_chunks(node_modules, "generator-code") + load_chunks(
        node_modules, "typescript-language-server"
    )
    embedder = JinaEmbedder(max_tokens=IndexConfig().max_chunk_tokens)
    results = {}
    for name, text in [("raw", raw), ("header", document_text)]:
        print(f"{name}:", flush=True)
        results[name] = evaluate(embedder, chunks, text)
    print(f"\n{len(QUERIES)} queries, {len(chunks)} chunks")
    for name, ranks in results.items():
        print(f"{name:7s} {summary(ranks)}")
    print("\nrank per query (raw -> header):")
    for (query, _, _), a, b in zip(QUERIES, results["raw"], results["header"], strict=True):
        print(f"  {a:4d} -> {b:4d}  {query}")


if __name__ == "__main__":
    main()
