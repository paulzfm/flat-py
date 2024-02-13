from flat.compiler import predef
from flat.compiler.errors import *
from flat.compiler.grammar import LangObject
from flat.compiler.issuer import Issuer
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

    def __getitem__(self, name: str) -> NormalForm:
        return self._items[name]

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
    def __init__(self, issuer: Issuer):
        self.issuer = issuer
        self.langs: dict[str, LangObject] = {}
        self._type_aliases: dict[str, NormalForm] = {}

    def normalize(self, annot: Type) -> NormalForm:
        """Expand a type (may not be simple) into normal form."""
        match annot:
            case SimpleType() as simple:
                return simple
            case NamedType(x):
                if x in self._type_aliases:
                    return self._type_aliases[x]
                else:
                    self.issuer.error(UndefinedName(annot.pos))
                    return NoType
            case RefinementType(b1, r1) as rt:
                match self.normalize(b1):
                    case SimpleType():
                        return rt
                    case RefinementType(b, r2):
                        return RefinementType(b, apply('&&', r1, r2))

    def expand(self, annot: Type) -> SimpleType:
        """Expand a type into simple type."""
        match self.normalize(annot):
            case SimpleType() as simple:
                return simple
            case RefinementType(base, _):
                self.issuer.error(ExpectSimpleType(annot.pos))
                assert isinstance(base, SimpleType)
                return base
        # match annot:
        #     case SimpleType() as simple:
        #         return simple
        #     case NamedType(x) as node:
        #         if x in self._type_aliases:
        #             match self._type_aliases[x]:
        #                 case SimpleType() as simple:
        #                     return simple
        #                 case _:
        #                     raise TypeError
        #         else:
        #             self.issuer.error(UndefinedName(node.pos))
        #             return NoType
        #     case _:
        #         raise TypeError

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
                                self.issuer.error(UndefinedName(expr.pos))
                                return NoType
                            case t:
                                return t
                    case nf:
                        return get_base_type(nf)
            case App(fun, args):
                match self.infer(fun, scope):
                    case FunType(arg_types, return_type):
                        if len(arg_types) != len(args):
                            self.issuer.error(ArityMismatch(len(arg_types), len(args), expr.pos))
                        for te, e in zip(arg_types, args):
                            self.ensure(e, te, scope)
                        return return_type
                    case non_fun:
                        if non_fun != NoType:
                            self.issuer.error(TypeMismatch('fun type', pretty_tree(non_fun), fun.pos))
                        return NoType
            case InLang(receiver, lang):
                self.ensure(receiver, StringType(), scope)
                self.resolve_lang(lang)
            case Select(receiver, select_all, lang, absolute_path, path):
                self.ensure(receiver, StringType(), scope)
                match self.resolve_lang(lang):
                    case None:
                        pass
                    case o:
                        self.ensure_valid_path(o, path, absolute_path, not select_all)
                return ListType(StringType()) if select_all else StringType()
            case IfThenElse(cond, then_branch, else_branch):
                self.ensure(cond, BoolType(), scope)
                t = self.infer(then_branch, scope)
                self.ensure(else_branch, t, scope)
                return t
            case _:
                self.issuer.error(MissingTypeAnnot(expr.pos))
                return NoType

    def ensure(self, expr: Expr, expected: SimpleType, scope: Scope) -> None:
        match expr:
            case Lambda(params, body):
                match expected:
                    case FunType(arg_types, return_type):
                        formal_scope = Scope(scope)
                        for param, t in zip(params, arg_types):
                            if formal_scope.has_defined(param.name):
                                tree = f'parameter {param.name} of type {pretty_tree(formal_scope[param.name])}'
                                self.issuer.error(RedefinedName(tree, param.pos))
                            else:
                                formal_scope.update(param.name, t)
                        self.ensure(body, return_type, formal_scope)
                    case _:
                        self.issuer.error(TypeMismatch(pretty_tree(expected), 'fun type', expr.pos))
            case IfThenElse(cond, then_branch, else_branch):
                self.ensure(cond, BoolType(), scope)
                self.ensure(then_branch, expected, scope)
                self.ensure(else_branch, expected, scope)
            case other:  # fall back to infer mode
                actual = self.infer(other, scope)
                if self.is_subtype(actual, expected):
                    pass
                else:
                    self.issuer.error(TypeMismatch(pretty_tree(expected), pretty_tree(actual), expr.pos))

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

    def resolve_lang(self, ident: Ident) -> Optional[LangObject]:
        if ident.name not in self.langs:
            self.issuer.error(UndefinedName(ident.pos))
            return None
        return self.langs[ident.name]

    def ensure_valid_path(self, lang: LangObject, path: list[Ident], is_abs: bool, require_unique: bool) -> None:
        for symbol in path:
            if symbol.name not in lang.defined_symbols:
                self.issuer.error(UndefinedName(symbol.pos))
                return

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

    def define_lang(self, ident: Ident, rules: list[Rule]) -> None:
        if ident.name in self.langs:
            self.issuer.error(RedefinedName(f'lang {ident.name}', ident.pos))
            return
        if ident.name in self._type_aliases:
            self.issuer.error(RedefinedName(
                f'type {ident.name} = {pretty_tree(self._type_aliases[ident.name])}', ident.pos))
            return

        grammar: dict[str, Rule] = {}
        for rule in rules:
            if rule.name in grammar:
                self.issuer.error(RedefinedName(f'rule {grammar[rule.name]}', rule.ident.pos))
            else:
                grammar[rule.name] = rule

        if 'start' not in grammar:
            self.issuer.error(MissingStartRule(ident.pos))

        unused: set[str] = set(grammar.keys()) - {'start'}

        def check(clause: Clause) -> None:
            match clause:
                case CharSet(Literal(lower), lit) as cs:
                    if cs.end <= cs.begin:
                        self.issuer.error(InvalidClause(f'this charactor (code={cs.end}) must > '
                                                        f'"{lower}" (code={cs.begin})', lit.pos))
                case Symbol('start'):
                    self.issuer.error(InvalidClause('using start rule is not allowed here', clause.pos,
                                                    hint='introduce a new rule and let start rule point to it'))
                case Symbol(name):
                    if name in grammar:
                        unused.discard(name)
                    elif name not in self.langs:
                        self.issuer.error(UndefinedName(clause.pos))
                case Rep(clause, rep_range):
                    check(clause)
                    match rep_range:
                        case RepExactly(lit):
                            match lit.value:
                                case 0:
                                    self.issuer.error(InvalidClause('0 is not allowed here', lit.pos,
                                                                    hint='use the empty clause "" instead'))
                                case 1:
                                    self.issuer.error(InvalidClause('1 is redundant here', lit.pos,
                                                                    hint='drop the repetition in this clause'))
                        case RepInRange(_, Literal() as lit) if lit.value == 0:
                            self.issuer.error(InvalidClause('0 is not allowed here', lit.pos,
                                                            hint='use the empty clause "" instead'))
                        case RepInRange(Literal(lower), Literal() as lit) if lit.value <= lower:
                            self.issuer.error(InvalidClause(f'this value must > {lower}', lit.pos))
                case Seq(clauses):
                    for clause in clauses:
                        check(clause)
                case Alt(clauses):
                    for clause in clauses:
                        check(clause)

        for rule in rules:
            check(rule.body)

        for rule_name in unused:
            self.issuer.error(UnusedRule(grammar[rule_name].ident.pos))

        self.langs[ident.name] = LangObject(ident.name,
                                            dict([(rule_name, grammar[rule_name].body) for rule_name in grammar]))
        self._type_aliases[ident.name] = RefinementType(StringType(), InLang(Var('_'), ident))

    def define_type_alias(self, ident: Ident, nf: NormalForm) -> None:
        if ident.name in self.langs:
            self.issuer.error(RedefinedName(f'lang {ident.name}', ident.pos))
        elif ident.name in self._type_aliases:
            self.issuer.error(RedefinedName(
                f'type {ident.name} = {pretty_tree(self._type_aliases[ident.name])}', ident.pos))
        else:
            self._type_aliases[ident.name] = nf
