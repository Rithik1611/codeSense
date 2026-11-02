"""The vector store contract, so the backend stays replaceable (spec 5.4)."""

from collections.abc import Iterable, Sequence
from typing import Protocol

from codesense.embedding.base import Vectors
from codesense.models import CodeChunk


class VectorStore(Protocol):
    """Chunks and their vectors for one repository and one embedding model.

    Writes are per file and atomic: a file is always fully old or fully new.
    """

    def replace_file(
        self,
        path: str,
        language: str,
        file_hash: str,
        chunks: Sequence[CodeChunk],
        vectors: Vectors,
    ) -> None:
        """Add or update a file: its previous chunks are removed in the same transaction."""
        ...

    def delete_file(self, path: str) -> None: ...

    def file_hashes(self) -> dict[str, str]:
        """Content hash of every indexed file, so unchanged files can be skipped."""
        ...

    def existing_vectors(self, keys: Iterable[str]) -> dict[str, Vectors]:
        """Stored vectors by ``embedding_key``; unknown keys are left out."""
        ...

    def search(self, query: Vectors, k: int) -> list[tuple[CodeChunk, float]]:
        """The ``k`` nearest chunks with their cosine similarity (-1..1), best first."""
        ...

    def clear(self) -> None:
        """Remove every chunk and file but keep the index's identity (model, repository)."""
        ...

    def close(self) -> None: ...
