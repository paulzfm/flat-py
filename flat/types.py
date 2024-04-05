import sys
from typing import Optional

from flat.errors import ParsingError
from flat.grammars import GrammarBuilder, Grammar
from flat.parser import parse_using, rules
from flat.typing import LangType


class LangBuilder(GrammarBuilder):
    def lookup_lang(self, name: str) -> Optional[Grammar]:
        return None


def make_lang_type(name: str, grammar_rules: str, basic_rules: str = '') -> LangType:
    builder = LangBuilder()
    try:
        grammar = builder(name, parse_using(rules, grammar_rules + basic_rules, '<file>', (1, 1)))
        return LangType(grammar)
    except ParsingError as err:
        err.print()
        sys.exit(1)


rfc_core_rules = """
ALPHA: %x41-5A | %x61-7A;
DIGIT: %x30-39;
HEXDIG: DIGIT | [A-F] | [a-f];
DQUOTE: %x22;
SP: %x20;
HTAB: %x09;
WSP: SP | HTAB;
LWSP: (WSP | CRLF WSP)*;
VCHAR: %x21-7E;
CHAR: %x01-7F;
OCTET: %x00-FF;
CTL: %x00-1F | %x7F;
CR: %x0D;
LF: %x0A;
CRLF: CR LF;
BIT: [0-1];
"""

# REF: https://github.com/declaresub/abnf/blob/master/src/abnf/grammars/rfc5322.py
RFC_Email = make_lang_type('RFC_Email', """
start: local-part "@" domain;
local-part: dot-atom | quoted-string | obs-local-part;
domain: dot-atom | domain-literal | obs-domain;
// dot-atom
dot-atom: CFWS? dot-atom-text CFWS?;
dot-atom-text: atext ("." atext)*;
atext: ALPHA | DIGIT | "!" | "#" | "$" | "%" | "&" | "'" | "*" | "+" | "-" | "|" | "=" | "?" | "^" | "_" 
     | "`" | "{" | "|" | "}" | "~";
// quoted-string
quoted-string: CFWS? DQUOTE (FWS? qcontent)* FWS? DQUOTE CFWS?;
qcontent: qtext | quoted-pair;
qtext: %d33 | %d35-91 | %d93-126 | obs-qtext;
quoted-pair: ("\\\\" (VCHAR | WSP)) | obs-qp;
obs-qtext: obs-NO-WS-CTL;
obs-qp: "\\\\" (%d0 | obs-NO-WS-CTL | LF | CR);
obs-NO-WS-CTL: %d1-8 | %d11 | %d12 | %d14-31 | %d127;
// obs-local-part
obs-local-part: word ("." word)*;
word: atom | quoted-string;
atom: CFWS? atext CFWS?;
// domain-literal
domain-literal: CFWS? "[" (FWS? dtext)* FWS? "]" CFWS?;
dtext: %d33-90 | %d94-126 | obs-dtext;
obs-dtext: obs-NO-WS-CTL | quoted-pair;
// obs-domain
obs-domain: atom ("." atom)*;
// aux
FWS: ((WSP* CRLF)? WSP) | obs-FWS;
obs-FWS: WSP (CRLF WSP)*;
CFWS: ((FWS? comment) FWS?) | FWS;
// comment
comment: "(" (FWS? ccontent)* FWS? ")";
ccontent: ctext | quoted-pair | comment;
ctext: %d33-39 | %d42-91 | %d93-126 | obs-ctext;
obs-ctext: obs-NO-WS-CTL;
""", rfc_core_rules)
