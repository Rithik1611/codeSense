"""Expected failures.

Raise a ``CodeSenseError`` when the cause is outside our control (bad settings,
missing model, unreadable index); its message is shown to the user. Any other
exception is a bug and is reported as an internal error with a traceback.
Subclasses are added in the step that first raises them.
"""


class CodeSenseError(Exception):
    """A failure with a message that is safe and useful to show the user."""


class ConfigError(CodeSenseError):
    """Invalid user configuration (settings or environment variables)."""


class EmbeddingError(CodeSenseError):
    """The embedding model could not be loaded or failed to produce valid vectors."""


class StoreError(CodeSenseError):
    """The index file cannot be opened, read or written."""


class IndexMismatchError(StoreError):
    """The index was built with a different schema, model or repository; rebuild it."""


class IngestError(CodeSenseError):
    """The repository as a whole cannot be indexed (a single bad file is skipped instead)."""
