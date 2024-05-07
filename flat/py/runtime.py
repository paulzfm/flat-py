import ast
import importlib.util
import inspect
import sys
from typing import Any, Callable, Generator, Optional

from isla.solver import ISLaSolver
from termcolor import cprint

from flat.py.errors import *
from flat.py.isla_extensions import *
from flat.typing import Type, value_has_type, LangType, ListType


def load_source_module(path: str) -> None:
    spec = importlib.util.spec_from_file_location('_.source', path)
    source_module = importlib.util.module_from_spec(spec)
    sys.modules['_.source'] = source_module
    spec.loader.exec_module(source_module)


def has_type(obj: Any, expected: Type) -> bool:
    match obj:
        case (int() | bool() | str()) as v:
            return value_has_type(v, expected)
        case list() as xs:
            match expected:
                case ListType(t):
                    return all(has_type(x, t) for x in xs)
                case _:
                    return False
        case _:
            raise RuntimeError(f'cannot check type for object {obj} with type {type(obj)}')


def assert_type(value: Any, value_loc: Loc, expected_type: Type):
    if not has_type(value, expected_type):
        raise TypeMismatch(str(expected_type), show_value(value), value_loc)


def assert_arg_type(value: Any, k: int, of_method: str, expected_type: Type):
    if not has_type(value, expected_type):
        raise ArgTypeMismatch(str(expected_type), show_value(value), k, of_method)


def assert_pre(cond: bool, args: list[Tuple[str, Any]], of_method: str):
    if not cond:
        raise PreconditionViolated(of_method, [(name, show_value(v)) for name, v in args])


def assert_post(cond: bool, args: list[Tuple[str, Any]], return_value: Any, return_value_loc: Loc, of_method: str):
    if not cond:
        raise PostconditionViolated(of_method, [(name, show_value(v)) for name, v in args],
                                    show_value(return_value), return_value_loc)


def show_value(value: Any):
    match value:
        case str() as s:
            return ast.unparse(ast.Constant(s))
        case _:
            return str(value)


Gen = Generator[Any, None, None]


def constant_generator(value: Any) -> Gen:
    while True:
        yield value


def isla_generator(typ: LangType, formula: Optional[str] = None) -> Gen:
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


def fuzz(target: Callable, times: int, args_producer: Gen, verbose: bool = False) -> None:
    # copy __source__, __line__ from the last frame
    frame = inspect.currentframe()
    back_frame = frame.f_back
    if '__line__' in back_frame.f_locals:
        frame.f_locals['__line__'] = back_frame.f_locals['__line__']
        frame.f_globals['__source__'] = back_frame.f_globals['__source__']

    for _ in range(times):
        inputs = next(args_producer)
        try:
            target(*inputs)
        except Error as err:
            cprint(f'[Error] {target.__name__}{tuple(inputs)}', 'red')
            err.print()
            continue
        except Exception as exc:
            cprint(f'[Error] {target.__name__}{tuple(inputs)}', 'red')
            cprint('{}: {}'.format(type(exc).__name__, exc), 'red')
            continue
        else:
            if verbose:
                cprint(f'[OK] {target.__name__}{tuple(inputs)}', 'green')


def run_main(main: Callable) -> None:
    try:
        main()
    except Error as err:
        err.print()
