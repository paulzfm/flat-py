from random import randint
from typing import Union

from string_utils.manipulation import __RomanNumbers

from flat.py import requires, lang, fuzz, refine
from flat.py.runtime import isla_generator
from flat.py.utils import print_fuzz_report

RomanSyntax = lang('RomanSyntax', """
start: thousand? hundred? tens? units?;
thousand: "M"{1,3};
hundred: "C"{1,3} | "CD" | "D" "C"{0,3} | "CM";
tens: "X"{1,3} | "XL" | "L" "X"{0,3} | "XC";
units: "I"{1,3} | "IV" | "V" "I"{0,3} | "IX";
""")

RomanNumber = refine(RomanSyntax, '_ != ""')


@requires(lambda num: 1 <= int(num) <= 3999)
def roman_encode(input_number: Union[str, int]) -> RomanNumber:
    """
    Convert the given number/string into a roman number.

    The passed input must represents a positive integer in the range 1-3999 (inclusive).

    Why this limit? You may be wondering:

    1. zero is forbidden since there is no related representation in roman numbers
    2. the upper bound 3999 is due to the limitation in the ascii charset\
    (the higher quantity sign displayable in ascii is "M" which is equal to 1000, therefore based on\
    roman numbers rules we can use 3 times M to reach 3000 but we can't go any further in thousands without\
    special "boxed chars").

    *Examples:*

    >>> roman_encode(37) # returns 'XXXVIII'
    >>> roman_encode('2020') # returns 'MMXX'

    :param input_number: An integer or a string to be converted.
    :type input_number: Union[str, int]
    :return: Roman number string.
    """
    return __RomanNumbers.encode(input_number)


def roman_decode(input_string: RomanNumber) -> int:
    """
    Decode a roman number string into an integer if the provided string is valid.

    *Example:*

    >>> roman_decode('VII') # returns 7

    :param input_string: (Assumed) Roman number
    :type input_string: str
    :return: Integer value
    """
    return __RomanNumbers.decode(input_string)


def number_gen():
    while True:
        yield randint(1, 3999)


def main():
    report = fuzz(roman_encode, 100, using={'input_number': number_gen()})
    print_fuzz_report(report)

    report = fuzz(roman_decode, 100)
    print_fuzz_report(report)

    g = number_gen()
    for _ in range(100):
        n = next(g)
        assert roman_decode(roman_encode(n)) == n

    g = isla_generator(RomanSyntax)
    for _ in range(100):
        r = next(g)
        if r != '':
            assert roman_encode(roman_decode(r)) == r
