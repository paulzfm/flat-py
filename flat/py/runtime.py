import sys
import traceback as tb
from typing import Any, Callable, Tuple, Generator, Optional

from isla.solver import ISLaSolver

from flat.py.isla_extensions import *
from flat.types import Type, value_has_type, LangType


def has_type(obj: Any, expected: Type) -> bool:
    match obj:
        case (int() | bool() | str()) as v:
            return value_has_type(v, expected)
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


def assert_type(value: Any, expected_type: Type):
    if not has_type(value, expected_type):
        print(f'Type mismatch:', file=sys.stderr)
        print(f'  expected type: {expected_type}', file=sys.stderr)
        print(f'  actual value:  {value}', file=sys.stderr)

        # Stack: frame of this fun, frame of the target fun, ...
        _print_stacktrace(1)


def assert_arg_type(value: Any, k: int, of_method: str, expected_type: Type):
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


def isla_generator(typ: LangType, formula: Optional[str]) -> Gen:
    assert typ is not None
    volume = 10
    solver = ISLaSolver(typ.grammar.isla_solver.grammar, formula,
                        structural_predicates={EBNF_DIRECT_CHILD, EBNF_KTH_CHILD},
                        max_number_free_instantiations=volume)
    while True:
        try:
            yield solver.solve().to_string()
        except StopIteration:
            volume *= 2
            solver = ISLaSolver(typ.grammar.isla_solver.grammar, formula,
                                structural_predicates={EBNF_DIRECT_CHILD, EBNF_KTH_CHILD},
                                max_number_free_instantiations=volume)


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
