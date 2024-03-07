import re

from string_utils._regex import CAMEL_CASE_REPLACE_RE
from string_utils.errors import InvalidInputError
from string_utils.validation import is_string, is_camel_case, is_snake_case, is_full_string

from flat.lib import select_all, xpath, select
from flat.py import lang, fuzz, ensures

CamelCase = lang('CamelCase', """
start: first rest+;
first: (lower | upper) lower*;
rest: upper lower*;
upper: [A-Z];
lower: [a-z];
""")


def camel_words(s: str) -> list[str]:
    return [
        word.lower() for word in
        [select(xpath(CamelCase, "..first"), s)] + select_all(xpath(CamelCase, "..rest"), s)
    ]


SnakeCase = lang('SnakeCase', """
start: first rest+;
first: word;
rest: "_" word;
word: [a-z]+;
""")


def snake_words(s: str) -> list[str]:
    return select_all(xpath(SnakeCase, "..word"), s)


@ensures(lambda camel, _, snake: camel_words(camel) == snake_words(snake))
def python_string_camel_to_snake(input_string: CamelCase, separator='_') -> SnakeCase:
    """
    Source: https://github.com/daveoncode/python-string-utils/blob/master/string_utils/manipulation.py
    Convert a camel case string into a snake case one.
    (The original string is returned if is not a valid camel case string)

    *Example:*

    >>> python_string_camel_to_snake('ThisIsACamelStringTest') # returns 'this_is_a_camel_case_string_test'

    :param input_string: String to convert.
    :type input_string: str
    :param separator: Sign to use as separator.
    :type separator: str
    :return: Converted string.
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_camel_case(input_string):
        return input_string

    return CAMEL_CASE_REPLACE_RE.sub(lambda m: m.group(1) + separator, input_string).lower()


@ensures(lambda snake, flag, _, camel: snake_words(snake) == camel_words(camel))
def python_string_snake_to_camel(input_string: SnakeCase, upper_case_first: bool = True,
                                 separator: str = '_') -> CamelCase:
    """
    Convert a snake case string into a camel case one.
    (The original string is returned if is not a valid snake case string)

    *Example:*

    >>> python_string_snake_to_camel('the_snake_is_green') # returns 'TheSnakeIsGreen'

    :param input_string: String to convert.
    :type input_string: str
    :param upper_case_first: True to turn the first letter into uppercase (default).
    :type upper_case_first: bool
    :param separator: Sign to use as separator (default to "_").
    :type separator: str
    :return: Converted string
    """
    if not is_string(input_string):
        raise InvalidInputError(input_string)

    if not is_snake_case(input_string, separator):
        return input_string

    tokens = [s.title() for s in input_string.split(separator) if is_full_string(s)]

    if not upper_case_first:
        tokens[0] = tokens[0].lower()

    out = ''.join(tokens)

    return out


@ensures(lambda camel, snake: camel_words(camel) == snake_words(snake))
def sertit_camel_to_snake(snake_str: CamelCase) -> SnakeCase:
    """
    Source: https://sertit-utils.readthedocs.io/en/stable/_modules/sertit/strings.html#camel_to_snake_case
    Convert a :code:`CamelCase` string to :code:`snake_case`.

    Args:
        snake_str (str): String formatted in CamelCase

    Returns:
        str: String formatted in snake_case

    Example:
        >>> sertit_camel_to_snake("CamelCase")
        "camel_case"
    """
    return "".join(["_" + c.lower() if c.isupper() else c for c in snake_str]).lstrip(
        "_"
    )


@ensures(lambda snake, camel: snake_words(snake) == camel_words(camel))
def sertit_snake_to_camel(snake_str: SnakeCase) -> CamelCase:
    """
    Convert a :code:`snake_case` string to :code:`CamelCase`.

    Args:
        snake_str (str): String formatted in snake_case

    Returns:
        str: String formatted in CamelCase

    Example:
        >>> sertit_snake_to_camel("snake_case")
        "SnakeCase"
    """
    return "".join((w.capitalize() for w in snake_str.split("_")))


@ensures(lambda camel, snake: camel_words(camel) == snake_words(snake))
def marko_camel_to_snake(name: CamelCase) -> SnakeCase:
    """
    Source: https://github.com/frostming/marko/blob/master/marko/helpers.py
    Takes a camelCased string and converts to snake_case.
    """
    pattern = r"[A-Z][a-z]+|[A-Z]+(?![a-z])"
    return "_".join(map(str.lower, re.findall(pattern, name)))


def main():
    fuzz(python_string_camel_to_snake, 20)
    fuzz(sertit_camel_to_snake, 20)
    fuzz(marko_camel_to_snake, 20)
    # fuzz(python_string_snake_to_camel, 20)
    # fuzz(python_string_snake_to_camel, 20, {'upper_case_first': constant_generator(False)})
    # fuzz(sertit_snake_to_camel, 20)
