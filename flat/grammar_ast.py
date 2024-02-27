from dataclasses import dataclass
from typing import Optional

from parsy import (forward_declaration, string, seq, alt, Parser, regex, any_char, decimal_digit, whitespace,
                   ParseError, line_info_at)

from flat.compiler.pos import Pos
from flat.compiler.trees import Tree, Literal, Ident


# --- Lang rules ---
class Clause(Tree):
    pass


@dataclass
class Token(Clause):
    text: str


@dataclass
class CharSet(Clause):
    lhs: Literal  # char
    rhs: Literal  # char

    @property
    def begin(self) -> int:
        return ord(self.lhs.value)

    @property
    def end(self) -> int:
        return ord(self.rhs.value)

    @property
    def get_range(self) -> range:
        return range(self.begin, self.end + 1)


@dataclass
class Symbol(Clause):
    """A nonterminal symbol or referring to another lang."""
    name: str


class RepRange(Tree):
    lower: int
    upper: Optional[int]  # None = inf


class RepStar(RepRange):
    lower = 0
    upper = None


class RepPlus(RepRange):
    lower = 1
    upper = None


class RepOpt(RepRange):
    lower = 0
    upper = 1


@dataclass
class RepExactly(RepRange):
    times: Literal  # int

    @property
    def lower(self) -> int:
        return self.times.value

    @property
    def upper(self) -> int:
        return self.times.value


@dataclass
class RepInRange(RepRange):
    at_least: Optional[Literal]  # int
    at_most: Optional[Literal]  # int

    @property
    def lower(self) -> int:
        return self.at_least.value if self.at_least else 0

    @property
    def upper(self) -> Optional[int]:
        return self.at_most.value if self.at_most else None


@dataclass
class Rep(Clause):
    clause: Clause
    rep_range: RepRange


@dataclass
class Seq(Clause):
    clauses: list[Clause]


@dataclass
class Alt(Clause):
    clauses: list[Clause]


@dataclass
class Rule(Tree):
    ident: Ident
    body: Clause

    @property
    def name(self) -> str:
        return self.ident.name


# whitespaces
skip_whitespaces = whitespace.many()


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


def parse_rules(code: str):
    try:
        return (rule.at_least(1) << skip_whitespaces).parse(code)
    except ParseError as e:
        line, col = line_info_at(e.stream, e.index)
        print(e.stream.splitlines()[line])
        print(' ' * col + '^')
        raise SyntaxError(str(e))
