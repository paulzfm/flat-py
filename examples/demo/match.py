from typing import Literal

from flat.py import refine, ensures

pos = refine(int, '_ > 0')
neg = refine(int, '_ < 0')


@ensures(lambda n, out: out == (n >= 0))
def is_nat(n: int) -> bool:
    return n == 0 or isinstance(n, pos)


@ensures(lambda n, s: s == (1 if n > 0 else 0 if n == 0 else -1))
def sign(n: int) -> Literal[1, 0, -1]:
    match n:
        case pos():
            return 1
        case 0:
            return 0
        case neg():
            return -1


def same_sign(n1: int, n2: int):
    match n1, n2:
        # NOTE: or patterns may lead to unbound names
        case (pos(), pos()):
            return True
        case (neg(), neg()):
            return True
        case (0, 0):
            return True
        case _:
            return False


def main():
    for n in range(-10, 10):
        is_nat(n)
        sign(n)
        if n % 2 == 0:
            same_sign(n, n)
        else:
            same_sign(n, -n)
