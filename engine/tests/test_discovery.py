from pathlib import Path

import pytest
from conftest import MakeRepo

from codesense.config import IndexConfig
from codesense.errors import CodeSenseError, IngestError
from codesense.ingest.discovery import discover
from codesense.models import SkippedFile, SkipReason

CODE = "export const x = 1;\n"


def discovered(root: Path, config: IndexConfig | None = None) -> list[str]:
    return list(discover(root, config or IndexConfig()).files)


# --- 3.2: walk, supported languages, default exclusions -------------------------------


def test_finds_supported_files_as_sorted_posix_paths(make_repo: MakeRepo) -> None:
    root = make_repo(
        {"src/b.ts": CODE, "src/a.tsx": CODE, "lib/util/c.js": CODE, "index.mjs": CODE}
    )

    assert discovered(root) == ["index.mjs", "lib/util/c.js", "src/a.tsx", "src/b.ts"]


def test_ignores_unsupported_languages_without_recording_them(make_repo: MakeRepo) -> None:
    root = make_repo({"app.ts": CODE, "main.py": "x = 1\n", "README.md": "# hi\n"})

    result = discover(root, IndexConfig())

    assert result.files == ("app.ts",)
    assert result.skipped == ()  # out of scope is not a failure


@pytest.mark.parametrize(
    "excluded_dir", ["node_modules", ".git", "dist", "build", "out", "coverage"]
)
@pytest.mark.parametrize("parent", ["", "packages/web/"])
def test_default_excluded_directories_at_any_depth(
    make_repo: MakeRepo, excluded_dir: str, parent: str
) -> None:
    root = make_repo({"src/app.ts": CODE, f"{parent}{excluded_dir}/lib/x.js": CODE})

    assert discovered(root) == ["src/app.ts"]


def test_default_excluded_file_patterns(make_repo: MakeRepo) -> None:
    root = make_repo({"app.js": CODE, "vendor/jquery.min.js": CODE, "types/index.d.ts": CODE})

    assert discovered(root) == ["app.js"]


def test_excluded_names_only_match_whole_directory_names(make_repo: MakeRepo) -> None:
    root = make_repo({"builder/app.ts": CODE, "src/output.ts": CODE, "src/dist.ts": CODE})

    assert discovered(root) == ["builder/app.ts", "src/dist.ts", "src/output.ts"]


@pytest.mark.parametrize("missing", ["does-not-exist", "file.ts"])
def test_root_must_be_an_existing_directory(make_repo: MakeRepo, missing: str) -> None:
    root = make_repo({"file.ts": CODE})

    with pytest.raises(IngestError, match="not a directory") as error:
        discover(root / missing, IndexConfig())
    assert isinstance(error.value, CodeSenseError)


def _symlink(target: Path, link: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError:  # Windows without Developer Mode cannot create symlinks
        pytest.skip("symlinks are not available on this machine")


def test_symlinked_source_file_is_recorded_not_followed(make_repo: MakeRepo) -> None:
    root = make_repo({"src/real.ts": CODE})
    _symlink(root / "src" / "real.ts", root / "src" / "link.ts")

    result = discover(root, IndexConfig())

    assert result.files == ("src/real.ts",)
    assert result.skipped == (SkippedFile("src/link.ts", SkipReason.SYMLINK),)


def test_symlinked_directory_is_not_entered(make_repo: MakeRepo) -> None:
    root = make_repo({"src/real.ts": CODE})
    _symlink(root / "src", root / "loop")  # following it would visit src twice (or forever)

    assert discovered(root) == ["src/real.ts"]


# --- 3.3: .gitignore (root + nested) and user exclude_globs ---------------------------


def test_root_gitignore_excludes_files_and_directories(make_repo: MakeRepo) -> None:
    root = make_repo(
        {
            ".gitignore": "# build output\n\ngenerated/\n*.gen.ts\n",
            "src/app.ts": CODE,
            "src/api.gen.ts": CODE,
            "src/generated/types.ts": CODE,
        }
    )

    assert discovered(root) == ["src/app.ts"]


def test_nested_gitignore_patterns_are_relative_to_their_own_directory(
    make_repo: MakeRepo,
) -> None:
    root = make_repo(
        {
            "packages/web/.gitignore": "/generated/\n",  # leading / anchors to packages/web/
            "packages/web/generated/x.ts": CODE,
            "packages/web/src/generated/y.ts": CODE,  # not anchored here: kept
            "generated/z.ts": CODE,  # outside packages/web: kept
        }
    )

    assert discovered(root) == ["generated/z.ts", "packages/web/src/generated/y.ts"]


def test_deeper_gitignore_can_re_include_a_file(make_repo: MakeRepo) -> None:
    root = make_repo(
        {
            ".gitignore": "*.gen.ts\n",
            "src/.gitignore": "!keep.gen.ts\n",
            "src/keep.gen.ts": CODE,
            "src/drop.gen.ts": CODE,
        }
    )

    assert discovered(root) == ["src/keep.gen.ts"]


def test_nested_gitignore_does_not_affect_sibling_directories(make_repo: MakeRepo) -> None:
    root = make_repo({"a/.gitignore": "*.ts\n", "a/x.ts": CODE, "b/y.ts": CODE})

    assert discovered(root) == ["b/y.ts"]


def test_files_inside_an_ignored_directory_cannot_be_re_included(make_repo: MakeRepo) -> None:
    # Git's rule: once a directory is excluded, nothing inside it is looked at.
    root = make_repo({".gitignore": "vendor/\n!vendor/keep.ts\n", "vendor/keep.ts": CODE})

    assert discovered(root) == []


def test_gitignore_cannot_re_include_default_exclusions(make_repo: MakeRepo) -> None:
    root = make_repo({".gitignore": "!node_modules/\n", "node_modules/lib/x.js": CODE})

    assert discovered(root) == []


def test_non_utf8_gitignore_does_not_crash(make_repo: MakeRepo) -> None:
    root = make_repo({".gitignore": "# caf\xe9\n*.gen.ts\n".encode("latin-1"), "a.gen.ts": CODE})

    assert discovered(root) == []


def test_user_exclude_globs_use_gitignore_syntax(make_repo: MakeRepo) -> None:
    root = make_repo({"src/app.ts": CODE, "src/app.spec.ts": CODE, "test/fixtures/sample.ts": CODE})
    config = IndexConfig(exclude_globs=("*.spec.ts", "fixtures/"))

    assert discovered(root, config) == ["src/app.ts"]


# --- 3.4: file cap ---------------------------------------------------------------------


def test_file_cap_keeps_the_first_files_in_sorted_order_and_records_the_rest(
    make_repo: MakeRepo,
) -> None:
    root = make_repo({"c.ts": CODE, "a.ts": CODE, "b.ts": CODE})

    result = discover(root, IndexConfig(max_files=2))

    assert result.files == ("a.ts", "b.ts")  # sorted first, so the cut is deterministic
    assert result.skipped == (SkippedFile("c.ts", SkipReason.FILE_CAP),)


def test_file_cap_counts_only_supported_files(make_repo: MakeRepo) -> None:
    root = make_repo({"a.ts": CODE, "notes.md": "x", "node_modules/x.js": CODE})

    assert discover(root, IndexConfig(max_files=1)).skipped == ()
