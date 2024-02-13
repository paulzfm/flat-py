from dataclasses import dataclass
from typing import Tuple, Optional

from flat.compiler.trees import Pos


@dataclass
class Error:
    summary: str  # main message
    pos: Pos  # main position
    explanation: Optional[list[str]] = None  # multi-line detailed explanation


class ParsingError(Error):
    def __init__(self, at: Tuple[int, int], expected: list[str]):
        if len(expected) == 1:
            msg = expected[0]
        else:
            msg = f"one of {', '.join(expected)}"
        super().__init__('Parsing error', Pos(at, at), [f'expect {msg}'])


class UndefinedName(Error):
    def __init__(self, pos: Pos):
        super().__init__('Undefined name', pos)


class RedefinedName(Error):
    def __init__(self, conflict_with: str, pos: Pos):
        super().__init__('Redefined name', pos, f'conflict with {conflict_with}')


class ExpectSimpleType(Error):
    def __init__(self, pos: Pos):
        super().__init__('Expect a simple type', pos, 'this type is not allowed here')


class ArityMismatch(Error):
    def __init__(self, expected: int, actual: int, pos: Pos):
        super().__init__('Arity mismatch', pos, [f'expect:    {expected} argument(s)'
                                                 f'but given: {actual}'])


class TypeMismatch(Error):
    def __init__(self, expected: str, actual: str, pos: Pos):
        super().__init__('Type mismatch', pos, [f'expect:    {expected}'
                                                f'but found: {actual}'])


class MissingTypeAnnot(Error):
    def __init__(self, pos: Pos):
        super().__init__('Missing type annotation', pos)


class InvalidPath(Error):
    def __init__(self, reason: str, pos: Pos):
        super().__init__('Invalid path', pos, [reason])


class MissingStartRule(Error):
    def __init__(self, pos: Pos):
        super().__init__('Missing start rule', pos)


class InvalidClause(Error):
    def __init__(self, reason: str, pos: Pos, hint: Optional[str] = None):
        details = [reason]
        if hint:
            details.append(f'Hint: {hint}')
        super().__init__('Invalid clause', pos, details)


class UnusedRule(Error):
    def __init__(self, pos: Pos):
        super().__init__('Rule is defined but not used', pos, ['Hint: you may delete this rule'])


class RuntimeUnsat(Error):
    def __init__(self, cond: str, env: list[Tuple[str, Optional[str], str]], pos: Pos):
        details = []
        for name, note, value in env:
            details.append((f'{name} ({note})' if note else name) + f' = {value}')
        super().__init__(f'Condition "{cond}" is unsat', pos, details)


class AssertionFailure(Error):
    def __init__(self, pos: Pos):
        super().__init__(f'Assertion failure', pos)
