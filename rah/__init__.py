"""
RAH — Retrieval-Augmented Hierarchy

A smarter alternative to RAG that maps your file structure and routes
queries to the right files — instead of blindly scanning chunks.

Usage:
    from rah import RAH

    def my_llm(prompt: str) -> str:
        return your_model.generate(prompt)

    rah = RAH(llm=my_llm)
    knowledge_map = rah.index("/path/to/project")
    answer = rah.ask("How does authentication work?")
"""

__version__ = "0.1.0"
__author__ = "RAH Contributors"

from rah.core.models import FileNode, Relationship, KnowledgeMap, Answer
from rah.core.config import RAHConfig
from rah.core.exceptions import (
    RAHError,
    IndexingError,
    QueryError,
    NoLLMError,
    MapNotFoundError,
)
from rah.indexing.map_builder import MapBuilder
from rah.querying.answerer import QueryEngine
from rah.storage.json_store import JSONStore

from typing import Callable, Optional, Union
from pathlib import Path


class RAH:
    """
    Main entry point for the RAH library.

    RAH (Retrieval-Augmented Hierarchy) analyzes your project's file
    structure, builds a knowledge map, and routes queries to the most
    relevant files — instead of scanning every chunk like traditional RAG.

    Args:
        llm: A callable that takes a prompt string and returns a response string.
             This is YOUR LLM — RAH doesn't bundle any model.
        config: Optional RAHConfig for customizing behavior.
    """

    def __init__(
        self,
        llm: Callable[[str], str],
        config: Optional[RAHConfig] = None,
    ):
        if not callable(llm):
            raise NoLLMError(
                "The 'llm' argument must be a callable that takes a prompt (str) "
                "and returns a response (str). RAH does not bundle any LLM — "
                "you must provide your own."
            )
        self.llm = llm
        self.config = config or RAHConfig()
        self._map: Optional[KnowledgeMap] = None
        self._store = JSONStore()
        self._builder = MapBuilder(llm=self.llm, config=self.config)
        self._engine = QueryEngine(llm=self.llm, config=self.config)

    def index(
        self,
        path: Union[str, Path],
        incremental: bool = True,
    ) -> KnowledgeMap:
        """
        Index a project directory and build a Knowledge Map.

        Analyzes every file, extracts summaries and relationships,
        and saves the map as .rah.json in the project root.

        Args:
            path: Path to the project directory to index.
            incremental: If True, only re-index files that changed since
                         the last indexing. If False, re-index everything.

        Returns:
            The generated KnowledgeMap.
        """
        root = Path(path).resolve()
        if not root.is_dir():
            raise IndexingError(f"Path '{root}' is not a directory.")

        # Try to load existing map for incremental indexing
        existing_map = None
        if incremental:
            existing_map = self._store.load(root)

        self._map = self._builder.build(root, existing_map=existing_map)
        self._store.save(self._map, root)
        return self._map

    def ask(
        self,
        question: str,
        project_path: Optional[Union[str, Path]] = None,
    ) -> Answer:
        """
        Ask a question about the indexed project.

        Routes the question to the most relevant files using the
        Knowledge Map, reads their content (plus directly connected files),
        and generates an answer using your LLM.

        Args:
            question: The question to ask about the project.
            project_path: Path to the project. If not provided, uses
                          the last indexed project.

        Returns:
            An Answer object with text, sources, connections, and reasoning.
        """
        if self._map is None and project_path is not None:
            self._map = self._store.load(Path(project_path).resolve())

        if self._map is None:
            raise MapNotFoundError(
                "No Knowledge Map found. Run rah.index('/path/to/project') first, "
                "or provide a project_path that has been previously indexed."
            )

        return self._engine.query(question, self._map)

    def get_map(
        self,
        project_path: Optional[Union[str, Path]] = None,
    ) -> Optional[KnowledgeMap]:
        """
        Get the Knowledge Map for a project.

        Returns the in-memory map if available, otherwise loads from disk.

        Args:
            project_path: Path to load the map from. If not provided,
                          returns the in-memory map.

        Returns:
            The KnowledgeMap, or None if not found.
        """
        if self._map is not None:
            return self._map

        if project_path is not None:
            self._map = self._store.load(Path(project_path).resolve())

        return self._map

    def __repr__(self) -> str:
        status = "indexed" if self._map else "not indexed"
        return f"RAH(status={status}, version={__version__})"
