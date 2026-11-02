import pytest

from codesense.chunking.symbols import Symbol, extract_symbols, parse
from codesense.models import SymbolKind

FUNCTION, METHOD, CLASS = SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CLASS
ALL_LANGUAGES = pytest.mark.parametrize("language", ["typescript", "tsx", "javascript"])
TS_LANGUAGES = pytest.mark.parametrize("language", ["typescript", "tsx"])


def symbols(code: str, language: str) -> list[Symbol]:
    return extract_symbols(parse(code, language))


# --- 4.2: parsing ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("language", "code"),
    [
        ("typescript", "function add(a: number, b: number): number { return a + b; }\n"),
        ("tsx", "const App = (p: Props) => <div>{p.title}</div>;\n"),
        ("javascript", "const App = () => <div>hi</div>;\n"),  # .jsx uses this grammar
    ],
)
def test_each_language_parses_its_own_syntax(language: str, code: str) -> None:
    root = parse(code, language).root_node

    assert root.type == "program"
    assert not root.has_error


def test_angle_bracket_cast_is_why_tsx_has_its_own_grammar() -> None:
    assert not parse("const a = <T>x;\n", "typescript").root_node.has_error
    assert parse("const a = <T>x;\n", "tsx").root_node.has_error  # read as a JSX element


def test_broken_code_still_parses_into_a_tree() -> None:
    # Error recovery: editors parse half-typed code all the time.
    tree = parse("function ok() {}\nfunction broken( {\n", "typescript")

    assert tree.root_node.has_error
    assert symbols("function ok() {}\nfunction broken( {\n", "typescript")[0].name == "ok"


# --- 4.3: functions --------------------------------------------------------------------


@ALL_LANGUAGES
def test_function_declaration(language: str) -> None:
    code = "function add(a, b) {\n  return a + b;\n}\n"

    assert symbols(code, language) == [Symbol("add", FUNCTION, 1, 3)]


@ALL_LANGUAGES
@pytest.mark.parametrize(
    ("code", "name"),
    [
        ("function* ids() {}\n", "ids"),
        ("const fetchUser = async (id) => {\n  return id;\n};\n", "fetchUser"),
        ("let handler = function () {};\n", "handler"),
        ("var legacy = function named() {};\n", "legacy"),  # the variable is what callers use
        ("const gen = function* () {};\n", "gen"),
    ],
)
def test_functions_bound_to_a_name(language: str, code: str, name: str) -> None:
    assert [s.name for s in symbols(code, language)] == [name]
    assert symbols(code, language)[0].kind == FUNCTION


@ALL_LANGUAGES
def test_export_keyword_is_part_of_the_symbol(language: str) -> None:
    code = "export function a() {}\n\nexport const b = () => {\n  return 1;\n};\n"

    assert symbols(code, language) == [Symbol("a", FUNCTION, 1, 1), Symbol("b", FUNCTION, 3, 5)]


@ALL_LANGUAGES
@pytest.mark.parametrize(
    "code",
    [
        "export default function () {}\n",
        "export default async function* () {}\n",
        "export default () => 1;\n",
    ],
)
def test_anonymous_default_export_is_named_default(language: str, code: str) -> None:
    assert symbols(code, language) == [Symbol("default", FUNCTION, 1, 1)]


@ALL_LANGUAGES
@pytest.mark.parametrize(
    "code",
    [
        "const x = 1;\n",
        "const a = () => 1, b = () => 2;\n",  # several declarators: left to gap windows
        "const { a, b } = obj;\n",
        "module.exports.legacy = function () {};\n",  # CommonJS: left to gap windows
        "export { a, b };\n",
        "import { db } from './db';\n",
        "const api = { get() {} };\n",  # object-literal methods: left to gap windows
    ],
)
def test_non_symbols_are_ignored(language: str, code: str) -> None:
    assert symbols(code, language) == []


@ALL_LANGUAGES
def test_nested_functions_stay_inside_their_parent(language: str) -> None:
    code = "function outer() {\n  function inner() {}\n  const f = () => 1;\n}\n"

    assert symbols(code, language) == [Symbol("outer", FUNCTION, 1, 4)]


@TS_LANGUAGES
def test_typescript_declarations_without_code_are_ignored(language: str) -> None:
    code = "interface User { id: string }\ntype Id = string;\nenum Color { Red }\n"

    assert symbols(code, language) == []


# --- 4.3: doc comments (D3) -------------------------------------------------------------


@ALL_LANGUAGES
def test_doc_comment_directly_above_is_included(language: str) -> None:
    code = "/**\n * Adds two numbers.\n */\nfunction add(a, b) {}\n"

    assert symbols(code, language) == [Symbol("add", FUNCTION, 1, 4)]


@ALL_LANGUAGES
def test_consecutive_line_comments_are_included(language: str) -> None:
    code = "// Adds numbers.\n// Pure.\nexport function add(a, b) {}\n"

    assert symbols(code, language) == [Symbol("add", FUNCTION, 1, 3)]


@ALL_LANGUAGES
def test_blank_line_detaches_a_comment(language: str) -> None:
    code = "// Section: math helpers\n\nfunction add(a, b) {}\n"

    assert symbols(code, language) == [Symbol("add", FUNCTION, 3, 3)]


@ALL_LANGUAGES
def test_trailing_comment_of_the_previous_line_is_not_a_doc_comment(language: str) -> None:
    code = "setup(); // configure\nfunction add(a, b) {}\n"

    assert symbols(code, language) == [Symbol("add", FUNCTION, 2, 2)]


# --- 4.3: classes: header + methods (D1), qualified names (D4) --------------------------

CLASS_CODE = """\
/** Caches users. */
export class UserService extends Base {
  cache = new Map();

  /** Finds a user. */
  async getUser(id) {
    return this.cache.get(id);
  }

  get size() {
    return 1;
  }
  handler = () => {
    return 2;
  };
  static #secret() {}
  [Symbol.iterator]() {}
}
"""


@ALL_LANGUAGES
def test_class_is_split_into_header_and_methods(language: str) -> None:
    assert symbols(CLASS_CODE, language) == [
        Symbol("UserService", CLASS, 1, 4),  # header: up to the first method's doc comment
        Symbol("UserService.getUser", METHOD, 5, 8),
        Symbol("UserService.size", METHOD, 10, 12),
        Symbol("UserService.handler", METHOD, 13, 15),  # arrow-function field
        Symbol("UserService.#secret", METHOD, 16, 16),
        Symbol("UserService.[Symbol.iterator]", METHOD, 17, 17),
    ]


@ALL_LANGUAGES
def test_class_without_methods_is_one_chunk(language: str) -> None:
    code = "class Point {\n  x = 0;\n  y = 0;\n}\n"

    assert symbols(code, language) == [Symbol("Point", CLASS, 1, 4)]


@ALL_LANGUAGES
def test_one_line_class_is_one_chunk(language: str) -> None:
    # A method on the class's first line leaves no room for a header.
    assert symbols("class A { m() {} }\n", language) == [Symbol("A", CLASS, 1, 1)]


@ALL_LANGUAGES
def test_anonymous_default_class(language: str) -> None:
    code = "export default class {\n  run() {}\n}\n"

    assert symbols(code, language) == [
        Symbol("default", CLASS, 1, 1),
        Symbol("default.run", METHOD, 2, 2),
    ]


@TS_LANGUAGES
def test_abstract_class_skips_bodiless_signatures(language: str) -> None:
    code = "abstract class Job {\n  abstract run(): void;\n  start() {}\n}\n"

    assert symbols(code, language) == [
        Symbol("Job", CLASS, 1, 2),
        Symbol("Job.start", METHOD, 3, 3),
    ]
