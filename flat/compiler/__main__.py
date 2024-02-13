import os
import sys

from flat.compiler.executor import Executor
from flat.compiler.instrumentor import Instrumentor
from flat.compiler.issuer import Issuer
from flat.compiler.parser import Parser
from flat.compiler.printer import pretty_tree
from flat.compiler.values import pretty_value


def compile_source(file_path: str):
    if not os.path.exists(file_path):
        print(f'Error: file not found: {file_path}')
        sys.exit(1)

    with open(file_path) as f:
        source_lines = f.readlines()

    # parse
    issuer = Issuer(source_lines)
    parser = Parser(issuer)
    program = parser.parse()
    if issuer.has_errors():
        issuer.print()
        sys.exit(1)

    # type check and instrument
    instrumentor = Instrumentor(issuer)
    instrumentor.instrument(program)
    if issuer.has_errors():
        issuer.print()
        sys.exit(1)
    print(pretty_tree(program))

    # execute
    executor = Executor(issuer, instrumentor.typer.langs, debug=True)
    value = executor.run(program)
    print(f'Out: {pretty_value(value)}')


def print_usage():
    print('Usage: python -m flat.compiler FILE')
    sys.exit(1)


if len(sys.argv) != 2:
    print_usage()
compile_source(sys.argv[1])
