import os
import sys

from flat.compiler.executor import Executor
from flat.compiler.instrumentor import Instrumentor
from flat.compiler.parser import parse_program
from flat.compiler.printer import pretty_tree
from flat.compiler.values import pretty_value


def compile_source(file_path: str):
    if not os.path.exists(file_path):
        print(f'Error: file not found: {file_path}')
        sys.exit(1)

    with open(file_path) as f:
        code = f.read()

    program = parse_program(code)
    instrumentor = Instrumentor()
    instrumentor.instrument(program)
    print(pretty_tree(program))
    executor = Executor(debug=True)
    value = executor.run(program)
    print(f'Out: {pretty_value(value)}')


def print_usage():
    print('Usage: python -m flat.compiler FILE')
    sys.exit(1)


if len(sys.argv) != 2:
    print_usage()
compile_source(sys.argv[1])
