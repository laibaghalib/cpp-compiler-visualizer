"""Connects all phases into one compiler."""
from typing import Any, Dict

from .codegen import AssemblyGenerator, CodeGenerator
from .lexer import LexicalAnalyzer
from .optimizer import CodeOptimizer
from .parser import SyntaxAnalyzer
from .semantic import SemanticAnalyzer
from .tac import ThreeAddressCode


class CppCompiler:
    def __init__(self):
        self.lexer = LexicalAnalyzer()
        self.parser = SyntaxAnalyzer()
        self.semantic = SemanticAnalyzer()
        self.intermediate = ThreeAddressCode()
        self.optimizer = CodeOptimizer()
        self.codegen = CodeGenerator()
        self.asmgen = AssemblyGenerator()

    def compile(self, source: str) -> Dict[str, Any]:
        r: Dict[str, Any] = {'warnings': []}
        tokens, r['lexical_errors'] = self.lexer.tokenize(source)
        r['tokens'] = tokens
        if r['lexical_errors']:
            return r
        r['ast'], r['parse_errors'] = self.parser.parse(tokens)
        if r['parse_errors']:
            return r
        sem = self.semantic.analyze(r['ast'])
        r['symbol_table'], r['semantic_errors'], r['warnings'] = sem['symbol_table'], sem['errors'], sem['warnings']
        if r['semantic_errors']:
            return r
        r['intermediate_code'] = self.intermediate.generate(r['ast'])
        r['optimized_code'] = self.optimizer.optimize(r['intermediate_code'])
        r['opt_stats'] = dict(self.optimizer.stats)
        r['final_code'] = self.codegen.generate(r['optimized_code'], self.intermediate.types)
        r['assembly'] = self.asmgen.generate(r['optimized_code'])
        return r
