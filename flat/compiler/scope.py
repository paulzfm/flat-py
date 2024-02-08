from typing import Optional

from flat.compiler.trees import SimpleType, RefinementType

NormalForm = SimpleType | RefinementType


class Scope:
    def __init__(self, parent: Optional = None):
        self.parent: Optional[Scope] = parent
        self._terms: dict[str, NormalForm] = {}
        self._types: dict[str, NormalForm] = {}

    def lookup_term(self, name: str) -> Optional[NormalForm]:
        if name in self._terms:
            return self._terms[name]
        if self.parent:
            return self.parent.lookup_term(name)

    def lookup_type(self, name: str) -> Optional[NormalForm]:
        if name in self._types:
            return self._types[name]
        if self.parent:
            return self.parent.lookup_type(name)

    def has_defined(self, name: str) -> bool:
        return name in self._terms or name in self._types

    def update_term(self, name: str, typ: NormalForm) -> None:
        self._terms[name] = typ

    def update_type(self, name: str, typ: NormalForm) -> None:
        self._types[name] = typ
