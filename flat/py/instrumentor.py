import ast
from typing import Optional

from flat.py.runtime import *

TypeAnnot = ast.expr


class FunContext:
    def __init__(self):
        self.param_names: list[str] = []
        self.returns: Optional[TypeAnnot] = None
        self.postconditions: list[ast.Lambda] = []
        self.type_annots: dict[str, TypeAnnot] = {}


def load(name: str) -> ast.Name:
    return ast.Name(name, ctx=ast.Load())


def const(value: int | str | None) -> ast.Constant:
    return ast.Constant(value)


def assign(var: str, value: ast.expr | int) -> ast.Assign:
    if isinstance(value, int):
        value = ast.Constant(value)

    return ast.Assign([ast.Name(var, ctx=ast.Store())], value)


def apply(fun: str | ast.expr, *args: int | str | ast.expr) -> ast.Call:
    if isinstance(fun, str):
        fun = load(fun)
    exprs = []
    for arg in args:
        match arg:
            case int() as n:
                exprs += [ast.Constant(n)]
            case str() as s:
                exprs += [ast.Constant(s)]
            case ast.expr() as e:
                exprs += [e]
    return ast.Call(fun, exprs, keywords=[])


def apply_flat(fun: Callable, *args: int | str | ast.expr) -> ast.Call:
    return apply(ast.Attribute(load('__flat__'), fun.__name__, ctx=ast.Load()), *args)


def call_flat(fun: Callable, *args: int | str | ast.expr) -> ast.Expr:
    return ast.Expr(apply_flat(fun, *args))


class Instrumentor(ast.NodeTransformer):
    def __init__(self):
        # self._inside_body = False
        self._last_lineno = 0
        self._next_id = 0
        self._case_guards: list[ast.expr] = []

    def __call__(self, source: str, code: str) -> str:
        self._env = {}
        exec(code, {}, self._env)

        tree = ast.parse(code)
        self._ctx_stack: list[FunContext] = []
        self._last_lineno = 0
        self.visit(tree)
        import_runtime = ast.parse('from flat.py import runtime as __flat__').body[0]
        set_source = ast.parse(f'__source__ = "{source}"').body[0]
        tree.body.insert(0, import_runtime)
        tree.body.insert(1, set_source)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree)

    def track_lineno(self, lineno: int) -> list[ast.stmt]:
        # assert self._inside_body
        body = []
        if lineno != self._last_lineno:
            body += [assign('__line__', lineno)]
            self._last_lineno = lineno

        return body

    def needs_check(self, type_annot: TypeAnnot) -> bool:
        match eval(ast.unparse(type_annot), {}, self._env):
            case LangType() | RefinementType():
                return True
            case _:
                return False

    def fresh_name(self) -> str:
        self._next_id += 1
        return f'_{self._next_id}'

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.stmt:
        # self._inside_body = True
        body = self.track_lineno(node.lineno)
        ctx = FunContext()

        # check arg types
        k = 0
        for arg in node.args.args:
            k += 1
            name = arg.arg
            ctx.param_names += [name]
            if arg.annotation and self.needs_check(arg.annotation):
                ctx.type_annots[name] = arg.annotation
                body += [call_flat(assert_arg_type, load(name), k, node.name, arg.annotation)]

        # check pre and remember post
        arg_names = [x for x in ctx.param_names]
        processed = []
        for decorator in node.decorator_list:
            match decorator:
                case ast.Call(ast.Name('requires'), [cond]):
                    body += self.track_lineno(cond.lineno)
                    body += [call_flat(assert_pre, cond,
                                       ast.List([ast.Tuple([const(x), load(x)]) for x in arg_names]), node.name)]
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

        # update body and return
        self._ctx_stack.pop()
        if node.name == 'main' and len(node.args.args) == 0:
            name_eq_main = ast.Compare(load('__name__'), [ast.Eq()], [const('__main__')], type_ignores=[])
            return ast.If(name_eq_main, body, orelse=[])
        else:
            node.body = body
            # self._inside_body = False
            return node

    def visit_Assign(self, node: ast.Assign) -> list[ast.stmt]:
        node.value = self.visit(node.value)
        if len(self._ctx_stack) == 0:
            return [node]

        ctx = self._ctx_stack[-1]
        body = self.track_lineno(node.lineno)
        body += [node]
        for target in node.targets:
            for var in vars_in_target(target):
                if var in ctx.type_annots:
                    body += [call_flat(assert_type, node.value, ctx.type_annots[var])]

        return body

    def visit_AnnAssign(self, node: ast.AnnAssign) -> list[ast.stmt]:
        if node.value:
            node.value = self.visit(node.value)
        if len(self._ctx_stack) == 0:
            return [node]

        ctx = self._ctx_stack[-1]
        body = self.track_lineno(node.lineno)
        body += [node]
        match node.target:
            case ast.Name(var):
                if self.needs_check(node.annotation):
                    ctx.type_annots[var] = node.annotation
                    body += [call_flat(assert_type, node.value, ctx.type_annots[var])]
            case _:
                raise TypeError

        return body

    def visit_AugAssign(self, node: ast.AugAssign) -> list[ast.stmt]:
        node.value = self.visit(node.value)
        if len(self._ctx_stack) == 0:
            return [node]

        ctx = self._ctx_stack[-1]
        body = self.track_lineno(node.lineno)
        body += [node]
        match node.target:
            case ast.Name(var):
                if var in ctx.type_annots:
                    body += [call_flat(assert_type, node.value, ctx.type_annots[var])]

        return body

    def visit_Return(self, node: ast.Return) -> list[ast.stmt]:
        if node.value:
            node.value = self.visit(node.value)
        else:
            node.value = const(None)

        ctx = self._ctx_stack[-1]
        body = self.track_lineno(node.lineno)
        if ctx.returns is None and len(ctx.postconditions) == 0:  # no check, just return
            return body + [node]

        body += [assign('__return__', node.value)]
        if ctx.returns:
            body += [call_flat(assert_type, load('__return__'), ctx.returns)]

        arg_names = [x for x in ctx.param_names]
        for cond in ctx.postconditions:
            body += self.track_lineno(cond.lineno)
            body += [call_flat(assert_post, cond,
                               ast.List([ast.Tuple([const(x), load(x)]) for x in arg_names]),
                               load('__return__'))]
        body += self.track_lineno(node.lineno)
        body += [ast.Return(load('__return__'))]
        return body

    def visit_Call(self, node: ast.Call):
        match node:
            case ast.Call(ast.Name('isinstance'), [obj, typ]) if self.needs_check(typ):
                return apply_flat(has_type, obj, typ)
            case _:
                return super().generic_visit(node)

    def visit_Match(self, node: ast.Match):
        node.subject = self.visit(node.subject)
        new_cases = []
        for case in node.cases:
            self._case_guards = []
            case = self.visit(case)
            if len(self._case_guards) > 0:
                cond = ast.BoolOp(ast.And(), self._case_guards)
                case.guard = cond if case.guard is None else ast.BoolOp(ast.And(), [case.guard, cond])
            new_cases.append(case)
        node.cases = new_cases

        return node

    def visit_MatchAs(self, node: ast.MatchAs):
        match node:
            case ast.MatchAs(ast.MatchClass(cls, [], [], []), x) if self.needs_check(cls):
                self._case_guards.append(apply_flat(has_type, load(x), cls))
                return ast.MatchAs(None, x)
            case _:
                return super().generic_visit(node)

    def visit_MatchClass(self, node: ast.MatchClass):
        match node:
            case ast.MatchClass(cls, [], [], []) if self.needs_check(cls):
                x = self.fresh_name()
                self._case_guards.append(apply_flat(has_type, load(x), cls))
                return ast.MatchAs(None, x)
            case _:
                return super().generic_visit(node)

    def generic_visit(self, node: ast.AST):
        if isinstance(node, ast.stmt):
            body = self.track_lineno(node.lineno)
            match super().generic_visit(node):
                case ast.stmt() as s:
                    body.append(s)
                case list() as ss:
                    body += ss
            return body

        return super().generic_visit(node)


def vars_in_target(expr: ast.expr) -> list[str]:
    match expr:
        case ast.Name(x):
            return [x]
        case ast.Tuple(es):
            return [x for e in es for x in vars_in_target(e)]
        case _:
            return []
