import subprocess
import sys

import numpy as np

from codesense.embedding.base import Embedder
from codesense.embedding.fake import FakeEmbedder


def test_satisfies_the_embedder_protocol() -> None:
    embedder: Embedder = FakeEmbedder()  # mypy checks the structure; no inheritance needed

    assert embedder.dimensions == 768
    assert embedder.model_id == "fake/hashing"


def test_documents_are_float32_unit_vectors_in_input_order() -> None:
    texts = ["function add(a, b) {}", "class UserService {}", "}"]

    vectors = FakeEmbedder().embed_documents(texts)

    assert vectors.shape == (3, 768)
    assert vectors.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1.0, rtol=1e-6)
    np.testing.assert_array_equal(vectors[1], FakeEmbedder().embed_query(texts[1]))


def test_empty_input_gives_an_empty_matrix() -> None:
    assert FakeEmbedder(dimensions=8).embed_documents([]).shape == (0, 8)


def test_shared_words_mean_higher_similarity() -> None:
    fake = FakeEmbedder()
    query = fake.embed_query("get user by id")
    get_user, add = fake.embed_documents(
        ["async getUser(id) { return this.cache.get(id); }", "function add(a, b) {}"]
    )

    assert float(query @ get_user) > float(query @ add)  # camelCase is split: getUser -> get user


def test_vectors_are_identical_across_processes() -> None:
    # Python's hash() is salted per process; a fake built on it would change every run.
    code = (
        "from codesense.embedding.fake import FakeEmbedder;"
        "print(FakeEmbedder().embed_query('getUser').tobytes().hex())"
    )
    other_process = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert other_process.stdout.strip() == FakeEmbedder().embed_query("getUser").tobytes().hex()
