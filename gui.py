"""Tkinter GUI that shows the output of every compiler phase."""
import difflib
import os
import re
import shutil
import subprocess
import tempfile

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from cppc import CppCompiler
from cppc.common import TYPES


class CompilerVisualizerGUI:
    C = {'bg': '#1e1e1e', 'panel': '#252526', 'header': '#2d2d30', 'fg': '#d4d4d4',
         'blue': '#1976D2', 'green': '#388E3C', 'red': '#D32F2F', 'warn': '#ffcc00', 'ok': '#44ff44'}
    CPP_KW = TYPES | {'return', 'if', 'else', 'while', 'goto', 'main', 'void', 'true', 'false'}
    TOKEN_COLORS = {'KEYWORD': '#569CD6', 'IDENTIFIER': '#9CDCFE', 'NUMBER': '#B5CEA8', 'OPERATOR': '#FF7B72',
                    'PUNCTUATION': '#6A9955', 'STRING': '#CE9178', 'CHAR': '#CE9178'}
    EXAMPLES = {
        'Loop': """int main() {
    int n = 5;
    int sum = 0;
    int i = 1;
    while (i <= n) {
        sum = sum + i;
        i++;
    }
    if (sum > 10) {
        sum = sum * 2;
    } else {
        sum = 0;
    }
    return sum;
}""",
        'Folding': """int main() {
    // everything here is known at compile time
    int a = 10;
    int b = 5;
    int sum = a + b;
    int product = a * b;
    int result = (a + b) * 2 - product;
    return result;
}""",
        'CSE': """int main() {
    int a = 7;
    int b = 3;
    while (a > 0) {
        b = b + 1;
        a = a - 1;
    }
    int x = a * b + 4;
    int y = a * b + 9;
    return x + y;
}""",
        'Error 1': """int main() {
    int x = 5
    int y = (x + 2;
    return y;
}""",
        'Error 2': """#include <iostream>
/* multi-line
   comment */
int main() {
    int a = 4;
    int a = 5;
    float f = 2.5;
    int b = f * a;
    return c / 0;
}""",
    }

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("C++ Compiler Phase Visualizer")
        self.root.geometry("1400x900")
        self.root.configure(bg=self.C['bg'])
        self.compiler = CppCompiler()
        self.final_code = ''
        self.setup_style()
        self.build_ui()
        self.load_example('Loop')

    # ---------- construction ----------
    def setup_style(self):
        C, st = self.C, ttk.Style()
        st.theme_use('clam')
        st.configure('TNotebook', background=C['panel'], borderwidth=0)
        st.configure('TNotebook.Tab', background='#333333', foreground='white', padding=[12, 6], font=('Segoe UI', 9, 'bold'))
        st.map('TNotebook.Tab', background=[('selected', C['blue'])])
        st.configure('Treeview', background=C['bg'], fieldbackground=C['bg'], foreground=C['fg'], rowheight=22, borderwidth=0)
        st.configure('Treeview.Heading', background='#333333', foreground='white', font=('Segoe UI', 9, 'bold'))
        st.map('Treeview', background=[('selected', '#094771')])

    def make_text(self, parent, **kw):
        t = scrolledtext.ScrolledText(parent, font=('Consolas', 10), bg=self.C['bg'], fg=self.C['fg'],
                                      insertbackground='white', relief=tk.FLAT, wrap=tk.NONE, **kw)
        return t

    def make_tree(self, tab, columns, widths, tree_mode=False):
        frame = tk.Frame(tab, bg=self.C['bg'])
        frame.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(frame, columns=columns, show='tree headings' if tree_mode else 'headings')
        for c, w in zip(columns, widths):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor=tk.W)
        if tree_mode:
            tree.heading('#0', text='Node')
            tree.column('#0', width=380)
        sb = ttk.Scrollbar(frame, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)
        return tree

    def build_ui(self):
        C = self.C
        head = tk.Frame(self.root, bg=C['header'])
        head.pack(fill=tk.X)
        tk.Label(head, text="C++ Compiler Phase Visualizer", font=("Segoe UI", 22, "bold"), bg=C['header'], fg="#61dafb").pack(pady=(10, 0))
        tk.Label(head, text="Source  →  Tokens  →  AST  →  Symbol Table  →  Three-Address Code  →  Optimizer  →  C++ / Assembly",
                 font=("Segoe UI", 10), bg=C['header'], fg="#cccccc").pack(pady=(0, 8))

        main = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=C['bg'], sashwidth=5)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        left = tk.Frame(main, bg=C['panel'])
        main.add(left, minsize=320, width=430)
        tk.Label(left, text=" INPUT C++ CODE ", font=("Segoe UI", 11, "bold"), bg=C['blue'], fg="white").pack(fill=tk.X, padx=10, pady=(10, 4))
        self.input_text = self.make_text(left)
        self.input_text.configure(wrap=tk.NONE)
        self.input_text.pack(fill=tk.BOTH, expand=True, padx=10)
        self.input_text.tag_config('errline', background='#5a1d1d')
        ex = tk.Frame(left, bg=C['panel'])
        ex.pack(fill=tk.X, padx=10, pady=8)
        for name in self.EXAMPLES:
            color = C['red'] if name.startswith('Error') else C['green']
            tk.Button(ex, text=name, bg=color, fg='white', relief=tk.FLAT, cursor='hand2',
                      command=lambda n=name: self.load_example(n)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        right = tk.Frame(main, bg=C['panel'])
        main.add(right, minsize=600)
        nb = ttk.Notebook(right)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        def tab(title):
            f = tk.Frame(nb, bg=C['bg'])
            nb.add(f, text=title)
            return f

        self.tok_tree = self.make_tree(tab("1 Lexical"), ('line', 'col', 'type', 'value'), (60, 60, 140, 260))
        for t, color in self.TOKEN_COLORS.items():
            self.tok_tree.tag_configure(t, foreground=color)
        self.ast_tree = self.make_tree(tab("2 Syntax (AST)"), ('line',), (80,), tree_mode=True)
        self.sym_tree = self.make_tree(tab("3 Semantic"), ('type', 'declared at', 'initialized'), (100, 110, 110), tree_mode=True)

        self.tac_text = self.make_text(tab("4 Intermediate"))
        self.tac_text.pack(fill=tk.BOTH, expand=True)

        opt = tab("5 Optimization")
        self.opt_info = tk.Label(opt, text="", bg=C['bg'], fg=C['warn'], font=("Segoe UI", 10, "bold"), anchor=tk.W)
        self.opt_info.pack(fill=tk.X, padx=8, pady=4)
        pw = tk.PanedWindow(opt, orient=tk.HORIZONTAL, bg=C['bg'])
        pw.pack(fill=tk.BOTH, expand=True)
        self.diff_l, self.diff_r = self.make_text(pw), self.make_text(pw)
        pw.add(self.diff_l)
        pw.add(self.diff_r)
        self.diff_l.tag_config('removed', background='#5a1d1d')
        self.diff_r.tag_config('added', background='#1d4d2a')

        final = tab("6 Final C++")
        bar = tk.Frame(final, bg=C['bg'])
        bar.pack(fill=tk.X, pady=4)
        tk.Button(bar, text="▶ Compile with g++ and run", bg=C['green'], fg='white', relief=tk.FLAT,
                  command=self.run_cpp, cursor='hand2').pack(side=tk.LEFT, padx=8)
        self.final_text = self.make_text(final, height=16)
        self.final_text.pack(fill=tk.BOTH, expand=True)
        self.run_out = self.make_text(final, height=5)
        self.run_out.pack(fill=tk.X)
        self.asm_text = self.make_text(tab("7 Assembly"))
        self.asm_text.pack(fill=tk.BOTH, expand=True)

        ctl = tk.Frame(self.root, bg=C['header'])
        ctl.pack(fill=tk.X, padx=10)
        tk.Button(ctl, text="▶ COMPILE & SHOW ALL PHASES", font=("Segoe UI", 12, "bold"), bg=C['red'], fg='white',
                  relief=tk.FLAT, padx=24, pady=8, cursor='hand2', command=self.compile_and_show).pack(side=tk.LEFT, padx=5, pady=6)
        tk.Button(ctl, text="CLEAR", bg="#555555", fg='white', relief=tk.FLAT, padx=16, pady=6,
                  cursor='hand2', command=self.clear_all).pack(side=tk.LEFT, padx=5)
        self.problems = tk.Text(self.root, height=6, bg=C['bg'], fg=C['fg'], font=('Consolas', 9), relief=tk.FLAT)
        self.problems.pack(fill=tk.X, padx=10, pady=(6, 0))
        self.problems.tag_config('error', foreground='#ff6b6b')
        self.problems.tag_config('warning', foreground=C['warn'])
        self.status = tk.Label(self.root, text="Ready", bg=C['header'], fg="#888888", anchor=tk.W, font=("Segoe UI", 9))
        self.status.pack(fill=tk.X, padx=10, pady=(4, 6))

    # ---------- actions ----------
    def load_example(self, name):
        self.input_text.delete('1.0', tk.END)
        self.input_text.insert('1.0', self.EXAMPLES[name])
        self.compile_and_show()

    def clear_all(self):
        for t in (self.tok_tree, self.ast_tree, self.sym_tree):
            t.delete(*t.get_children())
        for t in (self.tac_text, self.diff_l, self.diff_r, self.final_text, self.asm_text, self.run_out, self.problems):
            t.delete('1.0', tk.END)
        self.opt_info.config(text="")
        self.status.config(text="Cleared", fg="#888888")

    def set_code(self, widget, text, highlight=False):
        widget.delete('1.0', tk.END)
        widget.insert('1.0', text)
        if highlight:
            self.highlight_cpp(widget)

    def highlight_cpp(self, w):
        w.tag_config('kw', foreground='#569CD6', font=('Consolas', 10, 'bold'))
        w.tag_config('num', foreground='#B5CEA8')
        w.tag_config('label', foreground='#DCDCAA')
        for n, line in enumerate(w.get('1.0', tk.END).split('\n'), 1):
            for m in re.finditer(r'\b[A-Za-z_]\w*\b|\b\d+(\.\d+)?\b', line):
                w_ = m.group()
                tag = 'kw' if w_ in self.CPP_KW else 'num' if w_[0].isdigit() else 'label' if re.fullmatch(r'L\d+', w_) else None
                if tag:
                    w.tag_add(tag, f"{n}.{m.start()}", f"{n}.{m.end()}")

    def compile_and_show(self):
        src = self.input_text.get('1.0', 'end-1c')
        self.clear_all()
        self.input_text.tag_remove('errline', '1.0', tk.END)
        if not src.strip():
            messagebox.showwarning("Input", "Please enter some C++ code.")
            return
        r = self.compiler.compile(src)

        for t in r['tokens']:
            self.tok_tree.insert('', tk.END, values=(t.line, t.column, t.type, t.value), tags=(t.type,))
        if 'ast' in r:
            self.insert_ast('', r['ast'])
        for label, depth, scope in r.get('symbol_table', []):
            node = self.sym_tree.insert('', tk.END, text=f"Scope {depth}: {label}", open=True)
            for name, info in scope.items():
                self.sym_tree.insert(node, tk.END, text=name,
                                     values=(info['type'], f"line {info['line']}", '✓' if info['initialized'] else '✗'))
        if 'intermediate_code' in r:
            self.set_code(self.tac_text, "\n".join(f"{n:3}: {l}" for n, l in enumerate(r['intermediate_code'])))
            self.show_diff(r['intermediate_code'], r['optimized_code'])
            s = r['opt_stats']
            self.opt_info.config(text=f"{len(r['intermediate_code'])} → {len(r['optimized_code'])} instructions   |   "
                                      f"folded: {s.get('folded', 0)}  propagated: {s.get('propagated', 0)}  "
                                      f"CSE: {s.get('cse', 0)}  fused: {s.get('fused', 0)}  dead removed: {s.get('dead_removed', 0)}  "
                                      f"branches simplified: {s.get('branches', 0)}")
            self.final_code = r['final_code']
            self.set_code(self.final_text, r['final_code'], highlight=True)
            self.set_code(self.asm_text, r['assembly'])

        errors = r['lexical_errors'] + r.get('parse_errors', []) + r.get('semantic_errors', [])
        for msg in errors:
            self.problems.insert(tk.END, f"error: {msg}\n", 'error')
        for msg in r['warnings']:
            self.problems.insert(tk.END, f"warning: {msg}\n", 'warning')
        for msg in errors:
            m = re.match(r'Line (\d+)', msg)
            if m:
                self.input_text.tag_add('errline', f"{m.group(1)}.0", f"{m.group(1)}.end+1c")
        if errors:
            self.status.config(text=f"Compilation stopped: {len(errors)} error(s)", fg=self.C['red'])
        else:
            self.status.config(text="Compilation successful" + (f" ({len(r['warnings'])} warning(s))" if r['warnings'] else ""), fg=self.C['ok'])

    def insert_ast(self, parent, node):
        label = node.node_type + (f": {node.value}" if node.value else "")
        item = self.ast_tree.insert(parent, tk.END, text=label, values=(node.line or '',), open=True)
        for c in node.children:
            self.insert_ast(item, c)

    def show_diff(self, a, b):
        for t in (self.diff_l, self.diff_r):
            t.delete('1.0', tk.END)
        self.diff_l.insert(tk.END, "BEFORE\n\n")
        self.diff_r.insert(tk.END, "AFTER\n\n")
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
            for l in a[i1:i2]:
                self.diff_l.insert(tk.END, l + "\n", () if tag == 'equal' else ('removed',))
            for l in b[j1:j2]:
                self.diff_r.insert(tk.END, l + "\n", () if tag == 'equal' else ('added',))

    def run_cpp(self):
        if not self.final_code:
            return
        gpp = shutil.which('g++') or shutil.which('clang++')
        self.run_out.delete('1.0', tk.END)
        if not gpp:
            self.run_out.insert(tk.END, "No g++/clang++ found on PATH. Install a C++ compiler to use this button.")
            return
        # wrap generated main() so the returned value becomes visible output
        code = ('#include <iostream>\n' + self.final_code.replace('int main()', 'static int compiled_main()', 1) +
                '\nint main() { std::cout << "main() returned: " << compiled_main() << std::endl; }\n')
        with tempfile.TemporaryDirectory() as d:
            src, exe = os.path.join(d, 'out.cpp'), os.path.join(d, 'out.exe' if os.name == 'nt' else 'out')
            with open(src, 'w') as f:
                f.write(code)
            try:
                p = subprocess.run([gpp, src, '-o', exe], capture_output=True, text=True, timeout=30)
                if p.returncode:
                    self.run_out.insert(tk.END, "Compile error:\n" + p.stderr)
                    return
                q = subprocess.run([exe], capture_output=True, text=True, timeout=10)
                self.run_out.insert(tk.END, q.stdout or "(no output)")
            except subprocess.TimeoutExpired:
                self.run_out.insert(tk.END, "Timed out (infinite loop?)")

    def run(self):
        self.root.mainloop()
