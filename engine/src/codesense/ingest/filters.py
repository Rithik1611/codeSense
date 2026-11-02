"""Read one discovered file defensively: a bad file is skipped with a reason, never fatal."""

import logging
from pathlib import Path

from codesense.config import IndexConfig
from codesense.ingest.languages import language_for
from codesense.models import SkippedFile, SkipReason, SourceFile

logger = logging.getLogger(__name__)

_BINARY_SNIFF_BYTES = 8000  # the same window git uses to decide "binary"


def read_source(root: Path, path: str, config: IndexConfig) -> SourceFile | SkippedFile:
    language = language_for(path)
    if language is None:
        raise ValueError(f"unsupported file {path!r}: discover() only returns supported files")

    try:
        with (root / path).open("rb") as file:
            # One byte past the limit is enough to know it is too big; a 2 GB file is never loaded.
            data = file.read(config.max_file_bytes + 1)
    except OSError as error:
        logger.warning("cannot read %s: %s", path, error.strerror)
        return SkippedFile(path, SkipReason.UNREADABLE)

    if len(data) > config.max_file_bytes:
        return SkippedFile(path, SkipReason.OVERSIZED)
    if b"\0" in data[:_BINARY_SNIFF_BYTES]:
        return SkippedFile(path, SkipReason.BINARY)
    try:
        text = data.decode("utf-8-sig")  # -sig strips a leading byte order mark if present
    except UnicodeDecodeError:
        return SkippedFile(path, SkipReason.NOT_UTF8)
    return SourceFile(path, language, text)
