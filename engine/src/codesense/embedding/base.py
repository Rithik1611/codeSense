"""The embedding contract every model, real or fake, follows."""

from collections.abc import Sequence
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from codesense.ids import content_hash
from codesense.models import CodeChunk

type Vectors = NDArray[np.float32]


def document_text(chunk: CodeChunk) -> str:
    """The text embedded for a chunk: a path/symbol header, then the code.

    Chosen by experiment 5.4 (docs/experiments/level1-embeddings.md): MRR 0.762 -> 0.805.
    The header includes the path, so embedding reuse must be keyed on this text, not on
    ``chunk.content_hash``: moving a file changes its vectors.
    """
    symbol = f"// symbol: {chunk.symbol_name} ({chunk.symbol_kind})\n" if chunk.symbol_name else ""
    return f"// path: {chunk.path}\n{symbol}{chunk.content}"


def embedding_key(chunk: CodeChunk) -> str:
    """Reuse key for a chunk's vector: changes exactly when the embedded text changes."""
    return content_hash(document_text(chunk))


class Embedder(Protocol):
    """Turns text into float32, L2-normalized vectors, so cosine similarity is a dot product.

    Queries and documents from one embedder share a vector space. Vectors from embedders
    with different ``model_id`` values are unrelated and must never be compared.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> Vectors:
        """One row per text, in input order; an empty input gives shape (0, dimensions)."""
        ...

    def embed_query(self, text: str) -> Vectors:
        """Shape (dimensions,)."""
        ...
