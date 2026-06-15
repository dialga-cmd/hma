"""
File reader for RAH querying.

Reads the actual content of files selected by the Router,
applying smart truncation if files are too large.
"""

from pathlib import Path
from typing import Optional

from rah.core.models import FileNode
from rah.core.config import RAHConfig


class Reader:
    """Reads file content from disk with truncation for context limits."""

    def __init__(self, config: RAHConfig):
        self.config = config

    def read_files(
        self, root_path: str, file_paths: list[str], max_chars_per_file: Optional[int] = None
    ) -> dict[str, str]:
        """
        Read the contents of multiple files.

        Args:
            root_path: Project root directory.
            file_paths: List of relative file paths to read.
            max_chars_per_file: Optional override for max chars per file.

        Returns:
            Dict mapping file_path to its content.
        """
        root = Path(root_path)
        contents = {}
        
        limit = max_chars_per_file or self.config.max_context_length // max(1, len(file_paths))

        for path in file_paths:
            full_path = root / path
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                    
                if len(content) > limit:
                    # Truncate but indicate it
                    content = content[:limit] + f"\n\n[... File truncated due to context limits. Showing first {limit} chars ...]"
                    
                contents[path] = content
            except Exception as e:
                contents[path] = f"[Error reading file {path}: {e}]"

        return contents
