from typing import Callable, TypeVar

from frozenlist import FrozenList

T = TypeVar('T')


def empty(xs: FrozenList[T]) -> bool:
    return len(xs) == 0


def nonempty(xs: FrozenList[T]) -> bool:
    return len(xs) > 0


def forall(xs: FrozenList[T], p: Callable[[T], bool]) -> bool:
    return all(p(x) for x in xs)


def exists(xs: FrozenList[T], p: Callable[[T], bool]) -> bool:
    return any(p(x) for x in xs)


def first(xs: FrozenList[T]) -> T:
    return xs[0]


def last(xs: FrozenList[T]) -> T:
    return xs[-1]


def flatten(xss: FrozenList[FrozenList[T]]) -> FrozenList[T]:
    return FrozenList(x for xs in xss for x in xs)
