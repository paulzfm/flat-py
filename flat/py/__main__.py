import os
import sys

from flat.py.instrumentor import Instrumentor


def instrument(file_path: str, out_dir: str):
    if not os.path.exists(file_path):
        print(f'Error: file not found: {file_path}')
        sys.exit(1)

    os.makedirs(out_dir, exist_ok=True)

    with open(file_path) as f:
        code = f.read()
    instrumentor = Instrumentor()
    output = instrumentor(os.path.abspath(file_path), code)

    base_name = os.path.basename(file_path)
    with open(os.path.join(out_dir, base_name), 'w') as f:
        f.write(output)


def print_usage():
    print('Usage: python -m flat.py FILE')
    sys.exit(1)


if len(sys.argv) != 2:
    print_usage()
instrument(sys.argv[1], 'examples/out')
