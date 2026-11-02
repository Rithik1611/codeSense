"""Parse source with tree-sitter and find the functions, classes and methods worth a chunk.

Only top-level declarations and class members are symbols. Everything else (nested
functions, interfaces, object-literal methods, CommonJS exports) stays inside its parent
or is covered by gap windows in the chunker.

Line numbers are 1-based here; tree-sitter rows are 0-based. Rows are used instead of
byte offsets because tree-sitter counts UTF-8 bytes while Python indexes characters.
"""

from dataclasses import dataclass

import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser, Tree

from codesense.models import SymbolKind

_GRAMMARS = {
    "typescript": Language(tree_sitter_typescript.language_typescript()),
    "tsx": Language(tree_sitter_typescript.language_tsx()),
    "javascript": Language(tree_sitter_javascript.language()),  # also parses JSX
}

_FUNCTION_DECLARATIONS = {"function_declaration", "generator_function_declaration"}
_FUNCTION_VALUES = {"arrow_function", "function_expression", "function", "generator_function"}
_CLASSES = {"class_declaration", "abstract_class_declaration", "class"}
_VARIABLES = {"lexical_declaration", "variable_declaration"}  # const/let, var
_FIELDS = {"public_field_definition", "field_definition"}  # TypeScript, JavaScript


@dataclass(frozen=True, slots=True)
class Symbol:
    name: str
    kind: SymbolKind
    start_line: int  # 1-based, inclusive; includes the doc comment above
    end_line: int


def parse(text: str, language: str) -> Tree:
    """Always returns a tree: syntax errors become ERROR nodes, the rest still parses."""
    return Parser(_GRAMMARS[language]).parse(text.encode("utf-8"))


def extract_symbols(tree: Tree) -> list[Symbol]:
    symbols: list[Symbol] = []
    for statement in tree.root_node.named_children:
        symbols += _statement_symbols(statement)
    return symbols


def _statement_symbols(statement: Node) -> list[Symbol]:
    # The statement gives the line range (so `export` and doc comments are included);
    # the declaration inside it decides what kind of symbol it is.
    node: Node | None = statement
    if statement.type == "export_statement":
        # `export function f` uses the declaration field, `export default <expr>` the value field.
        node = statement.child_by_field_name("declaration") or statement.child_by_field_name(
            "value"
        )
    if node is None:  # `export { a, b }`
        return []

    start, end = _first_line(statement), statement.end_point.row + 1
    if node.type in _FUNCTION_DECLARATIONS or node.type in _FUNCTION_VALUES:
        return [Symbol(_name(node), SymbolKind.FUNCTION, start, end)]
    if node.type in _CLASSES:
        return _class_symbols(node, _name(node), start, end)
    if node.type in _VARIABLES:
        declarators = [
            child for child in node.named_children if child.type == "variable_declarator"
        ]
        if len(declarators) == 1:  # `const a = () => 1, b = 2` is left to gap windows
            target = declarators[0].child_by_field_name("name")
            if (
                target is not None
                and target.type == "identifier"
                and _is_function(declarators[0].child_by_field_name("value"))
            ):
                return [Symbol(_text(target), SymbolKind.FUNCTION, start, end)]
    return []


def _class_symbols(node: Node, name: str, start: int, end: int) -> list[Symbol]:
    """A header chunk (doc comment, extends, fields) plus one chunk per method: no line twice."""
    body = node.child_by_field_name("body")
    members = body.named_children if body is not None else []
    methods = [method for member in members if (method := _method(member, name)) is not None]
    if not methods or methods[0].start_line <= start:  # no methods, or `class A { m() {} }`
        return [Symbol(name, SymbolKind.CLASS, start, end)]
    return [Symbol(name, SymbolKind.CLASS, start, methods[0].start_line - 1), *methods]


def _method(member: Node, class_name: str) -> Symbol | None:
    is_method = member.type == "method_definition" or (
        member.type in _FIELDS and _is_function(member.child_by_field_name("value"))
    )
    key = member.child_by_field_name("name") or member.child_by_field_name("property")
    if not is_method or key is None:  # fields, abstract signatures, comments
        return None
    return Symbol(
        f"{class_name}.{_text(key)}",
        SymbolKind.METHOD,
        _first_line(member),
        member.end_point.row + 1,
    )


def _first_line(node: Node) -> int:
    """Extend upward over comments directly above: a doc comment describes the code below it."""
    row = node.start_point.row
    comment = node.prev_sibling
    while (
        comment is not None
        and comment.type == "comment"
        and comment.end_point.row == row - 1  # a blank line in between detaches it
        and _starts_its_own_line(comment)  # not `setup(); // note` on the line above
    ):
        row = comment.start_point.row
        comment = comment.prev_sibling
    return row + 1


def _starts_its_own_line(comment: Node) -> bool:
    before = comment.prev_sibling
    return before is None or before.end_point.row < comment.start_point.row


def _is_function(node: Node | None) -> bool:
    return node is not None and node.type in _FUNCTION_VALUES


def _name(node: Node) -> str:
    name = node.child_by_field_name("name")
    return _text(name) if name is not None else "default"  # `export default function () {}`


def _text(node: Node) -> str:
    return (node.text or b"").decode("utf-8")
