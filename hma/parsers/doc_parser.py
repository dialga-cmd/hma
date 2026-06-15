"""
Document file parser for HMA.

Extracts structural information from document files:
- Markdown/TXT: headings, links, references
- PDF: text extraction (optional dependency: PyMuPDF)
- DOCX: text extraction (optional dependency: python-docx)
- YAML/JSON/TOML: key structure
"""

import re
import json
from pathlib import Path
from typing import Optional

from hma.core.exceptions import ParserError


class DocParseResult:
    """Result of parsing a document file."""

    def __init__(self):
        self.headings: list[str] = []
        self.references: list[str] = []  # Links, file refs, URLs
        self.key_sections: list[str] = []
        self.content_preview: str = ""  # First ~500 chars
        self.doc_type: str = ""


class DocParser:
    """Parses document files to extract structural information."""

    def parse(self, file_path: Path, content: str, doc_type: str) -> DocParseResult:
        """Parse a document file and extract structural info."""
        result = DocParseResult()
        result.doc_type = doc_type

        try:
            parser_map = {
                "markdown": self._parse_markdown,
                "text": self._parse_text,
                "restructuredtext": self._parse_rst,
                "yaml": self._parse_yaml,
                "json": self._parse_json,
                "toml": self._parse_toml,
                "ini": self._parse_ini,
                "csv": self._parse_csv,
                "xml": self._parse_xml,
                "env": self._parse_env,
                "pdf": self._parse_pdf,
                "docx": self._parse_docx,
            }
            parser_fn = parser_map.get(doc_type, self._parse_text)

            if doc_type in ("pdf", "docx"):
                parser_fn(file_path, result)
            else:
                parser_fn(content, result)
        except Exception:
            result.content_preview = content[:500] if content else ""

        return result

    def _parse_markdown(self, content: str, result: DocParseResult) -> None:
        """Parse Markdown files."""
        # Headings
        for m in re.finditer(r"^(#{1,6})\s+(.+)$", content, re.MULTILINE):
            level = len(m.group(1))
            result.headings.append(f"{'#' * level} {m.group(2).strip()}")

        # Links and references
        for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", content):
            result.references.append(m.group(2))

        # File references in code blocks
        for m in re.finditer(r"`([^`]*(?:\.\w+))`", content):
            if "." in m.group(1) and "/" in m.group(1):
                result.references.append(m.group(1))

        # Key sections (top-level headings)
        result.key_sections = [
            h.lstrip("# ") for h in result.headings if h.startswith("# ") or h.startswith("## ")
        ]

        result.content_preview = content[:500]

    def _parse_text(self, content: str, result: DocParseResult) -> None:
        """Parse plain text files."""
        lines = content.split("\n")
        # Look for section-like patterns (ALL CAPS lines, underlined lines)
        for i, line in enumerate(lines[:100]):
            stripped = line.strip()
            if stripped and stripped.isupper() and len(stripped) > 3:
                result.headings.append(stripped)
            elif i + 1 < len(lines) and lines[i + 1].strip().startswith("==="):
                result.headings.append(stripped)

        result.content_preview = content[:500]

    def _parse_rst(self, content: str, result: DocParseResult) -> None:
        """Parse reStructuredText files."""
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and all(c in "=-~^" for c in next_line) and len(next_line) >= 3:
                    result.headings.append(line.strip())

        # Directives and references
        for m in re.finditer(r"\.\.\s+(\w+)::", content):
            result.key_sections.append(f"directive: {m.group(1)}")

        result.content_preview = content[:500]

    def _parse_yaml(self, content: str, result: DocParseResult) -> None:
        """Parse YAML files - extract top-level keys."""
        for m in re.finditer(r"^(\w[\w-]*):", content, re.MULTILINE):
            result.headings.append(m.group(1))

        result.key_sections = result.headings[:20]
        result.content_preview = content[:500]

    def _parse_json(self, content: str, result: DocParseResult) -> None:
        """Parse JSON files - extract top-level keys."""
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                result.headings = list(data.keys())[:30]
                result.key_sections = result.headings[:20]
        except json.JSONDecodeError:
            pass

        result.content_preview = content[:500]

    def _parse_toml(self, content: str, result: DocParseResult) -> None:
        """Parse TOML files - extract sections and keys."""
        for m in re.finditer(r"^\[([^\]]+)\]", content, re.MULTILINE):
            result.headings.append(f"[{m.group(1)}]")

        result.key_sections = [h.strip("[]") for h in result.headings]
        result.content_preview = content[:500]

    def _parse_ini(self, content: str, result: DocParseResult) -> None:
        """Parse INI/config files."""
        for m in re.finditer(r"^\[([^\]]+)\]", content, re.MULTILINE):
            result.headings.append(m.group(1))

        result.key_sections = result.headings
        result.content_preview = content[:500]

    def _parse_csv(self, content: str, result: DocParseResult) -> None:
        """Parse CSV files - extract header row."""
        lines = content.split("\n")
        if lines:
            headers = lines[0].strip().split(",")
            result.headings = [h.strip().strip('"') for h in headers]
            result.key_sections = [f"{len(lines)} rows, {len(headers)} columns"]

        result.content_preview = content[:500]

    def _parse_xml(self, content: str, result: DocParseResult) -> None:
        """Parse XML files - extract top-level tags."""
        for m in re.finditer(r"<(\w+)[\s>]", content):
            tag = m.group(1)
            if tag not in result.headings and tag not in ("xml", "?xml"):
                result.headings.append(tag)
                if len(result.headings) >= 20:
                    break

        result.content_preview = content[:500]

    def _parse_env(self, content: str, result: DocParseResult) -> None:
        """Parse .env files - extract variable names."""
        for m in re.finditer(r"^([A-Z_][A-Z0-9_]*)=", content, re.MULTILINE):
            result.headings.append(m.group(1))

        result.key_sections = result.headings
        result.content_preview = content[:500]

    def _parse_pdf(self, file_path: Path, result: DocParseResult) -> None:
        """Parse PDF files using PyMuPDF (optional dependency)."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            result.content_preview = "[PDF parsing requires PyMuPDF: pip install PyMuPDF]"
            return

        try:
            doc = fitz.open(str(file_path))
            text_parts = []
            for page_num in range(min(len(doc), 10)):  # First 10 pages
                page = doc[page_num]
                text_parts.append(page.get_text())
            full_text = "\n".join(text_parts)

            # Extract headings (lines that look like titles)
            for line in full_text.split("\n"):
                stripped = line.strip()
                if stripped and len(stripped) < 100 and stripped[0].isupper():
                    if stripped.isupper() or (len(stripped.split()) <= 8):
                        result.headings.append(stripped)

            result.content_preview = full_text[:500]
            doc.close()
        except Exception:
            result.content_preview = "[Error reading PDF]"

    def _parse_docx(self, file_path: Path, result: DocParseResult) -> None:
        """Parse DOCX files using python-docx (optional dependency)."""
        try:
            from docx import Document
        except ImportError:
            result.content_preview = "[DOCX parsing requires python-docx: pip install python-docx]"
            return

        try:
            doc = Document(str(file_path))
            text_parts = []
            for para in doc.paragraphs:
                if para.style.name.startswith("Heading"):
                    result.headings.append(para.text)
                text_parts.append(para.text)

            result.content_preview = "\n".join(text_parts)[:500]
        except Exception:
            result.content_preview = "[Error reading DOCX]"
