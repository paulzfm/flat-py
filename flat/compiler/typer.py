from flat.compiler import predef
from flat.compiler.printer import pretty_tree
from flat.compiler.trees import *

NormalForm = SimpleType | RefinementType


class Scope:
    def __init__(self, parent: Optional = None):
        self.parent: Optional[Scope] = parent
        self._terms: dict[str, NormalForm] = {}
        self._types: dict[str, NormalForm] = {}

    def lookup_term(self, name: str) -> Optional[NormalForm]:
        if name in self._terms:
            return self._terms[name]
        if self.parent:
            return self.parent.lookup_term(name)

    def lookup_type(self, name: str) -> Optional[NormalForm]:
        if name in self._types:
            return self._types[name]
        if self.parent:
            return self.parent.lookup_type(name)

    def has_defined(self, name: str) -> bool:
        return name in self._terms or name in self._types

    def update_term(self, name: str, typ: NormalForm) -> None:
        self._terms[name] = typ

    def update_type(self, name: str, typ: NormalForm) -> None:
        self._types[name] = typ


def get_base_type(nf: NormalForm) -> SimpleType:
    match nf:
        case SimpleType() as simple:
            return simple
        case RefinementType(base, _):
            assert isinstance(base, SimpleType)
            return base


def normalize(annot: Type, scope: Scope) -> NormalForm:
    """Expand a type (may not be simple) into normal form."""
    match annot:
        case SimpleType() as simple:
            return simple
        case NamedType(x):
            return scope.lookup_type(x)
        case RefinementType(b1, r1) as rt:
            match normalize(b1, scope):
                case SimpleType():
                    return rt
                case RefinementType(b, r2):
                    return RefinementType(b, apply('&&', r1, r2))


def expand(annot: Type, scope: Scope) -> SimpleType:
    """Expand a type into simple type."""
    match annot:
        case SimpleType() as simple:
            return simple
        case NamedType(x):
            match scope.lookup_type(x):
                case SimpleType() as simple:
                    return simple
                case _:
                    raise TypeError
        case _:
            raise TypeError


def infer(expr: Expr, scope: Scope) -> SimpleType:
    match expr:
        case Literal(value):
            match value:
                case int():
                    return IntType()
                case bool():
                    return BoolType()
                case str():
                    return StringType()
        case Var(name):
            match scope.lookup_term(name):
                case None:
                    match predef.typ(name):
                        case None:
                            raise TypeError(f'undefined name: {name}')
                        case t:
                            return t
                case nf:
                    return get_base_type(nf)
        case App(fun, args):
            match infer(fun, scope):
                case FunType(arg_types, return_type):
                    if len(arg_types) != len(args):
                        raise TypeError
                    for te, e in zip(arg_types, args):
                        ensure(e, te, scope)
                    return return_type
                case other:
                    raise TypeError(f'expect fun type, but found {pretty_tree(other)}')
        case InLang(receiver, lang_name):
            ensure(receiver, StringType(), scope)
            ensure_lang(lang_name, scope)
        case Select(receiver, select_all, lang_name, absolute_path, path):
            ensure(receiver, StringType(), scope)
            ensure_lang(lang_name, scope)
            # TODO: check path
            return ListType(StringType()) if select_all else StringType()
        case IfThenElse(cond, then_branch, else_branch):
            ensure(cond, BoolType(), scope)
            t = infer(then_branch, scope)
            ensure(else_branch, t, scope)
            return t
        case other:
            raise TypeError(f'cannot infer type for: {pretty_tree(other)}')


def ensure(expr: Expr, expected: SimpleType, scope: Scope) -> None:
    match expr:
        case Lambda(params, body):
            match expected:
                case FunType(arg_types, return_type):
                    formal_scope = Scope(scope)
                    for x, t in zip(params, arg_types):
                        if formal_scope.has_defined(x):
                            raise TypeError(f'redefined lambda param {x}')
                        formal_scope.update_term(x, t)
                    ensure(body, return_type, formal_scope)
                case _:
                    raise TypeError(f'lambda expression cannot have non-function type')
        case IfThenElse(cond, then_branch, else_branch):
            ensure(cond, BoolType(), scope)
            ensure(then_branch, expected, scope)
            ensure(else_branch, expected, scope)
        case other:  # fall back to infer mode
            actual = infer(other, scope)
            if is_subtype(actual, expected):
                pass
            else:
                raise TypeError(f'expect {pretty_tree(expected)}, but found {pretty_tree(actual)}')


def is_subtype(lower: SimpleType, upper: SimpleType) -> bool:
    if lower == upper:
        return True

    match lower, upper:
        case (_, TopType()):
            return True
        case (ListType(t1), ListType(t2)):
            return is_subtype(t1, t2)
        case (FunType(ts1, t1), FunType(ts2, t2)) if len(ts1) == len(ts2):
            return is_subtype(t1, t2) and all([is_subtype(y, x) for x, y in zip(ts1, ts2)])
        case _:
            return False


def ensure_lang(name: str, scope) -> None:
    match scope.lookup_type(name):
        case None:
            raise TypeError(f'undefined name {name}')
        case RefinementType(StringType(), _):
            pass
        case other:
            raise TypeError(f'expect lang, but found {pretty_tree(other)}')
