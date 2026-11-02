import time
from collections.abc import Sequence
from typing import Any

import numpy as np
import pytest

from codesense.embedding import jina
from codesense.embedding.base import Embedder
from codesense.embedding.jina import JinaEmbedder
from codesense.errors import CodeSenseError, EmbeddingError

# --- fast: error handling with a stub model (5.6) -------------------------------------


class StubModel:
    """Stands in for SentenceTransformer: records settings, returns canned vectors."""

    def __init__(self, vectors: Any = None, error: Exception | None = None) -> None:
        self.max_seq_length = 8192
        self.vectors, self.error = vectors, error

    def encode(self, texts: Sequence[str], **kwargs: Any) -> Any:
        if self.error is not None:
            raise self.error
        return self.vectors


def use_stub(monkeypatch: pytest.MonkeyPatch, stub: StubModel) -> None:
    monkeypatch.setattr(jina, "_load_model", lambda: stub)


@pytest.mark.parametrize(
    "error",
    [
        OSError("We couldn't connect to 'https://huggingface.co'"),
        ImportError("cannot import name 'find_pruneable_heads_and_indices'"),
    ],
)
def test_load_failure_is_an_actionable_embedding_error(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def fail() -> None:
        raise error

    monkeypatch.setattr(jina, "_load_model", fail)

    with pytest.raises(EmbeddingError, match="could not load the embedding model") as raised:
        JinaEmbedder(max_tokens=512)
    assert isinstance(raised.value, CodeSenseError)
    assert raised.value.__cause__ is error  # `raise ... from` keeps the original for debugging


def test_token_cap_is_applied_to_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = StubModel()
    use_stub(monkeypatch, stub)

    JinaEmbedder(max_tokens=512)

    assert stub.max_seq_length == 512


def test_wrong_vector_shape_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    use_stub(monkeypatch, StubModel(vectors=np.zeros((2, 384), dtype=np.float32)))

    with pytest.raises(EmbeddingError, match=r"shape \(2, 384\), expected \(2, 768\)"):
        JinaEmbedder(max_tokens=512).embed_documents(["a", "b"])


def test_inference_failure_is_an_embedding_error(monkeypatch: pytest.MonkeyPatch) -> None:
    use_stub(monkeypatch, StubModel(error=RuntimeError("not enough memory")))

    with pytest.raises(EmbeddingError, match="not enough memory"):
        JinaEmbedder(max_tokens=512).embed_documents(["a"])


def test_empty_input_never_calls_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    use_stub(monkeypatch, StubModel(error=AssertionError("model was called")))

    assert JinaEmbedder(max_tokens=512).embed_documents([]).shape == (0, 768)


# --- slow: the real model (run with `uv run pytest -m slow`) ---------------------------

ADD = "/** Adds two numbers. */\nfunction add(a, b) {\n  return a + b;\n}"
FETCH = (
    "async function fetchUser(id) {\n"
    "  const response = await fetch(`/users/${id}`);\n"
    "  return response.json();\n}"
)
PARSE = "function parseCsvLine(line) {\n  return line.split(',').map((cell) => cell.trim());\n}"


@pytest.fixture(scope="module")
def real() -> JinaEmbedder:
    return JinaEmbedder(max_tokens=512)  # loaded once for all slow tests in this module


@pytest.mark.slow
def test_real_model_identity_and_pinned_code(real: JinaEmbedder) -> None:
    embedder: Embedder = real

    assert embedder.model_id == "jinaai/jina-embeddings-v2-base-code@516f4ba"
    assert embedder.dimensions == 768
    assert jina.CODE_REVISION in real.loaded_code_module  # the remote code that actually ran


@pytest.mark.slow
def test_real_vectors_are_float32_unit_vectors(real: JinaEmbedder) -> None:
    vectors = real.embed_documents([ADD, FETCH, PARSE])

    assert vectors.shape == (3, 768)
    assert vectors.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1.0, rtol=1e-5)


@pytest.mark.slow
def test_real_vectors_do_not_depend_on_batch_neighbours(real: JinaEmbedder) -> None:
    # In a batch, ADD is padded to FETCH's length; the attention mask must hide the padding.
    alone = real.embed_documents([ADD])[0]
    batched = real.embed_documents([ADD, FETCH])[0]

    np.testing.assert_allclose(alone, batched, atol=1e-4)  # float math differs slightly, not more


@pytest.mark.slow
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("add two numbers", 0),
        ("load a user from the API", 1),
        ("split a comma separated row", 2),
    ],
)
def test_query_is_closest_to_the_matching_code(
    real: JinaEmbedder, query: str, expected: int
) -> None:
    documents = real.embed_documents([ADD, FETCH, PARSE])

    similarities = documents @ real.embed_query(query)  # unit vectors: dot product = cosine

    assert int(np.argmax(similarities)) == expected


@pytest.mark.slow
def test_token_cap_keeps_huge_inputs_fast(real: JinaEmbedder) -> None:
    huge = "function f(a, b) { return a + b; }\n" * 2000  # ~30k tokens, like a bundled file

    started = time.perf_counter()
    real.embed_documents([huge])

    assert time.perf_counter() - started < 10  # ~1 s capped at 512; minutes uncapped
