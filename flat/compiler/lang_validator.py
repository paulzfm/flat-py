from typing import Optional

from flat.compiler.errors import RedefinedName, MissingStartRule, InvalidClause, UndefinedName, UnusedRule
from flat.compiler.grammar import LangObject
from flat.compiler.issuer import Issuer
from flat.compiler.trees import Ident, Rule, Clause, Literal, CharSet, Symbol, Rep, RepExactly, RepInRange, Seq, Alt


class LangValidator:
    def __init__(self, issuer: Issuer):
        self.issuer = issuer

    def lookup_lang(self, name: str) -> Optional[LangObject]:
        raise NotImplementedError

    def validate(self, ident: Ident, rules: list[Rule]) -> LangObject:
        grammar: dict[str, Rule] = {}
        for rule in rules:
            if rule.name in grammar:
                self.issuer.error(RedefinedName(grammar[rule.name].pos, rule.ident.pos))
            else:
                grammar[rule.name] = rule

        if 'start' not in grammar:
            self.issuer.error(MissingStartRule(ident.pos))

        unused: set[str] = set(grammar.keys()) - {'start'}

        def check(clause: Clause) -> None:
            match clause:
                case CharSet(Literal(lower), lit) as cs:
                    if cs.end <= cs.begin:
                        self.issuer.error(InvalidClause(f'this charactor (code={cs.end}) must > '
                                                        f'"{lower}" (code={cs.begin})', lit.pos))
                case Symbol('start'):
                    self.issuer.error(InvalidClause('using start rule is not allowed here', clause.pos,
                                                    hint='introduce a new rule and let start rule point to it'))
                case Symbol(name):
                    if name in grammar:
                        unused.discard(name)
                    elif self.lookup_lang(name) is None:
                        self.issuer.error(UndefinedName(clause.pos))
                case Rep(clause, rep_range):
                    check(clause)
                    match rep_range:
                        case RepExactly(lit):
                            match lit.value:
                                case 0:
                                    self.issuer.error(InvalidClause('0 is not allowed here', lit.pos,
                                                                    hint='use the empty clause "" instead'))
                                case 1:
                                    self.issuer.error(InvalidClause('1 is redundant here', lit.pos,
                                                                    hint='drop the repetition in this clause'))
                        case RepInRange(_, Literal() as lit) if lit.value == 0:
                            self.issuer.error(InvalidClause('0 is not allowed here', lit.pos,
                                                            hint='use the empty clause "" instead'))
                        case RepInRange(Literal(lower), Literal() as lit) if lit.value <= lower:
                            self.issuer.error(InvalidClause(f'this value must > {lower}', lit.pos))
                case Seq(clauses):
                    for clause in clauses:
                        check(clause)
                case Alt(clauses):
                    for clause in clauses:
                        check(clause)

        for rule in rules:
            check(rule.body)

        for rule_name in unused:
            self.issuer.error(UnusedRule(grammar[rule_name].ident.pos))

        return LangObject(ident.name, dict([(rule_name, grammar[rule_name].body) for rule_name in grammar]))
