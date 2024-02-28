from dataclasses import dataclass

from flat.core_lang.ast import Expr
from flat.types import Cond, Value


@dataclass
class CoreCond(Cond):
    expr: Expr

    def apply(self, value: Value) -> bool:
        raise NotImplementedError
