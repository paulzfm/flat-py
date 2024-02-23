from flat.py import *

Lit = lang('Lit', """
start: value;
value: list | integer;
list: "[" (value ("," value))? "]";
integer: "-"? [0-9]+;
""")


@requires('forall(lambda v: int(v) > 0, select_all(Lit, "..integer", lit))')
def all_int_pos(lit: Lit) -> int:
    return 0


@requires('forall(lambda v: int(v) > 0, select_all(Lit, "..list.value.integer", lit))')
def all_int_elem_pos(lit: Lit) -> int:
    return 0


@requires('forall(lambda v: int(v) > 0, select_all(Lit, ".value.list.value.integer", lit))')
def list_all_elem_pos(lit: Lit) -> int:
    return 0


@requires('forall(lambda v: int(v) > 0, select_all(Lit, ".value.list.value[1]..integer", lit))')
def list_first_elem_all_int_pos(lit: Lit) -> int:
    return 0


@requires('forall(lambda v: int(v) > 0, select_all(Lit, ".value.list.value[1]..list.value.integer", lit))')
def list_first_elem_all_int_elem_pos(lit: Lit) -> int:
    return 0


# TODO: direct_child -> direct_logical_child
def main():
    fuzz(all_int_pos, 5)
    fuzz(all_int_elem_pos, 5)
    fuzz(list_all_elem_pos, 5)
    fuzz(list_first_elem_all_int_pos, 5)
    fuzz(list_first_elem_all_int_elem_pos, 5)
