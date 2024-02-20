from dataclasses import dataclass

from flat.compiler.printer import quote
from flat.compiler.trees import Stmt


class Value:
    pass


@dataclass
class IntValue(Value):
    value: int


@dataclass
class BoolValue(Value):
    value: bool


@dataclass
class StringValue(Value):
    value: str


@dataclass
class Nothing(Value):
    pass


@dataclass
class SeqValue(Value):
    values: list[Value]


@dataclass
class FunObject(Value):
    name: str
    param_names: list[str]
    body: list[Stmt]


def pretty_value(value: Value) -> str:
    match value:
        case IntValue(n):
            return str(n)
        case BoolValue(True):
            return 'true'
        case BoolValue(False):
            return 'false'
        case StringValue(s):
            return quote(s)
        case Nothing():
            return 'none'
        case SeqValue(values):
            return '[' + ', '.join([pretty_value(v) for v in values]) + ']'
        case FunObject(name):
            return f'<function {name}>'