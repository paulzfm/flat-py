import sys
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple

from frozenlist import FrozenList

from flat.compiler.grammar import LangObject
from flat.compiler.issuer import Issuer
from flat.compiler.lang_validator import LangValidator
from flat.compiler.parser import Parser
from flat.compiler.trees import LangDef


@dataclass
class LangType(str):
    obj: LangObject

    def __str__(self):
        return self.obj.name


def parse_xpath(xpath: str) -> Tuple[bool, list[str]]:
    if xpath.startswith('/'):
        is_abs = True
        path = xpath[1:].split('/')
    else:
        is_abs = False
        path = xpath.split('/')

    return is_abs, path


def select(word: str, lang_type: LangType, xpath: str) -> str:
    is_abs, path = parse_xpath(xpath)
    return lang_type.obj.select_unique(word, path, is_abs)


def select_all(word: str, lang_type: LangType, xpath: str) -> FrozenList[str]:
    is_abs, path = parse_xpath(xpath)
    return FrozenList(lang_type.obj.select_all(word, path, is_abs))


class PyLangValidator(LangValidator):
    def lookup_lang(self, name: str) -> Optional[LangObject]:
        try:
            value = eval(name)
        except NameError:
            return None

        match value:
            case LangType(obj):
                return obj
            case _:
                return None


def lang(name: str, grammar_rules: str) -> LangType:
    source = 'lang ' + name + ' {' + grammar_rules + '}\n'
    issuer = Issuer(source.splitlines())
    parser = Parser(issuer)
    [tree] = parser.parse()
    if issuer.has_errors():
        issuer.print()
        sys.exit(1)
    assert isinstance(tree, LangDef)
    obj = PyLangValidator(issuer).validate(tree.ident, tree.rules)
    if issuer.has_errors():
        issuer.print()
        sys.exit(1)
    return LangType(obj)


@dataclass
class RefinementType:
    base: type | LangObject
    cond: Callable

    def __str__(self):
        return '{' + f'{self.base} | {self.cond}' + '}'


def refine(base_type: type | LangObject, refinement: Callable) -> RefinementType:
    if base_type not in [int, bool, str] and not isinstance(base_type, LangObject):
        raise TypeError

    from inspect import signature
    sig = signature(refinement)
    assert len(sig.parameters.keys()) == 1

    return RefinementType(base_type, refinement)


def requires(condition: Any):
    def decorate(func):
        def decorated(*args, **kwargs):
            func(*args, **kwargs)  # identity

        return decorated

    return decorate


def ensures(condition: Any):
    def decorate(func):
        def decorated(*args, **kwargs):
            func(*args, **kwargs)  # identity

        return decorated

    return decorate
