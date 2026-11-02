"""Print the tree-sitter syntax tree of a source file, to see what the chunker sees.

Usage (from engine/):  uv run python scripts/ast_dump.py path/to/file.ts
"""

import sys
from pathlib import Path

from tree_sitter import Node

from codesense.chunking.symbols import parse
from codesense.ingest.languages import language_for


def dump(node: Node, depth: int = 0) -> None:
    name = node.child_by_field_name("name")
    label = f"  name={(name.text or b'').decode()}" if name is not None else ""
    lines = f"[{node.start_point.row + 1}-{node.end_point.row + 1}]"  # 1-based, like the editor
    print(f"{'  ' * depth}{node.type} {lines}{label}")
    for child in node.named_children:
        dump(child, depth + 1)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = Path(sys.argv[1])
    language = language_for(path.as_posix())
    if language is None:
        sys.exit(f"unsupported file type: {path}")
    dump(parse(path.read_text(encoding="utf-8"), language).root_node)


if __name__ == "__main__":
    main()
