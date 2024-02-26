import ast
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, Tuple, Generator, TypeVar

from flat.compiler.grammar import LangObject
from flat.compiler.issuer import Issuer
from flat.compiler.lang_validator import LangValidator
from flat.compiler.parser import Parser
from flat.compiler.trees import LangDef
from flat.xpath import XPath, xpath_parser


class PyLangValidator(LangValidator):
    def lookup_lang(self, name: str) -> Optional[LangObject]:
        try:
            value = eval(name)
        except NameError:
            return None

        match value:
            case LangObject() as obj:
                return obj
            case _:
                return None


class BaseType(Enum):
    Int = 0
    Bool = 1
    String = 2
    Lang = 3


@dataclass(frozen=True)
class TypeNorm:
    base: BaseType
    cond: Optional[ast.expr] = None
    lang_object: Optional[LangObject] = None  # if base == Lang, this is the tree for the LangType


def lang(name: str, grammar_rules: str) -> TypeNorm:
    source = 'lang ' + name + ' {' + grammar_rules + '}\n'
    issuer = Issuer(source.splitlines())
    parser = Parser(issuer)
    [tree] = parser.parse()
    if issuer.has_errors():
        issuer.print()
        sys.exit(1)
    assert isinstance(tree, LangDef)
    obj = PyLangValidator(issuer).validate(tree.ident, tree.rules)
    if issuer.has_errors():
        issuer.print()
        sys.exit(1)
    return TypeNorm(BaseType.Lang, None, obj)


def parse_expr(code: str) -> ast.expr:
    match ast.parse(code).body[0]:
        case ast.Expr(expr):
            return expr
        case _:
            raise TypeError


def refine(base_type: type | LangObject | TypeNorm, refinement: str) -> TypeNorm:
    cond = parse_expr(refinement)
    match base_type:
        case type() as ty if ty in [int, bool, str]:
            return TypeNorm(BaseType.Int if ty == int else BaseType.Bool if ty == bool else BaseType.String, cond)
        case LangObject() as obj:
            return TypeNorm(BaseType.Lang, cond, obj)
        case TypeNorm(base, base_cond, obj):
            new_cond = cond if base_cond is None else ast.BoolOp(ast.And(), [base_cond, cond])
            return TypeNorm(base, new_cond, obj)
        case _:
            raise TypeError

    # from inspect import signature
    # sig = signature(refinement)
    # assert len(sig.parameters.keys()) == 1


def requires(condition: Any):
    def decorate(func):
        def decorated(*args, **kwargs):
            func(*args, **kwargs)  # identity

        return decorated

    return decorate


def ensures(condition: Any):
    def decorate(func):
        def decorated(*args, **kwargs):
            func(*args, **kwargs)  # identity

        return decorated

    return decorate


def fuzz(target: Callable, times: int,
         using_producers: Optional[dict[str, Generator[Any, None, None]]] = None) -> None:
    raise NotImplementedError


# builtin functions for writing spec
T = TypeVar('T')


def forall(f: Callable[[T], bool], xs: list[T]) -> bool:
    return all(f(x) for x in xs)


def exists(f: Callable[[T], bool], xs: list[T]) -> bool:
    return any(f(x) for x in xs)


def first(xs: list[T]) -> T:
    return xs[0]


def last(xs: list[T]) -> T:
    return xs[-1]


def xpath(path: str) -> XPath:
    return xpath_parser.parse(path)


#
#
# @dataclass
# class XPathSymbol:
#     name: str
#     index: Optional[int] = None

#
# @dataclass
# class XPath:
#     start: XPathSymbol
#     steps: list[Tuple[bool, XPathSymbol]]  # True for 'x.y'; False for 'x..y'
#
#     @property
#     def edges(self) -> list[Tuple[XPathSymbol, bool, XPathSymbol]]:
#         es = []
#         if self.start.name != 'start':
#             es.append((XPathSymbol('start'), False, self.start))
#
#         a = self.start
#         for op, b in self.steps:
#             es.append((a, op, b))
#             a = b
#         assert len(es) > 0
#         return es

def parse_xpath(p: str) -> Tuple[bool, list[str]]:
    if p.startswith('.'):
        is_abs = True
        path = p[1:].split('.')
    else:
        is_abs = False
        path = p.split('.')

    return is_abs, path


def select(lang_type: TypeNorm, path: XPath, word: str) -> str:
    assert lang_type.base == BaseType.Lang
    assert lang_type.lang_object is not None
    return lang_type.lang_object.select_unique(word, path)


def select_all(lang_type: TypeNorm, path: XPath, word: str) -> list[str]:
    assert lang_type.base == BaseType.Lang
    assert lang_type.lang_object is not None
    return lang_type.lang_object.select_all(word, path)
