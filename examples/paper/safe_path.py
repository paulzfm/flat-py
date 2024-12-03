import os
import sys

from flat.lib import select_all, xpath
from flat.py import lang, fuzz, raise_if, ensures


# https://github.com/macazaga/gpt-autopilot/blob/b782a1c7005eadb3f93f4dbd1f56cdf499ed265b/helpers.py#L15
def gpt_is_safe_path(path):
    base = os.path.abspath("code")
    file = os.path.abspath(os.path.join(base, path))
    if os.path.commonpath([base, file]) != base:
        print(f"ERROR: Tried to access file '{file}' outside of code/ folder!")
        sys.exit(1)
    return path


RelPath = lang('RelPath', """
start: part ("/" part)*;
part: "foo" | ".." | ".";
""")


def is_safe(path: str) -> bool:
    level = 0
    for part in select_all(xpath(RelPath, '..part'), path):
        match part:
            case 'foo':
                level += 1
            case '..':
                level -= 1
                if level < 0:
                    return False

    return True


@raise_if(SystemExit, cond=lambda path: not is_safe(path))
@ensures(lambda path, ret: ret == path)
def safe_path(path: RelPath) -> RelPath:
    base = os.path.abspath("code")
    file = os.path.abspath(os.path.join(base, path))
    if os.path.commonpath([base, file]) != base:
        print(f"ERROR: Tried to access file '{file}' outside of code/ folder!")
        sys.exit(1)
    return path


from flat.py.utils import log_fuzz_report, measure_overhead

def main():
    if len(sys.argv) < 2:
        print('Error: no log file')
        sys.exit(1)
    log = open(sys.argv[1], 'w')

    report = fuzz(safe_path, 1000)
    log_fuzz_report(report, log)
    original, overhead = measure_overhead(report, gpt_is_safe_path)
    log.write(f'Original execution time {original} s, overhead {overhead} s.\n')
    log.close()
