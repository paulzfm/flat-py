from flat.py import lang, requires, ensures, seq

Options = lang('Options', """
start: option (ws option)*;
option: opt_debug | opt_bound;
opt_debug: "--debug"?;
    opt_bound: "-k" ws bound;
    bound: [1-9];
    ws: " "+;
""")


@ensures(lambda opt, b: not b if seq.forall(opt.select_all('debug'), lambda s: s == '') else b)
def debug_mode(opt: Options) -> bool:
    return '--debug' in opt


@requires(lambda opt: seq.nonempty(opt.select_all('bound')))
@ensures(lambda opt, k: k == int(seq.last(opt.select_all('bound'))))
def get_bound(opt: Options) -> int:
    digit = opt[opt.rfind('-k') + 3]
    return int(digit)
