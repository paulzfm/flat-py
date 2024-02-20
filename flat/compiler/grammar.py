from functools import reduce
from typing import Optional, Literal

from isla.derivation_tree import DerivationTree
from isla.helpers import is_valid_grammar
from isla.solver import ISLaSolver
from isla.type_defs import Grammar as ISLAGrammar

from flat.compiler.trees import (Clause, Token, CharSet, Symbol, Rep, Seq, Alt)


class Converter:
    def __call__(self, clauses: dict[str, Clause]) -> ISLAGrammar:
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
        return self._grammar

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


class LangObject:
    name: str
    clauses: dict[str, Clause]

    def __init__(self, name: str, clauses: dict[str, Clause]):
        self.name = name
        assert isinstance(clauses, dict)
        self.clauses = clauses
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

    @property
    def isla_solver(self) -> ISLaSolver:
        if not self._isla_solver:
            grammar = Converter()(self.clauses)
            self._isla_solver = ISLaSolver(grammar, max_number_free_instantiations=self._solver_volume)
        return self._isla_solver

    def __contains__(self, word: str) -> bool:
        return self.isla_solver.check(word)

    def select_all(self, word: str, path: list[str], is_absolute: bool) -> list[str]:
        def collect_children(of: str, within: DerivationTree, out: list[DerivationTree]) -> None:
            for child in within.children:
                if child.value == of:
                    out.append(child)
                if child.value.startswith('<-'):  # skip fresh nodes, as they do not exist in the original grammar
                    collect_children(of, child, out)

        try:
            root = self.isla_solver.parse(word, skip_check=True)
        except SyntaxError:
            return []

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
            return self.produce()
