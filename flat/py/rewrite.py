import ast
from copy import deepcopy
from enum import Enum
from typing import Callable, Optional, Tuple

from flat.py import xpath


def negate(cond: ast.expr) -> ast.expr:
    """Logical negation of a condition."""
    return ast.UnaryOp(ast.Not(), cond)


def cnf(cond: ast.expr) -> list[ast.expr]:
    """Convert a condition into conjunctive normal form. Return the list of conjuncts."""
    match cond:
        case ast.BoolOp(ast.And(), operands):  # p and q
            return [c for e in operands for c in cnf(e)]
        case ast.UnaryOp(ast.Not(), ast.BoolOp(ast.Or(), operands)):  # not (p or q) = (not p) and (not q)
            return [c for e in operands for c in cnf(negate(e))]
        case atomic:
            return [atomic]


class FreeVarCollector(ast.NodeVisitor):
    def __call__(self, tree: ast.expr) -> frozenset[str]:
        """Collect the set of free variable names in an expression."""
        self._free: set[str] = set()
        self._bound: list[list[str]] = []
        self.visit(tree)
        return frozenset(self._free)

    def visit_Name(self, node: ast.Name):
        if all(node.id not in bound for bound in self._bound):
            self._free.add(node.id)

    def visit_Lambda(self, node: ast.Lambda):
        bound = [arg.arg for arg in node.args.args]
        self._bound.append(bound)
        self.visit(node.body)
        self._bound.pop()


free_vars: Callable[[ast.expr], frozenset[str]] = FreeVarCollector()


class Substitution(ast.NodeTransformer):
    def __call__(self, tree: ast.expr, subst_map: dict[str, ast.expr]) -> ast.expr:
        """Substitute free vars in an expression."""
        self._subst_map = subst_map
        self._bound: list[list[str]] = []
        node = deepcopy(tree)
        self.visit(node)
        return node

    def visit_Name(self, node: ast.Name) -> ast.expr:
        if node.id in self._subst_map and all(node.id not in bound for bound in self._bound):
            return self._subst_map[node.id]
        return node

    def visit_Lambda(self, node: ast.Lambda) -> ast.expr:
        bound = [arg.arg for arg in node.args.args]
        self._bound.append(bound)
        body = self.visit(node.body)
        self._bound.pop()
        node.body = body
        return node


subst: Callable[[ast.expr, dict[str, ast.expr]], ast.expr] = Substitution()


class ISLaType(Enum):
    Formula = 0
    Int = 1
    String = 2


def to_isla(expr: ast.expr, this) -> Optional[Tuple[str, ISLaType]]:
    """Convert an expression to a well-typed ISLa formula.
    :param expr: expression tree
    :param this: name of this binder
    """
    match expr:
        # constants
        case ast.Constant(True):
            return 'true', ISLaType.Formula
        case ast.Constant(False):
            return 'false', ISLaType.Formula
        case ast.Constant(int() as n):
            return str(n), ISLaType.Int
        case ast.Constant(str()):
            return '"' + ast.unparse(expr)[1:-1] + '"', ISLaType.String  # NOTE: isla uses double quote

        # boolean expressions
        case ast.BoolOp(op, operands):
            match op:
                case ast.And():
                    connective = ' and '
                case ast.Or():
                    connective = ' or '
                case _:
                    assert False
            results = [to_isla(e, this) for e in operands]
            if all(isinstance(result, tuple) and result[1] == ISLaType.Formula for result in results):
                formulae = [f for f, _ in results]  # type: ignore
                return '(' + connective.join(formulae) + ')', ISLaType.Formula
        case ast.UnaryOp(ast.Not(), operand):
            match to_isla(operand, this):
                case (formula, ISLaType.Formula):
                    return f'(not {formula})', ISLaType.Formula

        # arithmetic expressions, string concat (+)
        case ast.BinOp(left, op, right):
            match op:
                case ast.Add():
                    smt_op = '+'
                case ast.Sub():
                    smt_op = '-'
                case ast.Mult():
                    smt_op = '*'
                case ast.Div():
                    smt_op = '/'
                case ast.Mod():
                    smt_op = '%'
                case _:  # unsupported
                    return None
            match to_isla(left, this), to_isla(right, this):
                case (lhs, ISLaType.Int), (rhs, ISLaType.Int):
                    return f'({smt_op} {lhs} {rhs})', ISLaType.Int
                case ((lhs, ISLaType.String), (rhs, ISLaType.String)) if smt_op == '+':
                    return f'(str.++ {lhs} {rhs})', ISLaType.String
        case ast.UnaryOp(op, operand):
            match op, to_isla(operand, this):
                case ast.UAdd(), (formula, ISLaType.Int):
                    return formula, ISLaType.Int  # type: ignore
                case ast.USub(), (formula, ISLaType.Int):
                    return f'(- 0 {formula})', ISLaType.Int

        # comparison expressions, string comparison (<=), string contains (in)
        case ast.Compare(left, [op], [right]):
            match op:
                case ast.Eq():
                    smt_op = '='
                case ast.Lt():
                    smt_op = '<'
                case ast.LtE():
                    smt_op = '<='
                case ast.Gt():
                    smt_op = '>'
                case ast.GtE():
                    smt_op = '>='
                case ast.In():
                    smt_op = 'in'
                case _:  # unsupported
                    return None
            match to_isla(left, this), to_isla(right, this):
                case (lhs, ISLaType.Int), (rhs, ISLaType.Int) if smt_op != 'in':
                    return f'({smt_op} {lhs} {rhs})', ISLaType.Formula
                case (lhs, ISLaType.String), (rhs, ISLaType.String):
                    match smt_op:
                        case '<':
                            return f'((<= {lhs} {rhs}) and not (= {lhs} {rhs}))', ISLaType.Formula
                        case '>':
                            return f'(not (<= {lhs} {rhs}))', ISLaType.Formula
                        case '>=':
                            return f'(not (<= {lhs} {rhs}) or (= {lhs} {rhs}))', ISLaType.Formula
                        case 'in':
                            return f'(str.contains {rhs} {lhs})', ISLaType.Formula
                        case _:
                            return f'({smt_op} {lhs} {rhs})', ISLaType.Formula

        # string char at
        case ast.Subscript(receiver, ast.Constant(int() as index)):
            match to_isla(receiver, this):
                case string, ISLaType.String:
                    return f'(str.at {string} {index})', ISLaType.String
        # substring
        case ast.Subscript(receiver, ast.Slice(lower, upper, step=None)):
            match to_isla(receiver, this):
                case string, ISLaType.String:
                    match lower:
                        case ast.Constant(int() as index):
                            offset = index
                        case None:
                            offset = 0
                        case _:  # unsupported
                            return None
                    match upper:
                        case ast.Constant(int() as index):
                            length = f'(- {index} {offset})'
                        case None:
                            length = f'(str.len {string})'
                        case _:  # unsupported
                            return None
                    return f'(str.substr {string} {offset} {length})', ISLaType.String

        # string and builtin functions
        case ast.Call(ast.Name(fun, ctx=ast.Load()), args, keywords=[]):
            match fun, args:
                case 'len', [receiver]:
                    match to_isla(receiver, this):
                        case string, ISLaType.String:
                            return f'(str.len {string})', ISLaType.Int
                case 'ord', [receiver]:
                    match to_isla(receiver, this):
                        case string, ISLaType.String:
                            return f'(str.to_code {string})', ISLaType.Int
                case 'chr', [receiver]:
                    match to_isla(receiver, this):
                        case integer, ISLaType.Int:
                            return f'(str.from_code {integer})', ISLaType.String
                case 'int', [receiver]:
                    match to_isla(receiver, this):
                        case string, ISLaType.String:
                            # SMTLib: string cannot contain '-'.
                            # Python: allow '-'.
                            return f'(str.to.int {string})', ISLaType.Int
                case 'str', [receiver]:
                    match to_isla(receiver, this):
                        case integer, ISLaType.Int:
                            # SMTLib: integer is non-negative.
                            # Python: allow negative value.
                            return f'(str.from_int {integer})', ISLaType.String
                case 'forall' | 'exists', [ast.Lambda(ast.arguments([], [ast.arg(x)], None, [], [], None, []), cond),
                                           ast.Call(ast.Name('select_all'),
                                                    [_, ast.Constant(str() as path), ast.Name(w)])] if w == this:
                    match to_isla(cond, this):
                        case atom, ISLaType.Formula:
                            formula = atom
                            for parent, is_direct, child in reversed(xpath(path).edges):
                                binder = x if formula == atom else child
                                if is_direct:  # additional direct_child check
                                    conn = 'implies' if fun == 'forall' else 'and'
                                    formula = f'direct_child({binder}, {parent}) {conn} {formula}'
                                formula = f'({fun} <{child}> {binder} in {parent}: {formula})'
                            return formula, ISLaType.Formula
                        case _:
                            raise NotImplementedError

                case 'select', [_, ast.Constant(str() as path), ast.Name(w)] if w == this:
                    p = xpath(path)
                    term = f'<{p.start}>'
                    for is_direct, symbol in p.steps:
                        term += ('.' if is_direct else '..') + f'<{symbol}>'
                    return term, ISLaType.String

        case ast.Call(ast.Attribute(receiver, fun, ctx=ast.Load()), args, keywords=[]):
            match fun, args:
                case 'startswith', [s]:
                    match to_isla(receiver, str), to_isla(s, this):
                        case (string, ISLaType.String), (prefix, ISLaType.String):
                            return f'(str.prefixof {prefix} {string})', ISLaType.Formula
                case 'endswith', [s]:
                    match to_isla(receiver, str), to_isla(s, this):
                        case (string, ISLaType.String), (suffix, ISLaType.String):
                            return f'(str.suffixof {suffix} {string})', ISLaType.Formula
                case 'find' | 'index', _:  # `index` raises error if the pattern is not found
                    if len(args) not in [1, 2]:  # unsupported
                        return None
                    match to_isla(receiver, str), to_isla(args[0], this):
                        case (string, ISLaType.String), (pattern, ISLaType.String):
                            if len(args) == 2:
                                match to_isla(args[1], this):
                                    case start, ISLaType.Int:
                                        pass  # start assigned
                                    case _:
                                        return None
                            else:
                                start = '0'
                            return f'(str.indexof {string} {pattern} {start})', ISLaType.Int
                case 'replace', [s1, s2, ast.Constant(1)]:  # count = 1: replace the first occurrence only
                    match to_isla(receiver, str), to_isla(s1, str), to_isla(s2, this):
                        case (string, ISLaType.String), (old, ISLaType.String), (new, ISLaType.String), ():
                            return f'(str.replace {string} {old} {new})', ISLaType.String
                case 'replace', [s1, s2]:  # no count: replace all occurrences
                    match to_isla(receiver, str), to_isla(s1, str), to_isla(s2, this):
                        case (string, ISLaType.String), (old, ISLaType.String), (new, ISLaType.String), ():
                            # SMTLib: if `old` is empty, the result is the original `string`.
                            # Python: the result is to insert `new` everywhere like a delimiter.
                            return f'(str.replace_all {string} {old} {new})', ISLaType.String
                case 'isdigit', []:
                    match to_isla(receiver, this):
                        case string, ISLaType.String:
                            # SMTLib: require the string to be a singleton.
                            # Python: test all characters in the string.
                            return f'(str.is_digit {string})', ISLaType.Formula

    # otherwise
    return None
