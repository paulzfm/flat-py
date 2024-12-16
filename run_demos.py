import os

DEMO_FOLDER = 'examples/demo/'

for f in os.listdir(DEMO_FOLDER):
    if f.endswith('.py'):
        print(f'# {f}')
        os.system(f'python -m flat.py {os.path.join(DEMO_FOLDER, f)}')
        os.system(f'python examples/out/{f}')
