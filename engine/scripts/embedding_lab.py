"""Lab 5.1: look inside the embedding model before trusting it.

Usage (from engine/):  uv run python scripts/embedding_lab.py
Shows tokens, vector shape and length, a query x code similarity matrix, and how cost
grows with input length. Results: docs/experiments/level1-embeddings.md.
"""

import sys
import time

import numpy as np

from codesense.embedding import jina

SNIPPETS = {
    "add": "function add(a, b) {\n  return a + b;\n}",
    "fetchUser": (
        "async function fetchUser(id) {\n"
        "  const res = await fetch(`/users/${id}`);\n"
        "  return res.json();\n}"
    ),
    "parseCsv": "function parseCsvLine(line) {\n  return line.split(',').map((c) => c.trim());\n}",
    "debounce": (
        "function debounce(fn, ms) {\n  let t;\n"
        "  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };\n}"
    ),
    "isEmail": "const isEmail = (s) => /^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(s);",
}
QUERIES = [
    "sum two values",
    "load a user from the server",
    "split a comma separated row",
    "wait until typing stops before calling",
    "validate an email address",
]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Windows defaults to cp1252
    model = jina._load_model()  # the lab looks under the hood, so it uses the raw model

    print("1. Tokens: the model reads sub-word pieces, not characters or lines")
    code = SNIPPETS["fetchUser"]
    tokens = model.tokenizer.tokenize(code)
    ratio = len(code) / len(tokens)
    print(f"   {len(code)} characters -> {len(tokens)} tokens ({ratio:.1f} chars/token)")
    print(f"   {tokens[:16]} ...")
    print("   ('Ġ' marks a token that starts with a space)\n")

    print("2. One vector per text: token vectors are mean-pooled, then normalized")
    unnormalized = model.encode(code, normalize_embeddings=False)
    vector = model.encode(code, normalize_embeddings=True)
    before, after = np.linalg.norm(unnormalized), np.linalg.norm(vector)
    print(f"   shape {vector.shape}, length before {before:.2f}, after {after:.2f}")
    print(f"   first numbers: {np.round(vector[:6], 3)} (no single number 'means' anything)\n")

    print("3. Similarity matrix (cosine = dot product of unit vectors); * marks each row's best")
    documents = model.encode(list(SNIPPETS.values()), normalize_embeddings=True)
    queries = model.encode(QUERIES, normalize_embeddings=True)
    print(" " * 42 + "".join(f"{name:>11s}" for name in SNIPPETS))
    for query, scores in zip(QUERIES, queries @ documents.T, strict=True):
        best = int(np.argmax(scores))
        cells = "".join(f"{s:10.2f}{'*' if i == best else ' '}" for i, s in enumerate(scores))
        print(f"   {query:39s}{cells}")
    print("   Scores are relative: 0.4 is not '40% sure'. Compare them within one query only.\n")

    print("4. Cost grows faster than length (attention compares every token pair)")
    long_text = "function add(a, b) { return a + b; }\n" * 400
    ids = model.tokenizer(long_text)["input_ids"]
    for length in (128, 512, 1024, 2048):
        text = model.tokenizer.decode(ids[1 : length - 1])  # minus [CLS]/[SEP]
        model.encode([text])  # warm-up
        started = time.perf_counter()
        model.encode([text] * 3, batch_size=1)
        print(f"   {length:5d} tokens: {(time.perf_counter() - started) / 3 * 1000:6.0f} ms")


if __name__ == "__main__":
    main()
