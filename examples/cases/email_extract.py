import re
import time
from typing import Callable

from jionlp.rule.rule_pattern import EMAIL_PATTERN
from unstructured.nlp.patterns import EMAIL_ADDRESS_PATTERN

from flat.errors import Error
from flat.py import list_of, lang, ensures, fuzz
from flat.types import RFC_Email


def unstructured(text: str) -> list_of(RFC_Email):
    return re.findall(EMAIL_ADDRESS_PATTERN, text.lower())


def _extract_base(pattern, text, with_offset=False):
    if with_offset:
        results = [{'text': item.group(1),
                    'offset': (item.span()[0] - 1, item.span()[1] - 1)}
                   for item in pattern.finditer(text)]
    else:
        results = [item.group(1) for item in pattern.finditer(text)]

    return results


def jionlp(text: str) -> list_of(RFC_Email):
    email_pattern = re.compile(EMAIL_PATTERN)

    text = ''.join(['龥', text, '龥'])
    results = _extract_base(email_pattern, text, with_offset=False)
    return results


# Tests
class Counter:
    def __init__(self) -> None:
        self.value = 0

    def inc(self) -> None:
        self.value += 1


def run(fun: Callable, text: str, passed: Counter) -> None:
    try:
        fun(text)
    except Error:
        print(f'{fun.__name__} failure on: {text}')
    else:
        passed.inc()


VALID_EMAIL_ADDRESSES = [
    'simple@example.com',
    'very.common@example.com',
    'FirstName.LastName@EasierReading.org',
    'x@example.com',
    'long.email-address-with-hyphens@and.subdomains.example.com',
    'user.name+tag+sorting@example.com',
    'name/surname@example.com',
    'admin@example',
    'example@s.example',
    '" "@example.org',
    '"john..doe"@example.org',
    'mailhost!username@example.org',
    '"very.(),:;<>[]\\".VERY.\\"very@\\\\ \\"very\\".unusual"@strange.example.com',
    'user%example.com@example.org',
    'user-@example.org',
    'postmaster@[123.123.123.123]',
    'postmaster@[IPv6:2001:0db8:85a3:0000:0000:8a2e:0370:7334]',
    '_test@[IPv6:2001:0db8:85a3:0000:0000:8a2e:0370:7334]'
]


@ensures('len(_) > 0')
def unstructured_pos(text: str) -> list_of(RFC_Email):
    return unstructured(text)


@ensures('len(_) > 0')
def jionlp_pos(text: str) -> list_of(RFC_Email):
    return jionlp(text)


def positive_test() -> None:
    unstructured_passed = Counter()
    unstructured_time = 0
    jionlp_passed = Counter()
    jionlp_time = 0

    for email in VALID_EMAIL_ADDRESSES:
        text = f'To: <{email}>'

        t = time.process_time()
        run(unstructured_pos, text, unstructured_passed)
        unstructured_time += (time.process_time() - t) * 1000

        t = time.process_time()
        run(jionlp_pos, text, jionlp_passed)
        jionlp_time += (time.process_time() - t) * 1000

    print(f'-- Positive test --')
    print(f'unstructured: {unstructured_passed.value}/{len(VALID_EMAIL_ADDRESSES)} passed {unstructured_time} ms')
    print(f'jionlp:       {jionlp_passed.value}/{len(VALID_EMAIL_ADDRESSES)} passed {jionlp_time} ms')


INVALID_EMAIL_ADDRESSES = [
    'abc.example.com',
    'a@b@c@example.com',
    'a"b(c)d,e:f;g<h>i[j\\k]l@example.com',
    'just"not"right@example.com',
    'this is"not\\allowed@example.com',
    'this\\ still\\"not\\\\allowed@example.com',
    '1234567890123456789012345678901234567890123456789012345678901234+x@example.com',
    'i.like.underscores@but_they_are_not_allowed_in_this_part'
]


@ensures('len(_) == 0')
def unstructured_neg(text: str) -> list_of(RFC_Email):
    return unstructured(text)


@ensures('len(_) == 0')
def jionlp_neg(text: str) -> list_of(RFC_Email):
    return jionlp(text)


def negative_test() -> None:
    unstructured_passed = Counter()
    unstructured_time = 0
    jionlp_passed = Counter()
    jionlp_time = 0

    for email in INVALID_EMAIL_ADDRESSES:
        text = f'To: <{email}>'

        t = time.process_time()
        run(unstructured_neg, text, unstructured_passed)
        unstructured_time += (time.process_time() - t) * 1000

        t = time.process_time()
        run(jionlp_neg, text, jionlp_passed)
        jionlp_time += (time.process_time() - t) * 1000

    print(f'-- Negative test --')
    print(f'unstructured: {unstructured_passed.value}/{len(INVALID_EMAIL_ADDRESSES)} passed {unstructured_time} ms')
    print(f'jionlp:       {jionlp_passed.value}/{len(INVALID_EMAIL_ADDRESSES)} passed {jionlp_time} ms')


ToEmail = lang('ToEmail', """
start: "To: " RFC_Email;
""")


@ensures('len(_) > 0')
def unstructured_random(text: ToEmail) -> list_of(RFC_Email):
    return unstructured(text)


@ensures('len(_) > 0')
def jionlp_random(text: str) -> list_of(RFC_Email):
    return jionlp(text)


def main():
    positive_test()
    negative_test()
    fuzz([unstructured_random, jionlp_random], times=100)
