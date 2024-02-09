from typing import Optional

from flat.compiler.trees import SimpleType, FunType, IntType, StringType, BoolType, TopType
from flat.compiler.values import *


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
        case 'length':
            return FunType([StringType()], IntType())
        case 'concat':
            return FunType([StringType(), StringType()], StringType())
        case 'substring':
            return FunType([StringType(), IntType(), IntType()], StringType())
        case 'int':
            return FunType([StringType()], IntType())
        case _:
            return None


def apply(fun: str, args: list[Value]) -> Optional[Value]:
    match fun:
        case 'prefix_-':
            match args:
                case [IntValue(n)]:
                    return IntValue(-n)
                case _:
                    raise RuntimeError
        case 'prefix_!':
            match args:
                case [BoolValue(b)]:
                    return BoolValue(not b)
                case _:
                    raise RuntimeError
        case '+':
            match args:
                case [IntValue(n1), IntValue(n2)]:
                    return IntValue(n1 + n2)
                case _:
                    raise RuntimeError
        case '-':
            match args:
                case [IntValue(n1), IntValue(n2)]:
                    return IntValue(n1 - n2)
                case _:
                    raise RuntimeError
        case '*':
            match args:
                case [IntValue(n1), IntValue(n2)]:
                    return IntValue(n1 * n2)
                case _:
                    raise RuntimeError
        case '/':
            match args:
                case [IntValue(n1), IntValue(n2)]:
                    return IntValue(n1 // n2)
                case _:
                    raise RuntimeError
        case '%':
            match args:
                case [IntValue(n1), IntValue(n2)]:
                    return IntValue(n1 % n2)
                case _:
                    raise RuntimeError
        case '>=':
            match args:
                case [IntValue(n1), IntValue(n2)]:
                    return BoolValue(n1 >= n2)
                case _:
                    raise RuntimeError
        case '<=':
            match args:
                case [IntValue(n1), IntValue(n2)]:
                    return BoolValue(n1 <= n2)
                case _:
                    raise RuntimeError
        case '>':
            match args:
                case [IntValue(n1), IntValue(n2)]:
                    return BoolValue(n1 > n2)
                case _:
                    raise RuntimeError
        case '<':
            match args:
                case [IntValue(n1), IntValue(n2)]:
                    return BoolValue(n1 < n2)
                case _:
                    raise RuntimeError
        case '==':
            match args:
                case [v1, v2]:
                    return BoolValue(v1 == v2)
                case _:
                    raise RuntimeError
        case '!=':
            match args:
                case [v1, v2]:
                    return BoolValue(v1 != v2)
                case _:
                    raise RuntimeError
        case '&&':
            match args:
                case [BoolValue(b1), BoolValue(b2)]:
                    return BoolValue(b1 and b2)
                case _:
                    raise RuntimeError
        case '||':
            match args:
                case [BoolValue(b1), BoolValue(b2)]:
                    return BoolValue(b1 or b2)
                case _:
                    raise RuntimeError
        # string
        case 'length':
            match args:
                case [StringValue(s)]:
                    return IntValue(len(s))
                case _:
                    raise RuntimeError
        case 'concat':
            match args:
                case [StringValue(s1), StringValue(s2)]:
                    return StringValue(s1 + s2)
                case _:
                    raise RuntimeError
        case 'substring':
            match args:
                case [StringValue(s), IntValue(start), IntValue(end)]:
                    return StringValue(s[start:end])
                case _:
                    raise RuntimeError
        case 'int':
            match args:
                case [StringValue(s)]:
                    return IntValue(int(s))
                case _:
                    raise RuntimeError
        case _:
            return None
