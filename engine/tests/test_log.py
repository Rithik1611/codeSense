import logging
from collections.abc import Iterator

import pytest

from codesense.errors import CodeSenseError, ConfigError
from codesense.log import configure_logging


@pytest.fixture(autouse=True)
def restore_logging() -> Iterator[None]:
    # configure_logging mutates global logging state; undo it so other tests are unaffected.
    root, package = logging.getLogger(), logging.getLogger("codesense")
    handlers, root_level, package_level = root.handlers[:], root.level, package.level
    yield
    root.handlers[:] = handlers
    root.setLevel(root_level)
    package.setLevel(package_level)


def test_logs_go_to_stderr_and_never_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()

    logging.getLogger("codesense.indexer").info("indexed 42 files")

    out, err = capsys.readouterr()
    assert out == ""  # stdout is reserved for the JSON-RPC protocol (Step 10)
    assert "indexed 42 files" in err


def test_default_level_hides_debug(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()

    logging.getLogger("codesense.indexer").debug("noisy detail")

    assert "noisy detail" not in capsys.readouterr().err


def test_env_var_sets_level_case_insensitively(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CODESENSE_LOG_LEVEL", "debug")
    configure_logging()

    logging.getLogger("codesense.indexer").debug("noisy detail")

    assert "noisy detail" in capsys.readouterr().err


def test_third_party_info_stays_quiet(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CODESENSE_LOG_LEVEL", "DEBUG")
    configure_logging()

    logging.getLogger("transformers").info("library chatter")
    logging.getLogger("transformers").warning("library warning")

    err = capsys.readouterr().err
    assert "library chatter" not in err
    assert "library warning" in err


def test_invalid_level_is_a_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODESENSE_LOG_LEVEL", "verbose")

    with pytest.raises(ConfigError, match="CODESENSE_LOG_LEVEL") as error:
        configure_logging()

    # The server (Step 10) shows CodeSenseErrors to the user and treats anything else as a bug.
    assert isinstance(error.value, CodeSenseError)
