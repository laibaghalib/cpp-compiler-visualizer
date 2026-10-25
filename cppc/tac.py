"""Phase 4: intermediate code (three-address code) and helpers to read it back."""
import re
from typing import Dict, List

from .common import arith_type, binary_type, is_num, is_temp, literal_type
from .parser import ASTNode


class ThreeAddressCode:
    """
    TAC formats:   x = y | x = a op b | x = neg y | x = not y
                   L0: | goto L0 | ifFalse c goto L0 | return x
    """

    def generate(self, ast: ASTNode) -> List[str]:
        self.code: List[str] = []
        self.types: Dict[str, str] = {}
        self.temp = self.label = 0
        self.scopes: List[dict] = [{}]
        self.used: set = set()
        for fn in ast.children:
            self.emit(f"; Function: {fn.value}")
            self.block_body(fn.children[0])
        return self.code

    def emit(self, text):
        self.code.append(text)

    def new_temp(self, typ):
        t = f"t{self.temp}"
        self.temp += 1
        self.types[t] = typ
        return t

    def new_label(self):
        lab = f"L{self.label}"
        self.label += 1
        return lab

    def declare(self, name, typ):
        unique, k = name, 1
        while unique in self.used or re.fullmatch(r't\d+|L\d+', unique):  # avoid clashes with shadowed names / temps
            unique = f"{name}_{k}"
            k += 1
        self.used.add(unique)
        self.scopes[-1][name] = unique
        self.types[unique] = typ
        return unique

    def resolve(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return name

    def type_of(self, operand):
        return literal_type(operand) if is_num(operand) else self.types.get(operand, 'int')

    def block_body(self, block):
        self.scopes.append({})
        for s in block.children:
            self.statement(s)
        self.scopes.pop()

    def statement(self, node):
        k = node.node_type
        if k == 'DECL_LIST':
            for d in node.children:
                self.statement(d)
        elif k == 'DECLARATION':
            value = self.expr(node.children[1]) if len(node.children) > 1 else None
            name = self.declare(node.children[0].value, node.value)
            if value is not None:
                self.emit(f"{name} = {value}")
        elif k == 'EXPR_STMT':
            self.expr(node.children[0])
        elif k == 'RETURN':
            self.emit(f"return {self.expr(node.children[0])}" if node.children else "return")
        elif k == 'BLOCK':
            self.block_body(node)
        elif k == 'IF':
            cond = self.expr(node.children[0])
            else_l = self.new_label()
            self.emit(f"ifFalse {cond} goto {else_l}")
            self.statement(node.children[1])
            if len(node.children) > 2:
                end_l = self.new_label()
                self.emit(f"goto {end_l}")
                self.emit(f"{else_l}:")
                self.statement(node.children[2])
                self.emit(f"{end_l}:")
            else:
                self.emit(f"{else_l}:")
        elif k == 'WHILE':
            top, end = self.new_label(), self.new_label()
            self.emit(f"{top}:")
            cond = self.expr(node.children[0])
            self.emit(f"ifFalse {cond} goto {end}")
            self.statement(node.children[1])
            self.emit(f"goto {top}")
            self.emit(f"{end}:")

    def expr(self, node) -> str:
        k = node.node_type
        if k == 'NUMBER':
            return node.value
        if k == 'BOOL':
            return '1' if node.value == 'true' else '0'
        if k == 'IDENTIFIER':
            return self.resolve(node.value)
        if k == 'UNARY_OP':
            a = self.expr(node.children[0])
            t = self.new_temp('bool' if node.value == '!' else arith_type(self.type_of(a), 'int'))
            self.emit(f"{t} = {'not' if node.value == '!' else 'neg'} {a}")
            return t
        if k == 'BINARY_OP':
            a, b = self.expr(node.children[0]), self.expr(node.children[1])
            t = self.new_temp(binary_type(node.value, self.type_of(a), self.type_of(b)))
            self.emit(f"{t} = {a} {node.value} {b}")
            return t
        if k == 'ASSIGNMENT':
            value = self.expr(node.children[1])
            name = self.resolve(node.children[0].value)
            self.emit(f"{name} = {value}")
            return name
        return "0"


def parse_tac(line: str):
    s = line.strip()
    if s.startswith(';'):
        return ('comment', s)
    if s.endswith(':') and ' ' not in s:
        return ('label', s[:-1])
    p = s.split()
    if p[0] == 'goto':
        return ('goto', p[1])
    if p[0] == 'ifFalse':
        return ('iffalse', p[1], p[3])
    if p[0] == 'return':
        return ('return', p[1] if len(p) > 1 else None)
    if len(p) == 3 and p[1] == '=':
        return ('copy', p[0], p[2])
    if len(p) == 4 and p[1] == '=':
        return ('unary', p[0], p[2], p[3])
    if len(p) == 5 and p[1] == '=':
        return ('binary', p[0], p[2], p[3], p[4])
    return ('comment', f"; {s}")


def fmt_tac(i) -> str:
    k = i[0]
    if k == 'comment':
        return i[1]
    if k == 'label':
        return f"{i[1]}:"
    if k == 'goto':
        return f"goto {i[1]}"
    if k == 'iffalse':
        return f"ifFalse {i[1]} goto {i[2]}"
    if k == 'return':
        return "return" if i[1] is None else f"return {i[1]}"
    if k == 'copy':
        return f"{i[1]} = {i[2]}"
    if k == 'unary':
        return f"{i[1]} = {i[2]} {i[3]}"
    return f"{i[1]} = {i[2]} {i[3]} {i[4]}"


def reads_of(i) -> List[str]:
    k = i[0]
    r = {'copy': [i[2]] if k == 'copy' else [], 'unary': [i[3]] if k == 'unary' else [],
         'binary': [i[2], i[4]] if k == 'binary' else [], 'iffalse': [i[1]] if k == 'iffalse' else [],
         'return': [i[1]] if k == 'return' and i[1] else []}.get(k, [])
    return [x for x in r if not is_num(x)]


def dest_of(i):
    return i[1] if i[0] in ('copy', 'unary', 'binary') else None
