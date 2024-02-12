from functools import reduce
from typing import Optional, Literal

from isla.derivation_tree import DerivationTree
from isla.helpers import is_valid_grammar
from isla.solver import ISLaSolver
from isla.type_defs import Grammar as ISLAGrammar

from flat.compiler.trees import Rule, Clause, Token, CharSet, Symbol, Rep, Seq, Alt


class Converter:
    def __call__(self, rules: list[Rule]) -> ISLAGrammar:
        self._grammar = {}
        self._next_counter = 0

        for rule in rules:
            label = f'<{rule.name}>'
            self._grammar[label] = []

        for rule in rules:
            label = f'<{rule.name}>'
            match rule.body:
                case Alt(clauses):
                    self._grammar[label] += [self._convert(clause) for clause in clauses]
                case clause:
                    self._grammar[label].append(self._convert(clause))

        assert is_valid_grammar(self._grammar)
        return self._grammar

    def _fresh_name(self) -> str:
        fresh_name = f'<+{str(self._next_counter)}>'
        self._next_counter += 1
        return fresh_name

    def _convert(self, clause: Clause) -> str:
        match clause:
            case Token(text):
                assert '<' not in text and '>' not in text
                return text
            case CharSet(begin, end):
                nonterminal = self._fresh_name()
                self._grammar[nonterminal] = [chr(code) for code in range(begin, end + 1)]
                return nonterminal
            case Symbol(name):
                return f'<{name}>'
            case Rep(clause, at_least, at_most):
                element = self._convert(clause)
                nonterminal = self._fresh_name()
                if at_most:  # finite
                    self._grammar[nonterminal] = [element * k for k in range(at_least, at_most + 1)]
                else:  # infinite
                    required = element * at_least
                    optionals = self._fresh_name()
                    self._grammar[optionals] = ['', element + optionals]
                    self._grammar[nonterminal] = required + optionals
                return nonterminal
            case Seq(clauses):
                return ''.join([self._convert(clause) for clause in clauses])
            case Alt(clauses):
                nonterminal = self._fresh_name()
                self._grammar[nonterminal] = [self._convert(clause) for clause in clauses]
                return nonterminal


class LangObject:
    name: str
    rules: list[Rule]  # TODO: remove
    clauses: dict[str, Clause]

    def __init__(self, name: str, rules: list[Rule]):
        self.name = name
        self.rules = rules
        self.clauses = {}
        for rule in rules:
            self.clauses[rule.name] = rule.body
        self._solver_volume: int = 10
        self._isla_solver: Optional[ISLaSolver] = None

    @property
    def defined_symbols(self) -> frozenset[str]:
        return frozenset(self.clauses.keys())

    def count(self, target: str, clause: Clause | str, direct: bool) -> Literal[0, 1, 2]:
        """Count how many times a `target` nonterminal can appear in a parse tree derived from `clause`.
        If `direct` is set, only consider the direct children; otherwise the full tree.
        Return:
        - 0 if `target` does not appear on all trees;
        - 1 if `target` appears exactly once on all trees;
        - 2 if either `target` appears multiple times or undetermined.
        """

        def acc(n1: Literal[0, 1, 2], n2: Literal[0, 1, 2]) -> Literal[0, 1, 2]:
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
                n: Literal[0, 1, 2] = 1 if name == target else 0
                if not direct:
                    n = acc(n, self.count(target, self.clauses[name], direct))
                return n
            case Rep(clause, at_least, at_most):
                if at_most == 0:
                    return 0
                n = self.count(target, clause, direct)
                if n == 0:
                    return 0
                if at_least == at_most == 1:
                    return n
                return 2
            case Seq(clauses):
                return reduce(acc, [self.count(target, clause, direct) for clause in clauses])
            case Alt(clauses):
                return reduce(lambda v1, v2: v1 if v1 == v2 else 2,
                              [self.count(target, clause, direct) for clause in clauses])
            case _:  # terminal clause
                return 0

    @property
    def isla_solver(self) -> ISLaSolver:
        if not self._isla_solver:
            grammar = Converter()(self.rules)
            self._isla_solver = ISLaSolver(grammar, max_number_free_instantiations=self._solver_volume)
        return self._isla_solver

    def __contains__(self, word: str) -> bool:
        return self.isla_solver.check(word)

    def select_all(self, word: str, path: list[str], is_absolute: bool) -> list[str]:
        def collect_children(of: str, within: DerivationTree, out: list[DerivationTree]) -> None:
            for child in within.children:
                if child.value == of:
                    out.append(child)
                if child.value.startswith('<+'):  # skip fresh nodes, as they do not exist in the original grammar
                    collect_children(of, child, out)

        root = self.isla_solver.parse(word, skip_check=True)
        labels = [f'<{name}>' for name in path]
        if is_absolute:  # select from the root
            trees = [root]
        else:  # select from all nodes labelled with the first symbol of the path
            trees = [t for _, t in root.filter(lambda t: t.value == labels[0])]
            labels = labels[1:]

        for label in labels:
            if len(trees) == 0:  # no candidates
                break

            new_trees = []
            for tree in trees:  # for each candidate, move one step further according to the label
                collect_children(label, tree, new_trees)
            trees = new_trees

        return [tree.to_string() for tree in trees]

    def select_unique(self, word: str, path: list[str], is_absolute: bool) -> str:
        candidates = self.select_all(word, path, is_absolute)
        assert len(candidates) == 1, f'selected: {candidates}'
        return candidates[0]

    def produce(self) -> str:
        try:
            return self.isla_solver.solve().to_string()
        except StopIteration:
            self._solver_volume *= 2
            self._isla_solver = ISLaSolver(self.isla_solver.grammar,
                                           max_number_free_instantiations=self._solver_volume)
