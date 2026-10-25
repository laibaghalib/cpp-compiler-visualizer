"""Phase 1: lexical analysis (source text -> tokens)."""
import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class Token:
    type: str
    value: str
    line: int
    column: int


class LexicalAnalyzer:
    """Tokenizer with line/column tracking, preprocessor lines and multi-line comments."""

    KEYWORDS = {
        'int', 'float', 'double', 'char', 'void', 'bool', 'true', 'false',
        'if', 'else', 'while', 'for', 'do', 'switch', 'case', 'default',
        'break', 'continue', 'return', 'goto', 'const', 'static', 'extern',
        'auto', 'register', 'struct', 'class', 'union', 'enum', 'typedef',
        'sizeof', 'new', 'delete', 'this', 'namespace', 'public', 'private',
        'protected', 'virtual', 'friend', 'template', 'typename', 'try',
        'catch', 'throw',
    }
    OPERATORS = sorted({
        '+', '-', '*', '/', '%', '=', '==', '!=', '<', '>', '<=', '>=',
        '&&', '||', '!', '&', '|', '^', '~', '<<', '>>', '++', '--',
        '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^=', '<<=', '>>=',
        '.', '->', '::',
    }, key=len, reverse=True)
    PUNCT = set('(){}[];,:?')
    NUM_RE = re.compile(r'(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?')
    ID_RE = re.compile(r'[A-Za-z_]\w*')

    def tokenize(self, source: str) -> Tuple[List[Token], List[str]]:
        tokens, errors = [], []
        i, n, line, line_start = 0, len(source), 1, 0
        while i < n:
            c = source[i]
            col = i - line_start
            if c == '\n':
                line += 1
                i += 1
                line_start = i
                continue
            if c.isspace():
                i += 1
                continue
            if source.startswith('//', i):
                j = source.find('\n', i)
                i = n if j == -1 else j
                continue
            if source.startswith('/*', i):
                j = source.find('*/', i + 2)
                if j == -1:
                    errors.append(f"Line {line}: Unterminated /* comment")
                    break
                chunk = source[i:j + 2]
                if '\n' in chunk:
                    line += chunk.count('\n')
                    line_start = i + chunk.rfind('\n') + 1
                i = j + 2
                continue
            if c == '#':
                j = source.find('\n', i)
                j = n if j == -1 else j
                tokens.append(Token('PREPROCESSOR', source[i:j].strip(), line, col))
                i = j
                continue
            if c in '"\'':
                j = i + 1
                while j < n and source[j] not in (c, '\n'):
                    j += 2 if source[j] == '\\' else 1
                if j < n and source[j] == c:
                    tokens.append(Token('STRING' if c == '"' else 'CHAR', source[i:j + 1], line, col))
                    i = j + 1
                else:
                    kind = 'string' if c == '"' else 'character'
                    errors.append(f"Line {line}: Unterminated {kind} literal")
                    i = min(j, n)
                continue
            m = self.NUM_RE.match(source, i)
            if m and (c.isdigit() or c == '.'):
                tokens.append(Token('NUMBER', m.group(), line, col))
                i = m.end()
                continue
            m = self.ID_RE.match(source, i)
            if m:
                word = m.group()
                tokens.append(Token('KEYWORD' if word in self.KEYWORDS else 'IDENTIFIER', word, line, col))
                i = m.end()
                continue
            op = next((o for o in self.OPERATORS if source.startswith(o, i)), None)
            if op:
                tokens.append(Token('OPERATOR', op, line, col))
                i += len(op)
            elif c in self.PUNCT:
                tokens.append(Token('PUNCTUATION', c, line, col))
                i += 1
            else:
                errors.append(f"Line {line}, column {col}: Unknown character '{c}'")
                i += 1
        return tokens, errors
