from flat.compiler import typer
from flat.compiler.trees import *
from flat.compiler.typer import Scope, NormalForm


class MethodInfo:
    def __init__(self, params: list[Param], return_param: Param, requires: list[Expr], ensures: list[Expr]):
        self._params = params
        self._return_param = return_param
        self._requires = requires
        self._ensures = ensures

    @property
    def arity(self) -> int:
        return len(self._params)

    @property
    def formal_args(self) -> list[Var]:
        return [Var(p.name) for p in self._params]

    @property
    def param_types(self) -> list[NormalForm]:
        return [p.typ for p in self._params]

    @property
    def return_type(self) -> NormalForm:
        return self._return_param.typ

    def subst_pre_conditions(self, args: list[Expr]) -> list[Expr]:
        assert len(args) == self.arity
        mappings = dict((p.name, arg) for p, arg in zip(self._params, args))
        return [subst_expr(e, mappings) for e in self._requires]

    def subst_post_conditions(self, args: list[Expr]) -> list[Expr]:
        assert len(args) == self.arity + 1
        mappings = dict((p.name, arg) for p, arg in zip(self._params + [self._return_param], args))
        return [subst_expr(e, mappings) for e in self._ensures]


def check_subtype(lower: NormalForm, alias: str, upper: NormalForm) -> list[Stmt]:
    if typer.get_base_type(lower) != typer.get_base_type(upper):
        raise TypeError

    match upper:
        case SimpleType():  # ok
            return []
        case RefinementType(_, r):
            return [Assert(subst_expr(r, {'_': Var(alias)}))]


def check_type(value: Expr, alias: str, expected: NormalForm, scope: Scope) -> list[Stmt]:
    typer.ensure(value, typer.get_base_type(expected), scope)
    return check_subtype(expected, alias, expected)


def get_type_of_var(node: Assign | Call, scope: Scope) -> Optional[NormalForm]:
    if node.type_annot:
        return typer.normalize(node.type_annot, scope)
    return scope.lookup_term(node.var)


class Instrumentor:
    def __init__(self):
        self._methods: dict[str, MethodInfo] = {}
        self._root_scope: Scope = Scope()
        self._next_counter = 0

    def instrument(self, program: list[Def]) -> None:
        """Instrument in place."""
        for tree in program:
            match tree:
                case LangDef(name, rules):
                    self.validate_grammar(rules)
                    self._root_scope.update_type(name, RefinementType(StringType(), InLang(Var('_'), name)))

                case TypeAlias(name, body):
                    if self._root_scope.has_defined(name):
                        raise TypeError
                    else:
                        self._root_scope.update_type(name, typer.normalize(body, self._root_scope))

                case FunDef(name, params, return_annot, value):
                    # check params
                    formal_scope = Scope(self._root_scope)
                    arg_types = []
                    for param in params:
                        typ = typer.expand(param.typ, formal_scope)
                        arg_types.append(typ)
                        if formal_scope.has_defined(param.name):
                            raise TypeError
                        else:
                            formal_scope.update_term(param.name, typ)

                    # check return type and value
                    return_type = typer.expand(return_annot, formal_scope)

                    # add to scope
                    if self._root_scope.has_defined(name):
                        raise TypeError
                    else:
                        self._root_scope.update_term(name, FunType(arg_types, return_type))

                    # check body
                    typer.ensure(value, return_type, formal_scope)

                case MethodDef(name, params, return_param, specs, body) as m:
                    # check params
                    formal_scope = Scope(self._root_scope)
                    arg_types = []
                    for param in params:
                        typ = typer.normalize(param.typ, formal_scope)
                        arg_types.append(typ)
                        if formal_scope.has_defined(param.name):
                            raise TypeError
                        else:
                            formal_scope.update_term(param.name, typ)

                    # check pre-conditions
                    requires = []
                    for spec in specs:
                        match spec:
                            case MethodPreSpec(cond):
                                typer.ensure(cond, BoolType(), formal_scope)
                                requires.append(cond)

                    # check return param
                    return_typ = typer.normalize(return_param.typ, formal_scope)
                    if formal_scope.has_defined(return_param.name):
                        raise TypeError
                    else:
                        formal_scope.update_term(return_param.name, return_typ)

                    # check post-conditions
                    ensures = []
                    for spec in specs:
                        match spec:
                            case MethodPostSpec(cond):
                                typer.ensure(cond, BoolType(), formal_scope)
                                ensures.append(cond)

                    # build method info
                    info = MethodInfo([Param(p.name, t) for p, t in zip(params, arg_types)],
                                      Param(return_param.name, return_typ),
                                      requires, ensures)
                    if name in self._methods:
                        raise TypeError
                    else:
                        self._methods[name] = info

                    # check body
                    local_scope = Scope(formal_scope)
                    new_body = []
                    for stmt in body:
                        new_body += self.trans_stmt(stmt, info, local_scope)
                    m.body = new_body

    def validate_grammar(self, rules: list[Rule]) -> None:
        defined = set(rule.name for rule in rules)
        if 'start' not in defined:
            raise TypeError('no start rule')

        defined = frozenset(defined - {'start'})
        used: set[str] = set()

        def check(clause: Clause) -> None:
            match clause:
                case CharSet(begin, end):
                    if begin > end:
                        raise TypeError(f'invalid charset: {begin} must not greater than {end}')
                case Symbol('start'):
                    raise TypeError('cannot use start rule')
                case Symbol(name):
                    if name in defined:
                        used.add(name)
                    else:
                        match self._root_scope.lookup_type(name):
                            case None:
                                raise TypeError(f'undefined rule {name}')
                case Rep(clause, at_least, at_most):
                    check(clause)
                    if at_least > at_most:
                        raise TypeError(f'invalid rep: {at_least} must not greater than {at_most}')
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

    def trans_stmt(self, stmt: Stmt, this_method: MethodInfo, scope: Scope) -> list[Stmt]:
        match stmt:
            case Assign(var, value) as node:
                match get_type_of_var(node, scope):
                    case None:  # infer
                        typ = typer.infer(value, scope)
                        scope.update_term(var, typ)
                        return [stmt]
                    case typ:  # check
                        scope.update_term(var, typ)
                        check = check_type(value, var, typ, scope)
                        return [stmt] + check

            case Call(method_name, args) as node:
                if method_name not in self._methods:
                    raise TypeError

                method = self._methods[method_name]
                # evaluate args and check their types
                body = []
                new_args = []
                if len(args) != method.arity:
                    raise TypeError
                for arg, t in zip(args, method.param_types):
                    var = self.fresh_name()
                    body += [Assign(var, arg)]
                    body += check_type(arg, var, t, scope)
                    new_args.append(Var(var))
                # check pre
                for cond in method.subst_pre_conditions(new_args):
                    body += [Assert(cond)]
                # call
                body += [Call(method_name, new_args, var=node.var)]
                # check return type
                match get_type_of_var(node, scope):
                    case None:
                        if node.var:
                            scope.update_term(node.var, method.return_type)
                    case typ:
                        assert node.var is not None
                        scope.update_term(node.var, typ)
                        body += check_subtype(method.return_type, node.var, typ)

                return body

            case Assert(cond):
                typer.ensure(cond, BoolType(), scope)
                return [stmt]

            case Return(None):
                if this_method.return_type != UnitType():
                    raise TypeError
                return [stmt]

            case Return(value):
                if this_method.return_type == UnitType():
                    raise TypeError

                return_var = self.fresh_name()
                body = [Assign(return_var, value)]  # evaluate return value
                body += check_type(value, return_var, this_method.return_type, scope)  # check type
                # check post condition
                return_value = Var(return_var)
                for cond in this_method.subst_post_conditions(this_method.formal_args + [return_value]):
                    body += [Assert(cond)]
                # return
                body += [Return(return_value)]
                return body

            case If(cond, then_body, else_body):
                typer.ensure(cond, BoolType(), scope)

                then_scope = Scope(scope)
                new_then = []
                for stmt in then_body:
                    new_then += self.trans_stmt(stmt, this_method, then_scope)

                new_else = []
                for stmt in else_body:
                    new_else += self.trans_stmt(stmt, this_method, then_scope)

                return [If(cond, new_then, new_else)]

            case While(cond, body):
                typer.ensure(cond, BoolType(), scope)

                inner_scope = Scope(scope)
                new_body = []
                for stmt in body:
                    new_body += self.trans_stmt(stmt, this_method, inner_scope)

                return [While(cond, new_body)]

            case _:
                raise NotImplementedError

    def fresh_name(self) -> str:
        self._next_counter += 1
        return f'_{self._next_counter}'
