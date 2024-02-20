import sys

from flat.compiler import predef
from flat.compiler.errors import Error, AssertionFailure
from flat.compiler.grammar import LangObject
from flat.compiler.issuer import Issuer
from flat.compiler.trees import *
from flat.compiler.values import *


class StackFrame:
    def __init__(self):
        self._values: dict[str, Value] = {}

    def __contains__(self, name: str) -> bool:
        return name in self._values

    def get_value(self, name: str) -> Value:
        return self._values[name]

    def put_value(self, name: str, value: Value) -> None:
        self._values[name] = value

    @property
    def all_values(self) -> list[Tuple[str, Value]]:
        return [(x, self._values[x]) for x in self._values]


class Executor:
    def __init__(self, issuer: Issuer, langs: dict[str, LangObject], debug: bool = False):
        self._functions: dict[str, FunObject] = {}
        self._languages = langs
        self._call_stack: list[StackFrame] = []
        self._issuer = issuer
        self._debug = debug

    @property
    def _top_frame(self):
        assert len(self._call_stack) > 0
        return self._call_stack[-1]

    def abort(self, err: Error):
        self._issuer.error(err)
        self._issuer.print()
        sys.exit(1)

    def run(self, program: list[Def], entry: str = 'main') -> Value:
        for tree in program:
            self.load(tree)
        if entry not in self._functions:
            raise RuntimeError(f'Function "{entry}" not found')
        return self.call(self._functions[entry], [])

    def load(self, tree: Def) -> None:
        match tree:
            case LangDef():
                pass
            case TypeAlias():
                pass
            case FunDef(ident, params, _, value):
                self._functions[ident.name] = FunObject(ident.name, [p.name for p in params], [Return(value)])
            case MethodDef(ident, params, _, _, body):
                self._functions[ident.name] = FunObject(ident.name, [p.name for p in params], body)

    def call(self, fun_obj: FunObject, arg_values: list[Value]) -> Value:
        frame = StackFrame()
        self._call_stack.append(frame)
        # load args
        for x, v in zip(fun_obj.param_names, arg_values):
            frame.put_value(x, v)
        # execute body
        return_value = self.exec(fun_obj.body)
        self._call_stack.pop()
        if return_value:
            return return_value
        else:
            raise RuntimeError(f'Function {fun_obj.name}(...) did not return')

    def exec(self, body: list[Stmt]) -> Optional[Value]:
        for stmt in body:
            match stmt:
                case Assign(var, value):
                    self._top_frame.put_value(var.name, self.eval(value))
                case Call(method, args) as node:
                    arg_values = [self.eval(arg) for arg in args]
                    return_value = self.call(self._functions[method.name], arg_values)
                    if node.var:
                        self._top_frame.put_value(node.var.name, return_value)
                case Assert(cond) as node:
                    match self.eval(cond):
                        case BoolValue(True):
                            pass
                        case BoolValue(False):
                            if node.error_trigger:
                                model_vars, f = node.error_trigger
                                model_values = [pretty_value(self._top_frame.get_value(x)) for x in model_vars]
                                self.abort(f(model_values))
                            else:
                                self.abort(AssertionFailure(stmt.pos))
                        case v:
                            raise RuntimeError
                case Return(None):
                    return Nothing()
                case Return(value):
                    return_value = self.eval(value)
                    return return_value
                case If(cond, then_body, else_body):
                    match self.eval(cond):
                        case BoolValue(True):
                            return_value = self.exec(then_body)
                            if return_value:
                                return return_value
                        case BoolValue(False):
                            return_value = self.exec(else_body)
                            if return_value:
                                return return_value
                        case v:
                            raise RuntimeError
                case While(cond, body):
                    while True:
                        match self.eval(cond):
                            case BoolValue(True):
                                return_value = self.exec(body)
                                if return_value:
                                    return return_value
                            case BoolValue(False):
                                break  # loop terminates
                            case v:
                                raise RuntimeError
                case _:
                    raise RuntimeError

    def eval(self, expr: Expr) -> Value:
        match expr:
            case Literal(value):
                match value:
                    case int() as n:
                        return IntValue(n)
                    case bool() as b:
                        return BoolValue(b)
                    case str() as s:
                        return StringValue(s)
            case Var(name):
                if name in self._top_frame:
                    return self._top_frame.get_value(name)
                match predef.typ(name):
                    case FunType(ts, _):
                        names = [f'_{i}' for i in range(len(ts))]
                        wrapper = Lambda([Ident(x) for x in names], App(Var(name), [Var(x) for x in names]))
                        return self.eval(wrapper)
                    case _:
                        raise RuntimeError(f'undefined name in current frame: {name}')
            case Lambda(params, body):
                return FunObject('<lambda>', [param.name for param in params], [Return(body)])
            case App(fun, args):
                arg_values = [self.eval(arg) for arg in args]
                match fun:
                    case Var(f):
                        match self.apply_predef(f, arg_values):
                            case None:  # not a predefined function
                                if f in self._top_frame:
                                    match self._top_frame.get_value(f):
                                        case FunObject() as c:
                                            return self.call(c, arg_values)
                                        case v:
                                            raise RuntimeError

                                if f in self._functions:
                                    return self.call(self._functions[f], arg_values)

                                raise RuntimeError
                            case value:
                                return value
            case InLang(receiver, lang):
                match self.eval(receiver):
                    case StringValue(s):
                        return BoolValue(s in self._languages[lang.name])
                    case _:
                        raise RuntimeError
            case Select(receiver, select_all, lang, is_abs, path):
                match self.eval(receiver):
                    case StringValue(word):
                        o = self._languages[lang.name]
                        p = [symbol.name for symbol in path]
                        if select_all:
                            values = [StringValue(s) for s in o.select_all(word, p, is_abs)]
                            return SeqValue(values)
                        else:
                            return StringValue(o.select_unique(word, p, is_abs))
                    case v:
                        raise RuntimeError
            case IfThenElse(cond, then_branch, else_branch):
                match self.eval(cond):
                    case BoolValue(True):
                        return self.eval(then_branch)
                    case BoolValue(False):
                        return self.eval(else_branch)
                    case v:
                        raise RuntimeError
            case _:
                raise RuntimeError

    def apply_predef(self, fun: str, args: list[Value]) -> Optional[Value]:
        match fun, args:
            case 'prefix_-', [IntValue(n)]:
                return IntValue(-n)
            case 'prefix_!', [BoolValue(b)]:
                return BoolValue(not b)
            case '+', [IntValue(n1), IntValue(n2)]:
                return IntValue(n1 + n2)
            case '-', [IntValue(n1), IntValue(n2)]:
                return IntValue(n1 - n2)
            case '*', [IntValue(n1), IntValue(n2)]:
                return IntValue(n1 * n2)
            case '/', [IntValue(n1), IntValue(n2)]:
                return IntValue(n1 // n2)
            case '%', [IntValue(n1), IntValue(n2)]:
                return IntValue(n1 % n2)
            case '>=', [IntValue(n1), IntValue(n2)]:
                return BoolValue(n1 >= n2)
            case '<=', [IntValue(n1), IntValue(n2)]:
                return BoolValue(n1 <= n2)
            case '>', [IntValue(n1), IntValue(n2)]:
                return BoolValue(n1 > n2)
            case '<', [IntValue(n1), IntValue(n2)]:
                return BoolValue(n1 < n2)
            case '==', [v1, v2]:
                return BoolValue(v1 == v2)
            case '!=', [v1, v2]:
                return BoolValue(v1 != v2)
            case '&&', [BoolValue(b1), BoolValue(b2)]:
                return BoolValue(b1 and b2)
            case '||', [BoolValue(b1), BoolValue(b2)]:
                return BoolValue(b1 or b2)
            # string
            case 'empty', [StringValue(s)]:
                return BoolValue(s == '')
            case 'length', [StringValue(s)]:
                return IntValue(len(s))
            case 'concat', [StringValue(s1), StringValue(s2)]:
                return StringValue(s1 + s2)
            case 'nth', [StringValue(s), IntValue(k)]:
                return StringValue(s[k])
            case 'substring', [StringValue(s), IntValue(start), IntValue(end)]:
                return StringValue(s[start:end])
            case 'contains', [StringValue(s), StringValue(s1)]:
                return BoolValue(s1 in s)
            case 'find', [StringValue(s), StringValue(s1)]:
                return IntValue(s.find(s1))
            case 'rfind', [StringValue(s), StringValue(s1)]:
                return IntValue(s.rfind(s1))
            case 'int', [StringValue(s)]:
                return IntValue(int(s))
            # seq functions
            case 'seq_empty', [SeqValue(xs)]:
                return BoolValue(len(xs) == 0)
            case 'seq_forall', [SeqValue(xs), FunObject() as f]:
                for x in xs:
                    match self.call(f, [x]):
                        case BoolValue(True):
                            pass
                        case BoolValue(False):
                            return BoolValue(False)
                        case _:
                            raise RuntimeError
                return BoolValue(True)
            case 'seq_exists', [SeqValue(xs), FunObject() as f]:
                for x in xs:
                    match self.call(f, [x]):
                        case BoolValue(True):
                            return BoolValue(True)
                        case BoolValue(False):
                            pass
                        case _:
                            raise RuntimeError
                return BoolValue(False)
            case 'seq_first', [SeqValue(xs)]:
                return xs[0]
            case 'seq_last', [SeqValue(xs)]:
                return xs[-1]
            case _:
                return None