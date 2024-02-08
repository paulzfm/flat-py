from parsy import whitespace, string, decimal_digit, any_char, regex, alt, seq, Parser, forward_declaration

from flat.compiler.expr_parser import expr_parser, Postfix, Prefix, InfixL, InfixR
from flat.compiler.trees import *

# whitespaces and comments
new_line = string('\n') | string('\r\n')
single_line_comment = string('//') >> regex(r'[^\r\n]').many() << new_line
multi_line_comment = string('/*') >> regex(r'[^*/]').many() << string('*/')
skip_whitespaces = (whitespace | single_line_comment | multi_line_comment).many()


# lexers

def token(word: str) -> Parser:
    return skip_whitespaces >> string(word)


comma = token(',')


def paren(p: Parser) -> Parser:
    return token('(') >> p << token(')')


def bracket(p: Parser) -> Parser:
    return token('[') >> p << token(']')


def brace(p: Parser) -> Parser:
    return token('{') >> p << token('}')


def make_string(*parts: str | list[str]) -> str:
    buf = ''
    for part in parts:
        match part:
            case str() as s:
                buf += s
            case list() as ss:
                buf += ''.join(ss)
    return buf


integer = skip_whitespaces >> decimal_digit.at_least(1).map(lambda digits: int(make_string(digits)))
boolean = skip_whitespaces >> alt(string('true').result(True), string('false').result(False))


def unquote(raw: str) -> str:
    import ast
    e = ast.parse(raw).body[0]
    assert isinstance(e, ast.Expr) and isinstance(e.value, ast.Constant)
    v = e.value.value
    assert isinstance(v, str)
    return v


quote = string('"')
normal_char = regex(r'[^\r\n\f\\"]')
escape_char = seq(string('\\'), any_char).combine(make_string)
quoted_string = seq(quote, (normal_char | escape_char).many(), quote).combine(make_string)
string_lit = skip_whitespaces >> quoted_string.map(unquote)

ident_start = regex(r'[_a-zA-Z]')
ident_rest = ident_start | decimal_digit | string("'")
ident = skip_whitespaces >> seq(ident_start, ident_rest.many()).combine(make_string)

# parsers

clause = forward_declaration()
clause_term = string_lit.map(Token) | ident.map(Symbol) | paren(clause)
rep_range = alt(token('*').result((0, None)),
                token('+').result((1, None)),
                token('?').result((0, 1)),
                brace(seq(integer.optional(default=0), token(',') >> integer.optional(default=None))),
                brace(integer.map(lambda k: (k, k))))
repetition = seq(clause_term, rep_range).combine(lambda c, r: Rep(c, r[0], r[1])) | clause_term
concatenation = repetition.at_least(1).map(lambda cs: cs[0] if len(cs) == 1 else Seq(cs))
alternative = concatenation.sep_by(token('|'), min=1).map(lambda cs: cs[0] if len(cs) == 1 else Alt(cs))
clause.become(alternative)
rule = seq(ident, token(':') >> clause).combine(Rule) << token(';')

simple_type = forward_declaration()
builtin_type = alt(token('int').result(IntType()),
                   token('bool').result(BoolType()),
                   token('string').result(StringType()),
                   token('unit').result(UnitType()))
list_type = bracket(simple_type).map(ListType)
simple_type.become(expr_parser(builtin_type | list_type, [
    InfixR(token('->').result(lambda t1, t2: FunType([t1], t2))),
    Prefix(paren(simple_type.sep_by(comma)).map(lambda ts: lambda t: FunType(ts, t)) << token('->'))
]))

typ = forward_declaration()
expr = forward_declaration()
refinement_type = brace(seq(typ, token('|') >> expr)).combine(RefinementType)
typ.become(simple_type | ident.map(NamedType) | refinement_type)

path = ident.sep_by(token('/'), min=1)
is_abs = token('/').optional().map(lambda tk: tk is not None)
selector = token('@') >> seq(ident, token(':') >> is_abs, path).combine(Selector)
literal = (integer | boolean | string_lit).map(Literal) | selector

if_expr = token('if') >> seq(expr, token('then') >> expr, token('else') >> expr).combine(IfThenElse)
lambda_params = ident.map(lambda x: [x]) | paren(ident.sep_by(comma))
lambda_expr = seq(lambda_params, token('->') >> expr).combine(Lambda)


def prefix_parser(*ops: str) -> Parser:
    # NOTE: avoid capturing any variable in lambda expressions as their values may be updated
    return alt(*[token(op).map(lambda op: lambda e: prefix(op, e)) for op in ops])


def infix_parser(*ops: str) -> Parser:
    return alt(*[token(op).map(lambda op: lambda e1, e2: infix(op, e1, e2)) for op in ops])


expr.become(lambda_expr | if_expr | expr_parser(literal | ident.map(Var) | paren(expr), [
    Postfix(paren(expr.sep_by(comma)).map(lambda es: lambda f: App(f, es))),
    Prefix(prefix_parser('-')),
    InfixL(infix_parser('*', '/', '%')),
    InfixL(infix_parser('+', '-')),
    InfixL(infix_parser('==', '!=', '>=', '<=', '>', '<')),
    Prefix(prefix_parser('!')),
    InfixL(infix_parser('&&')),
    InfixL(infix_parser('||')),
    # Prefix(lambda_params.map(lambda xs: lambda e: Lambda(xs, e)) << token('->'))
]))

stmt = forward_declaration()
body = brace(stmt.many())

return_stmt = token('return') >> expr.optional(default=None).map(Return) << token(';')
if_stmt = token('if') >> seq(expr, body, (token('else') >> body).optional(default=[])).combine(If)
while_stmt = token('while') >> seq(expr, body).combine(While)

just_call = token('call') >> seq(ident, paren(expr.sep_by(comma))).combine(Call) << token(';')
type_annot = (token(':') >> typ).optional(default=None)
call_and_assign = seq(ident, type_annot, token('=') >> just_call).combine(
    lambda x, a, call: call.set_lvalue(x, a)
)
call_stmt = just_call | call_and_assign
assign_stmt = seq(ident, type_annot, token('=') >> expr).combine(lambda x, a, e: Assign(x, e, a)) << token(';')

stmt.become(return_stmt | if_stmt | while_stmt | call_stmt | assign_stmt)

lang_def = token('lang') >> seq(ident, brace(rule.many())).combine(LangDef)
type_alias = token('type') >> seq(ident, token('=') >> typ).combine(TypeAlias)

param = seq(ident, token(':') >> typ).combine(Param)
fun_def = token('fun') >> seq(ident, paren(param.sep_by(comma)), token(':') >> typ,
                              token('=') >> expr).combine(FunDef)

method_spec = token('requires') >> expr.map(MethodPreSpec) | token('ensures') >> expr.map(MethodPostSpec)
method_return_annot = typ.map(lambda t: Param('_', t)) | paren(param)
method_def = token('method') >> seq(ident, paren(param.sep_by(comma)), token(':') >> method_return_annot,
                                    method_spec.many(), body).combine(MethodDef)

top_level_def = lang_def | type_alias | fun_def | method_def
program = top_level_def.many() << skip_whitespaces


# entry
def parse_program(source: str) -> list[Def]:
    return program.parse(source)
