import sys
from typing import Optional

from flat.compiler.errors import Error
from flat.compiler.pos import Pos


class Issuer:
    def __init__(self, source_lines: list[str]):
        self.source_lines = source_lines
        self._errors: list[Error] = []

    def has_errors(self) -> bool:
        return len(self._errors) > 0

    def error(self, err: Error) -> None:
        self._errors.append(err)

    def _format_message(self, width: int, pos: Pos, details: Optional[list[str]]):
        # NOTE: show line numbers rather than row numbers
        row_nos = range(pos.start[0], pos.end[0] + 1)
        caret_start = 0
        for no in row_nos:
            line = self.source_lines[no]
            print(f' {str(no + 1).rjust(width)} |{line}', end='', file=sys.stderr)
            if no == pos.start[0]:  # the first error line
                caret_start = pos.start[1]
            else:
                caret_start = 0
            if no == pos.end[0]:  # the last error line
                caret_end = pos.end[1] + 1
            else:
                caret_end = len(line)

            caret_line = ' ' * (2 + width) + '|' + ' ' * caret_start + '^' * (caret_end - caret_start)
            print(caret_line, file=sys.stderr)

        if details:
            for line in details:
                print(f"{' ' * (2 + width)}|{' ' * caret_start}{line}", file=sys.stderr)

    def print(self) -> None:
        for err in sorted(self._errors, key=lambda e: e.pos):
            print(f'-- {err.summary}', file=sys.stderr)
            max_row_no = err.pos.end[0]
            if err.attachment:
                max_row_no = max(max_row_no, err.attachment[0].end[0])
            width = len(str(max_row_no + 1))
            self._format_message(width, err.pos, err.explanation)
            if err.attachment:
                pos, details = err.attachment
                self._format_message(width, pos, details)
