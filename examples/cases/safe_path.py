import os
import re
import sys

from flat.lib import select_all, xpath
from flat.py import lang, fuzz, returns, refine, raise_if

# https://github.com/macazaga/gpt-autopilot/blob/b782a1c7005eadb3f93f4dbd1f56cdf499ed265b/helpers.py#L15
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
@returns(lambda path: path)
def gpt_is_safe_path(path: RelPath) -> RelPath:
    base = os.path.abspath("code")
    file = os.path.abspath(os.path.join(base, path))

    if os.path.commonpath([base, file]) != base:
        print(f"ERROR: Tried to access file '{file}' outside of code/ folder!")
        sys.exit(1)

    return path


# https://github.com/joeken/Parenchym/blob/63864cdaff76b9aa1b8dbe795eb537b5be5add3a/pym/lib.py#L374
RE_INVALID_FS_CHARS = re.compile(r'[\x00-\x1f\x7f]+')
RE_BLANKS = re.compile('\s+')


def disallowed(char: str) -> bool:
    return ord(char) in range(0, 31 + 1) or ord(char) == 127 or char in {'/', '\\', ':'}


def sanitized(path: str) -> bool:
    if path.startswith('/'):
        return False
    parts = path.split('/')
    return not any(
        [part.startswith('-') or part.startswith('.') or part.startswith(' ') or part.endswith(' ') or
         any([disallowed(ch) for ch in part]) or '  ' in part
         for part in parts
         ])


AsciiString = lang('AsciiString', """
start: char*;
char: %x0-7F;
""")

Sanitized = refine(str, 'sanitized(_)')


def safepath(path: AsciiString, sep=os.path.sep) -> Sanitized:
    """
    Returns safe version of path.

    Safe means, path is normalised with func:`normpath`, and all parts are
    sanitised like this:

    - cannot start with dash ``-``
    - cannot start with dot ``.``
    - cannot have control characters: 0x01..0x1F (0..31) and 0x7F (127)
    - cannot contain null byte 0x00
    - cannot start or end with whitespace
    - cannot contain '/', '\', ':' (slash, backslash, colon)
    - consecutive whitespace are folded to one blank

    See also:

    - http://www.dwheeler.com/essays/fixing-unix-linux-filenames.html
    - http://www.dwheeler.com/secure-programs/Secure-Programs-HOWTO/file-names.html
    """
    path = RE_INVALID_FS_CHARS.sub('', path)
    path = RE_BLANKS.sub(' ', path)
    aa = path.split(sep)
    bb = []
    for a in aa:
        if a == '':
            continue
        b = a.strip().lstrip('.-').replace('/', '').replace('\\', '').replace(':', '')
        bb.append(b)
    res = normpath(sep.join(bb))
    return res


def normpath(path):
    """
    Returns normalised version of user defined path.

    Normalised means, relative path segments like '..' are resolved and leading
    '..' are removed.
    E.g.::
        "/../../foo/../../bar"  --> "bar"
        "/../../foo/bar"        --> "foo/bar"
        "/foo/bar"              --> "foo/bar"
    """
    return os.path.normpath(os.path.join(os.path.sep, path)).lstrip(
        os.path.sep)


Unusual = lang('Unusual', """
start: char*;
char: [abAB01] | [-./\\: ] | %x0-5;
""")


def safepath_1(path: Unusual, sep=os.path.sep) -> Sanitized:
    return safepath(path, sep)


def main():
    fuzz(gpt_is_safe_path, times=1000)
    fuzz(safepath, times=1000)
    fuzz(safepath_1, times=1000)
