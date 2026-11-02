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
