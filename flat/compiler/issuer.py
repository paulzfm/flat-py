import sys

from flat.compiler.errors import Error


class Issuer:
    def __init__(self, source_lines: list[str]):
        self.source_lines = source_lines
        self._errors: list[Error] = []

    def has_errors(self) -> bool:
        return len(self._errors) > 0

    def error(self, err: Error) -> None:
        self._errors.append(err)

    def _print_one(self, err: Error) -> None:
        print(f'-- {err.summary}', file=sys.stderr)
        # NOTE: show line numbers rather than row numbers
        row_nos = range(err.pos.start[0], err.pos.end[0] + 1)
        width = max([len(str(no + 1)) for no in row_nos])
        caret_start = 0
        for no in row_nos:
            line = self.source_lines[no]
            print(f' {str(no + 1).rjust(width)} |{line}', end='', file=sys.stderr)
            if no == err.pos.start[0]:  # the first error line
                caret_start = err.pos.start[1]
            else:
                caret_start = 0
            if no == err.pos.end[0]:  # the last error line
                caret_end = err.pos.end[1] + 1
            else:
                caret_end = len(line)

            caret_line = ' ' * (2 + width) + '|' + ' ' * caret_start + '^' * (caret_end - caret_start)
            print(caret_line, file=sys.stderr)

        if err.explanation:
            for line in err.explanation:
                print(f"{' ' * (2 + width)}|{' ' * caret_start}{line}", file=sys.stderr)

    def print(self) -> None:
        for error in sorted(self._errors, key=lambda e: e.pos):
            self._print_one(error)
