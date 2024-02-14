from dataclasses import dataclass
from typing import Tuple, Optional

from flat.compiler.pos import Pos


@dataclass
class Error:
    summary: str  # main message
    pos: Pos  # main position
    explanation: Optional[list[str]] = None  # multi-line detailed explanation
    attachment: Optional[Tuple[Pos, list[str]]] = None  # one more associated error position with explanations


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
    def __init__(self, conflict_with: Pos, pos: Pos):
        super().__init__('Redefined name', pos, [], (conflict_with, ['already defined here']))


class ExpectSimpleType(Error):
    def __init__(self, pos: Pos):
        super().__init__('Expect a simple type', pos, ['this type is not allowed here'])


class ArityMismatch(Error):
    def __init__(self, expected: int, actual: int, pos: Pos):
        super().__init__('Arity mismatch', pos, [f'expect:    {expected} argument(s)',
                                                 f'but given: {actual}'])


class TypeMismatch(Error):
    def __init__(self, expected: str, actual: str, pos: Pos):
        super().__init__('Type mismatch', pos, [f'expect:    {expected}',
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


class RuntimeTypeError(Error):
    pass


class RuntimeTypeMismatch(RuntimeTypeError):
    def __init__(self, expected: str, actual_value: str, pos: Pos):
        super().__init__('Type mismatch', pos, [f'expected type: {expected}',
                                                f'actual value:  {actual_value}'])


class PreconditionViolated(RuntimeTypeError):
    def __init__(self, method: str, args: list[Tuple[str, str]], at: Pos, cond_pos: Pos):
        """
        Constructor.
        :param method: method name.
        :param args: a list of formal argument names and their pretty-printed values.
        :param at: the position of the call statement where violation occurred.
        :param cond_pos: the position of the precondition.
        """
        details = ['inputs:'] + [f'  {name} = {value}' for name, value in args]
        super().__init__(f'Precondition of method {method} violated', cond_pos, details,
                         (at, ['caused by this method call']))


class PostconditionViolated(RuntimeTypeError):
    def __init__(self, args: list[Tuple[str, str]], returns: Tuple[str, str], at: Pos, cond_pos: Pos):
        """
        Constructor.
        :param args: a list of formal argument names and their pretty-printed values.
        :param returns: the return param name and its pretty-printed value.
        :param at: the position of the return statement where violation occurred.
        :param cond_pos: the position of the postcondition.
        """
        details = ['inputs:'] + [f'  {name} = {value}' for name, value in args] + [
            f'outputs:', f'  {returns[0]} = {returns[1]}']
        super().__init__(f'Postcondition violated', cond_pos, details, (at, ['at this returning point']))


class AssertionFailure(RuntimeTypeError):
    def __init__(self, pos: Pos):
        super().__init__(f'Assertion failure', pos)
