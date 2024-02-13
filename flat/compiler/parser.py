from parsy import whitespace, string, decimal_digit, any_char, regex, alt, seq, Parser, forward_declaration, ParseError, \
    line_info_at

from flat.compiler.errors import ParsingError
from flat.compiler.expr_parser import expr_parser, Postfix, Prefix, InfixL, InfixR
from flat.compiler.issuer import Issuer
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
ident_name = skip_whitespaces >> seq(ident_start, ident_rest.many()).combine(make_string)


def with_pos(p: Parser) -> Parser:
    return skip_whitespaces >> p.mark().combine(lambda begin, res, end: (res, Pos(begin, (end[0], end[1] - 1))))


def positional(p: Parser) -> Parser:
    return with_pos(p).combine(lambda tree, pos: tree.set_pos(pos))


ident = positional(ident_name.map(Ident))

# parsers

clause = forward_declaration()
terminal = positional(
    string_lit.map(Token)
)
char = positional(
    normal_char.map(Literal)
)
char_set = positional(
    bracket(seq(char, token('-') >> char)).combine(CharSet)
)
nonterminal = positional(
    ident_name.map(Symbol)
)
simple_clause = terminal | char_set | nonterminal | paren(clause)

times = positional(
    integer.map(Literal)
)
rep_range = positional(alt(
    token('*').result(RepStar()),
    token('+').result(RepPlus()),
    token('?').result(RepOpt()),
    brace(seq(times.optional(), token(',') >> times.optional())).combine(RepInRange),
    brace(times).map(RepExactly)
))
repetition = positional(
    seq(simple_clause, rep_range).combine(Rep)
) | simple_clause

concatenation = positional(
    repetition.at_least(1).map(lambda cs: cs[0] if len(cs) == 1 else Seq(cs))
)
alternative = positional(
    concatenation.sep_by(token('|'), min=1).map(lambda cs: cs[0] if len(cs) == 1 else Alt(cs))
)
clause.become(alternative)

rule = positional(
    seq(ident, token(':') >> clause).combine(Rule) << token(';')
)

simple_type = forward_declaration()
builtin_type = positional(alt(
    token('int').result(IntType()),
    token('bool').result(BoolType()),
    token('string').result(StringType()),
    token('unit').result(UnitType())
))
list_type = positional(
    bracket(simple_type).map(ListType)
)
simple_type.become(expr_parser(builtin_type | list_type, [
    InfixR(token('->').result(lambda t1, t2: FunType([t1], t2).copy_pos(t1, t2))),
    Prefix(with_pos(paren(simple_type.sep_by(comma))).combine(
        lambda ts, pos: lambda t: FunType(ts, t).set_pos(Pos(pos.start, t.pos.end))) << token('->'))
]))

named_type = positional(
    ident_name.map(NamedType)
)
typ = forward_declaration()
expr = forward_declaration()
refinement_type = positional(
    brace(seq(typ, token('|') >> expr)).combine(RefinementType)
)
typ.become(simple_type | named_type | refinement_type)

literal = positional(
    alt(integer, boolean, string_lit).map(Literal)
)
variable = positional(
    ident_name.map(Var)
)
if_expr = positional(
    token('if') >> seq(expr, token('then') >> expr, token('else') >> expr).combine(IfThenElse)
)
lambda_params = ident.map(lambda x: [x]) | paren(ident.sep_by(comma))
lambda_expr = positional(
    seq(lambda_params, token('->') >> expr).combine(Lambda)
)

is_all = token('@*').result(True) | token('@').result(False)
is_abs = token('/').optional().map(lambda tk: tk is not None)
path = ident.sep_by(token('/'), min=1)
select = seq(is_all, ident, token(':') >> is_abs, path).combine(
    lambda mode, lang, p_mode, p: lambda e: Select(e, mode, lang, p_mode, p).copy_pos(e, p[-1]))


def prefix_parser(*ops: str) -> Parser:
    # NOTE: avoid capturing any variable in lambda expressions as their values may be updated
    return alt(*[with_pos(token(op)).combine(
        lambda op, pos: lambda e: App(Var(f'prefix_{op}').set_pos(pos), [e]).set_pos(Pos(pos.start, e.pos.end)))
        for op in ops])


def infix_parser(*ops: str) -> Parser:
    return alt(*[with_pos(token(op)).combine(
        lambda op, pos: lambda e1, e2: App(Var(op).set_pos(pos), [e1, e2]).copy_pos(e1, e2))
        for op in ops])


expr.become(lambda_expr | if_expr | expr_parser(literal | variable | paren(expr), [
    Postfix(with_pos(paren(expr.sep_by(comma))).combine(
        lambda e, pos: lambda f: App(f, e).set_pos(Pos(f.pos.start, pos.end)))),
    Prefix(prefix_parser('-')),
    InfixL(infix_parser('*', '/', '%')),
    InfixL(infix_parser('+', '-')),
    Postfix(select.map(lambda f: lambda e: f(e))),
    Postfix(token('in') >> ident.map(lambda lang: lambda e: InLang(e, lang).copy_pos(e, lang))),
    InfixL(infix_parser('>=', '<=', '>', '<')),
    InfixL(infix_parser('==', '!=')),
    Prefix(prefix_parser('!')),
    InfixL(infix_parser('&&')),
    InfixL(infix_parser('||')),
    # Prefix(lambda_params.map(lambda xs: lambda e: Lambda(xs, e)) << token('->'))
]))

stmt = forward_declaration()
body = brace(stmt.many())

return_stmt = positional(
    token('return') >> expr.optional().map(Return) << token(';')
)
if_stmt = positional(
    token('if') >> seq(expr, body, (token('else') >> body).optional(default=[])).combine(If)
)
while_stmt = positional(
    token('while') >> seq(expr, body).combine(While)
)
assert_stmt = positional(
    token('assert') >> expr.map(Assert) << token(';')
)

just_call = positional(
    token('call') >> seq(ident, paren(expr.sep_by(comma))).combine(Call) << token(';')
)
type_annot = (token(':') >> typ).optional()
call_and_assign = positional(
    seq(ident, type_annot, token('=') >> just_call).combine(
        lambda x, a, call: call.set_lvalue(x, a))
)
call_stmt = just_call | call_and_assign
assign_stmt = positional(
    seq(ident, type_annot, token('=') >> expr).combine(lambda x, a, e: Assign(x, e, a)) << token(';')
)

stmt.become(return_stmt | if_stmt | while_stmt | assert_stmt | call_stmt | assign_stmt)

lang_def = positional(
    token('lang') >> seq(ident, brace(rule.many())).combine(LangDef)
)
type_alias = positional(
    token('type') >> seq(ident, token('=') >> typ).combine(TypeAlias)
)

param = positional(
    seq(ident, token(':') >> typ).combine(Param)
)
fun_def = positional(
    token('fun') >> seq(ident, paren(param.sep_by(comma)), token(':') >> typ, token('=') >> expr).combine(FunDef)
)

method_spec = positional(
    token('requires') >> expr.map(MethodPreSpec) | token('ensures') >> expr.map(MethodPostSpec)
)
method_return_annot = positional(
    typ.map(lambda t: Param(Ident('_').copy_pos(t), t)) | paren(param)
)
method_def = positional(
    token('method') >> seq(ident, paren(param.sep_by(comma)), token(':') >> method_return_annot,
                           method_spec.many(), body).combine(MethodDef)
)

top_level_def = lang_def | type_alias | fun_def | method_def
module = top_level_def.many() << skip_whitespaces


class Parser:
    def __init__(self, issuer: Issuer):
        self.issuer = issuer

    def parse(self) -> list[Def]:
        source = ''.join(self.issuer.source_lines)
        try:
            return module.parse(source)
        except ParseError as e:
            self.issuer.error(ParsingError(line_info_at(e.stream, e.index), sorted(repr(x) for x in e.expected)))
            return []
