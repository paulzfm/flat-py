import ast
import sys
import traceback as tb
from typing import Any, Callable, Tuple, Generator, Optional

from isla.solver import ISLaSolver

from flat.py import LangObject, TypeNorm, BaseType


def has_type(value: Any, expected: LangObject | TypeNorm) -> bool:
    match expected:
        case LangObject() as language:
            return isinstance(value, str) and value in language
        case TypeNorm(base, cond, lang_object):
            match base:
                case BaseType.Int:
                    if not isinstance(value, int):
                        return False
                case BaseType.Bool:
                    if not isinstance(value, bool):
                        return False
                case _:
                    if not isinstance(value, str):
                        return False
                    if base == BaseType.Lang:
                        assert lang_object is not None
                        if value not in lang_object:
                            return False
            if cond:
                return eval(ast.unparse(cond), globals(), {'_': value})
            else:
                return True
        case _:
            raise RuntimeError(f"illegal type: {expected}")


def _print_stacktrace(depth: int):
    summaries = []
    for frame, _ in tb.walk_stack(sys._getframe(depth).f_back):
        if '__line__' in frame.f_locals:
            source = frame.f_globals['__source__']
            line = frame.f_locals['__line__']
        else:
            source = frame.f_code.co_filename
            line = frame.f_lineno

        summaries.append(tb.FrameSummary(source, line, frame.f_code.co_name))

    stack_summary = tb.StackSummary.from_list(summaries)
    print('Traceback (most recent call last):', file=sys.stderr)
    for line in stack_summary.format():
        print(line, end='', file=sys.stderr)
    sys.exit(1)


def assert_type(value: Any, expected_type: LangObject | TypeNorm):
    if not has_type(value, expected_type):
        print(f'Type mismatch:', file=sys.stderr)
        print(f'  expected type: {expected_type}', file=sys.stderr)
        print(f'  actual value:  {value}', file=sys.stderr)

        # Stack: frame of this fun, frame of the target fun, ...
        _print_stacktrace(1)


def assert_arg_type(value: Any, k: int, of_method: str, expected_type: LangObject | TypeNorm):
    if not has_type(value, expected_type):
        print(f'Type mismatch for argument {k} of method {of_method}:', file=sys.stderr)
        print(f'  expected type: {expected_type}', file=sys.stderr)
        print(f'  actual value:  {value}', file=sys.stderr)

        # Stack: frame of this fun, frame of the callee, frame of the caller, ...
        _print_stacktrace(2)


def assert_pre(cond: bool, args: list[Tuple[str, Any]], of_method: str):
    if not cond:
        print(f'Precondition of method {of_method} violated:', file=sys.stderr)
        print('  inputs:', file=sys.stderr)
        for x, v in args:
            print(f'    {x} = {v}', file=sys.stderr)

        # Stack: frame of this fun, frame of the callee, frame of the caller, ...
        _print_stacktrace(1)


def assert_post(cond: bool, args: list[Tuple[str, Any]], return_value: Any):
    if not cond:
        print(f'Postcondition violated:', file=sys.stderr)
        print('  inputs:', file=sys.stderr)
        for x, v in args:
            print(f'    {x} = {v}', file=sys.stderr)
        print(f'  output: {return_value}', file=sys.stderr)

        # Stack: frame of this fun, frame of the target fun, ...
        _print_stacktrace(1)


Gen = Generator[Any, None, None]


def isla_generator(typ: TypeNorm, formula: Optional[str]) -> Gen:
    assert typ.lang_object is not None
    volume = 10
    solver = ISLaSolver(typ.lang_object.isla_solver.grammar, formula,
                        max_number_free_instantiations=volume)
    while True:
        try:
            yield solver.solve().to_string()
        except StopIteration:
            volume *= 2
            solver = ISLaSolver(typ.lang_object.isla_solver.grammar, formula,
                                max_number_free_instantiations=volume)
            print('[info] solver reset')


def producer(generator: Gen, test: Callable[[Any], bool]) -> Gen:
    while True:
        value = next(generator)
        if test(value):
            yield value


def product_producer(producers: list[Gen], test: Callable[[Any], bool]) -> Gen:
    while True:
        values = [next(p) for p in producers]
        if test(*values):
            yield values


def fuzz_test(target: Callable, times: int, args_producer: Gen) -> None:
    for _ in range(times):
        inputs = next(args_producer)
        print(f'Fuzz test: {target.__name__} with {inputs}')
        target(*inputs)
