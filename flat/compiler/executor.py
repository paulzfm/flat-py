import sys
from typing import Tuple

from flat.compiler.values import *
from flat.compiler.trees import *
from flat.compiler import predef
from flat.compiler.printer import pretty_print_tree


class StackFrame:
    def __init__(self):
        self._values: dict[str, Value] = {}

    def __contains__(self, name: str):
        return name in self._values

    def get_value(self, name: str):
        return self._values[name]

    def put_value(self, name: str, value: Value):
        self._values[name] = value

    @property
    def all_values(self) -> list[Tuple[str, Value]]:
        return [(x, self._values[x]) for x in self._values]


class Executor:
    def __init__(self, debug: bool = False):
        self._functions: dict[str, Callable] = {}
        self._call_stack: list[StackFrame] = []
        self._debug = debug

    @property
    def _top_frame(self):
        assert len(self._call_stack) > 0
        return self._call_stack[-1]

    def run(self, program: list[Def], entry: str = 'entry') -> Value:
        for tree in program:
            self.load(tree)
        if entry not in self._functions:
            self._abort(f'Function "{entry}" not found', '<entry point>')
        return self.call(self._functions[entry], [])

    def load(self, tree: Def) -> None:
        match tree:
            case LangDef():
                pass
            case TypeAlias():
                pass
            case FunDef(name, params, _, value):
                self._functions[name] = Callable(name, [p.name for p in params], [Return(value)])
            case MethodDef(name, params, _, _, body):
                self._functions[name] = Callable(name, [p.name for p in params], body)

    def call(self, fun_obj: Callable, arg_values: list[Value]) -> Value:
        frame = StackFrame()
        self._call_stack.append(frame)
        # load args
        for x, v in zip(fun_obj.param_names, arg_values):
            frame.put_value(x, v)
        # execute body
        return_value = self.exec(fun_obj.body)
        if return_value:
            return return_value
        else:
            self._abort('Function did not return', f'call {fun_obj.name}(...)')

    def exec(self, body: list[Stmt]) -> Optional[Value]:
        for stmt in body:
            match stmt:
                case Assign(var, value):
                    self._top_frame.put_value(var, self.eval(value))
                case Call(method_name, args) as node:
                    arg_values = [self.eval(arg) for arg in args]
                    return_value = self.call(self._functions[method_name], arg_values)
                    if node.var:
                        self._top_frame.put_value(node.var, return_value)
                case Assert(cond):
                    match self.eval(cond):
                        case BoolValue(True):
                            pass
                        case BoolValue(False):
                            note = ('Note: local variables: ' +
                                    ', '.join([f'{x}={pretty_print_value(v)}' for x, v in self._top_frame.all_values]))
                            self._abort('Assertion failure', pretty_print_tree(cond), note)
                        case v:
                            self._abort(f'illegal value: {pretty_print_value(v)}', pretty_print_tree(cond))
                case Return(None):
                    self._call_stack.pop()
                    return Nothing()
                case Return(value):
                    return_value = self.eval(value)
                    self._call_stack.pop()
                    return return_value
                case If(cond, then_body, else_body):
                    match self.eval(cond):
                        case BoolValue(True):
                            return_value = self.exec(then_body)
                            if return_value:
                                self._call_stack.pop()
                                return return_value
                        case BoolValue(False):
                            return_value = self.exec(else_body)
                            if return_value:
                                self._call_stack.pop()
                                return return_value
                        case v:
                            self._abort(f'illegal value: {pretty_print_value(v)}', pretty_print_tree(cond))
                case While(cond, body):
                    while True:
                        match self.eval(cond):
                            case BoolValue(True):
                                return_value = self.exec(body)
                                if return_value:
                                    self._call_stack.pop()
                                    return return_value
                            case BoolValue(False):
                                break  # loop terminates
                            case v:
                                self._abort(f'illegal value: {pretty_print_value(v)}', pretty_print_tree(cond))
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
                return self._top_frame.get_value(name)
            case Lambda(params, body):
                return Callable('<lambda>', params, [Return(body)])
            case App(fun, args):
                arg_values = [self.eval(arg) for arg in args]
                match fun:
                    case Var(f):
                        match predef.apply(f, arg_values):
                            case None:  # not a predefined function
                                if f in self._top_frame:
                                    match self._top_frame.get_value(f):
                                        case Callable() as c:
                                            return self.call(c, arg_values)
                                        case v:
                                            self._abort(f'illegal value: {pretty_print_value(v)}',
                                                        pretty_print_tree(fun))

                                if f in self._functions:
                                    return self.call(self._functions[f], arg_values)

                                self._abort(f'undefined name: {f}', pretty_print_tree(fun))
                            case value:
                                return value
            case IfThenElse(cond, then_branch, else_branch):
                match self.eval(cond):
                    case BoolValue(True):
                        return self.eval(then_branch)
                    case BoolValue(False):
                        return self.eval(else_branch)
                    case v:
                        self._abort(f'illegal value: {pretty_print_value(v)}', pretty_print_tree(cond))
            case _:
                raise RuntimeError

    def _abort(self, reason: str, where: str, detail: Optional[str] = None) -> None:
        print(f'Execution error: {reason}')
        print(f'  at {where}')
        if detail:
            print(detail)

        if self._debug:
            raise RuntimeError('aborted')
        else:
            sys.exit(1)
