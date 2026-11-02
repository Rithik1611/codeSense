"""A model-free embedder for tests: fast, deterministic, offline.

Feature hashing: every word adds 1 to a slot chosen by its hash, so texts that share
words point in similar directions. That is enough to test ranking without the real
model. It is not semantic: "sum" and "add" are unrelated here.
"""

import hashlib
import re
from collections.abc import Sequence

import numpy as np

from codesense.embedding.base import Vectors

# Words, with camelCase and snake_case split: "getUser_id" -> get, user, id.
_WORD = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")


class FakeEmbedder:
    model_id = "fake/hashing"

    def __init__(self, dimensions: int = 768) -> None:
        self.dimensions = dimensions

    def embed_documents(self, texts: Sequence[str]) -> Vectors:
        if not texts:
            return np.zeros((0, self.dimensions), dtype=np.float32)
        return np.stack([self._embed(text) for text in texts])

    def embed_query(self, text: str) -> Vectors:
        return self._embed(text)

    def _embed(self, text: str) -> Vectors:
        vector = np.zeros(self.dimensions, dtype=np.float32)
        words = [word.lower() for word in _WORD.findall(text)] or [text]  # never a zero vector
        for word in words:
            # sha256, not hash(): Python salts hash() per process, so vectors would change.
            digest = hashlib.sha256(word.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:8], "big") % self.dimensions] += 1.0
        return vector / np.linalg.norm(vector)
