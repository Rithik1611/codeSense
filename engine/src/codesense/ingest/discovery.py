"""Find the source files worth indexing without reading their contents.

Excluded directories are pruned before the walk enters them: never looking inside
``node_modules`` is what keeps discovery fast. Paths are repository-relative POSIX
strings, returned sorted so results are deterministic on every OS.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from pathspec import GitIgnoreSpec

from codesense.config import IndexConfig
from codesense.errors import IngestError
from codesense.ingest.languages import language_for
from codesense.models import SkippedFile, SkipReason

logger = logging.getLogger(__name__)

# Gitignore syntax: "name/" matches a directory of that name at any depth.
DEFAULT_EXCLUDES = (
    "node_modules/",
    ".git/",
    "dist/",
    "build/",
    "out/",
    "coverage/",
    "*.min.js",  # minified: one huge line, no meaningful structure
    "*.d.ts",  # declarations only: no implementation to search
)


type _Chain = tuple[tuple[str, GitIgnoreSpec], ...]  # (directory prefix, its .gitignore)


@dataclass(frozen=True, slots=True)
class Discovery:
    files: tuple[str, ...]
    skipped: tuple[SkippedFile, ...]


def discover(root: Path, config: IndexConfig) -> Discovery:
    if not root.is_dir():
        raise IngestError(f"cannot index {root}: not a directory")

    # Defaults and user globs are anchored at the root and cannot be re-included by a .gitignore.
    excludes = GitIgnoreSpec.from_lines((*DEFAULT_EXCLUDES, *config.exclude_globs))
    # The .gitignore files that apply inside each directory, root first; filled in by its parent.
    chains: dict[str, _Chain] = {"": ()}
    files: list[str] = []
    skipped: list[SkippedFile] = []

    # followlinks=False (the default): symlinked directories are listed but never entered.
    for dirpath, dirnames, filenames in os.walk(root, onerror=_log_walk_error):
        relative_dir = Path(dirpath).relative_to(root).as_posix()
        prefix = "" if relative_dir == "." else f"{relative_dir}/"
        chain = chains.pop(prefix)
        # shortcut: only .gitignore files are read, not .git/info/exclude or the user's global
        # excludes file; add them if indexed results show files the user expected to be ignored.
        if ".gitignore" in filenames:
            chain = (*chain, (prefix, _read_gitignore(Path(dirpath, ".gitignore"))))

        # Assigning to dirnames[:] in place is how os.walk is told not to descend.
        dirnames[:] = [
            name for name in dirnames if not _is_ignored(f"{prefix}{name}/", excludes, chain)
        ]
        for name in dirnames:
            chains[f"{prefix}{name}/"] = chain

        for name in filenames:
            path = prefix + name
            if language_for(path) is None or _is_ignored(path, excludes, chain):
                continue
            if Path(dirpath, name).is_symlink():
                skipped.append(SkippedFile(path, SkipReason.SYMLINK))
            else:
                files.append(path)

    files.sort()  # before the cap, so the same files are kept on every run and OS
    if len(files) > config.max_files:
        logger.warning("found %d files; indexing the first %d", len(files), config.max_files)
        skipped += [SkippedFile(path, SkipReason.FILE_CAP) for path in files[config.max_files :]]
        del files[config.max_files :]

    return Discovery(tuple(files), tuple(sorted(skipped, key=lambda s: s.path)))


def _is_ignored(path: str, excludes: GitIgnoreSpec, chain: _Chain) -> bool:
    """Directories are passed with a trailing "/" so patterns like ``build/`` match them.

    Each .gitignore applies relative to its own directory and the deepest decision wins.
    ``include`` is True (ignored), False (re-included by ``!``) or None (no pattern matched).
    """
    if excludes.match_file(path):
        return True
    ignored = False
    for base, spec in chain:
        include = spec.check_file(path.removeprefix(base)).include
        if include is not None:
            ignored = include
    return ignored


def _read_gitignore(path: Path) -> GitIgnoreSpec:
    try:
        # errors="replace": a stray non-UTF-8 comment must not break the whole file.
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as error:
        logger.warning("cannot read %s: %s", path, error.strerror)
        lines = []
    return GitIgnoreSpec.from_lines(lines)


def _log_walk_error(error: OSError) -> None:
    # A directory we cannot list is skipped, not fatal; os.walk would otherwise hide it.
    logger.warning("cannot read directory %s: %s", error.filename, error.strerror)
