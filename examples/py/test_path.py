from flat.py import *

Lit = lang('Lit', """
start: list;
list: "[" (value ("," value))? "]";
value: list | integer;
integer: "-"? [0-9]+;
""")


@requires('forall(lambda v: int(v) > 0, select_all(Lit, xpath("..integer"), lit))')
def all_int_pos(lit: Lit) -> int:
    return 0


@requires('forall(lambda v: int(v) > 0, select_all(Lit, xpath("..list.value.integer"), lit))')
def all_int_elem_pos(lit: Lit) -> int:
    return 0


@requires('forall(lambda v: int(v) > 0, select_all(Lit, xpath(".value.list.value.integer"), lit))')
def list_all_elem_pos(lit: Lit) -> int:
    return 0


@requires('forall(lambda v: int(v) > 0, select_all(Lit, xpath(".value.list.value[1]..integer"), lit))')
def list_first_elem_all_int_pos(lit: Lit) -> int:
    return 0


@requires('forall(lambda v: int(v) > 0, select_all(Lit, xpath(".value.list.value[1]..list.value.integer"), lit))')
def list_first_elem_all_int_elem_pos(lit: Lit) -> int:
    return 0


def main():
    fuzz(all_int_pos, 10)
    fuzz(all_int_elem_pos, 10)
    fuzz(list_all_elem_pos, 10)
    fuzz(list_first_elem_all_int_pos, 10)
    fuzz(list_first_elem_all_int_elem_pos, 10)
