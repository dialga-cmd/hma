"""
Configuration management for HMA.

Defines default settings for file exclusions, supported file types,
size limits, and other configurable behaviors.
"""

from dataclasses import dataclass, field
from typing import Optional


# File extensions and their types/categories
CODE_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c_header",
    ".hpp": "cpp_header",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".r": "r",
    ".R": "r",
    ".lua": "lua",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".ps1": "powershell",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".vue": "vue",
    ".svelte": "svelte",
    ".dart": "dart",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hs": "haskell",
    ".ml": "ocaml",
    ".pl": "perl",
    ".pm": "perl",
}

DOCUMENT_EXTENSIONS: dict[str, str] = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".rst": "restructuredtext",
    ".adoc": "asciidoc",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".csv": "csv",
    ".xml": "xml",
    ".env": "env",
    ".properties": "properties",
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "doc",
}

# Directories to always skip
DEFAULT_EXCLUDE_DIRS: set[str] = {
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".env",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".eggs",
    "*.egg-info",
    ".next",
    ".nuxt",
    ".output",
    "coverage",
    ".coverage",
    ".idea",
    ".vscode",
    ".DS_Store",
    "vendor",
    "target",  # Rust/Java build output
    "bin",
    "obj",  # .NET build output
}

# Files to always skip
DEFAULT_EXCLUDE_FILES: set[str] = {
    ".hma.json",
    ".DS_Store",
    "Thumbs.db",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "go.sum",
    "composer.lock",
    "Gemfile.lock",
}


@dataclass
class HMAConfig:
    """
    Configuration for HMA behavior.

    All settings have sensible defaults but can be customized.
    """

    # --- File Walking ---
    exclude_dirs: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDE_DIRS))
    """Directory names/patterns to skip during indexing."""

    exclude_files: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDE_FILES))
    """File names to skip during indexing."""

    exclude_patterns: list[str] = field(default_factory=list)
    """Additional glob patterns to exclude (e.g., '*.min.js')."""

    respect_gitignore: bool = True
    """Whether to respect .gitignore patterns."""

    # --- File Analysis ---
    max_file_size_bytes: int = 1_000_000  # 1 MB
    """Maximum file size to analyze. Larger files are skipped."""

    max_file_size_for_llm: int = 500_000  # 500 KB
    """Maximum file size to send to the LLM for summarization.
    Larger files will be truncated to key sections."""

    supported_code_extensions: dict[str, str] = field(
        default_factory=lambda: dict(CODE_EXTENSIONS)
    )
    """Mapping of file extension → language name for code files."""

    supported_doc_extensions: dict[str, str] = field(
        default_factory=lambda: dict(DOCUMENT_EXTENSIONS)
    )
    """Mapping of file extension → type name for document files."""

    # --- Summarization ---
    batch_small_files: bool = True
    """Whether to batch small files together for LLM summarization."""

    small_file_threshold_bytes: int = 2_000  # 2 KB
    """Files smaller than this are considered 'small' for batching."""

    max_batch_size: int = 5
    """Maximum number of small files to batch in one LLM call."""

    # --- Querying ---
    max_files_to_route: int = 3
    """Maximum number of files the router should select per query."""

    max_context_length: int = 100_000  # ~25k tokens
    """Maximum total character length of context sent to the LLM."""

    include_connections: bool = True
    """Whether to include directly connected files in the context."""

    # --- Storage ---
    map_filename: str = ".hma.json"
    """Filename for the Knowledge Map."""

    def get_file_type(self, extension: str) -> tuple[Optional[str], Optional[str]]:
        """
        Get the file type and category for a given extension.

        Args:
            extension: File extension including dot (e.g., '.py').

        Returns:
            Tuple of (file_type, category) or (None, None) if unsupported.
        """
        ext = extension.lower()
        if ext in self.supported_code_extensions:
            return self.supported_code_extensions[ext], "code"
        if ext in self.supported_doc_extensions:
            return self.supported_doc_extensions[ext], "document"
        return None, None

    def is_excluded_dir(self, dir_name: str) -> bool:
        """Check if a directory name should be excluded."""
        return dir_name in self.exclude_dirs

    def is_excluded_file(self, file_name: str) -> bool:
        """Check if a file name should be excluded."""
        return file_name in self.exclude_files
