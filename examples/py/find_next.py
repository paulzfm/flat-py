import random
import string
from typing import Container

from flat.lib import implies
from flat.py import ensures, fuzz
from flat.py.runtime import constant_generator


@ensures(lambda s, t, start, end, dis, i: implies(i == -1, t == "" or t not in s))
@ensures(lambda s, t, start, end, dis, i: implies(i == -2, any([w in s for w in dis])))
@ensures(lambda s, t, start, end, dis, i: implies(i > 0, s[i:].startswith(t) and start <= i < end if end else len(s)))
def find_next(
        text: str,
        target: Container[str],
        start: int = 0,
        end: int | None = None,
        disallowed: Container[str] = (),
) -> int:
    """
    Source: https://github.com/frostming/marko/blob/master/marko/helpers.py

    Find the next occurrence of target in text, and return the index
    Characters are escaped by backslash.
    Optional disallowed characters can be specified, if found, the search
    will fail with -2 returned. Otherwise, -1 is returned if not found.
    """
    if end is None:
        end = len(text)
    i = start
    escaped = False
    while i < end:
        c = text[i]
        if escaped:
            escaped = False
        elif c in target:
            return i
        elif c in disallowed:
            return -2
        elif c == "\\":
            escaped = True
        i += 1
    return -1


def text_producer(max_len: int = 25):
    alphabet = string.printable + '\n'
    while True:
        length = random.randrange(0, max_len)
        yield ''.join(random.choice(alphabet) for _ in range(length))


def main():
    fuzz(find_next, 500, {'text': text_producer(), 'target': constant_generator('\n')})
