import os
import re

from flat.lib import select_all, xpath
from flat.py import lang, fuzz, refine
from flat.py.runtime import isla_generator

# https://github.com/joeken/Parenchym/blob/63864cdaff76b9aa1b8dbe795eb537b5be5add3a/pym/lib.py#L374
RE_INVALID_FS_CHARS = re.compile(r'[\x00-\x1f\x7f]+')
RE_BLANKS = re.compile('\s+')


def safepath_old(path: str, sep=os.path.sep) -> str:
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


def is_not_allowed(char: str) -> bool:
    return ord(char) in range(0, 31 + 1) or ord(char) == 127 or char in {'/', '\\', ':'}


def is_sanitized(path: str) -> bool:
    parts = select_all(xpath(Path, '..part'), path)
    return not any(
        [part.startswith('-') or part.startswith('.') or part.startswith(' ') or part.endswith(' ') or
         any([is_not_allowed(ch) for ch in part]) or '  ' in part
         for part in parts
         ])


Path = lang('Path', """
start: "/" | "/"? part ("/" part)*;
part: (%x0-2E | %x30-7F)*;
""")

SanitizedPath = refine(Path, 'is_sanitized(_)')


def safepath(path: Path, sep=os.path.sep) -> SanitizedPath:
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


UnusualPath = lang('UnusualPath', """
start: "/" | "/"? part ("/" part)*;
part: char*;
char: [abAB0] | [-.\\: ] | %x0-4;
""")

import sys
from flat.py.utils import log_fuzz_report, measure_overhead


def main():
    if len(sys.argv) < 2:
        print('Error: no log file')
        sys.exit(1)
    log = open(sys.argv[1], 'w')

    report = fuzz(safepath, 1000)
    log_fuzz_report(report, log)

    report = fuzz(safepath, 1000, using={'path': isla_generator(UnusualPath)})
    log_fuzz_report(report, log)
    original, overhead = measure_overhead(report, safepath_old)
    log.write(f'Original execution time {original} s, overhead {overhead} s.\n')

    log.close()
