from dataclasses import dataclass

from flat.py import parse_expr, fuzz
from flat.py.rewrite import cnf, to_isla, ISLaType, free_vars, subst
from flat.py.runtime import *
from flat.py.utils import classify


@dataclass(frozen=True)
class FunSig:
    """Only interesting types are specified."""
    name: str
    params: list[Tuple[str, Optional[TypeNorm], Optional[ast.expr]]]
    returns: Optional[Tuple[TypeNorm, ast.expr]]
    preconditions: list[ast.expr]  # bind params
    postconditions: list[ast.expr]  # bind params and '_' for return value

    @property
    def param_names(self) -> list[str]:
        return [x for x, _, _ in self.params]


class FunContext:
    def __init__(self, fun: FunSig, annots: dict[str, ast.expr]):
        self.fun = fun
        self.annots = annots


def load(name: str) -> ast.Name:
    return ast.Name(name, ctx=ast.Load())


def const(value: int | str | None) -> ast.Constant:
    return ast.Constant(value)


def conjunction(conjuncts: list[ast.expr]) -> ast.expr:
    match conjuncts:
        case []:
            return ast.Constant(True)
        case [cond]:
            return cond
        case _:
            return ast.BoolOp(ast.And(), conjuncts)


def assign(var: str, value: ast.expr | int) -> ast.stmt:
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


def lambda_expr(args: list[str], body: ast.expr) -> ast.Lambda:
    return ast.Lambda(ast.arguments([], [ast.arg(x) for x in args], None, [], [], None, []), body)


def apply_flat(fun: Callable, *args: int | str | ast.expr) -> ast.Call:
    return apply(ast.Attribute(load('__flat__'), fun.__name__, ctx=ast.Load()), *args)


def call_flat(fun: Callable, *args: int | str | ast.expr) -> ast.Expr:
    return ast.Expr(apply_flat(fun, *args))


class Instrumentor(ast.NodeTransformer):
    def __init__(self) -> None:
        # self._inside_body = False
        self._last_lineno = 0
        self._next_id = 0
        self._case_guards: list[ast.expr] = []
        self._functions: dict[str, FunSig] = {}

    def __call__(self, source: str, code: str) -> str:
        self._env: dict[str, Any] = {}
        exec(code, {}, self._env)

        tree = ast.parse(code)
        self._last_lineno = 0
        self._stack: list[FunContext] = []
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

    def expand(self, annot: ast.expr) -> Optional[TypeNorm]:
        match eval(ast.unparse(annot), {}, self._env):
            case LangObject() as obj:
                return TypeNorm(BaseType.Lang, None, obj)
            case TypeNorm() as norm:
                return norm
            case _:
                return None

    def fresh_name(self) -> str:
        self._next_id += 1
        return f'_{self._next_id}'

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # self._inside_body = True
        body = self.track_lineno(node.lineno)
        annots = {}

        # check arg types
        params: list[Tuple[str, Optional[TypeNorm], Optional[ast.expr]]] = []
        for arg in node.args.args:
            x = arg.arg
            if arg.annotation:
                norm = self.expand(arg.annotation)
                if norm:
                    annots[x] = arg.annotation
                    body += [call_flat(assert_arg_type, load(x), len(params), node.name, arg.annotation)]
            else:
                norm = None
            params.append((x, norm, arg.annotation))

        # check return type
        if node.returns:
            match self.expand(node.returns):
                case None:
                    returns = None
                case norm:
                    returns = norm, node.returns
        else:
            returns = None

        # check specifications
        preconditions: list[ast.expr] = []
        postconditions: list[ast.expr] = []
        processed: list[ast.expr] = []
        arg_names = [x for x, _, _ in params]
        for decorator in node.decorator_list:
            match decorator:
                case ast.Call(ast.Name('requires'), [ast.Constant(str() as literal)]):
                    pre = parse_expr(literal)
                    preconditions.append(pre)
                    body += self.track_lineno(decorator.lineno)
                    body += [call_flat(assert_pre, pre,
                                       ast.List([ast.Tuple([const(x), load(x)]) for x in arg_names]), node.name)]
                    processed.append(decorator)  # to remove it
                case ast.Call(ast.Name('ensures'), [ast.Constant(str() as literal)]):
                    post = parse_expr(literal)
                    post.lineno = decorator.lineno
                    postconditions.append(post)
                    processed.append(decorator)  # to remove it
        for x in processed:
            node.decorator_list.remove(x)

        # signature done
        sig = FunSig(node.name, params, returns, preconditions, postconditions)
        self._functions[node.name] = sig

        # transform body
        self._stack.append(FunContext(sig, annots))
        for stmt in node.body:
            match self.visit(stmt):
                case ast.stmt() as s:
                    body.append(s)
                case list() as ss:
                    body += ss
        self._stack.pop()

        # update body and return
        if node.name == 'main' and len(node.args.args) == 0:
            name_eq_main = ast.Compare(load('__name__'), [ast.Eq()], [const('__main__')], type_ignores=[])
            return ast.If(name_eq_main, body, orelse=[])
        else:
            node.body = body
            # self._inside_body = False
            return node

    def visit_Assign(self, node: ast.Assign) -> list[ast.stmt]:
        node.value = self.visit(node.value)
        if len(self._stack) == 0:
            return [node]

        ctx = self._stack[-1]
        body = self.track_lineno(node.lineno)
        body += [node]
        for target in node.targets:
            for var in vars_in_target(target):
                if var in ctx.annots:
                    body += [call_flat(assert_type, node.value, ctx.annots[var])]

        return body

    def visit_AnnAssign(self, node: ast.AnnAssign) -> list[ast.stmt]:
        if node.value:
            node.value = self.visit(node.value)
        if len(self._stack) == 0:
            return [node]

        ctx = self._stack[-1]
        body = self.track_lineno(node.lineno)
        body += [node]
        match node.target:
            case ast.Name(var):
                if self.expand(node.annotation) is not None:
                    ctx.annots[var] = node.annotation
                    body += [call_flat(assert_type, node.value, ctx.annots[var])]
            case _:
                raise TypeError

        return body

    def visit_AugAssign(self, node: ast.AugAssign):
        node.value = self.visit(node.value)
        if len(self._stack) == 0:
            return [node]

        ctx = self._stack[-1]
        body = self.track_lineno(node.lineno)
        body += [node]
        match node.target:
            case ast.Name(var):
                if var in ctx.annots:
                    body += [call_flat(assert_type, node.value, ctx.annots[var])]

        return body

    def visit_Return(self, node: ast.Return):
        if node.value:
            node.value = self.visit(node.value)
        else:
            node.value = const(None)

        ctx = self._stack[-1]
        body = self.track_lineno(node.lineno)
        if ctx.fun.returns is None and len(ctx.fun.postconditions) == 0:  # no check, just return
            return body + [node]

        body += [assign('__return__', node.value)]
        if ctx.fun.returns:
            body += [call_flat(assert_type, load('__return__'), ctx.fun.returns[1])]

        arg_names = [x for x in ctx.fun.param_names]
        for cond in ctx.fun.postconditions:  # note: return value is '_' in cond
            body += self.track_lineno(cond.lineno)
            body += [call_flat(assert_post, subst(cond, {'_': load('__return__')}),
                               ast.List([ast.Tuple([const(x), load(x)]) for x in arg_names]),
                               load('__return__'))]
        body += self.track_lineno(node.lineno)
        body += [ast.Return(load('__return__'))]
        return body

    def visit_Call(self, node: ast.Call):
        match node:
            case ast.Call(ast.Name('isinstance'), [obj, typ]) if self.expand(typ) is not None:
                return apply_flat(has_type, obj, typ)
            case ast.Call(ast.Name('fuzz'), [ast.Name(target), times, *args]) if self._env['fuzz'] == fuzz:
                if target in self._functions:
                    fun = self._functions[target]
                else:
                    raise NameError(f'Undefined function: {target}')
                match args:
                    case []:
                        using: dict[str, ast.expr] = {}
                    case [ast.Dict(keys, values)]:
                        raise NotImplementedError
                return apply_flat(fuzz_test, load(target), times, synth_producer(fun, using))
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
            case ast.MatchAs(ast.MatchClass(cls, [], [], []), x) if self.expand(cls) is not None:
                self._case_guards.append(apply_flat(has_type, load(x), cls))
                return ast.MatchAs(None, x)
            case _:
                return super().generic_visit(node)

    def visit_MatchClass(self, node: ast.MatchClass):
        match node:
            case ast.MatchClass(cls, [], [], []) if self.expand(cls) is not None:
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


def synth_producer(fun: FunSig, using_producers: dict[str, ast.expr]) -> ast.expr:
    pre_conjuncts = [c for pre in fun.preconditions for c in cnf(pre)]

    producers: list[ast.expr] = []
    for x, norm, annot in fun.params:
        if x in using_producers:
            producers += [using_producers[x]]
        elif norm is not None and norm.base == BaseType.Lang:  # synthesize an isla producer
            formulae: list[str] = []  # conjuncts that isla can solve
            test_conditions: list[ast.expr] = []  # other conjuncts: fall back to Python
            if norm.cond:
                for cond in cnf(norm.cond):
                    match to_isla(cond, '_', {}):
                        case formula, ISLaType.Formula:
                            formulae += [formula]  # type: ignore
                        case _:
                            test_conditions += [cond]

            # pick conjuncts that could be written in the refinement position
            # i.e., it is a predicate over the param x only
            picked, pre_conjuncts = classify(lambda c: free_vars(c) & (set(fun.param_names) - {x}) == set(),
                                             pre_conjuncts)
            for cond in picked:
                match to_isla(cond, x, {}):
                    case formula, ISLaType.Formula:
                        formulae += [formula]  # type: ignore
                    case _:
                        test_conditions += [subst(cond, {x: load('_')})]

            match formulae:
                case []:
                    formula = const(None)
                case [f]:
                    formula = const(f)
                case _:
                    formula = const(' and '.join(formulae))

            assert annot is not None
            producers += [
                apply_flat(producer,
                           apply_flat(isla_generator, annot, formula),
                           lambda_expr(['_'], conjunction(test_conditions)))
            ]
        else:
            raise TypeError

    return apply_flat(product_producer, ast.List(producers),
                      lambda_expr(fun.param_names, conjunction(pre_conjuncts)))
