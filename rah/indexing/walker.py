"""
File system walker for RAH.

Recursively traverses a project directory, respecting exclusion
patterns and .gitignore rules, and returns a list of files to index.
"""

import os
import fnmatch
from pathlib import Path
from dataclasses import dataclass

from rah.core.config import RAHConfig


@dataclass
class FileInfo:
    """Basic metadata about a discovered file."""

    path: Path
    """Absolute path to the file."""

    relative_path: str
    """Path relative to the project root."""

    size_bytes: int
    """File size in bytes."""

    extension: str
    """File extension including dot (e.g., '.py')."""


class Walker:
    """
    Walks a project directory and discovers files to index.

    Respects .gitignore patterns, configurable exclusions,
    and file size limits.
    """

    def __init__(self, config: RAHConfig):
        self.config = config
        self._gitignore_patterns: list[str] = []

    def walk(self, root: Path) -> list[FileInfo]:
        """
        Walk the directory tree and return all indexable files.

        Args:
            root: Absolute path to the project root.

        Returns:
            List of FileInfo objects for each discovered file.
        """
        root = root.resolve()
        files: list[FileInfo] = []

        # Load .gitignore if configured
        if self.config.respect_gitignore:
            self._load_gitignore(root)

        self._walk_recursive(root, root, files)
        return files

    def _walk_recursive(
        self, current: Path, root: Path, files: list[FileInfo]
    ) -> None:
        """Recursively walk directories."""
        try:
            entries = sorted(current.iterdir())
        except PermissionError:
            return

        for entry in entries:
            relative = str(entry.relative_to(root))

            if entry.is_dir():
                # Skip excluded directories
                if self.config.is_excluded_dir(entry.name):
                    continue
                if self._is_gitignored(relative + "/"):
                    continue
                self._walk_recursive(entry, root, files)

            elif entry.is_file():
                # Skip excluded files
                if self.config.is_excluded_file(entry.name):
                    continue

                # Skip files matching exclude patterns
                if any(
                    fnmatch.fnmatch(entry.name, pat)
                    for pat in self.config.exclude_patterns
                ):
                    continue

                if self._is_gitignored(relative):
                    continue

                # Check if file type is supported
                ext = entry.suffix
                file_type, category = self.config.get_file_type(ext)
                if file_type is None:
                    continue

                # Check file size
                try:
                    size = entry.stat().st_size
                except OSError:
                    continue

                if size > self.config.max_file_size_bytes:
                    continue

                if size == 0:
                    continue

                files.append(
                    FileInfo(
                        path=entry,
                        relative_path=relative,
                        size_bytes=size,
                        extension=ext,
                    )
                )

    def _load_gitignore(self, root: Path) -> None:
        """Load .gitignore patterns from the project root."""
        gitignore_path = root / ".gitignore"
        if not gitignore_path.exists():
            return

        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue
                    self._gitignore_patterns.append(line)
        except (IOError, OSError):
            pass

    def _is_gitignored(self, relative_path: str) -> bool:
        """Check if a path matches any .gitignore pattern."""
        for pattern in self._gitignore_patterns:
            # Handle directory-specific patterns
            if pattern.endswith("/"):
                dir_pattern = pattern.rstrip("/")
                parts = relative_path.split(os.sep)
                if dir_pattern in parts:
                    return True
            # Handle glob patterns
            elif fnmatch.fnmatch(relative_path, pattern):
                return True
            elif fnmatch.fnmatch(os.path.basename(relative_path), pattern):
                return True
            # Handle patterns with leading /
            elif pattern.startswith("/"):
                if fnmatch.fnmatch(relative_path, pattern.lstrip("/")):
                    return True
        return False

    def build_directory_tree(self, root: Path, files: list[FileInfo]) -> dict:
        """
        Build a nested dictionary representing the directory structure.

        Only includes directories that contain indexed files.

        Args:
            root: Project root path.
            files: List of discovered files.

        Returns:
            Nested dict like: {"src": {"main.py": None, "utils": {"helper.py": None}}}
        """
        tree: dict = {}
        for file_info in files:
            parts = file_info.relative_path.split(os.sep)
            current = tree
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            # Files are stored as None values
            current[parts[-1]] = None
        return tree
