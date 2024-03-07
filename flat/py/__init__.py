import ast
from typing import Any, Callable, Optional, Generator

import flat.parser
from flat.grammars import GrammarBuilder, Grammar
from flat.parser import parse_using
from flat.types import LangType, RefinementType, Cond, BuiltinType, Value


class LangBuilder(GrammarBuilder):
    def lookup_lang(self, name: str) -> Optional[Grammar]:
        try:
            value = eval(name)
        except NameError:
            return None

        match value:
            case LangType(g):
                return g
            case _:
                return None


def lang(name: str, rules: str) -> LangType:
    builder = LangBuilder()
    grammar = builder(name, parse_using(flat.parser.rules, rules, '<file>', (1, 1)))
    return LangType(grammar)


class PyCond(Cond):
    expr: ast.expr

    def __init__(self, code: str):
        match ast.parse(code).body[0]:
            case ast.Expr(expr):
                self.expr = expr
            case _:
                raise TypeError

    def __and__(self, other):
        if isinstance(other, PyCond):
            return PyCond(ast.And([self.expr, other.expr]))
        raise TypeError

    def apply(self, value: Value) -> bool:
        match eval(ast.unparse(self.expr), globals(), {'_': value}):
            case bool() as b:
                return b
            case _:
                raise TypeError


def refine(base_type: type | LangType | RefinementType, refinement: str) -> RefinementType:
    cond = PyCond(refinement)
    match base_type:
        case type() as ty if ty in [int, bool, str]:
            return RefinementType(
                BuiltinType.Int if ty == int else BuiltinType.Bool if ty == bool else BuiltinType.String, cond)
        case LangType() as t:
            return RefinementType(t, cond)
        case RefinementType(base, base_cond):
            new_cond = cond if base_cond is None else (base_cond and cond)
            return RefinementType(base, new_cond)
        case _:
            raise TypeError

    # from inspect import signature
    # sig = signature(refinement)
    # assert len(sig.parameters.keys()) == 1


def requires(condition: Any):
    def decorate(func):
        def decorated(*args, **kwargs):
            return func(*args, **kwargs)  # identity

        return decorated

    return decorate


def ensures(condition: Any):
    def decorate(func):
        def decorated(*args, **kwargs):
            return func(*args, **kwargs)  # identity

        return decorated

    return decorate


def returns(value: Any):
    def decorate(func):
        def decorated(*args, **kwargs):
            return func(*args, **kwargs)  # identity

        return decorated

    return decorate


def fuzz(target: Callable, times: int,
         using: Optional[dict[str, Generator[Any, None, None]]] = None) -> None:
    raise NotImplementedError
