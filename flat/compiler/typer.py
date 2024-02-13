from flat.compiler import predef
from flat.compiler.grammar import LangObject
from flat.compiler.printer import pretty_tree
from flat.compiler.trees import *

NormalForm = SimpleType | RefinementType


class Scope:
    def __init__(self, parent: Optional = None):
        self.parent: Optional[Scope] = parent
        self._items: dict[str, NormalForm] = {}

    def lookup(self, name: str) -> Optional[NormalForm]:
        if name in self._items:
            return self._items[name]
        if self.parent:
            return self.parent.lookup(name)

    def has_defined(self, name: str) -> bool:
        return name in self._items

    def update(self, name: str, typ: NormalForm) -> None:
        self._items[name] = typ


def get_base_type(nf: NormalForm) -> SimpleType:
    match nf:
        case SimpleType() as simple:
            return simple
        case RefinementType(base, _):
            assert isinstance(base, SimpleType)
            return base


class Typer:
    def __init__(self):
        self._languages: dict[str, LangObject] = {}
        self._type_aliases: dict[str, NormalForm] = {}

    def define_lang(self, ident: Ident, rules: list[Rule]) -> None:
        defined = set(rule.name for rule in rules)
        if 'start' not in defined:
            raise TypeError('no start rule')

        defined = frozenset(defined - {'start'})
        used: set[str] = set()

        def check(clause: Clause) -> None:
            match clause:
                case CharSet(lhs, rhs) as cs:
                    if cs.begin > cs.end:
                        raise TypeError(f"invalid charset: '{lhs.value}' must not greater than '{rhs.value}'")
                case Symbol('start'):
                    raise TypeError('cannot use start rule')
                case Symbol(name):
                    if name in defined:
                        used.add(name)
                    elif name not in self._languages:
                        raise TypeError(f'undefined rule {name}')
                case Rep(clause, rep_range):
                    check(clause)
                    match rep_range:
                        case RepExactly(0):
                            raise TypeError
                        case RepExactly(1):
                            raise TypeError
                        case RepInRange(k1, k2) if k1 >= k2:
                            raise TypeError(f'invalid rep: {k1} must be less than {k2}')
                case Seq(clauses):
                    for clause in clauses:
                        check(clause)
                case Alt(clauses):
                    for clause in clauses:
                        check(clause)

        for rule in rules:
            check(rule.body)

        for unused in defined - used:
            raise TypeError(f'unused rule {unused}')

        self._languages[ident.name] = LangObject(ident.name, rules)
        assert ident.name not in self._type_aliases
        self._type_aliases[ident.name] = RefinementType(StringType(), InLang(Var('_'), ident))

    def define_type_alias(self, ident: Ident, nf: NormalForm) -> None:
        assert ident.name not in self._type_aliases
        self._type_aliases[ident.name] = nf

    def normalize(self, annot: Type) -> NormalForm:
        """Expand a type (may not be simple) into normal form."""
        match annot:
            case SimpleType() as simple:
                return simple
            case NamedType(x):
                return self._type_aliases[x]
            case RefinementType(b1, r1) as rt:
                match self.normalize(b1):
                    case SimpleType():
                        return rt
                    case RefinementType(b, r2):
                        return RefinementType(b, apply('&&', r1, r2))

    def expand(self, annot: Type) -> SimpleType:
        """Expand a type into simple type."""
        match annot:
            case SimpleType() as simple:
                return simple
            case NamedType(x):
                match self._type_aliases[x]:
                    case SimpleType() as simple:
                        return simple
                    case _:
                        raise TypeError
            case _:
                raise TypeError

    def infer(self, expr: Expr, scope: Scope) -> SimpleType:
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
                match scope.lookup(name):
                    case None:
                        match predef.typ(name):
                            case None:
                                raise TypeError(f'undefined name: {name}')
                            case t:
                                return t
                    case nf:
                        return get_base_type(nf)
            case App(fun, args):
                match self.infer(fun, scope):
                    case FunType(arg_types, return_type):
                        if len(arg_types) != len(args):
                            raise TypeError
                        for te, e in zip(arg_types, args):
                            self.ensure(e, te, scope)
                        return return_type
                    case other:
                        raise TypeError(f'expect fun type, but found {pretty_tree(other)}')
            case InLang(receiver, lang):
                self.ensure(receiver, StringType(), scope)
                self.ensure_lang(lang)
            case Select(receiver, select_all, lang, absolute_path, path):
                self.ensure(receiver, StringType(), scope)
                self.ensure_lang(lang)
                self.ensure_valid_path(lang.name, path, absolute_path, not select_all)
                return ListType(StringType()) if select_all else StringType()
            case IfThenElse(cond, then_branch, else_branch):
                self.ensure(cond, BoolType(), scope)
                t = self.infer(then_branch, scope)
                self.ensure(else_branch, t, scope)
                return t
            case other:
                raise TypeError(f'cannot infer type for: {pretty_tree(other)}')

    def ensure(self, expr: Expr, expected: SimpleType, scope: Scope) -> None:
        match expr:
            case Lambda(params, body):
                match expected:
                    case FunType(arg_types, return_type):
                        formal_scope = Scope(scope)
                        for param, t in zip(params, arg_types):
                            if formal_scope.has_defined(param.name):
                                raise TypeError(f'redefined lambda param {param}')
                            formal_scope.update(param.name, t)
                        self.ensure(body, return_type, formal_scope)
                    case _:
                        raise TypeError(f'lambda expression cannot have non-function type')
            case IfThenElse(cond, then_branch, else_branch):
                self.ensure(cond, BoolType(), scope)
                self.ensure(then_branch, expected, scope)
                self.ensure(else_branch, expected, scope)
            case other:  # fall back to infer mode
                actual = self.infer(other, scope)
                if self.is_subtype(actual, expected):
                    pass
                else:
                    raise TypeError(f'expect {pretty_tree(expected)}, but found {pretty_tree(actual)}')

    def is_subtype(self, lower: SimpleType, upper: SimpleType) -> bool:
        if lower == upper:
            return True

        match lower, upper:
            case (_, TopType()):
                return True
            case (ListType(t1), ListType(t2)):
                return self.is_subtype(t1, t2)
            case (FunType(ts1, t1), FunType(ts2, t2)) if len(ts1) == len(ts2):
                return self.is_subtype(t1, t2) and all([self.is_subtype(y, x) for x, y in zip(ts1, ts2)])
            case _:
                return False

    def ensure_lang(self, ident: Ident) -> None:
        if ident.name not in self._languages:
            raise TypeError(f'undefined lang {ident.name}')

    def ensure_valid_path(self, lang_name: str, path: list[Ident], is_abs: bool, require_unique: bool) -> None:
        lang = self._languages[lang_name]

        for symbol in path:
            if symbol.name not in lang.defined_symbols:
                raise TypeError

        if is_abs:
            last_symbol = Ident('start')
            symbols = path
        else:
            last_symbol = path[0]
            symbols = path[1:]
            match lang.count(last_symbol.name, 'start', False):
                case 0:
                    raise TypeError(f'unreachable symbol {last_symbol}')
                case 2 if require_unique:
                    raise TypeError(f'path not unique, as there may exist multiple node labelled with {last_symbol}')

        for symbol in symbols:
            match lang.count(symbol.name, last_symbol.name, True):
                case 0:
                    raise TypeError(f'unreachable symbol {symbol}')
                case 2 if require_unique:
                    raise TypeError(f'path not unique, as there may exist multiple node labelled with {symbol}')
            last_symbol = symbol
