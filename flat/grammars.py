import abc
from functools import reduce

from isla.derivation_tree import DerivationTree
from isla.helpers import is_valid_grammar
from isla.solver import ISLaSolver
from isla.type_defs import Grammar as ISLaGrammar

from flat.grammar_ast import *


class Grammar:
    def __init__(self, clauses: dict[str, Clause], isla_grammar: ISLaGrammar):
        self.clauses = clauses
        self.isla_solver = ISLaSolver(isla_grammar)

    def __contains__(self, word: str) -> bool:
        return self.isla_solver.check(word)

    def parse(self, word: str) -> DerivationTree:
        return self.isla_solver.parse(word, skip_check=True)

    def count(self, target: str, clause: Clause | str, direct: bool):
        """Count how many times a `target` nonterminal can appear in a parse tree derived from `clause`.
        If `direct` is set, only consider the direct children; otherwise the full tree.
        Return:
        - 0 if `target` does not appear on all trees;
        - 1 if `target` appears exactly once on all trees;
        - 2 if either `target` appears multiple times or undetermined.
        """

        def acc(n1, n2):
            """Addition of times: min(2, n1 + n2)."""
            match n1 + n2:
                case 0:
                    return 0
                case 1:
                    return 1
                case _:
                    return 2

        if isinstance(clause, str):
            clause = self.clauses[clause]

        match clause:
            case Symbol(name):
                n = 1 if name == target else 0
                if not direct:
                    n = acc(n, self.count(target, self.clauses[name], direct))
                return n
            case Rep(clause, _):
                if self.count(target, clause, direct) == 0:
                    return 0
                return 2
            case Seq(clauses):
                return reduce(acc, [self.count(target, clause, direct) for clause in clauses])
            case Alt(clauses):
                return reduce(lambda v1, v2: v1 if v1 == v2 else 2,
                              [self.count(target, clause, direct) for clause in clauses])
            case _:  # terminal clause
                return 0


class GrammarBuilder:
    @abc.abstractmethod
    def lookup_lang(self, name: str) -> Optional[Grammar]:
        raise NotImplementedError

    def validate(self, rules: list[Rule]):
        grammar: dict[str, Rule] = {}
        for rule in rules:
            if rule.name in grammar:
                raise NameError
                # self.issuer.error(RedefinedName(grammar[rule.name].pos, rule.ident.pos))
            else:
                grammar[rule.name] = rule

        if 'start' not in grammar:
            raise NameError
            # self.issuer.error(MissingStartRule(ident.pos))

        unused: set[str] = set(grammar.keys()) - {'start'}

        def check(clause: Clause) -> None:
            match clause:
                case CharSet(Literal(lower), lit) as cs:
                    if cs.end <= cs.begin:
                        raise NameError
                        # self.issuer.error(InvalidClause(f'this charactor (code={cs.end}) must > '
                        #                                 f'"{lower}" (code={cs.begin})', lit.pos))
                case Symbol('start'):
                    raise NameError
                    # self.issuer.error(InvalidClause('using start rule is not allowed here', clause.pos,
                    #                                 hint='introduce a new rule and let start rule point to it'))
                case Symbol(name):
                    if name in grammar:
                        unused.discard(name)
                    elif self.lookup_lang(name) is None:
                        raise NameError
                        # self.issuer.error(UndefinedName(clause.pos))
                case Rep(clause, rep_range):
                    check(clause)
                    match rep_range:
                        case RepExactly(lit):
                            match lit.value:
                                case 0:
                                    raise NameError
                                    # self.issuer.error(InvalidClause('0 is not allowed here', lit.pos,
                                    #                                 hint='use the empty clause "" instead'))
                                case 1:
                                    raise NameError
                                    # self.issuer.error(InvalidClause('1 is redundant here', lit.pos,
                                    #                                 hint='drop the repetition in this clause'))
                        case RepInRange(_, Literal() as lit) if lit.value == 0:
                            raise NameError
                            # self.issuer.error(InvalidClause('0 is not allowed here', lit.pos,
                            #                                 hint='use the empty clause "" instead'))
                        case RepInRange(Literal(lower), Literal() as lit) if lit.value <= lower:
                            raise NameError
                            # self.issuer.error(InvalidClause(f'this value must > {lower}', lit.pos))
                case Seq(clauses):
                    for clause in clauses:
                        check(clause)
                case Alt(clauses):
                    for clause in clauses:
                        check(clause)

        for rule in rules:
            check(rule.body)

        for rule_name in unused:
            raise NameError
            # self.issuer.error(UnusedRule(grammar[rule_name].ident.pos))

    def __call__(self, rules: list[Rule]) -> Grammar:
        self.validate(rules)
        clauses = dict([(rule.name, rule.body) for rule in rules])

        self._grammar = {}
        self._next_counter = 0

        for symbol in clauses:
            label = f'<{symbol}>'
            self._grammar[label] = []

        for symbol in clauses:
            label = f'<{symbol}>'
            match clauses[symbol]:
                case Alt(cs):
                    self._grammar[label] += [self._convert(c) for c in cs]
                case c:
                    self._grammar[label].append(self._convert(c))

        assert is_valid_grammar(self._grammar)
        # print('converted grammar:')
        # print(self._grammar)
        return Grammar(clauses, self._grammar)

    def _fresh_name(self) -> str:
        fresh_name = f'<-{str(self._next_counter)}>'
        self._next_counter += 1
        return fresh_name

    def _convert(self, clause: Clause) -> str:
        match clause:
            case Token(text):
                assert '<' not in text and '>' not in text
                return text
            case CharSet() as cs:
                nonterminal = self._fresh_name()
                self._grammar[nonterminal] = [chr(code) for code in cs.get_range]
                return nonterminal
            case Symbol(name):
                return f'<{name}>'
            case Rep(clause, rep_range):
                element = self._convert(clause)
                nonterminal = self._fresh_name()

                k1 = rep_range.lower
                k2 = rep_range.upper
                if k2:  # finite
                    self._grammar[nonterminal] = [element * k for k in range(k1, k2 + 1)]
                else:  # infinite
                    required = element * k1
                    if required == '':  # save a fresh symbol;
                        # look like ISLA may have problems in parsing if introducing a redundant symbol?
                        self._grammar[nonterminal] = ['', element + nonterminal]
                    else:
                        optionals = self._fresh_name()
                        self._grammar[optionals] = ['', element + optionals]
                        self._grammar[nonterminal] = [required + optionals]
                return nonterminal
            case Seq(clauses):
                return ''.join([self._convert(clause) for clause in clauses])
            case Alt(clauses):
                nonterminal = self._fresh_name()
                self._grammar[nonterminal] = [self._convert(clause) for clause in clauses]
                return nonterminal
