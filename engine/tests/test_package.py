import tomllib
from pathlib import Path

import codesense

PYPROJECT = Path(__file__).parents[1] / "pyproject.toml"


def test_version_matches_pyproject() -> None:
    expected = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]

    assert codesense.__version__ == expected
