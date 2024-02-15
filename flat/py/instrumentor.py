import ast
from typing import Optional

from flat.compiler.grammar import LangObject
from flat.py import RefinementType

TypeAnnot = ast.expr


class FunContext:
    def __init__(self):
        self.param_names: list[str] = []
        self.returns: Optional[TypeAnnot] = None
        self.postconditions: list[ast.Lambda] = []
        self.type_annots: dict[str, TypeAnnot] = {}


def load(name: str) -> ast.Name:
    return ast.Name(name, ctx=ast.Load())


def const(value: int | str) -> ast.Constant:
    return ast.Constant(value)


def apply(fun: str | ast.expr, *args: int | str | ast.expr) -> ast.Call:
    if isinstance(fun, str):
        fun = load(fun)
    exprs = []
    for arg in args:
        match arg:
            case int() as n:
                exprs += [const(n)]
            case str() as s:
                exprs += [const(s)]
            case ast.expr() as e:
                exprs += [e]
    return ast.Call(fun, exprs, keywords=[])


def location_of(node: ast.AST) -> ast.Tuple:
    return ast.Tuple([const(node.lineno), const(node.col_offset + 1)])


def call(fun: str | ast.expr, *args: int | str | ast.expr) -> ast.Expr:
    return ast.Expr(apply(fun, *args))


def make_check_type(expr: ast.expr, as_var: str, expected_type: ast.expr) -> ast.stmt:
    return (call('assert_true',
                 apply('has_type', load(as_var), expected_type),
                 apply('TypeMismatch', const(as_var), const(ast.unparse(expected_type)),
                       const(''), location_of(expr))))


def assign(var: str, with_value: ast.expr) -> ast.Assign:
    return ast.Assign([ast.Name(var, ctx=ast.Store())], with_value)


class Instrumentor(ast.NodeTransformer):
    def __call__(self, source_name: str, code: str) -> str:
        self._source_file = source_name
        self._env = {}
        exec(code, {}, self._env)

        tree = ast.parse(code)
        self._ctx_stack: list[FunContext] = []
        self.visit(tree)
        import_runtime = ast.parse('from flat.py.runtime import *').body[0]
        tree.body.insert(0, import_runtime)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree)

    def needs_check(self, type_annot: ast.expr) -> bool:
        match eval(ast.unparse(type_annot), {}, self._env):
            case LangObject() | RefinementType():
                return True
            case _:
                return False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        ctx = FunContext()
        body = []

        # check arg types
        for arg in node.args.args:
            name = arg.arg
            ctx.param_names += [name]
            if arg.annotation and self.needs_check(arg.annotation):
                ctx.type_annots[name] = arg.annotation
                body += [call('assert_true',
                              apply('has_type', load(name), arg.annotation),
                              apply('ArgTypeMismatch', name, ast.unparse(arg.annotation),
                                    self._source_file, location_of(arg)))]

        # check pre and remember post
        args = [load(x) for x in ctx.param_names]
        processed = []
        for decorator in node.decorator_list:
            match decorator:
                case ast.Call(ast.Name('requires'), [predicate]):
                    body += [call('assert_true',
                                  apply(predicate, *args),
                                  apply('PreconditionViolated', self._source_file, location_of(predicate),
                                        ast.List(args)))]
                    processed.append(decorator)  # to remove it
                case ast.Call(ast.Name('ensures'), [predicate]):
                    ctx.postconditions += [predicate]
                    processed.append(decorator)  # to remove it
        for x in processed:
            node.decorator_list.remove(x)

        # transform body
        self._ctx_stack.append(ctx)
        for stmt in node.body:
            match self.visit(stmt):
                case ast.stmt() as s:
                    body.append(s)
                case list() as ss:
                    body += ss

        # update body
        node.body = body
        self._ctx_stack.pop()
        return node

    def visit_Assign(self, node: ast.Assign) -> list[ast.stmt]:
        if len(self._ctx_stack) == 0:
            return [node]

        ctx = self._ctx_stack[-1]
        body = [node]
        for target in node.targets:
            for var in vars_in_target(target):
                if var in ctx.type_annots:
                    body.append(make_check_type(node.value, var, ctx.type_annots[var]))

        return body

    def visit_AnnAssign(self, node: ast.AnnAssign) -> list[ast.stmt]:
        if len(self._ctx_stack) == 0:
            return [node]

        ctx = self._ctx_stack[-1]
        body = [node]
        match node.target:
            case ast.Name(var):
                if self.needs_check(node.annotation):
                    ctx.type_annots[var] = node.annotation
                    body.append(make_check_type(node.value, var, node.annotation))
            case _:
                raise TypeError

        return body

    def visit_AugAssign(self, node: ast.AugAssign) -> list[ast.stmt]:
        if len(self._ctx_stack) == 0:
            return [node]

        ctx = self._ctx_stack[-1]
        body = [node]
        match node.target:
            case ast.Name(var):
                if var in ctx.type_annots:
                    body.append(make_check_type(node.value, var, ctx.type_annots[var]))

        return body

    def visit_Return(self, node: ast.Return) -> list[ast.stmt]:
        ctx = self._ctx_stack[-1]
        body = [assign('__return__', node.value)]
        if ctx.returns is not None and node.value is not None:
            body.append(make_check_type(node.value, '__return__', ctx.returns))

        args = [load(x) for x in ctx.param_names] + [load('__return__')]
        for predicate in ctx.postconditions:
            body += [call('assert_true',
                          apply(predicate, *args),
                          apply('PostconditionViolated', self._source_file,
                                location_of(predicate), location_of(node.value), ast.List(args)))]

        body += [node]
        return body


def vars_in_target(expr: ast.expr) -> list[str]:
    match expr:
        case ast.Name(x):
            return [x]
        case ast.Tuple(es):
            return [x for e in es for x in vars_in_target(e)]
        case _:
            return []
