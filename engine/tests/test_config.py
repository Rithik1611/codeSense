from typing import Any

import pytest

from codesense.config import IndexConfig
from codesense.errors import ConfigError


def test_defaults_are_valid() -> None:
    config = IndexConfig()

    assert config.exclude_globs == ()
    assert config.window_overlap < config.window_lines


def test_from_dict_accepts_full_settings_as_sent_by_the_extension() -> None:
    raw = {
        "exclude_globs": ["**/generated/**", "*.spec.ts"],
        "max_file_bytes": 500_000,
        "max_files": 5_000,
        "max_chunk_tokens": 512,
        "window_lines": 30,
        "window_overlap": 5,
    }

    config = IndexConfig.from_dict(raw)

    assert config.exclude_globs == ("**/generated/**", "*.spec.ts")  # list -> immutable tuple
    assert config.max_files == 5_000
    assert config.window_overlap == 5


def test_from_dict_keeps_defaults_for_missing_settings() -> None:
    assert IndexConfig.from_dict({"max_files": 100}) == IndexConfig(max_files=100)


def test_from_dict_rejects_unknown_settings_and_lists_valid_ones() -> None:
    with pytest.raises(ConfigError, match=r"maxFiles.*valid settings.*max_files"):
        IndexConfig.from_dict({"maxFiles": 100})


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("max_files", "100"),  # string from a hand-edited settings file
        ("max_files", 1.5),
        ("max_files", True),  # bool is a subclass of int in Python
        ("max_files", None),
        ("exclude_globs", "**/dist/**"),  # a bare string, not a list
        ("exclude_globs", ["ok", 3]),
    ],
)
def test_from_dict_rejects_wrong_types(setting: str, value: Any) -> None:
    with pytest.raises(ConfigError, match=setting):
        IndexConfig.from_dict({setting: value})


@pytest.mark.parametrize(
    "setting", ["max_file_bytes", "max_files", "max_chunk_tokens", "window_lines"]
)
@pytest.mark.parametrize("value", [0, -1])
def test_rejects_non_positive_limits(setting: str, value: int) -> None:
    with pytest.raises(ConfigError, match=rf"{setting} must be >= 1, got {value}"):
        IndexConfig.from_dict({setting: value})


@pytest.mark.parametrize("overlap", [-1, 40, 41])
def test_rejects_overlap_outside_window(overlap: int) -> None:
    # overlap >= window would make the window chunker stop advancing (infinite loop).
    with pytest.raises(ConfigError, match="window_overlap"):
        IndexConfig(window_lines=40, window_overlap=overlap)


@pytest.mark.parametrize("glob", ["", "   "])
def test_rejects_empty_exclude_glob(glob: str) -> None:
    with pytest.raises(ConfigError, match="exclude_globs"):
        IndexConfig(exclude_globs=("**/dist/**", glob))
