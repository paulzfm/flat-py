from dataclasses import dataclass

from flat.types import Type


@dataclass(frozen=True)
class FunType(Type):
    takes: list[Type]
    returns: Type
