import unittest

from flat.compiler.parser import simple_type, typ, expr, stmt, top_level_def
from flat.compiler.trees import *


class ParserTest(unittest.TestCase):
    def test_parse_builtin_types(self):
        self.assertEqual(simple_type.parse('int'), IntType())
        self.assertEqual(simple_type.parse('bool'), BoolType())
        self.assertEqual(simple_type.parse('string'), StringType())
        self.assertEqual(simple_type.parse('unit'), UnitType())

    def test_parse_list_type(self):
        self.assertEqual(simple_type.parse('[int]'), ListType(IntType()))

    def test_parse_fun_types(self):
        int_to_int = FunType([IntType()], IntType())
        self.assertEqual(simple_type.parse('int -> int'), int_to_int)
        self.assertEqual(simple_type.parse('() -> string'), FunType([], StringType()))
        self.assertEqual(simple_type.parse('([bool], int -> int) -> int -> int'),
                         FunType([ListType(BoolType()), int_to_int], int_to_int))

    def test_parse_named_type(self):
        self.assertEqual(typ.parse('Email'), NamedType('Email'))

    def test_parse_refinement_types(self):
        gt_zero = apply('>', Var('_'), Literal(0))
        pos = RefinementType(IntType(), gt_zero)
        self.assertEqual(typ.parse('{int | _ > 0}'), pos)
        self.assertEqual(typ.parse('{even | _ > 0}'), RefinementType(NamedType('even'), gt_zero))
        self.assertEqual(typ.parse('{{int | _ > 0} | _ < 10}'),
                         RefinementType(pos, apply('<', Var('_'), Literal(10))))

    def test_parse_literals(self):
        self.assertEqual(Literal(23), expr.parse('23'))
        self.assertEqual(Literal(False), expr.parse('false'))
        self.assertEqual(Literal('ok'), expr.parse('"ok"'))

    def test_parse_in_lang(self):
        self.assertEqual(InLang(Var('url'), 'URL'), expr.parse('url in URL'))

    def test_parse_select(self):
        self.assertEqual(Select(Var('url'), False, 'URL', True, ['local']),
                         expr.parse('url @ URL:/local'))
        self.assertEqual(Select(Var('arr'), True, 'JSON', False, ['array', 'element']),
                         expr.parse('arr @* JSON:array/element'))

    def test_parse_unary_expressions(self):
        self.assertEqual(prefix('-', prefix('-', Var('n'))),
                         expr.parse('--n'))
        self.assertEqual(prefix('!', prefix('!', apply('>=', Var('_'), Literal(0)))),
                         expr.parse('!! _ >= 0'))

    def test_parse_binary_expressions(self):
        self.assertEqual(apply('-',
                               apply('+',
                                     Var('a'),
                                     apply('%',
                                           apply('*', Var('b'), Var('c')),
                                           Literal(2))),
                               apply('+', Var('d'), Var('d'))),
                         expr.parse('a + b * c % 2 - (d + d)'))
        self.assertEqual(apply('||',
                               apply('&&', Literal(True), prefix('!', Literal(False))),
                               apply('&&',
                                     apply('&&', Var('b1'), prefix('!', Var('b2'))),
                                     apply('!=', Var('n'), Literal(0)))),
                         expr.parse('true && !false || b1 && !b2 && n != 0'))

    def test_parse_ite_expressions(self):
        ite = IfThenElse(apply('==', Var('n'), Literal(0)), Literal(0), Literal(1))
        self.assertEqual(ite, expr.parse('if n == 0 then 0 else 1'))
        self.assertEqual(IfThenElse(Literal(True), prefix('-', Literal(1)), ite),
                         expr.parse('if true then -1 else if n == 0 then 0 else 1'))

    def test_parse_lambda_expressions(self):
        self.assertEqual(Lambda(['x'], Var('x')), expr.parse('x -> x'))
        self.assertEqual(Lambda([], Literal(1)), expr.parse('() -> 1'))
        self.assertEqual(Lambda(['x', 'f'], apply('f', Var('x'))),
                         expr.parse('(x, f) -> f(x)'))
        self.assertEqual(Lambda(['x'], Lambda(['y'], apply('/', Var('x'), Var('y')))),
                         expr.parse('x -> y -> x / y'))
        self.assertEqual(Lambda(['x', 'y'],
                                IfThenElse(apply('==', Var('n'), Literal(0)), Var('x'), Var('y'))),
                         expr.parse('(x, y) -> if n == 0 then x else y'))

    def test_parse_return_stmts(self):
        self.assertEqual(Return(), stmt.parse('return;'))
        self.assertEqual(Return(Literal(0)), stmt.parse('return 0;'))

    def test_parse_if_stmts_with_call(self):
        n_le_10 = apply('<=', Var('n'), Literal(10))
        self.assertEqual(If(n_le_10, [Return()], []),
                         stmt.parse('if n <= 10 { return; }'))
        self.assertEqual(If(n_le_10, [Call('m', [Var('n')], var='x'), Return()], [Call('print', [Var('n')])]),
                         stmt.parse('if n <= 10 { x = call m(n); return; } else { call print(n); }'))

    def test_parse_while_stmts_with_assign(self):
        n_le_10 = apply('<=', Var('n'), Literal(10))
        self.assertEqual(While(n_le_10, [Assign('n', apply('+', Var('n'), Literal(1)))]),
                         stmt.parse('while n <= 10 { n = n + 1; }'))
        self.assertEqual(While(Literal(True), [Assert(Literal(True))]),
                         stmt.parse('while true { assert true; }'))

    def test_parse_assignments_with_type_annot(self):
        gt_zero = apply('>', Var('_'), Literal(0))
        pos = RefinementType(IntType(), gt_zero)
        self.assertEqual(Assign('x', Literal(1), type_annot=pos),
                         stmt.parse('x: {int | _ > 0} = 1;'))
        self.assertEqual(Call('m', [], var='x', type_annot=pos),
                         stmt.parse('x: {int | _ > 0} = call m();'))

    def test_parse_type_alias(self):
        gt_zero = apply('>', Var('_'), Literal(0))
        pos = RefinementType(IntType(), gt_zero)
        self.assertEqual(TypeAlias('pos', pos), top_level_def.parse('type pos = {int | _ > 0}'))

    def test_parse_fun_def(self):
        self.assertEqual(FunDef('id', [Param('x', IntType())], IntType(), Var('x')),
                         top_level_def.parse('fun id(x: int): int = x'))

    def test_parse_method_def(self):
        import textwrap
        self.assertEqual(
            MethodDef('extract_ip', [Param('url', NamedType('URL'))], Param('address', NamedType('IPv4')),
                      [MethodPostSpec(apply('==', Var('address'),
                                            apply('select', Var('url'), Literal('/address'))))], []),
            top_level_def.parse(textwrap.dedent("""\
            method extract_ip(url: URL): (address: IPv4)
                ensures address == select(url, "/address") {}
            """).rstrip())
        )
