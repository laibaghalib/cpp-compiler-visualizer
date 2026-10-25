"""Educational C++-subset compiler, split into one module per phase."""
from .pipeline import CppCompiler

__all__ = ["CppCompiler"]
