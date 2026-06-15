"""
Code file parser for RAH.

Extracts structural information from source code files using
AST parsing (for Python) and regex patterns (for other languages).
"""

import ast
import re
from pathlib import Path
from typing import Optional

from rah.core.exceptions import ParserError


class CodeParseResult:
    """Result of parsing a code file."""

    def __init__(self):
        self.imports: list[str] = []
        self.import_sources: list[str] = []
        self.exports: list[str] = []
        self.docstring: str = ""
        self.language: str = ""
        self.has_main: bool = False


class CodeParser:
    """Parses code files to extract structural information."""

    def parse(self, file_path: Path, content: str, language: str) -> CodeParseResult:
        """Parse a code file and extract structural information."""
        result = CodeParseResult()
        result.language = language

        try:
            parser_map = {
                "python": self._parse_python,
                "javascript": self._parse_js_ts,
                "typescript": self._parse_js_ts,
                "java": self._parse_java,
                "go": self._parse_go,
                "c": self._parse_c_cpp,
                "cpp": self._parse_c_cpp,
                "c_header": self._parse_c_cpp,
                "cpp_header": self._parse_c_cpp,
                "rust": self._parse_rust,
                "ruby": self._parse_ruby,
                "php": self._parse_php,
                "shell": self._parse_shell,
                "bash": self._parse_shell,
            }
            parser_fn = parser_map.get(language, self._parse_generic)
            parser_fn(content, result)
        except Exception:
            pass

        return result

    def _parse_python(self, content: str, result: CodeParseResult) -> None:
        """Parse Python using the AST module."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            self._parse_python_regex(content, result)
            return

        docstring = ast.get_docstring(tree)
        if docstring:
            result.docstring = docstring

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    result.imports.append(f"import {alias.name}")
                    result.import_sources.append(alias.name)

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = ", ".join(a.name for a in node.names)
                result.imports.append(f"from {module} import {names}")
                if module:
                    result.import_sources.append(module)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node in tree.body:
                    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
                    args = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
                    arg_str = ", ".join(args[:3]) + (", ..." if len(args) > 3 else "")
                    result.exports.append(f"{prefix}def {node.name}({arg_str})")

            elif isinstance(node, ast.ClassDef):
                if node in tree.body:
                    result.exports.append(f"class {node.name}")

            elif isinstance(node, ast.Assign):
                if node in tree.body:
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.isupper():
                            result.exports.append(target.id)

        result.has_main = "__main__" in content

    def _parse_python_regex(self, content: str, result: CodeParseResult) -> None:
        """Fallback regex parser for Python files with syntax errors."""
        for m in re.finditer(r"^(?:from\s+(\S+)\s+)?import\s+(.+)$", content, re.MULTILINE):
            if m.group(1):
                result.imports.append(f"from {m.group(1)} import {m.group(2)}")
                result.import_sources.append(m.group(1))
            else:
                result.imports.append(f"import {m.group(2)}")
                result.import_sources.append(m.group(2).split(",")[0].strip())

        for m in re.finditer(r"^(?:async\s+)?def\s+(\w+)\s*\(", content, re.MULTILINE):
            result.exports.append(f"def {m.group(1)}()")
        for m in re.finditer(r"^class\s+(\w+)", content, re.MULTILINE):
            result.exports.append(f"class {m.group(1)}")

    def _parse_js_ts(self, content: str, result: CodeParseResult) -> None:
        """Parse JavaScript/TypeScript using regex."""
        for m in re.finditer(r"import\s+(?:{[^}]+}|\w+|\*\s+as\s+\w+)\s+from\s+['\"]([^'\"]+)['\"]", content):
            result.imports.append(m.group(0))
            result.import_sources.append(m.group(1))
        for m in re.finditer(r"(?:const|let|var)\s+\w+\s*=\s*require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", content):
            result.import_sources.append(m.group(1))

        for m in re.finditer(r"export\s+(?:default\s+)?(?:async\s+)?function\s+(\w+)", content):
            result.exports.append(f"function {m.group(1)}")
        for m in re.finditer(r"export\s+(?:default\s+)?class\s+(\w+)", content):
            result.exports.append(f"class {m.group(1)}")
        for m in re.finditer(r"export\s+(?:const|let|var)\s+(\w+)", content):
            result.exports.append(m.group(1))
        for m in re.finditer(r"^(?:async\s+)?function\s+(\w+)", content, re.MULTILINE):
            name = f"function {m.group(1)}"
            if name not in result.exports:
                result.exports.append(name)

    def _parse_java(self, content: str, result: CodeParseResult) -> None:
        """Parse Java using regex."""
        for m in re.finditer(r"import\s+([\w.]+);", content):
            result.imports.append(f"import {m.group(1)}")
            result.import_sources.append(m.group(1))
        for m in re.finditer(r"(?:public|private|protected)?\s*(?:abstract\s+)?class\s+(\w+)", content):
            result.exports.append(f"class {m.group(1)}")
        for m in re.finditer(r"(?:public\s+)?interface\s+(\w+)", content):
            result.exports.append(f"interface {m.group(1)}")
        for m in re.finditer(r"public\s+(?:static\s+)?(?:\w+)\s+(\w+)\s*\(", content):
            result.exports.append(f"method {m.group(1)}")

    def _parse_go(self, content: str, result: CodeParseResult) -> None:
        """Parse Go using regex."""
        for m in re.finditer(r'import\s+"([^"]+)"', content):
            result.import_sources.append(m.group(1))
        for m in re.finditer(r"import\s+\(([\s\S]*?)\)", content):
            for line in m.group(1).strip().split("\n"):
                line = line.strip().strip('"')
                if line:
                    result.import_sources.append(line)
        for m in re.finditer(r"func\s+(?:\([^)]+\)\s+)?([A-Z]\w+)\s*\(", content):
            result.exports.append(f"func {m.group(1)}")
        for m in re.finditer(r"type\s+([A-Z]\w+)\s+(?:struct|interface)", content):
            result.exports.append(f"type {m.group(1)}")

    def _parse_c_cpp(self, content: str, result: CodeParseResult) -> None:
        """Parse C/C++ using regex."""
        for m in re.finditer(r'#include\s+[<"]([^>"]+)[>"]', content):
            result.imports.append(f"#include {m.group(1)}")
            result.import_sources.append(m.group(1))
        for m in re.finditer(r"class\s+(\w+)", content):
            result.exports.append(f"class {m.group(1)}")
        for m in re.finditer(r"(?:typedef\s+)?struct\s+(\w+)", content):
            result.exports.append(f"struct {m.group(1)}")
        result.has_main = "int main(" in content or "void main(" in content

    def _parse_rust(self, content: str, result: CodeParseResult) -> None:
        """Parse Rust using regex."""
        for m in re.finditer(r"use\s+([\w:]+(?:::\{[^}]+\})?);", content):
            result.imports.append(f"use {m.group(1)}")
            result.import_sources.append(m.group(1))
        for m in re.finditer(r"pub\s+(?:async\s+)?fn\s+(\w+)", content):
            result.exports.append(f"fn {m.group(1)}")
        for m in re.finditer(r"pub\s+struct\s+(\w+)", content):
            result.exports.append(f"struct {m.group(1)}")
        for m in re.finditer(r"pub\s+enum\s+(\w+)", content):
            result.exports.append(f"enum {m.group(1)}")
        for m in re.finditer(r"pub\s+trait\s+(\w+)", content):
            result.exports.append(f"trait {m.group(1)}")

    def _parse_ruby(self, content: str, result: CodeParseResult) -> None:
        """Parse Ruby using regex."""
        for m in re.finditer(r"require(?:_relative)?\s+['\"]([^'\"]+)['\"]", content):
            result.import_sources.append(m.group(1))
        for m in re.finditer(r"class\s+(\w+(?:::\w+)*)", content):
            result.exports.append(f"class {m.group(1)}")
        for m in re.finditer(r"module\s+(\w+(?:::\w+)*)", content):
            result.exports.append(f"module {m.group(1)}")
        for m in re.finditer(r"def\s+(?:self\.)?(\w+[?!]?)", content):
            result.exports.append(f"def {m.group(1)}")

    def _parse_php(self, content: str, result: CodeParseResult) -> None:
        """Parse PHP using regex."""
        for m in re.finditer(r"(?:use|require|require_once|include)\s+['\"]?([^;'\"]+)", content):
            result.import_sources.append(m.group(1))
        for m in re.finditer(r"class\s+(\w+)", content):
            result.exports.append(f"class {m.group(1)}")
        for m in re.finditer(r"function\s+(\w+)\s*\(", content):
            result.exports.append(f"function {m.group(1)}")

    def _parse_shell(self, content: str, result: CodeParseResult) -> None:
        """Parse shell scripts using regex."""
        for m in re.finditer(r"(?:source|\.)\s+['\"]?([^'\"\s;]+)", content):
            result.import_sources.append(m.group(1))
        for m in re.finditer(r"(?:function\s+)?(\w+)\s*\(\s*\)\s*\{", content):
            result.exports.append(f"function {m.group(1)}")

    def _parse_generic(self, content: str, result: CodeParseResult) -> None:
        """Generic fallback parser."""
        for m in re.finditer(r"^(?:import|require|include|use)\s+(.+)$", content, re.MULTILINE):
            result.imports.append(m.group(0).strip())
        for m in re.finditer(r"^(?:def|func|function|fn|sub)\s+(\w+)", content, re.MULTILINE):
            result.exports.append(f"function {m.group(1)}")
        for m in re.finditer(r"^(?:class|struct|type|interface)\s+(\w+)", content, re.MULTILINE):
            result.exports.append(f"class {m.group(1)}")
