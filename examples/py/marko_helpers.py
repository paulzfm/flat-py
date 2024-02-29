"""
Source: marko/marko/helpers.py
Helper functions and data structures
"""

import random
import re
import string
from typing import Container, Iterable

from flat.lib import select_all, xpath, implies
from flat.py import lang, ensures, returns

CamelCase = lang('CamelCase', """
start: "" | first rest*;
first: (lower | upper) lower*;
rest: upper lower*;
upper: [A-Z];
lower: [a-z];
""")

SnakeCase = lang('SnakeCase', """
start: "" | first rest*;
first: word;
rest: "_" word;
word: [a-z]+;
""")


def camel_case_words(s: str) -> list[str]:
    return select_all(xpath(CamelCase, "..first"), s) + select_all(xpath(CamelCase, "..rest"), s)


def snake_case_words(s: str) -> list[str]:
    return select_all(xpath(SnakeCase, "..word"), s)


@ensures(lambda c, s: camel_case_words(c) == snake_case_words(s))
def camel_to_snake_case(name: CamelCase) -> SnakeCase:
    """Takes a camelCased string and converts to snake_case."""
    pattern = r"[A-Z][a-z]+|[A-Z]+(?![a-z])"
    return "_".join(map(str.lower, re.findall(pattern, name)))


def is_paired(text: Iterable[str], open: str = "(", close: str = ")") -> bool:
    """Check if the text only contains:
    1. blackslash escaped parentheses, or
    2. parentheses paired.
    """
    count = 0
    escape = False
    for c in text:
        if escape:
            escape = False
        elif c == "\\":
            escape = True
        elif c == open:
            count += 1
        elif c == close:
            if count == 0:
                return False
            count -= 1
    return count == 0


@returns(lambda label: label.strip())
def normalize_label(label: str) -> str:
    """Return the normalized form of link label."""
    return re.sub(r"\s+", " ", label).strip().casefold()


def end_of(text: str, end: int | None) -> int:
    return len(text) if end is None else end


@ensures(lambda s, t, start, end, dis, i: implies(i == -1, t == "" or t not in s))
@ensures(lambda s, t, start, end, dis, i: implies(i == -2, any([w in s for w in dis])))
@ensures(lambda s, t, start, end, dis, i: implies(i > 0, s[i:].startswith(t) and start <= i < end_of(s, end)))
def find_next(
        text: str,
        target: Container[str],
        start: int = 0,
        end: int | None = None,
        disallowed: Container[str] = (),
) -> int:
    """Find the next occurrence of target in text, and return the index
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


@ensures('_[1] in spaces')
@ensures('text == _[0] + _[1] + _[2]')
def partition_by_spaces(text: str, spaces: str = " \t") -> tuple[str, str, str]:
    """Split the given text by spaces or tabs, and return a tuple of
    (start, delimiter, remaining). If spaces are not found, the latter
    two elements will be empty.
    """
    start = end = -1
    for i, c in enumerate(text):
        if c in spaces:
            if start >= 0:
                continue
            start = i
        elif start >= 0:
            end = i
            break
    if start < 0:
        return text, "", ""
    if end < 0:
        return text[:start], text[start:], ""
    return text[:start], text[start:end], text[end:]


def text_producer(max_len: int = 25):
    alphabet = string.printable + '\n'
    while True:
        length = random.randrange(0, max_len)
        yield ''.join(random.choice(alphabet) for _ in range(length))


def main():
    # fuzz(normalize_label, 10, {'label': text_producer()})
    # fuzz(partition_by_spaces, 10, {'text': text_producer()})
    # fuzz(find_next, 100, {'text': text_producer(), 'target': constant_generator('\n')})

    # failure case
    assert '0QGu\\\n'.find('\n') > 0
    find_next('0QGu\\\n', '\n')
    # assert '\tUulH!'.find('sH') == -1
    # find_next('\tUulH!', 'sH')
