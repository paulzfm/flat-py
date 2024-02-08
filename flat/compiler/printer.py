import io

from flat.compiler.trees import *


def quote(text: str) -> str:
    return eval('text')


class IndentPrinter:
    def __init__(self, spaces: int):
        self._spaces = spaces
        self._level = 0
        self._buf = io.StringIO()
        self._at_line_begin = True

    def inc_level(self):
        assert self._at_line_begin
        self._level += 1

    def dec_level(self):
        assert self._at_line_begin
        assert self._level > 0
        self._level -= 1

    def _write_spaces(self):
        if self._at_line_begin:
            self._buf.write(' ' * (self._spaces * self._level))
            self._at_line_begin = False

    def write(self, text: str):
        self._write_spaces()
        assert '\n' not in text
        self._buf.write(text)

    def write_line(self, text: str = ''):
        self._write_spaces()
        assert '\n' not in text
        self._buf.write(text + '\n')
        self._at_line_begin = True

    def get(self) -> str:
        return self._buf.getvalue()


infix_ops = {'+', '-', '*', '/', '%', '==', '!=', '>=', '<=', '>', '<', '&&', '||'}


def pretty_print_tree(tree: Tree | list[Tree], spaces: int = 4) -> str:
    to = IndentPrinter(spaces)

    def print_group(elements: list[Tree | str]):
        to.write('(')
        if len(elements) > 0:
            match elements[0]:
                case Tree() as t:
                    print_tree(t)
                case str() as s:
                    to.write(s)
            for element in elements[1:]:
                to.write(', ')
                match element:
                    case Tree() as t:
                        print_tree(t)
                    case str() as s:
                        to.write(s)
        to.write(')')

    def print_body(stmts: list[Stmt]):
        to.write_line('{')
        to.inc_level()
        for stmt in stmts:
            print_tree(stmt)
        to.dec_level()
        to.write('}')

    def print_prefix(op: str, args: list[Expr]):
        match args:
            case [operand]:
                to.write(f'{op}(')
                print_tree(operand)
                to.write(')')
            case _:
                assert False

    def print_infix(op: str, args: list[Expr]):
        match args:
            case [lhs, rhs]:
                to.write('(')
                print_tree(lhs)
                to.write(f' {op} ')
                print_tree(rhs)
                to.write(')')
            case _:
                assert False

    def print_tree(node: Tree):
        match node:
            # types
            case IntType():
                to.write('int')
            case BoolType():
                to.write('bool')
            case StringType():
                to.write('string')
            case ListType(elem):
                to.write('[')
                print_tree(elem)
                to.write(']')
            case FunType(args, returns):
                if len(args) == 1:
                    print_tree(args[0])
                else:
                    print_group(args)
                to.write(' -> ')
                print_tree(returns)
            case NamedType(name):
                to.write(name)
            case RefinementType(base, refinement):
                to.write('{')
                print_tree(base)
                to.write(' | ')
                print_tree(refinement)
                to.write('}')
            # expressions
            case Literal(value):
                match value:
                    case int() as n:
                        to.write(str(n))
                    case True:
                        to.write('true')
                    case False:
                        to.write('false')
                    case str() as s:
                        to.write(quote(s))
            case Var(name):
                to.write(name)
            case App(fun, args):
                match fun:
                    case Var(name) if name.startswith('prefix_'):
                        print_prefix(name[7:], args)
                    case Var(name) if name in infix_ops:
                        print_infix(name, args)
                    case _:
                        print_tree(fun)
                        print_group(args)
            case Lambda(params, body):
                if len(params) == 1:
                    to.write(params[0])
                else:
                    print_group(params)
                to.write(' -> ')
                print_tree(body)
            # statements
            case Assign(var, value, type_annot):
                to.write(var)
                if type_annot:
                    to.write(': ')
                    print_tree(type_annot)
                to.write(' = ')
                print_tree(value)
                to.write_line(';')
            case Call(method_name, args, var, type_annot):
                if var:
                    to.write(var)
                    if type_annot:
                        to.write(': ')
                        print_tree(type_annot)
                    to.write(' = ')
                to.write(method_name)
                print_group(args)
                to.write_line(';')
            case Assert(cond):
                to.write('assert ')
                print_tree(cond)
                to.write_line(';')
            case Return(value):
                to.write('return')
                if value:
                    to.write(' ')
                    print_tree(value)
                to.write_line(';')
            case If(cond, then_branch, else_branch):
                to.write('if ')
                print_tree(cond)
                to.write(' ')
                print_body(then_branch)
                if else_branch:
                    to.write(' else ')
                    print_body(else_branch)
                to.write_line()
            case While(cond, body):
                to.write('while ')
                print_tree(cond)
                to.write(' ')
                print_body(body)
                to.write_line()
            # params
            case Param(name, typ):
                to.write(f'{name}: ')
                print_tree(typ)
            # specs
            case MethodPreSpec(cond):
                to.write('requires ')
                print_tree(cond)
                to.write_line()
            case MethodPostSpec(cond):
                to.write('ensures ')
                print_tree(cond)
                to.write_line()
            # definitions
            case TypeAlias(name, body):
                to.write(f'type {name} = ')
                print_tree(body)
                to.write_line()
            case FunDef(name, params, return_annot, value):
                to.write(f'fun {name}')
                print_group(params)
                to.write(': ')
                print_tree(return_annot)
                to.write(' = ')
                print_tree(value)
                to.write_line()
            case MethodDef(name, params, return_param, specs, body):
                to.write(f'method {name}')
                print_group(params)
                to.write(': ')
                print_tree(return_param)
                if len(specs) > 0:
                    to.write_line()
                    to.inc_level()
                    for spec in specs:
                        print_tree(spec)
                    to.dec_level()
                print_body(body)
                to.write_line()
            case other:
                raise NotImplementedError(f'{other}')

    match tree:
        case Tree() as t:
            print_tree(t)
        case list() as ts:
            for t in ts:
                print_tree(t)
    return to.get()
