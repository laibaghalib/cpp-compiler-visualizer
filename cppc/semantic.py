"""Phase 3: semantic analysis (scopes, symbol table, type checks)."""
from typing import Any, Dict, List

from .common import RANK, arith_type, binary_type, literal_type
from .parser import ASTNode


class SymbolTable:
    def __init__(self):
        self.scopes: List[dict] = []
        self.history: List[tuple] = []  # (label, depth, scope_dict) in creation order
        self.errors: List[str] = []
        self.enter_scope('global')

    def enter_scope(self, label):
        scope = {}
        self.scopes.append(scope)
        self.history.append((label, len(self.scopes) - 1, scope))

    def exit_scope(self):
        self.scopes.pop()

    def declare(self, name, typ, line):
        if name in self.scopes[-1]:
            first = self.scopes[-1][name]['line']
            self.errors.append(f"Line {line}: Redeclaration of '{name}' (first declared at line {first})")
            return False
        self.scopes[-1][name] = {'type': typ, 'line': line, 'initialized': False}
        return True

    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None


class SemanticAnalyzer:
    """Scope checking, type inference/checking, and basic sanity checks."""

    def analyze(self, ast: ASTNode) -> Dict[str, Any]:
        self.table = SymbolTable()
        self.errors: List[str] = []
        self.warnings: List[str] = []
        for fn in ast.children:
            self.table.enter_scope(f"function {fn.value}")
            for stmt in fn.children[0].children:
                self.statement(stmt)
            self.table.exit_scope()
        return {'symbol_table': self.table.history,
                'errors': self.table.errors + self.errors,
                'warnings': self.warnings}

    def statement(self, node):
        k = node.node_type
        if k == 'DECL_LIST':
            for d in node.children:
                self.statement(d)
        elif k == 'DECLARATION':
            name, typ = node.children[0].value, node.value
            init_type = self.expr(node.children[1]) if len(node.children) > 1 else None
            self.table.declare(name, typ, node.line)
            if init_type:
                self.table.lookup(name)['initialized'] = True
                self.check_narrowing(typ, init_type, node.line)
        elif k == 'RETURN':
            if node.children:
                self.expr(node.children[0])
            else:
                self.errors.append(f"Line {node.line}: 'return' in an int function needs a value")
        elif k == 'EXPR_STMT':
            self.expr(node.children[0])
        elif k == 'BLOCK':
            self.table.enter_scope('block')
            for s in node.children:
                self.statement(s)
            self.table.exit_scope()
        elif k in ('IF', 'WHILE'):
            self.expr(node.children[0])
            for s in node.children[1:]:
                self.statement(s)

    def check_narrowing(self, target, source, line):
        if RANK[target] < RANK[source] and source in ('float', 'double') and target in ('int', 'bool'):
            self.warnings.append(f"Line {line}: Narrowing conversion from {source} to {target}")

    def expr(self, node) -> str:
        k = node.node_type
        if k == 'NUMBER':
            return literal_type(node.value)
        if k == 'BOOL':
            return 'bool'
        if k == 'IDENTIFIER':
            sym = self.table.lookup(node.value)
            if not sym:
                self.errors.append(f"Line {node.line}: Undeclared variable '{node.value}'")
                return 'int'
            if not sym['initialized']:
                self.warnings.append(f"Line {node.line}: Variable '{node.value}' may be used uninitialized")
            return sym['type']
        if k == 'UNARY_OP':
            t = self.expr(node.children[0])
            return 'bool' if node.value == '!' else arith_type(t, 'int')
        if k == 'BINARY_OP':
            lt, rt = self.expr(node.children[0]), self.expr(node.children[1])
            right = node.children[1]
            if node.value in ('/', '%') and right.node_type == 'NUMBER' and float(right.value) == 0:
                self.errors.append(f"Line {node.line}: Division by zero")
            if node.value == '%' and (lt in ('float', 'double') or rt in ('float', 'double')):
                self.errors.append(f"Line {node.line}: Operands of '%' must be integers")
            return binary_type(node.value, lt, rt)
        if k == 'ASSIGNMENT':
            rt = self.expr(node.children[1])
            target = node.children[0]
            sym = self.table.lookup(target.value)
            if not sym:
                self.errors.append(f"Line {target.line}: Undeclared variable '{target.value}'")
                return rt
            sym['initialized'] = True
            self.check_narrowing(sym['type'], rt, target.line)
            return sym['type']
        return 'int'
