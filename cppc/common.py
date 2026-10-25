"""Type helpers shared by every compiler phase."""
import re

TYPES = {'int', 'float', 'double', 'bool'}
RANK = {'bool': 0, 'int': 1, 'float': 2, 'double': 3}
COMPARE = {'<', '>', '<=', '>=', '==', '!='}


def arith_type(a: str, b: str) -> str:
    return ['int', 'int', 'float', 'double'][max(RANK[a], RANK[b])]


def binary_type(op: str, a: str, b: str) -> str:
    return 'bool' if op in COMPARE or op in ('&&', '||') else arith_type(a, b)


def is_num(s: str) -> bool:
    return bool(re.fullmatch(r'-?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?', s))


def literal_type(s: str) -> str:
    return 'double' if re.search(r'[.eE]', s) else 'int'


def is_temp(s: str) -> bool:
    return bool(re.fullmatch(r't\d+', s))
