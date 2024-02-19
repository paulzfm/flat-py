import sys
from typing import Any, Tuple, Callable

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
            return False


def _show_error_paragraph(source_file: str, loc: Tuple[int, int], details: list[str]):
    line_no, col_no = loc
    print(f'File "{source_file}", line {line_no}')
    with open(source_file, 'r') as f:
        print('  ' + f.readlines()[line_no - 1].rstrip())
    print('  ' + '^'.rjust(col_no))
    for detail in details:
        print(' ' * (1 + col_no) + detail)


def assert_type(value: Any, value_col: int, expected_type: LangType | RefinementType):
    if not has_type(value, expected_type):
        # Stack: frame of this fun, frame of the target fun
        frame = sys._getframe(1)
        src = frame.f_globals['__source__']
        loc = (frame.f_locals['__line__'], value_col)

        print('Type mismatch')
        _show_error_paragraph(src, loc, [f'expected type: {expected_type}',
                                         f'actual value:  {value}'])
        sys.exit(1)


def assert_arg_type(value: Any, name: str, expected_type: LangType | RefinementType):
    if not has_type(value, expected_type):
        # Stack: frame of this fun, frame of the callee, frame of the caller, ...
        fun_name = sys._getframe(1).f_code.co_name
        caller_frame = sys._getframe(2)
        src = caller_frame.f_globals['__source__']
        loc = (caller_frame.f_locals['__line__'], 2)

        print('Argument type mismatch')
        _show_error_paragraph(src, loc, [f'expected type: {expected_type}',
                                         f'actual value:  {value}'])
        sys.exit(1)


def assert_pre(cond: Callable, cond_loc: Tuple[int, int], args: list[str, Any]):
    vs = [v for _, v in args]
    if not cond(*vs):
        # Stack: frame of this fun, frame of the callee, frame of the caller, ...
        callee_frame = sys._getframe(1)
        cond_src = callee_frame.f_globals['__source__']

        caller_frame = callee_frame.f_back
        call_src = caller_frame.f_globals['__source__']
        call_loc = (caller_frame.f_locals['__line__'], 2)

        print('Precondition violated')
        _show_error_paragraph(cond_src, cond_loc, ['inputs:'] + [f'  {x} = {v}' for x, v in args])
        _show_error_paragraph(call_src, call_loc, ['called here'])
        sys.exit(1)


def assert_post(cond: Callable, cond_loc: Tuple[int, int], args: list[str, Any],
                return_value: Any, return_col: Tuple[int, int]):
    vs = [v for _, v in args] + [return_value]
    if not cond(*vs):
        # Stack: frame of this fun, frame of the target fun
        frame = sys._getframe(1)
        src = frame.f_globals['__source__']
        return_loc = (frame.f_locals['__line__'], return_col)

        print('Postcondition violated')
        _show_error_paragraph(src, cond_loc, ['inputs:'] + [f'  {x} = {v}' for x, v in args] +
                              ['outputs:', f'  {return_value}'])
        _show_error_paragraph(src, return_loc, ['at this returning point'])
        sys.exit(1)
