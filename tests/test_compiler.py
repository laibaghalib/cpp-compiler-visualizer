import os, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cppc import CppCompiler
from cppc.lexer import LexicalAnalyzer

C = CppCompiler()


def errors(r):
    return r["lexical_errors"] + r.get("parse_errors", []) + r.get("semantic_errors", [])


class LexerTests(unittest.TestCase):
    def test_tokens_and_positions(self):
        toks, errs = LexicalAnalyzer().tokenize("int x = 10;")
        self.assertEqual(errs, [])
        self.assertEqual([t.type for t in toks], ["KEYWORD", "IDENTIFIER", "OPERATOR", "NUMBER", "PUNCTUATION"])
        self.assertEqual(toks[1].column, 4)

    def test_multiline_comment_and_line_numbers(self):
        toks, _ = LexicalAnalyzer().tokenize("/* a\nb */ int y;")
        self.assertEqual(toks[0].line, 2)

    def test_unknown_character(self):
        _, errs = LexicalAnalyzer().tokenize("int a = 5 @ 3;")
        self.assertTrue(any("Unknown character" in e for e in errs))


class ErrorTests(unittest.TestCase):
    def test_missing_semicolon(self):
        r = C.compile("int main() {\n int x = 5\n return x;\n}")
        self.assertTrue(any("Expected ';'" in e for e in r["parse_errors"]))

    def test_undeclared(self):
        r = C.compile("int main() { return z; }")
        self.assertTrue(any("Undeclared" in e for e in r["semantic_errors"]))

    def test_redeclaration(self):
        r = C.compile("int main() { int a = 1; int a = 2; return a; }")
        self.assertTrue(any("Redeclaration" in e for e in r["semantic_errors"]))

    def test_division_by_zero(self):
        r = C.compile("int main() { return 4 / 0; }")
        self.assertTrue(any("Division by zero" in e for e in r["semantic_errors"]))


class OptimizerTests(unittest.TestCase):
    def test_constant_folding_collapses_program(self):
        r = C.compile("int main() { int a = 10; int b = 5; return (a + b) * 2 - a * b; }")
        self.assertEqual(r["optimized_code"][-1], "return -20")
        self.assertLess(len(r["optimized_code"]), len(r["intermediate_code"]))

    def test_cse(self):
        r = C.compile("int main() { int a = 7; int b = 3; while (a > 0) { a = a - 1; } int x = a * b + 4; int y = a * b + 9; return x + y; }")
        self.assertEqual(sum(1 for l in r["optimized_code"] if "a * b" in l), 1)

    def test_dead_branch_removed(self):
        r = C.compile("int main() { int a = 1; if (0) { a = 9; } return a; }")
        self.assertEqual(r["optimized_code"][-1], "return 1")


@unittest.skipUnless(shutil.which("g++"), "g++ not installed")
class EquivalenceTests(unittest.TestCase):
    PROGRAMS = [
        "int main() { int n = 5; int s = 0; int i = 1; while (i <= n) { s = s + i; i++; } if (s > 10) { s = s * 2; } else { s = 0; } return s; }",
        "int main() { int x = 1; { int x = 2; x = x + 5; } return x; }",
        "int main() { int i = 0; int s = 0; while (i < 4) { int j = 0; while (j < 3) { s += i * j; j++; } i++; } return s; }",
        "int main() { int a = 3; int b = 0; if (a > 2 && b == 0 || !a) { return 7; } return 9; }",
        "int main() { double d = 2.5; int k = 4; double r = d * k + 1; return r; }",
    ]

    @staticmethod
    def run_cpp(code):
        with tempfile.TemporaryDirectory() as d:
            src, exe = os.path.join(d, "a.cpp"), os.path.join(d, "a.exe")
            open(src, "w").write(code)
            subprocess.run(["g++", "-w", src, "-o", exe], check=True, capture_output=True)
            return subprocess.run([exe]).returncode

    def test_generated_code_behaves_like_original(self):
        for p in self.PROGRAMS:
            r = C.compile(p)
            self.assertEqual(errors(r), [], p)
            self.assertEqual(self.run_cpp(p), self.run_cpp(r["final_code"]), p)


if __name__ == "__main__":
    unittest.main()
