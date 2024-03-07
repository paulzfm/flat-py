from random import randint
from typing import Union

from string_utils.manipulation import __RomanNumbers

from flat.py import requires, lang, fuzz

RomanNumber = lang('RomanNumber', """
start: digit+;
digit: "I" | "V" | "X" | "L" | "C" | "D" | "M";
""")


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
    # fuzz(roman_encode, 100, {'input_number': number_gen()})
    fuzz(roman_decode, 100)
