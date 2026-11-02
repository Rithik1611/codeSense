import pytest

from codesense.ingest.languages import language_for


@pytest.mark.parametrize(
    ("path", "language"),
    [
        ("src/app.ts", "typescript"),
        ("src/App.tsx", "tsx"),  # TSX needs its own grammar: <T>x is JSX there, a cast in .ts
        ("src/app.js", "javascript"),
        ("src/App.jsx", "javascript"),  # the JavaScript grammar parses JSX
        ("src/app.mjs", "javascript"),
        ("src/app.cjs", "javascript"),
    ],
)
def test_supported_extensions(path: str, language: str) -> None:
    assert language_for(path) == language


@pytest.mark.parametrize(
    "path", ["main.py", "package.json", "README.md", "Makefile", ".gitignore", "src/ts"]
)
def test_unsupported_files_have_no_language(path: str) -> None:
    assert language_for(path) is None


def test_extension_match_is_case_insensitive() -> None:
    assert language_for("src/LEGACY.JS") == "javascript"


def test_only_the_last_suffix_counts() -> None:
    # Excluding declaration files is a discovery rule (3.2); the registry only names languages.
    assert language_for("types/index.d.ts") == "typescript"
    assert language_for("app.ts.bak") is None
