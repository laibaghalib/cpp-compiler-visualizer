"""Phase 2: syntax analysis (tokens -> AST), recursive descent with error recovery."""
from typing import List, Tuple

from .common import TYPES
from .lexer import Token


class ASTNode:
    def __init__(self, node_type, children=None, value=None, token=None):
        self.node_type = node_type
        self.children = children if children is not None else []
        self.value = value
        self.token = token

    @property
    def line(self):
        return self.token.line if self.token else 0

    def dump(self, level=0):
        out = "  " * level + self.node_type + (f": {self.value}" if self.value else "") + "\n"
        return out + "".join(c.dump(level + 1) for c in self.children)

    __repr__ = dump


class ParseError(Exception):
    pass


class SyntaxAnalyzer:
    """
    Grammar (EBNF):
      program    -> function
      function   -> type IDENT '(' [void] ')' block
      block      -> '{' statement* '}'
      statement  -> declaration | if | while | return | block | expr ';' | ';'
      declaration-> type IDENT ['=' expr] (',' IDENT ['=' expr])* ';'
      if         -> 'if' '(' expr ')' statement ['else' statement]
      while      -> 'while' '(' expr ')' statement
      expr       -> assignment ;  assignment -> binary [assign-op assignment]
      binary     -> precedence levels:  ||  &&  == !=  < > <= >=  + -  * / %
      unary      -> ('-' | '!') unary | primary ['++' | '--']
      primary    -> NUMBER | IDENT | true | false | '(' expr ')'
    """
    LEVELS = [('||',), ('&&',), ('==', '!='), ('<', '>', '<=', '>='), ('+', '-'), ('*', '/', '%')]
    STMT_START = TYPES | {'if', 'while', 'return'}

    def parse(self, tokens: List[Token]) -> Tuple[ASTNode, List[str]]:
        self.tokens = [t for t in tokens if t.type != 'PREPROCESSOR']
        self.pos = 0
        self.errors: List[str] = []
        self.eof = Token('EOF', '', self.tokens[-1].line if self.tokens else 1, 0)
        functions = []
        while not self.at_end():
            try:
                if self.cur().value == 'using':
                    while not self.at_end() and self.cur().value != ';':
                        self.pos += 1
                    self.pos += 1
                    continue
                if functions:
                    raise self.error("Only one function ('main') is supported")
                functions.append(self.parse_function())
            except ParseError as e:
                self.errors.append(str(e))
                start = self.pos
                while not self.at_end() and self.cur().value != '}':
                    self.pos += 1
                self.pos = max(self.pos + 1, start + 1)
        if not functions and not self.errors:
            self.errors.append("Line 1: No 'main' function found")
        return ASTNode('PROGRAM', functions), self.errors

    # ---- helpers ----
    def cur(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else self.eof

    def at_end(self):
        return self.pos >= len(self.tokens)

    def advance(self):
        tok = self.cur()
        self.pos += 1
        return tok

    def error(self, msg, tok=None):
        tok = tok or self.cur()
        return ParseError(f"Line {tok.line}: {msg}")

    def expect(self, value):
        if not self.at_end() and self.cur().value == value:
            return self.advance()
        found = self.cur().value or 'end of file'
        # a missing ';' or ')' is best reported on the line where it should have been
        tok = self.tokens[self.pos - 1] if value in (';', ')') and self.pos > 0 else self.cur()
        raise self.error(f"Expected '{value}' but found '{found}'", tok)

    def sync(self):
        while not self.at_end():
            v = self.cur().value
            if v == ';':
                self.pos += 1
                return
            if v == '}' or v in self.STMT_START:
                return
            self.pos += 1

    # ---- declarations / statements ----
    def parse_function(self):
        ret = self.cur()
        if ret.value != 'int':
            raise self.error(f"Expected 'int' return type but found '{ret.value or 'end of file'}'")
        self.advance()
        name = self.advance()
        if name.type != 'IDENTIFIER' or name.value != 'main':
            raise self.error("Expected function name 'main'", name)
        self.expect('(')
        if self.cur().value == 'void':
            self.advance()
        self.expect(')')
        body = self.parse_block()
        return ASTNode('FUNCTION', [body], name.value, name)

    def parse_block(self):
        open_tok = self.expect('{')
        stmts = []
        while not self.at_end() and self.cur().value != '}':
            start = self.pos
            try:
                stmts.append(self.parse_statement())
            except ParseError as e:
                self.errors.append(str(e))
                self.sync()
                if self.pos == start:
                    self.pos += 1
        self.expect('}')
        return ASTNode('BLOCK', stmts, token=open_tok)

    def parse_statement(self):
        t = self.cur()
        if t.value in TYPES:
            return self.parse_declaration()
        if t.value == 'return':
            self.advance()
            expr = None if self.cur().value == ';' else self.parse_expression()
            self.expect(';')
            return ASTNode('RETURN', [expr] if expr else [], 'return', t)
        if t.value == 'if':
            self.advance()
            self.expect('(')
            cond = self.parse_expression()
            self.expect(')')
            kids = [cond, self.parse_statement()]
            if self.cur().value == 'else':
                self.advance()
                kids.append(self.parse_statement())
            return ASTNode('IF', kids, token=t)
        if t.value == 'while':
            self.advance()
            self.expect('(')
            cond = self.parse_expression()
            self.expect(')')
            return ASTNode('WHILE', [cond, self.parse_statement()], token=t)
        if t.value == '{':
            return self.parse_block()
        if t.value == ';':
            self.advance()
            return ASTNode('EMPTY', token=t)
        expr = self.parse_expression()
        self.expect(';')
        return ASTNode('EXPR_STMT', [expr], token=t)

    def parse_declaration(self):
        type_tok = self.advance()
        decls = []
        while True:
            name = self.cur()
            if name.type != 'IDENTIFIER':
                raise self.error(f"Expected variable name after '{type_tok.value}'")
            self.advance()
            node = ASTNode('DECLARATION', [ASTNode('IDENTIFIER', value=name.value, token=name)], type_tok.value, type_tok)
            if self.cur().value == '=':
                self.advance()
                node.children.append(self.parse_expression())
            decls.append(node)
            if self.cur().value == ',':
                self.advance()
                continue
            break
        self.expect(';')
        return decls[0] if len(decls) == 1 else ASTNode('DECL_LIST', decls, token=type_tok)

    # ---- expressions ----
    def parse_expression(self):
        return self.parse_assignment()

    def parse_assignment(self):
        left = self.parse_binary(0)
        t = self.cur()
        if t.type == 'OPERATOR' and t.value in ('=', '+=', '-=', '*=', '/=', '%='):
            self.advance()
            if left.node_type != 'IDENTIFIER':
                raise self.error(f"Left side of '{t.value}' must be a variable", t)
            right = self.parse_assignment()
            if t.value != '=':  # desugar  x += e   ->   x = x + e
                right = ASTNode('BINARY_OP', [ASTNode('IDENTIFIER', value=left.value, token=left.token), right], t.value[0], t)
            return ASTNode('ASSIGNMENT', [left, right], '=', t)
        return left

    def parse_binary(self, level):
        if level == len(self.LEVELS):
            return self.parse_unary()
        left = self.parse_binary(level + 1)
        while self.cur().type == 'OPERATOR' and self.cur().value in self.LEVELS[level]:
            op = self.advance()
            left = ASTNode('BINARY_OP', [left, self.parse_binary(level + 1)], op.value, op)
        return left

    def parse_unary(self):
        t = self.cur()
        if t.type == 'OPERATOR' and t.value in ('-', '!'):
            self.advance()
            return ASTNode('UNARY_OP', [self.parse_unary()], t.value, t)
        node = self.parse_primary()
        p = self.cur()
        if node.node_type == 'IDENTIFIER' and p.type == 'OPERATOR' and p.value in ('++', '--'):
            self.advance()  # i++ is treated as  i = i + 1
            one = ASTNode('NUMBER', value='1', token=p)
            ident = ASTNode('IDENTIFIER', value=node.value, token=node.token)
            return ASTNode('ASSIGNMENT', [node, ASTNode('BINARY_OP', [ident, one], p.value[0], p)], '=', p)
        return node

    def parse_primary(self):
        t = self.cur()
        if t.type == 'NUMBER':
            self.advance()
            return ASTNode('NUMBER', value=t.value, token=t)
        if t.type == 'IDENTIFIER':
            self.advance()
            return ASTNode('IDENTIFIER', value=t.value, token=t)
        if t.value in ('true', 'false') and t.type == 'KEYWORD':
            self.advance()
            return ASTNode('BOOL', value=t.value, token=t)
        if t.value == '(' and t.type == 'PUNCTUATION':
            self.advance()
            expr = self.parse_expression()
            self.expect(')')
            return expr
        raise self.error(f"Unexpected '{t.value}'" if t.value else "Unexpected end of file", t)
