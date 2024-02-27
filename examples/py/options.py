from flat.lib import *
from flat.py import *

Options = lang('Options', """
start: option (ws option)*;
option: opt_debug | opt_bound;
opt_debug: "--debug"?;
opt_bound: "-k " bound;
bound: [1-9];
ws: " "+;
""")


@ensures(lambda opt, b: not b if selected_all(lambda x: x == "", xpath(Options, "..opt_debug"), opt) else b)
def debug_mode(opt: Options) -> bool:
    return '--debug' in opt


@requires(lambda opt: selected_any(lambda _: True, xpath(Options, "..bound"), opt))
@ensures(lambda opt, k: k == int(select_kth(xpath(Options, "..bound"), opt, -1)))
def get_bound(opt: Options) -> int:
    digit = opt[opt.rfind('-k') + 3]
    return int(digit)


def main():
    debug_mode("")
    debug_mode("--debug")
    debug_mode("-k 4  --debug")
    assert get_bound("--debug -k 5 -k 7") == 7
    # get_bound("--debug -k 5 -k -1")

    fuzz(get_bound, 10)
