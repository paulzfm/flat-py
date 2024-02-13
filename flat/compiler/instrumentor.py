from flat.compiler.errors import RedefinedName, UndefinedName, ArityMismatch, TypeMismatch
from flat.compiler.issuer import Issuer
from flat.compiler.printer import pretty_tree
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
    def param_names(self) -> list[str]:
        return [p.name for p in self._params]

    @property
    def formal_args(self) -> list[Var]:
        return [Var(p.name) for p in self._params]

    @property
    def param_types(self) -> list[NormalForm]:
        return [p.typ for p in self._params]

    @property
    def return_type(self) -> NormalForm:
        return self._return_param.typ

    @property
    def typ(self) -> FunType:
        return FunType(self.param_types, self.return_type)

    def subst_pre_conditions(self, args: list[Expr]) -> list[Expr]:
        assert len(args) == self.arity
        mappings = dict((p.name, arg) for p, arg in zip(self._params, args))
        return [subst_expr(e, mappings) for e in self._requires]

    def subst_post_conditions(self, args: list[Expr]) -> list[Expr]:
        assert len(args) == self.arity + 1
        mappings = dict((p.name, arg) for p, arg in zip(self._params + [self._return_param], args))
        return [subst_expr(e, mappings) for e in self._ensures]


class Instrumentor:
    def __init__(self, issuer: Issuer):
        self._methods: dict[str, MethodInfo] = {}
        self._root_scope: Scope = Scope()
        self._next_counter = 0
        self.issuer = issuer
        self.typer = Typer(issuer)

    def instrument(self, program: list[Def]) -> None:
        """Instrument in place."""
        for tree in program:
            match tree:
                case LangDef(ident, rules):
                    self.typer.define_lang(ident, rules)

                case TypeAlias(ident, body):
                    self.typer.define_type_alias(ident, self.typer.normalize(body))

                case FunDef(ident, params, return_annot, value):
                    if ident.name in self._methods:
                        self.issuer.error(RedefinedName(f'method {ident.name} '
                                                        f'of type {pretty_tree(self._methods[ident.name].typ)}',
                                                        ident.pos))
                        continue

                    if self._root_scope.has_defined(ident.name):
                        self.issuer.error(RedefinedName(f'fun {ident.name} '
                                                        f'of type {pretty_tree(self._root_scope[ident.name])}',
                                                        ident.pos))
                        continue

                    # check params
                    formal_scope = Scope(self._root_scope)
                    arg_types = []
                    for param in params:
                        typ = self.typer.expand(param.typ)
                        arg_types.append(typ)
                        if formal_scope.has_defined(param.name):
                            self.issuer.error(RedefinedName(f'parameter {param.name} '
                                                            f'of type {pretty_tree(formal_scope[param.name])}',
                                                            param.ident.pos))
                        else:
                            formal_scope.update(param.name, typ)

                    # check return type and value
                    return_type = self.typer.expand(return_annot)

                    # add to scope
                    self._root_scope.update(ident.name, FunType(arg_types, return_type))

                    # check body
                    self.typer.ensure(value, return_type, formal_scope)

                case MethodDef(ident, params, return_param, specs, body) as m:
                    if ident.name in self._methods:
                        self.issuer.error(RedefinedName(f'method {ident.name} '
                                                        f'of type {pretty_tree(self._methods[ident.name].typ)}',
                                                        ident.pos))
                        continue

                    if self._root_scope.has_defined(ident.name):
                        self.issuer.error(RedefinedName(f'fun {ident.name} '
                                                        f'of type {pretty_tree(self._root_scope[ident.name])}',
                                                        ident.pos))
                        continue

                    # check params
                    formal_scope = Scope(self._root_scope)
                    arg_types = []
                    for param in params:
                        typ = self.typer.normalize(param.typ)
                        arg_types.append(typ)
                        if formal_scope.has_defined(param.name):
                            self.issuer.error(RedefinedName(f'parameter {param.name} '
                                                            f'of type {pretty_tree(formal_scope[param.name])}',
                                                            param.ident.pos))
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
                        self.issuer.error(RedefinedName(f'parameter {return_param.name} '
                                                        f'of type {pretty_tree(formal_scope[return_param.name])}',
                                                        return_param.ident.pos))
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
                    info = MethodInfo([Param(p.ident, t) for p, t in zip(params, arg_types)],
                                      Param(return_param.ident, return_typ),
                                      requires, ensures)
                    self._methods[ident.name] = info

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
                        scope.update(var.name, typ)
                        return [stmt]
                    case typ:  # check
                        scope.update(var.name, typ)
                        check = self.check_type(value, var.name, typ, scope)
                        return [stmt] + check

            case Call(method, args) as node:
                if method.name not in self._methods:
                    self.issuer.error(UndefinedName(method.pos))
                    return [stmt]

                m = self._methods[method.name]
                # evaluate args and check their types
                body = []
                new_args = []
                if len(args) != m.arity:
                    self.issuer.error(ArityMismatch(m.arity, len(args), stmt.pos))
                for arg, t in zip(args, m.param_types):
                    x = self.fresh_name()
                    body += [Assign(Ident(x), arg)]
                    body += self.check_type(arg, x, t, scope)
                    new_args.append(Var(x).copy_pos(arg))
                # check pre
                model_vars = {}
                for v, x in zip(new_args, m.param_names):
                    model_vars[v.name] = x
                for cond in m.subst_pre_conditions(new_args):
                    body += [AssertSatisfy(cond, model_vars).copy_pos(stmt)]
                # call
                body += [Call(method, new_args, var=node.var).copy_pos(stmt)]
                # check return type
                match self.get_type_of_var(node, scope):
                    case None:  # infer: simply the method return type
                        if node.var:
                            scope.update(node.var.name, m.return_type)
                    case typ:  # check
                        assert node.var is not None
                        scope.update(node.var.name, typ)
                        body += self.check_subtype(m.return_type, stmt.pos, node.var.name, typ)

                return body

            case Assert(cond):
                self.typer.ensure(cond, BoolType(), scope)
                return [stmt]

            case Return(None):
                if this_method.return_type != UnitType():
                    self.issuer.error(TypeMismatch(pretty_tree(this_method.return_type), 'unit', stmt.pos))
                return [stmt]

            case Return(value):
                if this_method.return_type == UnitType():
                    self.issuer.error(TypeMismatch('unit', pretty_tree(this_method.return_type), value.pos))
                    return [stmt]

                return_var = self.fresh_name()
                body = [Assign(Ident(return_var), value)]  # evaluate return value
                body += self.check_type(value, return_var, this_method.return_type, scope)  # check type
                # check post condition
                return_value = Var(return_var)
                for cond in this_method.subst_post_conditions(this_method.formal_args + [return_value]):
                    body += [AssertSatisfy(cond, {return_var: 'return value'}).copy_pos(value)]
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

    def check_subtype(self, value_type: NormalForm, value_pos: Pos, value_ref: str, expected: NormalForm) -> list[Stmt]:
        if get_base_type(value_type) != get_base_type(expected):
            raise TypeError

        match expected:
            case SimpleType():  # ok
                return []
            case RefinementType(_, r):
                return [AssertSatisfy(subst_expr(r, {'_': Var(value_ref)}),
                                      {value_ref: 'this expr'}).set_pos(value_pos)]

    def check_type(self, value: Expr, value_ref: str, expected: NormalForm, scope: Scope) -> list[Stmt]:
        self.typer.ensure(value, get_base_type(expected), scope)
        return self.check_subtype(expected, value.pos, value_ref, expected)

    def get_type_of_var(self, node: Assign | Call, scope: Scope) -> Optional[NormalForm]:
        if node.type_annot:
            return self.typer.normalize(node.type_annot)
        if node.var:
            return scope.lookup(node.var.name)
        return None

    def fresh_name(self) -> str:
        self._next_counter += 1
        return f'_{self._next_counter}'
