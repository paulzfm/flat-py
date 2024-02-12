from flat.compiler.trees import *
from flat.compiler.typer import Scope, NormalForm, Typer, get_base_type


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


class Instrumentor:
    def __init__(self):
        self._methods: dict[str, MethodInfo] = {}
        self._root_scope: Scope = Scope()
        self._next_counter = 0
        self.typer = Typer()

    def instrument(self, program: list[Def]) -> None:
        """Instrument in place."""
        for tree in program:
            match tree:
                case LangDef(name, rules):
                    self.typer.define_lang(name, rules)

                case TypeAlias(name, body):
                    self.typer.define_type_alias(name, self.typer.normalize(body))

                case FunDef(name, params, return_annot, value):
                    # check params
                    formal_scope = Scope(self._root_scope)
                    arg_types = []
                    for param in params:
                        typ = self.typer.expand(param.typ)
                        arg_types.append(typ)
                        if formal_scope.has_defined(param.name):
                            raise TypeError
                        else:
                            formal_scope.update(param.name, typ)

                    # check return type and value
                    return_type = self.typer.expand(return_annot)

                    # add to scope
                    if self._root_scope.has_defined(name):
                        raise TypeError
                    else:
                        self._root_scope.update(name, FunType(arg_types, return_type))

                    # check body
                    self.typer.ensure(value, return_type, formal_scope)

                case MethodDef(name, params, return_param, specs, body) as m:
                    # check params
                    formal_scope = Scope(self._root_scope)
                    arg_types = []
                    for param in params:
                        typ = self.typer.normalize(param.typ)
                        arg_types.append(typ)
                        if formal_scope.has_defined(param.name):
                            raise TypeError
                        else:
                            formal_scope.update(param.name, typ)

                    # check pre-conditions
                    requires = []
                    for spec in specs:
                        match spec:
                            case MethodPreSpec(cond):
                                self.typer.ensure(cond, BoolType(), formal_scope)
                                requires.append(cond)

                    # check return param
                    return_typ = self.typer.normalize(return_param.typ)
                    if formal_scope.has_defined(return_param.name):
                        raise TypeError
                    else:
                        formal_scope.update(return_param.name, return_typ)

                    # check post-conditions
                    ensures = []
                    for spec in specs:
                        match spec:
                            case MethodPostSpec(cond):
                                self.typer.ensure(cond, BoolType(), formal_scope)
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

    def trans_stmt(self, stmt: Stmt, this_method: MethodInfo, scope: Scope) -> list[Stmt]:
        match stmt:
            case Assign(var, value) as node:
                match self.get_type_of_var(node, scope):
                    case None:  # infer
                        typ = self.typer.infer(value, scope)
                        scope.update(var, typ)
                        return [stmt]
                    case typ:  # check
                        scope.update(var, typ)
                        check = self.check_type(value, var, typ, scope)
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
                    body += self.check_type(arg, var, t, scope)
                    new_args.append(Var(var))
                # check pre
                for cond in method.subst_pre_conditions(new_args):
                    body += [Assert(cond)]
                # call
                body += [Call(method_name, new_args, var=node.var)]
                # check return type
                match self.get_type_of_var(node, scope):
                    case None:
                        if node.var:
                            scope.update(node.var, method.return_type)
                    case typ:
                        assert node.var is not None
                        scope.update(node.var, typ)
                        body += self.check_subtype(method.return_type, node.var, typ)

                return body

            case Assert(cond):
                self.typer.ensure(cond, BoolType(), scope)
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
                body += self.check_type(value, return_var, this_method.return_type, scope)  # check type
                # check post condition
                return_value = Var(return_var)
                for cond in this_method.subst_post_conditions(this_method.formal_args + [return_value]):
                    body += [Assert(cond)]
                # return
                body += [Return(return_value)]
                return body

            case If(cond, then_body, else_body):
                self.typer.ensure(cond, BoolType(), scope)

                then_scope = Scope(scope)
                new_then = []
                for stmt in then_body:
                    new_then += self.trans_stmt(stmt, this_method, then_scope)

                new_else = []
                for stmt in else_body:
                    new_else += self.trans_stmt(stmt, this_method, then_scope)

                return [If(cond, new_then, new_else)]

            case While(cond, body):
                self.typer.ensure(cond, BoolType(), scope)

                inner_scope = Scope(scope)
                new_body = []
                for stmt in body:
                    new_body += self.trans_stmt(stmt, this_method, inner_scope)

                return [While(cond, new_body)]

            case _:
                raise NotImplementedError

    def check_subtype(self, lower: NormalForm, alias: str, upper: NormalForm) -> list[Stmt]:
        if get_base_type(lower) != get_base_type(upper):
            raise TypeError

        match upper:
            case SimpleType():  # ok
                return []
            case RefinementType(_, r):
                return [Assert(subst_expr(r, {'_': Var(alias)}))]

    def check_type(self, value: Expr, alias: str, expected: NormalForm, scope: Scope) -> list[Stmt]:
        self.typer.ensure(value, get_base_type(expected), scope)
        return self.check_subtype(expected, alias, expected)

    def get_type_of_var(self, node: Assign | Call, scope: Scope) -> Optional[NormalForm]:
        if node.type_annot:
            return self.typer.normalize(node.type_annot)
        return scope.lookup(node.var)

    def fresh_name(self) -> str:
        self._next_counter += 1
        return f'_{self._next_counter}'
