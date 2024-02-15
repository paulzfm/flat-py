import ast
import sys
from dataclasses import dataclass
from typing import Any, Tuple

from flat.compiler.grammar import LangObject
from flat.py import RefinementType


def has_type(value: Any, expected: LangObject | RefinementType) -> bool:
    match expected:
        case LangObject() as language:
            return isinstance(value, str) and value in language
        case RefinementType(LangObject() as language, cond):
            return isinstance(value, str) and value in language and cond(value)
        case RefinementType(base, cond):
            return isinstance(value, base) and cond(value)


class FlatError:
    def print_error(self) -> None:
        raise NotImplementedError

    def print_stacktrace(self) -> None:
        raise NotImplementedError


def format_error(source_file: str, loc: Tuple[int, int], details: list[str]):
    line_no, col_no = loc
    lines = [f'File "{source_file}", line {line_no}\n']
    with open(source_file, 'r') as f:
        lines.append('  ' + f.readlines()[line_no - 1])
    width = col_no + 1
    lines.append('^'.rjust(width) + '\n')
    for detail in details:
        lines.append(detail.rjust(width) + '\n')
    return ''.join(lines)


@dataclass
class TypeMismatch(FlatError):
    actual_var_name: str
    expected_type: str
    source_file: str
    loc: Tuple[int, int]

    def print_error(self) -> None:
        print('Type mismatch')
        print(format_error(self.source_file, self.loc, [f'expected type: {self.expected_type}',
                                                        f'actual value:  {eval(self.actual_var_name)}']))


@dataclass
class ArgTypeMismatch(FlatError):
    arg: str
    expected_type: str
    source_file: str
    loc: Tuple[int, int]

    def print_error(self) -> None:
        print('Type mismatch')
        print(format_error(self.source_file, self.loc, [f'expected type: {self.expected_type}',
                                                        f'actual value:  {eval(self.arg)}']))


@dataclass
class PreconditionViolated(FlatError):
    source_file: str
    cond_loc: Tuple[int, int]
    args: list[str]

    def print_error(self) -> None:
        print('Precondition violated')
        details = ['inputs:'] + [f'  {x} = {eval(x)}' for x in self.args]
        print(format_error(self.source_file, self.cond_loc, details))


@dataclass
class PostconditionViolated(FlatError):
    source_file: str
    cond_loc: Tuple[int, int]
    return_loc: Tuple[int, int]
    args: list[ast.expr]

    def print_error(self) -> None:
        print('Postcondition violated')
        details = ['inputs:'] + [f'  {x} = {eval(x)}' for x in self.args] + [
            f'outputs:', f'  {eval("__return__")}']
        print(format_error(self.source_file, self.cond_loc, details))
        print(format_error(self.source_file, self.return_loc, ['at this returning point']))


def assert_true(cond: bool, err: FlatError) -> None:
    if not cond:
        err.print_error()
        sys.exit(1)
