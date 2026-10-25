"""Phase 6: code generation (optimized TAC -> C++ and pseudo-assembly)."""
from typing import Dict, List

from .tac import dest_of, parse_tac, reads_of


class CodeGenerator:
    """Turns optimized TAC back into compilable C++ (declarations first, then gotos/labels)."""

    def generate(self, code: List[str], types: Dict[str, str]) -> str:
        ins = [parse_tac(l) for l in code if l.strip()]
        names = []
        for i in ins:
            for n in ([dest_of(i)] if dest_of(i) else []) + reads_of(i):
                if n not in names:
                    names.append(n)
        lines = ["int main() {"]
        for typ in ('int', 'float', 'double', 'bool'):
            group = [n for n in names if types.get(n, 'int') == typ]
            if group:
                lines.append(f"    {typ} {', '.join(group)};")
        last = None
        for i in ins:
            k = i[0]
            if k == 'comment':
                continue
            last = k
            if k == 'label':
                lines.append(f"  {i[1]}:;")
            elif k == 'goto':
                lines.append(f"    goto {i[1]};")
            elif k == 'iffalse':
                lines.append(f"    if (!{i[1]}) goto {i[2]};")
            elif k == 'return':
                lines.append(f"    return {i[1]};" if i[1] else "    return 0;")
            elif k == 'copy':
                lines.append(f"    {i[1]} = {i[2]};")
            elif k == 'unary':
                lines.append(f"    {i[1]} = {'-' if i[2] == 'neg' else '!'}{i[3]};")
            else:
                lines.append(f"    {i[1]} = {i[2]} {i[3]} {i[4]};")
        if last != 'return':
            lines.append("    return 0;")
        lines.append("}")
        return "\n".join(lines)


class AssemblyGenerator:
    """Simple two-operand pseudo-assembly (one register R0) to show a real back-end target."""
    OPS = {'+': 'ADD', '-': 'SUB', '*': 'MUL', '/': 'DIV', '%': 'MOD', '&&': 'AND', '||': 'OR',
           '<': 'SETLT', '>': 'SETGT', '<=': 'SETLE', '>=': 'SETGE', '==': 'SETEQ', '!=': 'SETNE'}

    def generate(self, code: List[str]) -> str:
        out = ["main:"]
        for l in code:
            i = parse_tac(l)
            k = i[0]
            if k == 'comment':
                continue
            if k == 'label':
                out.append(f"{i[1]}:")
            elif k == 'goto':
                out.append(f"    JMP   {i[1]}")
            elif k == 'iffalse':
                out += [f"    CMP   {i[1]}, 0", f"    JE    {i[2]}"]
            elif k == 'return':
                out += ([f"    MOV   R0, {i[1]}"] if i[1] else []) + ["    RET"]
            elif k == 'copy':
                out.append(f"    MOV   {i[1]}, {i[2]}")
            elif k == 'unary':
                out += [f"    MOV   R0, {i[3]}", f"    {'NEG' if i[2] == 'neg' else 'NOT'}   R0", f"    MOV   {i[1]}, R0"]
            else:
                op = self.OPS[i[3]]
                if op.startswith('SET'):
                    out += [f"    MOV   R0, {i[2]}", f"    CMP   R0, {i[4]}", f"    {op:<5} R0"]
                else:
                    out += [f"    MOV   R0, {i[2]}", f"    {op:<5} R0, {i[4]}"]
                out.append(f"    MOV   {i[1]}, R0")
        return "\n".join(out)
