from typing import Optional

from flat.compiler.values import *


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
                case [StringValue(s1), StringValue(s2)]:
                    return StringValue(s1 + s2)
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
        case '==':
            match args:
                case [IntValue(n1), IntValue(n2)]:
                    return BoolValue(n1 == n2)
                case [BoolValue(b1), BoolValue(b2)]:
                    return BoolValue(b1 == b2)
                case [StringValue(s1), StringValue(s2)]:
                    return BoolValue(s1 == s2)
                case _:
                    return BoolValue(False)
        case '!=':
            match args:
                case [IntValue(n1), IntValue(n2)]:
                    return BoolValue(n1 != n2)
                case [BoolValue(b1), BoolValue(b2)]:
                    return BoolValue(b1 != b2)
                case [StringValue(s1), StringValue(s2)]:
                    return BoolValue(s1 != s2)
                case _:
                    return BoolValue(False)
        case '>=':
            match args:
                case [IntValue(n1), IntValue(n2)]:
                    return BoolValue(n1 >= n2)
                case [StringValue(s1), StringValue(s2)]:
                    return BoolValue(s1 >= s2)
                case _:
                    raise RuntimeError
        case '<=':
            match args:
                case [IntValue(n1), IntValue(n2)]:
                    return BoolValue(n1 <= n2)
                case [StringValue(s1), StringValue(s2)]:
                    return BoolValue(s1 <= s2)
                case _:
                    raise RuntimeError
        case '>':
            match args:
                case [IntValue(n1), IntValue(n2)]:
                    return BoolValue(n1 > n2)
                case [StringValue(s1), StringValue(s2)]:
                    return BoolValue(s1 > s2)
                case _:
                    raise RuntimeError
        case '<':
            match args:
                case [IntValue(n1), IntValue(n2)]:
                    return BoolValue(n1 < n2)
                case [StringValue(s1), StringValue(s2)]:
                    return BoolValue(s1 < s2)
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
        case 'substring':
            match args:
                case [StringValue(s), IntValue(start), IntValue(end)]:
                    return StringValue(s[start:end])
                case _:
                    raise RuntimeError
        case _:
            return None
