from flat.py import lang, requires, ensures, seq, select_all

Options = lang('Options', """
start: option (ws option)*;
option: opt_debug | opt_bound;
opt_debug: "--debug"?;
opt_bound: "-k" ws bound;
bound: [1-9];
ws: " "+;
""")


@ensures(lambda opt, b: not b if seq.forall(select_all(opt, Options, 'opt_debug'), lambda s: s == '') else b)
def debug_mode(opt: Options) -> bool:
    return '--debug' in opt


@requires(lambda opt: seq.nonempty(select_all(opt, Options, 'bound')))
@ensures(lambda opt, k: k == int(seq.last(select_all(opt, Options, 'bound'))))
def get_bound(opt: Options) -> int:
    digit = opt[opt.rfind('-k') + 3]
    return int(digit)


def main():
    debug_mode("")
    debug_mode("--debug")
    debug_mode("-k  4  --debug")
    assert get_bound("--debug -k 5 -k 7") == 7
    get_bound("--debug -k 5 -k -1")
