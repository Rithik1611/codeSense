import subprocess
import sys
from pathlib import Path

import pytest

from codesense.ids import chunk_id, content_hash, repo_id


def test_content_hash_matches_known_sha256_vector() -> None:
    # Golden value: if this changes, every stored hash in every index silently stops matching.
    assert content_hash("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_content_hash_is_deterministic() -> None:
    assert content_hash("function a() {}") == content_hash("function a() {}")


def test_content_hash_ignores_line_ending_style() -> None:
    assert content_hash("a();\r\nb();\r\n") == content_hash("a();\nb();\n")


def test_content_hash_detects_any_change() -> None:
    assert content_hash("return a + b") != content_hash("return a - b")


def test_chunk_id_differs_by_position() -> None:
    base = chunk_id("repo", "src/a.ts", 1, 10)

    assert base != chunk_id("repo", "src/a.ts", 2, 10)
    assert base != chunk_id("repo", "src/a.ts", 1, 11)
    assert base != chunk_id("repo", "src/b.ts", 1, 10)
    assert base != chunk_id("other", "src/a.ts", 1, 10)


def test_chunk_id_is_same_for_windows_and_posix_paths() -> None:
    windows_id = chunk_id("repo", "src\\http\\retry.ts", 1, 9)

    assert windows_id == chunk_id("repo", "src/http/retry.ts", 1, 9)


def test_chunk_id_parts_cannot_run_together() -> None:
    # Without a separator both would hash the string "src/abc.ts".
    assert chunk_id("repo", "src/ab", 1, 1) != chunk_id("repo", "src/a", 1, 1)
    assert chunk_id("repo", "a.ts", 1, 23) != chunk_id("repo", "a.ts", 12, 3)


def test_chunk_id_is_stable_across_processes() -> None:
    # Python's built-in hash() is randomized per process; a stored ID must survive restarts.
    code = "from codesense.ids import chunk_id; print(chunk_id('repo', 'src/a.ts', 1, 10))"
    output = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()

    assert output == chunk_id("repo", "src/a.ts", 1, 10)


def test_repo_id_is_same_for_equivalent_paths(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()

    assert repo_id(tmp_path) == repo_id(tmp_path / "sub" / "..")


def test_repo_id_differs_between_repositories(tmp_path: Path) -> None:
    assert repo_id(tmp_path / "one") != repo_id(tmp_path / "two")


@pytest.mark.skipif(sys.platform != "win32", reason="paths are case-insensitive only on Windows")
def test_repo_id_ignores_path_case_on_windows(tmp_path: Path) -> None:
    assert repo_id(Path(str(tmp_path).upper())) == repo_id(Path(str(tmp_path).lower()))
