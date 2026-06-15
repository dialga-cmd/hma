"""
JSON storage for RAH Knowledge Maps.

Handles persisting the KnowledgeMap to a `.rah.json` file.
"""

import json
from pathlib import Path
from typing import Optional

from rah.core.models import KnowledgeMap
from rah.core.config import RAHConfig
from rah.core.exceptions import StorageError


class JSONStore:
    """
    Handles saving and loading the KnowledgeMap to/from a JSON file.
    """

    def __init__(self, filename: str = ".rah.json"):
        self.filename = filename

    def save(self, kmap: KnowledgeMap, project_root: Path) -> None:
        """
        Save the KnowledgeMap to a JSON file in the project root.

        Args:
            kmap: The KnowledgeMap to save.
            project_root: The root directory of the project.
        """
        file_path = project_root / self.filename
        try:
            data = kmap.to_dict()
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            raise StorageError(f"Failed to save Knowledge Map to {file_path}: {e}")

    def load(self, project_root: Path) -> Optional[KnowledgeMap]:
        """
        Load the KnowledgeMap from a JSON file in the project root.

        Args:
            project_root: The root directory of the project.

        Returns:
            The loaded KnowledgeMap, or None if it doesn't exist.
        """
        file_path = project_root / self.filename
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return KnowledgeMap.from_dict(data)
        except Exception as e:
            raise StorageError(f"Failed to load Knowledge Map from {file_path}: {e}")
