# C++ Compiler Phase Visualizer

**Live demo:** https://laibaghalib.github.io/cpp-compiler-visualizer/

> Note: this compiles a small C++ subset only (one `main()`, no functions, no `for` loops, no arrays or pointers). It is a learning tool, not a full C++ compiler.

Educational compiler for a C++ subset, written in Python, with a Tkinter GUI (desktop) and a browser version (Pyodide) that show every phase.

```
Source -> Lexer -> Parser (AST) -> Semantic (symbol table) -> Three-Address Code -> Optimizer -> C++ / Assembly
```

## Run
```
python main.py              # GUI
python main.py program.cpp  # all phases printed in the terminal
python -m unittest discover -s tests -v
```

## Layout
| File | Phase |
|---|---|
| `cppc/lexer.py` | tokens, line/column tracking |
| `cppc/parser.py` | recursive descent parser + AST, error recovery |
| `cppc/semantic.py` | scopes, symbol table, type checks |
| `cppc/tac.py` | three-address code |
| `cppc/optimizer.py` | folding, propagation, CSE, dead code elimination |
| `cppc/codegen.py` | C++ and pseudo-assembly output |
| `cppc/pipeline.py` | connects all phases |
| `gui.py` | Tkinter visualizer (desktop) |
| `index.html` | browser visualizer, runs the same `cppc/` code with Pyodide |
| `.nojekyll` | lets GitHub Pages serve `cppc/__init__.py` |

## Supported subset
One `int main()`, `int/float/double/bool`, arithmetic/comparison/logical operators,
`= += -= *= /= %= ++ --`, `if/else`, `while`, blocks, `return`.

## Limitations / future work
Single function, no calls, no `for`, arrays or pointers. Propagation and CSE are basic-block local.