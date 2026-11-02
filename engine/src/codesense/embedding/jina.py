"""The real embedding model: jina-embeddings-v2-base-code on CPU (ADR-0002).

Measured on CPU (docs/experiments/level1-embeddings.md): cost grows roughly with the
square of the input length, so inputs are capped at ``max_tokens`` and truncated.
"""

import logging
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np

from codesense.embedding.base import Vectors
from codesense.errors import EmbeddingError

if TYPE_CHECKING:  # importing sentence_transformers loads PyTorch: seconds, so only on use
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = "jinaai/jina-embeddings-v2-base-code"
REVISION = "516f4baf13dec4ddddda8631e019b5737c8bc250"
# trust_remote_code runs Python from the Hub, and this model loads it from ANOTHER repo
# (jina-bert-v2-qk-post-norm). Pinning REVISION alone would not pin the code that runs.
CODE_REVISION = "3baf9e3ac750e76e8edd3019170176884695fb94"
_DIMENSIONS = 768
_BATCH_SIZE = 8  # measured: CPU throughput is flat from 1 to 32; batching pays off on GPUs


def _load_model() -> "SentenceTransformer":
    from sentence_transformers import SentenceTransformer

    pin = {"code_revision": CODE_REVISION}
    model: SentenceTransformer = SentenceTransformer(
        MODEL_NAME,
        revision=REVISION,
        trust_remote_code=True,
        device="cpu",
        model_kwargs=pin,
        config_kwargs=pin,
    )
    return model


class JinaEmbedder:
    model_id = f"{MODEL_NAME}@{REVISION[:7]}"
    dimensions = _DIMENSIONS

    def __init__(self, max_tokens: int) -> None:
        """Load the model once; it is reused for every batch and query (loading takes seconds)."""
        logger.info("loading %s (first use downloads ~300 MB, then works offline)", self.model_id)
        started = time.perf_counter()
        try:
            self._model = _load_model()
        except (OSError, ImportError, ValueError, RuntimeError) as error:
            raise EmbeddingError(
                f"could not load the embedding model {MODEL_NAME}: {error}. "
                "The first run needs an internet connection to download it (~300 MB); "
                "an ImportError usually means an unsupported transformers version."
            ) from error
        self._model.max_seq_length = max_tokens  # longer inputs are truncated, not rejected
        logger.info("model loaded in %.1f s", time.perf_counter() - started)

    @property
    def loaded_code_module(self) -> str:
        """Python module of the remote model code that actually ran (contains its revision)."""
        return type(self._model[0].auto_model).__module__

    def embed_documents(self, texts: Sequence[str]) -> Vectors:
        return self._encode(list(texts))

    def embed_query(self, text: str) -> Vectors:
        return self._encode([text]).reshape(self.dimensions)

    def _encode(self, texts: list[str]) -> Vectors:
        if not texts:
            return np.zeros((0, self.dimensions), dtype=np.float32)
        try:
            vectors = self._model.encode(
                texts,
                batch_size=_BATCH_SIZE,
                normalize_embeddings=True,  # unit length: cosine similarity = dot product
                convert_to_numpy=True,
                show_progress_bar=False,  # stdout/stderr belong to the protocol and logs
            )
        except RuntimeError as error:  # PyTorch reports out-of-memory and similar this way
            raise EmbeddingError(f"embedding {len(texts)} texts failed: {error}") from error
        expected = (len(texts), self.dimensions)
        if vectors.shape != expected:
            raise EmbeddingError(
                f"model returned vectors of shape {vectors.shape}, expected {expected}"
            )
        return np.asarray(vectors, dtype=np.float32)  # typed result; no copy when already float32
