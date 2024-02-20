import sys
import traceback as tb
from typing import Any, Callable, Iterable

from flat.py import RefinementType, LangType


def has_type(value: Any, expected: LangType | RefinementType) -> bool:
    match expected:
        case LangType(language):
            return isinstance(value, str) and value in language
        case RefinementType(LangType(language), cond):
            return isinstance(value, str) and value in language and cond(value)
        case RefinementType(base, cond):
            return isinstance(value, base) and cond(value)
        case _:
            assert False


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


def assert_type(value: Any, expected_type: LangType | RefinementType):
    if not has_type(value, expected_type):
        print(f'Type mismatch:', file=sys.stderr)
        print(f'  expected type: {expected_type}', file=sys.stderr)
        print(f'  actual value:  {value}', file=sys.stderr)

        # Stack: frame of this fun, frame of the target fun, ...
        _print_stacktrace(1)


def assert_arg_type(value: Any, k: int, of_method: str, expected_type: LangType | RefinementType):
    if not has_type(value, expected_type):
        print(f'Type mismatch for argument {k} of method {of_method}:', file=sys.stderr)
        print(f'  expected type: {expected_type}', file=sys.stderr)
        print(f'  actual value:  {value}', file=sys.stderr)

        # Stack: frame of this fun, frame of the callee, frame of the caller, ...
        _print_stacktrace(2)


def assert_pre(cond: Callable, args: list[str, Any], of_method: str):
    vs = [v for _, v in args]
    if not cond(*vs):
        print(f'Precondition of method {of_method} violated:', file=sys.stderr)
        print('  inputs:', file=sys.stderr)
        for x, v in args:
            print(f'    {x} = {v}', file=sys.stderr)

        # Stack: frame of this fun, frame of the callee, frame of the caller, ...
        _print_stacktrace(1)


def assert_post(cond: Callable, args: list[str, Any], return_value: Any):
    vs = [v for _, v in args] + [return_value]
    if not cond(*vs):
        print(f'Postcondition violated:', file=sys.stderr)
        print('  inputs:', file=sys.stderr)
        for x, v in args:
            print(f'    {x} = {v}', file=sys.stderr)
        print(f'  output: {return_value}', file=sys.stderr)

        # Stack: frame of this fun, frame of the target fun, ...
        _print_stacktrace(1)


def fuzz_test(target: Callable, n: int, generators: list[Iterable[Any]]) -> None:
    for i in range(n):
        inputs = []
        for g in generators:
            inputs.append(next(g))

        print(f'Fuzz test: {target.__name__} with {inputs}')
        target(*inputs)


def isla_generator(typ: LangType) -> Iterable[str]:
    while True:
        yield typ.obj.produce()
