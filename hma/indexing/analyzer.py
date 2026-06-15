"""
File content analyzer for HMA.

Reads files, detects their type, and extracts structural metadata
using the appropriate parser. This is all done locally — no LLM needed.
"""

import hashlib
from pathlib import Path
from dataclasses import dataclass, field

from hma.core.config import HMAConfig
from hma.parsers.code_parser import CodeParser, CodeParseResult
from hma.parsers.doc_parser import DocParser, DocParseResult
from hma.indexing.walker import FileInfo


@dataclass
class AnalysisResult:
    """Complete analysis of a single file."""

    relative_path: str
    file_type: str
    category: str  # "code" or "document"
    size_bytes: int
    line_count: int
    content: str
    content_hash: str

    # From code parser
    imports: list[str] = field(default_factory=list)
    import_sources: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    docstring: str = ""

    # From doc parser
    headings: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    key_sections: list[str] = field(default_factory=list)
    content_preview: str = ""


class Analyzer:
    """
    Analyzes file content and extracts structural metadata.

    Uses CodeParser for code files and DocParser for documents.
    All analysis is done locally without an LLM.
    """

    def __init__(self, config: HMAConfig):
        self.config = config
        self._code_parser = CodeParser()
        self._doc_parser = DocParser()

    def analyze(self, file_info: FileInfo) -> AnalysisResult:
        """
        Analyze a single file.

        Args:
            file_info: FileInfo from the walker.

        Returns:
            AnalysisResult with extracted metadata.
        """
        file_type, category = self.config.get_file_type(file_info.extension)

        # Read file content
        content = self._read_file(file_info.path, file_type)
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        line_count = content.count("\n") + 1 if content else 0

        result = AnalysisResult(
            relative_path=file_info.relative_path,
            file_type=file_type or "unknown",
            category=category or "unknown",
            size_bytes=file_info.size_bytes,
            line_count=line_count,
            content=content,
            content_hash=content_hash,
        )

        # Parse based on category
        if category == "code":
            parse_result = self._code_parser.parse(
                file_info.path, content, file_type
            )
            result.imports = parse_result.imports
            result.import_sources = parse_result.import_sources
            result.exports = parse_result.exports
            result.docstring = parse_result.docstring

        elif category == "document":
            parse_result = self._doc_parser.parse(
                file_info.path, content, file_type
            )
            result.headings = parse_result.headings
            result.references = parse_result.references
            result.key_sections = parse_result.key_sections
            result.content_preview = parse_result.content_preview

        return result

    def _read_file(self, path: Path, file_type: str) -> str:
        """Read file content, handling encoding issues."""
        # Binary file types that need special handling
        if file_type in ("pdf", "docx", "doc"):
            return ""  # These are handled by their respective parsers

        encodings = ["utf-8", "latin-1", "cp1252"]
        for encoding in encodings:
            try:
                with open(path, "r", encoding=encoding, errors="strict") as f:
                    content = f.read()
                # Truncate if too large for LLM
                if len(content) > self.config.max_file_size_for_llm:
                    content = content[: self.config.max_file_size_for_llm]
                    content += "\n\n[... file truncated due to size ...]"
                return content
            except (UnicodeDecodeError, ValueError):
                continue

        # If all encodings fail, try with replace
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except (IOError, OSError):
            return ""
