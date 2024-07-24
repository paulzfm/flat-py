import os
from typing import Literal

from flat.lib import select_all, xpath
from flat.py import lang, fuzz, returns

# https://github.com/macazaga/gpt-autopilot/blob/b782a1c7005eadb3f93f4dbd1f56cdf499ed265b/helpers.py#L15
RelPath = lang('FilePath', """
start: part ("/" part)*;
part: "foo" | ".." | ".";
""")


def safe(path: str) -> bool:
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


@returns(lambda path: safe(path))
def gpt_is_safe_path(path: RelPath) -> bool:
    base = os.path.abspath("code")
    file = os.path.abspath(os.path.join(base, path))

    if os.path.commonpath([base, file]) != base:
        # print(f"ERROR: Tried to access file '{file}' outside of code/ folder!")
        return False

    return True


#


def is_kinda_safe_path(path):
    """
    Check if given path is not one of the "sensitive" paths or its parents
    """
    sensitive_paths = [os.environ['HOME'], '/home', '/var/lib', '/tmp', '/run', '/run/user']
    given_path = os.path.realpath(path)  # this function will try to resolve an absolute path on the OS
    for sp in sensitive_paths:
        if os.path.commonpath([given_path, sp]) == given_path:
            return False
    return True


SensitivePath = Literal['/', '/home', '/var', '/var/lib', '/tmp', '/run', '/run/user']


def is_kinda_safe_path_neg(path: SensitivePath) -> Literal[False]:
    return is_kinda_safe_path(path)


def main():
    fuzz(gpt_is_safe_path, times=1000)
    fuzz(is_kinda_safe_path_neg, times=10)
