from flat.py import *

Options = lang('Options', """
start: option (ws option)*;
option: opt_debug | opt_bound;
opt_debug: "--debug"?;
opt_bound: "-k " bound;
bound: [1-9];
ws: " "+;
""")


@ensures('not _ if forall(lambda x: x == "", select_all(Options, xpath("..opt_debug"), opt)) else _')
def debug_mode(opt: Options) -> bool:
    return '--debug' in opt


@requires('exists(lambda x: True, select_all(Options, xpath("..bound"), opt))')
@ensures('_ == int(last(select_all(Options, xpath("..bound"), opt)))')
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
