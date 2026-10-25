"""Phase 5: optimization passes on three-address code."""
import re
from collections import Counter
from typing import List

from .common import is_num, is_temp
from .tac import dest_of, fmt_tac, parse_tac, reads_of


class CodeOptimizer:
    """
    Passes (repeated until nothing changes):
      constant folding + constant/copy propagation + algebraic simplification
      common subexpression elimination (CSE)
      temporary fusion (t = a+b; x = t  ->  x = a+b)
      dead code elimination (unused definitions) + dead/unreachable branch removal
    Propagation and CSE are basic-block local (their knowledge is reset at every label).
    """
    COMMUTATIVE = {'+', '*', '==', '!=', '&&', '||'}

    def optimize(self, code: List[str]) -> List[str]:
        self.stats = Counter()
        ins = [parse_tac(l) for l in code]
        for _ in range(12):
            new = self.cleanup_flow(self.dce(self.fuse(self.propagate(self.cse(self.propagate(ins))))))
            if new == ins:
                break
            ins = new
        return [fmt_tac(i) for i in ins]

    @staticmethod
    def fold(op, a, b):
        def num(s):
            return float(s) if re.search(r'[.eE]', s) else int(s)
        x, y = num(a), num(b)
        both_int = isinstance(x, int) and isinstance(y, int)
        if op in ('/', '%') and y == 0:
            return None
        if op == '+': r = x + y
        elif op == '-': r = x - y
        elif op == '*': r = x * y
        elif op == '/': r = (abs(x) // abs(y)) * (1 if (x < 0) == (y < 0) else -1) if both_int else x / y
        elif op == '%':
            if not both_int:
                return None
            r = abs(x) % abs(y) * (1 if x >= 0 else -1)
        elif op == '<': r = int(x < y)
        elif op == '>': r = int(x > y)
        elif op == '<=': r = int(x <= y)
        elif op == '>=': r = int(x >= y)
        elif op == '==': r = int(x == y)
        elif op == '!=': r = int(x != y)
        elif op == '&&': r = int(bool(x) and bool(y))
        elif op == '||': r = int(bool(x) or bool(y))
        else: return None
        return str(r)

    def propagate(self, ins):
        out, env = [], {}

        def sub(o):
            if o in env:
                self.stats['propagated'] += 1
                return env[o]
            return o

        def kill(v):
            env.pop(v, None)
            for key in [k for k, val in env.items() if val == v]:
                env.pop(key)

        def copy(d, s):
            kill(d)
            if s != d:
                out.append(('copy', d, s))
                if is_num(s) or is_temp(d) or not is_temp(s):
                    env[d] = s

        for i in ins:
            k = i[0]
            if k == 'label':
                env.clear()
                out.append(i)
            elif k == 'copy':
                copy(i[1], sub(i[2]))
            elif k == 'unary':
                d, op, a = i[1], i[2], sub(i[3])
                if is_num(a):
                    self.stats['folded'] += 1
                    v = -float(a) if re.search(r'[.eE]', a) else -int(a)
                    copy(d, str(v) if op == 'neg' else str(int(float(a) == 0)))
                else:
                    kill(d)
                    out.append(('unary', d, op, a))
            elif k == 'binary':
                d, a, op, b = i[1], sub(i[2]), i[3], sub(i[4])
                r = self.fold(op, a, b) if is_num(a) and is_num(b) else None
                if r is not None:
                    self.stats['folded'] += 1
                elif (op in ('+', '-') and b == '0') or (op in ('*', '/') and b == '1'):
                    r = a
                elif (op == '+' and a == '0') or (op == '*' and a == '1'):
                    r = b
                elif op == '*' and '0' in (a, b):
                    r = '0'
                if r is not None:
                    copy(d, r)
                else:
                    kill(d)
                    out.append(('binary', d, a, op, b))
            elif k == 'iffalse':
                c = sub(i[1])
                if is_num(c):
                    self.stats['branches'] += 1
                    if float(c) == 0:
                        out.append(('goto', i[2]))
                else:
                    out.append(('iffalse', c, i[2]))
            elif k == 'return':
                out.append(('return', sub(i[1]) if i[1] else None))
            else:
                out.append(i)
        return out

    def cse(self, ins):
        out, table = [], {}

        def kill(v):
            for key in [k for k, r in table.items() if r == v or v in (k[1], k[2])]:
                table.pop(key)

        for i in ins:
            if i[0] == 'label':
                table.clear()
            elif i[0] == 'binary':
                d, a, op, b = i[1], i[2], i[3], i[4]
                key = (op,) + (tuple(sorted((a, b))) if op in self.COMMUTATIVE else (a, b))
                if key in table and table[key] != d:
                    self.stats['cse'] += 1
                    kill(d)
                    out.append(('copy', d, table[key]))
                    continue
                kill(d)
                if d not in (a, b):
                    table[key] = d
            elif dest_of(i):
                kill(dest_of(i))
            out.append(i)
        return out

    def fuse(self, ins):
        uses = Counter(r for i in ins for r in reads_of(i))
        out, skip = [], False
        for idx, i in enumerate(ins):
            if skip:
                skip = False
                continue
            nxt = ins[idx + 1] if idx + 1 < len(ins) else None
            d = dest_of(i)
            if d and is_temp(d) and nxt and nxt[0] == 'copy' and nxt[2] == d and uses[d] == 1:
                self.stats['fused'] += 1
                out.append((i[0], nxt[1]) + i[2:])
                skip = True
            else:
                out.append(i)
        return out

    def dce(self, ins):
        while True:
            reads = Counter(r for i in ins for r in reads_of(i))
            new = [i for i in ins if not (dest_of(i) and reads[dest_of(i)] == 0)]
            self.stats['dead_removed'] += len(ins) - len(new)
            if len(new) == len(ins):
                return new
            ins = new

    def cleanup_flow(self, ins):
        out, dead = [], False
        for i in ins:
            if i[0] == 'label':
                dead = False
            if not dead:
                out.append(i)
            if i[0] in ('goto', 'return'):
                dead = True
        out = [i for n, i in enumerate(out)
               if not (i[0] == 'goto' and n + 1 < len(out) and out[n + 1] == ('label', i[1]))]
        targets = {i[1] for i in out if i[0] == 'goto'} | {i[2] for i in out if i[0] == 'iffalse'}
        return [i for i in out if i[0] != 'label' or i[1] in targets]
