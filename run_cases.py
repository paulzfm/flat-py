import os

PAPER_FOLDER = 'examples/paper/'

for f in os.listdir(PAPER_FOLDER):
    if f.endswith('.py'):
        print(f'# {f}')
        os.system(f'python -m flat.py {os.path.join(PAPER_FOLDER, f)}')
        os.system(f'python examples/out/{f} examples/out/{f[:-3]}.log')
