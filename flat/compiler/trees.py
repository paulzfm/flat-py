from copy import deepcopy
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class Pos:
    start: Tuple[int, int]
    end: Tuple[int, int]


class Tree:
    def __init__(self):
        self.pos: Optional[Pos] = None

    def set_pos(self, start: Tuple[int, int], end: Tuple[int, int]):
        self.pos = Pos(start, end)
        return self

    def copy_pos(self, start_from, end_from: Optional = None):
        if not end_from:
            end_from = start_from
        self.pos = Pos(start_from.pos.start, end_from.pos.end)
        return self


@dataclass
class Ident(Tree):
    name: str


class Expr(Tree):
    pass


SimpleLiteralValue = int | bool | str


@dataclass
class Literal(Expr):
    value: SimpleLiteralValue


# --- Lang rules ---
class Clause(Tree):
    pass


@dataclass
class Token(Clause):
    text: str


@dataclass
class CharSet(Clause):
    lhs: Literal  # char
    rhs: Literal  # char

    @property
    def begin(self) -> int:
        return ord(self.lhs.value)

    @property
    def end(self) -> int:
        return ord(self.rhs.value)

    @property
    def get_range(self) -> range:
        return range(self.begin, self.end + 1)


@dataclass
class Symbol(Clause):
    """A nonterminal symbol or referring to another lang."""
    name: str


class RepRange(Tree):
    lower: int
    upper: Optional[int]  # None = inf


class RepStar(RepRange):
    lower = 0
    upper = None


class RepPlus(RepRange):
    lower = 1
    upper = None


class RepOpt(RepRange):
    lower = 0
    upper = 1


@dataclass
class RepExactly(RepRange):
    times: Literal  # int

    @property
    def lower(self) -> int:
        return self.times.value

    @property
    def upper(self) -> int:
        return self.times.value


@dataclass
class RepInRange(RepRange):
    at_least: Optional[Literal]  # int
    at_most: Optional[Literal]  # int

    @property
    def lower(self) -> int:
        return self.at_least.value if self.at_least else 0

    @property
    def upper(self) -> Optional[int]:
        return self.at_most.value if self.at_most else None


@dataclass
class Rep(Clause):
    clause: Clause
    rep_range: RepRange


@dataclass
class Seq(Clause):
    clauses: list[Clause]


@dataclass
class Alt(Clause):
    clauses: list[Clause]


@dataclass
class Rule(Tree):
    ident: Ident
    body: Clause

    @property
    def name(self) -> str:
        return self.ident.name


# --- Types ---
class Type(Tree):
    pass


class SimpleType(Type):
    pass


@dataclass
class TopType(SimpleType):
    pass


@dataclass
class IntType(SimpleType):
    pass


@dataclass
class BoolType(SimpleType):
    pass


@dataclass
class StringType(SimpleType):
    pass


@dataclass
class UnitType(SimpleType):
    pass


@dataclass
class ListType(SimpleType):
    elem: SimpleType


@dataclass
class FunType(SimpleType):
    args: list[SimpleType]
    returns: SimpleType


@dataclass
class NamedType(Type):
    name: str


@dataclass
class RefinementType(Type):
    base: Type
    refinement: Expr


@dataclass
class Param(Tree):
    ident: Ident
    typ: Type

    @property
    def name(self) -> str:
        return self.ident.name


# --- Expressions ---
@dataclass
class Var(Expr):
    name: str


@dataclass
class App(Expr):
    fun: Expr
    args: list[Expr]


def apply(name: str, *args: Expr) -> App:
    return App(Var(name), list(args))


def prefix(op: str, operand: Expr) -> App:
    return apply(f'prefix_{op}', operand)


def infix(op: str, lhs: Expr, rhs: Expr) -> App:
    return apply(op, lhs, rhs)


@dataclass
class InLang(Expr):
    receiver: Expr
    lang: Ident


@dataclass
class Select(Expr):
    receiver: Expr
    select_all: bool
    lang: Ident
    path_is_absolute: bool
    path: list[Ident]


@dataclass
class Lambda(Expr):
    params: list[Ident]
    body: Expr


@dataclass
class IfThenElse(Expr):
    cond: Expr
    then_branch: Expr
    else_branch: Expr


def subst_expr(expr: Expr, mappings: dict[str, Expr], closed: frozenset[str] = frozenset()) -> Expr:
    match expr:
        case Literal():
            return expr
        case Var(x):
            return mappings[x] if x in mappings and x not in closed else expr
        case App(e, es):
            return App(subst_expr(e, mappings, closed),
                       [subst_expr(e, mappings, closed) for e in es])
        case Lambda(xs, e):
            return Lambda(xs, subst_expr(e, mappings, closed | frozenset(x.ident for x in xs)))
        case InLang(e, lang):
            return InLang(subst_expr(e, mappings, closed), lang)
        case Select(e) as node:
            copied = deepcopy(node)
            copied.receiver = subst_expr(e, mappings, closed)
            return copied
        case IfThenElse(e, e1, e2):
            return IfThenElse(subst_expr(e, mappings, closed),
                              subst_expr(e1, mappings, closed),
                              subst_expr(e2, mappings, closed))
        case other:
            raise NotImplementedError(f'subst {other}')


# --- Statements ---
class Stmt(Tree):
    pass


@dataclass
class Assign(Stmt):
    var: Ident
    value: Expr
    type_annot: Optional[Type] = None


@dataclass
class Call(Stmt):
    method: Ident
    args: list[Expr]
    var: Optional[Ident] = None
    type_annot: Optional[Type] = None

    def set_lvalue(self, var: Ident, type_annot: Optional[Type]):
        self.var = var
        self.type_annot = type_annot
        return self


@dataclass
class Assert(Stmt):
    cond: Expr


@dataclass
class Return(Stmt):
    value: Optional[Expr] = None


@dataclass
class If(Stmt):
    cond: Expr
    then_body: list[Stmt]
    else_body: list[Stmt]


@dataclass
class While(Stmt):
    cond: Expr
    body: list[Stmt]


# --- Definitions ---
@dataclass
class Def(Tree):
    ident: Ident

    @property
    def name(self) -> str:
        return self.ident.name


@dataclass
class LangDef(Def):
    rules: list[Rule]


@dataclass
class TypeAlias(Def):
    body: Type


@dataclass
class FunDef(Def):
    params: list[Param]
    return_type: Type
    value: Expr


@dataclass
class MethodSpec(Tree):
    cond: Expr


class MethodPreSpec(MethodSpec):
    pass


class MethodPostSpec(MethodSpec):
    pass


@dataclass
class MethodDef(Def):
    params: list[Param]
    return_param: Param
    specs: list[MethodSpec]
    body: list[Stmt]
