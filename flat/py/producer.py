from typing import Any, Callable, Self, Optional

from isla.solver import ISLaSolver

from flat.grammars import Grammar
from flat.py.isla_extensions import EBNF_DIRECT_CHILD, EBNF_KTH_CHILD
from flat.typing import LangType


class Producer:
    def produce(self) -> Any:
        raise NotImplementedError

    def filter(self, test: Callable[[Any], bool]) -> Self:
        class FilterProducer(Producer):
            def produce(self) -> Any:
                while True:
                    x = super().produce()
                    if test(x):
                        return x

        return FilterProducer()

    def concat(self, other: Self, concat_op: Optional[Callable[[Any, Any], Any]] = None) -> Self:
        class ConcatProducer(Producer):
            def produce(self) -> Any:
                x1 = super().produce()
                x2 = other.produce()
                if concat_op:
                    return concat_op(x1, x2)
                return x1 + x2

        return ConcatProducer()


class ProductProducer(Producer):
    def __init__(self, element_producers: list[Producer]) -> None:
        super().__init__()
        self._producers = element_producers

    def produce(self) -> list[Any]:
        return [p.produce() for p in self._producers]


class ConstProducer(Producer):
    def __init__(self, constant: Any) -> None:
        super().__init__()
        self.constant = constant

    def produce(self) -> Any:
        return self.constant


class ISLaProducer(Producer):
    def __init__(self, g: LangType | Grammar, formula: Optional[str] = None) -> None:
        super().__init__()
        if isinstance(g, LangType):
            grammar = g.grammar
        else:
            grammar = g

        self._capacity = 10
        self._solver = ISLaSolver(grammar.isla_solver.grammar, formula,
                                  structural_predicates={EBNF_DIRECT_CHILD, EBNF_KTH_CHILD},
                                  max_number_free_instantiations=self._capacity)

    def produce(self) -> str:
        while True:
            try:
                return self._solver.solve().to_string()
            except StopIteration:
                self._capacity *= 2
                self._solver = ISLaSolver(self._solver.grammar, self._solver.formula,
                                          structural_predicates={EBNF_DIRECT_CHILD, EBNF_KTH_CHILD},
                                          max_number_free_instantiations=self._capacity)
