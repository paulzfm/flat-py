from typing import TypeVar, Callable, Tuple

T = TypeVar('T')


def classify(f: Callable[[T], bool], xs: list[T]) -> Tuple[list[T], list[T]]:
    passed = []
    failed = []
    for x in xs:
        if f(x):
            passed.append(x)
        else:
            failed.append(x)

    return passed, failed
