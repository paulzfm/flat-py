import ast
from typing import cast

from flat.py import ensures, lang, fuzz
from flat.py.runtime import isla_generator, constant_generator


@ensures('validate_assignment(_)')
def make_assignment(value: int | bool | str, to: str) -> ast.Assign:
    return ast.Assign([ast.Name(to, ctx=ast.Store())], ast.Constant(value))


def validate_assignment(node: ast.Assign) -> bool:
    ast.fix_missing_locations(node)
    var = cast(ast.Name, node.targets[0]).id
    try:
        code = ast.unparse(node)
        env = {}
        exec(code, env)
    except Exception as exc:
        print('{}: {}'.format(type(exc).__name__, exc))
        return False
    else:
        return var in env


LowerName = lang('LowerName', """
start: char{1,3};
char: [a-z];
""")


def main():
    # node = make_assignment(23, 'as')
    # validate_assignment(node)
    #
    fuzz(make_assignment, 1000, {'value': constant_generator(23), 'to': isla_generator(LowerName)})
