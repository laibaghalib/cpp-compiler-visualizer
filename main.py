"""Entry point.   python main.py            -> GUI
                python main.py file.cpp   -> print every phase in the terminal"""
import sys

from cppc import CppCompiler


def cli(path):
    with open(path) as f:
        r = CppCompiler().compile(f.read())
    for key, title in (('lexical_errors', 'LEXICAL ERRORS'), ('parse_errors', 'SYNTAX ERRORS'), ('semantic_errors', 'SEMANTIC ERRORS'), ('warnings', 'WARNINGS')):
        if r.get(key):
            print(f"== {title} ==\n" + "\n".join(r[key]))
    if 'ast' in r and not r.get('parse_errors'):
        print("== AST ==\n" + r['ast'].dump())
    for key, title in (('intermediate_code', 'THREE-ADDRESS CODE'), ('optimized_code', 'OPTIMIZED CODE')):
        if key in r:
            print(f"== {title} ==\n" + "\n".join(r[key]))
    for key, title in (('final_code', 'FINAL C++'), ('assembly', 'ASSEMBLY')):
        if key in r:
            print(f"== {title} ==\n{r[key]}")


def main():
    if len(sys.argv) > 1:
        cli(sys.argv[1])
    else:
        try:
            from gui import CompilerVisualizerGUI
        except ImportError:
            print("Tkinter is not available; pass a source file to use the command-line mode.")
            return
        CompilerVisualizerGUI().run()


if __name__ == "__main__":
    main()
