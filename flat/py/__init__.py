import sys
from dataclasses import dataclass
from typing import Any, Callable, Optional

from flat.compiler.grammar import LangObject
from flat.compiler.issuer import Issuer
from flat.compiler.lang_validator import LangValidator
from flat.compiler.parser import Parser
from flat.compiler.trees import LangDef


class PyLangValidator(LangValidator):
    def lookup_lang(self, name: str) -> Optional[LangObject]:
        try:
            value = eval(name)
        except NameError:
            return None

        match value:
            case LangObject() as obj:
                return obj
            case _:
                return None


def lang(name: str, grammar_rules: str) -> LangObject:
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
    return obj


@dataclass
class RefinementType:
    base: type | LangObject
    cond: Callable


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
