from typing import Optional

from flat.compiler.trees import SimpleType, FunType, IntType, StringType, BoolType, TopType, SeqType


def typ(name: str) -> Optional[SimpleType]:
    match name:
        case 'prefix_-':
            return FunType([IntType()], IntType())
        case 'prefix_!':
            return FunType([BoolType()], BoolType())
        case '+':
            return FunType([IntType(), IntType()], IntType())
        case '-' | '*' | '/' | '%':
            return FunType([IntType(), IntType()], IntType())
        case '>=' | '<=' | '>' | '<':
            return FunType([IntType(), IntType()], BoolType())
        case '==' | '!=':
            return FunType([TopType(), TopType()], BoolType())
        case '&&' | '||':
            return FunType([BoolType(), BoolType()], BoolType())
        # string functions
        case 'empty':
            return FunType([StringType()], BoolType())
        case 'length':
            return FunType([StringType()], IntType())
        case 'concat':
            return FunType([StringType(), StringType()], StringType())
        case 'nth':
            return FunType([StringType(), IntType()], StringType())
        case 'substring':
            return FunType([StringType(), IntType(), IntType()], StringType())
        case 'contains':
            return FunType([StringType(), StringType()], BoolType())
        case 'find' | 'rfind':
            return FunType([StringType(), StringType()], IntType())
        case 'int':
            return FunType([StringType()], IntType())
        # seq functions
        case 'seq_empty':
            return FunType([SeqType()], BoolType())
        case 'seq_forall' | 'seq_exists':
            return FunType([SeqType(), FunType([StringType()], BoolType())], BoolType())
        case 'seq_first' | 'seq_last':
            return FunType([SeqType()], StringType())
        case _:
            return None
