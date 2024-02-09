from copy import deepcopy
from dataclasses import dataclass
from typing import Optional


@dataclass
class Pos:
    line: int
    column: int


class Tree:
    pos: Pos

    def set_pos(self, pos: Pos):
        self.pos = pos
        return self


# --- Lang rules ---
class Clause(Tree):
    pass


@dataclass
class Token(Clause):
    text: str


@dataclass
class CharSet(Clause):
    begin: int
    end: int


@dataclass
class Symbol(Clause):
    """A nonterminal symbol or referring to another lang."""
    name: str


@dataclass
class Rep(Clause):
    clause: Clause
    at_least: int
    at_most: Optional[int]


@dataclass
class Seq(Clause):
    clauses: list[Clause]


@dataclass
class Alt(Clause):
    clauses: list[Clause]


@dataclass
class Rule(Tree):
    name: str
    body: Clause


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
class OverloadFunType(SimpleType):
    """Only for type checker."""
    options: list[FunType]


@dataclass
class NamedType(Type):
    name: str


class Expr(Tree):
    pass


@dataclass
class RefinementType(Type):
    base: Type
    refinement: Expr


@dataclass
class Param(Tree):
    name: str
    typ: Type


# --- Expressions ---
SimpleLiteralValue = int | bool | str


@dataclass
class Literal(Expr):
    value: SimpleLiteralValue


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
    lang_name: str


@dataclass
class Select(Expr):
    receiver: Expr
    select_all: bool
    lang_name: str
    path_is_absolute: bool
    path: list[str]


@dataclass
class Lambda(Expr):
    params: list[str]
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
            return Lambda(xs, subst_expr(e, mappings, closed | frozenset(x.name for x in xs)))
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
    var: str
    value: Expr
    type_annot: Optional[Type] = None


@dataclass
class Call(Stmt):
    method_name: str
    args: list[Expr]
    var: Optional[str] = None
    type_annot: Optional[Type] = None

    def set_lvalue(self, var: str, type_annot: Optional[Type]):
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
    name: str


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
class MethodSpec:
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
