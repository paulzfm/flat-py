from flat.compiler.printer import pretty_print_tree
from flat.compiler.scope import NormalForm, Scope
from flat.compiler.trees import *


def get_base_type(nf: NormalForm) -> SimpleType:
    match nf:
        case SimpleType() as simple:
            return simple
        case RefinementType(base, _):
            assert isinstance(base, SimpleType)
            return base


def normalize(annot: Type, scope: Scope) -> NormalForm:
    """Expand a type (may not be simple) into normal form."""
    match annot:
        case SimpleType() as simple:
            return simple
        case NamedType(x):
            return scope.lookup_type(x)
        case RefinementType(b1, r1) as rt:
            match normalize(b1, scope):
                case SimpleType():
                    return rt
                case RefinementType(b, r2):
                    return RefinementType(b, apply('&&', r1, r2))


def expand(annot: Type, scope: Scope) -> SimpleType:
    """Expand a type into simple type."""
    match annot:
        case SimpleType() as simple:
            return simple
        case NamedType(x):
            match scope.lookup_type(x):
                case SimpleType() as simple:
                    return simple
                case _:
                    raise TypeError
        case _:
            raise TypeError


def infer(expr: Expr, scope: Scope) -> SimpleType:
    match expr:
        case Literal(value):
            match value:
                case int():
                    return IntType()
                case bool():
                    return BoolType()
                case str():
                    return StringType()
        case Selector(lang, is_abs, path):
            match scope.lookup_type(lang):
                case None:
                    raise TypeError(f'undefined name: {lang}')
                case LangType(_, info) as lt:
                    return SelectorType(lt)
                case _:
                    raise TypeError(f'not a lang type: {lang}')
        case Var(name):
            match scope.lookup_term(name):
                case None:
                    match get_builtin_fun_type(name):
                        case None:
                            raise TypeError(f'undefined name: {name}')
                        case t:
                            return t
                case nf:
                    return get_base_type(nf)
        case App(fun, args):
            if isinstance(fun, Var) and fun.name == 'select':  # select
                match args:
                    case [receiver, selector]:
                        match infer(receiver, scope), infer(selector, scope):
                            case (LangType() as t1, SelectorType(t2)):
                                if t1 == t2:
                                    return StringType()
                                else:
                                    raise TypeError
                            case _:
                                raise TypeError
                    case _:
                        raise TypeError

            # else: a normal function application
            match infer(fun, scope):
                case FunType(arg_types, return_type):
                    if len(arg_types) != len(args):
                        raise TypeError
                    for te, e in zip(arg_types, args):
                        ensure(e, te, scope)
                    return return_type
                case OverloadFunType(options):
                    for option in options:
                        arg_types = option.args
                        if len(arg_types) != len(args):
                            continue  # try the next one=
                        success = True
                        for te, e in zip(arg_types, args):
                            if check(e, te, scope) is not None:  # failure
                                success = False
                                break
                        if success:
                            return option.returns
                        # else: try the next one
                    # all options failed
                    raise TypeError
                case other:
                    raise TypeError(f'expect fun type, but found {other}')
        case IfThenElse(cond, then_branch, else_branch):
            ensure(cond, BoolType(), scope)
            t = infer(then_branch, scope)
            ensure(else_branch, t, scope)
        case other:
            raise TypeError(f'cannot infer type for {other}')


def check(expr: Expr, expected: SimpleType, scope: Scope) -> Optional[SimpleType | str]:
    match expr:
        case Lambda(params, body):
            match expected:
                case FunType(arg_types, return_type):
                    formal_scope = Scope(scope)
                    for x, t in zip(params, arg_types):
                        if formal_scope.has_defined(x):
                            raise TypeError(f'redefined lambda param {x}')
                        formal_scope.update_term(x, t)
                    match check(body, return_type, formal_scope):
                        case None:
                            return None
                        case body_actual:
                            return FunType(arg_types, body_actual)

                case _:
                    return 'fun type'
        case IfThenElse(cond, then_branch, else_branch):
            ensure(cond, BoolType(), scope)
            match check(then_branch, expected, scope):
                case None:
                    match check(else_branch, expected, scope):
                        case None:
                            return None
                        case body_actual:
                            return body_actual
                case body_actual:
                    return body_actual
        case other:  # fall back to infer mode
            actual = infer(other, scope)
            if is_subtype(actual, expected):
                return None
            return actual


def is_subtype(lower: SimpleType, upper: SimpleType) -> bool:
    if lower == upper:
        return True
    match lower, upper:
        case (LangType(), StringType()):
            return True
    return False


def ensure(expr: Expr, expected: SimpleType, scope: Scope) -> None:
    assert isinstance(expected, SimpleType)
    match check(expr, expected, scope):
        case None:
            pass
        case actual:
            raise TypeError(f'expect {pretty_print_tree(expected)}, but found {pretty_print_tree(actual)}')


def get_builtin_fun_type(name: str) -> Optional[SimpleType]:
    match name:
        case 'prefix_-':
            return FunType([IntType()], IntType())
        case 'prefix_!':
            return FunType([BoolType()], BoolType())
        case '+':
            return OverloadFunType([
                FunType([IntType(), IntType()], IntType()),
                FunType([StringType(), StringType()], StringType())
            ])
        case '-' | '*' | '/' | '%':
            return FunType([IntType(), IntType()], IntType())
        case '==' | '!=':
            return OverloadFunType([
                FunType([IntType(), IntType()], BoolType()),
                FunType([BoolType(), BoolType()], BoolType()),
                FunType([StringType(), StringType()], BoolType())
            ])
        case '>=' | '<=' | '>' | '<':
            return OverloadFunType([
                FunType([IntType(), IntType()], BoolType()),
                FunType([StringType(), StringType()], BoolType())
            ])
        case '&&' | '||':
            return FunType([BoolType(), BoolType()], BoolType())
        case 'substring':
            return FunType([StringType(), IntType(), IntType()], StringType())
        case 'int':
            return FunType([StringType()], IntType())
        case _:
            return None
