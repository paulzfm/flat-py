from flat.py import raise_if


@raise_if(ZeroDivisionError, lambda x, y: y == 0)
def int_div(x: int, y: int) -> int:
    return x // y


def main():
    int_div(2, 2)
    int_div(2, 0)
