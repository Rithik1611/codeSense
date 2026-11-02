from collections.abc import Callable
from pathlib import Path

import pytest

type MakeRepo = Callable[[dict[str, str | bytes]], Path]


@pytest.fixture
def make_repo(tmp_path: Path) -> MakeRepo:
    """Build a fake repository in tmp_path from {relative path: text or bytes}.

    Built per test instead of committed fixtures: our own .gitignore would hide
    fixture node_modules/ and dist/ folders from git, so CI would never see them.
    """

    def make(files: dict[str, str | bytes]) -> Path:
        for relative, content in files.items():
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            # Bytes, not write_text: on Windows write_text silently turns "\n" into "\r\n".
            path.write_bytes(content if isinstance(content, bytes) else content.encode())
        return tmp_path

    return make
