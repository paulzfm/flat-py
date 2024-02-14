from typing import TypeVar, Generic, Tuple

from flat.compiler.pos import Pos
from flat.compiler.trees import NameTree

T = TypeVar('T')


class Context(Generic[T]):
    def __init__(self):
        self._items: dict[str, Tuple[Pos, T]] = {}

    def __contains__(self, name: str) -> bool:
        return name in self._items

    def __getitem__(self, name: str) -> T:
        return self._items[name][1]

    def get_pos(self, name: str) -> Pos:
        return self._items[name][0]

    def update(self, key: NameTree, value: T) -> None:
        self._items[key.name] = (key.pos, value)
