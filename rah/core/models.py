"""
Data models for RAH Knowledge Maps.

These dataclasses define the structure of the Knowledge Map —
the central data structure that RAH uses to route queries to
the right files instead of scanning chunks.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class FileNode:
    """
    Represents a single file in the Knowledge Map.

    Each file in the indexed project gets a FileNode that stores
    its metadata, LLM-generated summary, key topics, and exports.
    """

    path: str
    """Relative path from the project root."""

    file_type: str
    """Detected file type, e.g., 'python', 'javascript', 'markdown'."""

    category: str
    """Either 'code' or 'document'."""

    size_bytes: int
    """File size in bytes."""

    summary: str
    """LLM-generated 2-3 sentence summary of what this file does."""

    key_topics: list[str] = field(default_factory=list)
    """Extracted topics/keywords relevant to this file's content."""

    exports: list[str] = field(default_factory=list)
    """Functions, classes, or variables exported/defined in this file."""

    imports: list[str] = field(default_factory=list)
    """Files or modules this file imports from."""

    last_indexed: str = ""
    """ISO timestamp of when this file was last indexed."""

    content_hash: str = ""
    """SHA-256 hash of file content, used for incremental re-indexing."""

    line_count: int = 0
    """Number of lines in the file."""

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "path": self.path,
            "file_type": self.file_type,
            "category": self.category,
            "size_bytes": self.size_bytes,
            "summary": self.summary,
            "key_topics": self.key_topics,
            "exports": self.exports,
            "imports": self.imports,
            "last_indexed": self.last_indexed,
            "content_hash": self.content_hash,
            "line_count": self.line_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileNode":
        """Deserialize from dictionary."""
        return cls(
            path=data["path"],
            file_type=data["file_type"],
            category=data["category"],
            size_bytes=data["size_bytes"],
            summary=data["summary"],
            key_topics=data.get("key_topics", []),
            exports=data.get("exports", []),
            imports=data.get("imports", []),
            last_indexed=data.get("last_indexed", ""),
            content_hash=data.get("content_hash", ""),
            line_count=data.get("line_count", 0),
        )


@dataclass
class Relationship:
    """
    A direct connection between two files.

    Relationships are single-hop only — RAH tracks which files are
    directly connected but does NOT recursively follow connections.
    """

    source: str
    """Source file path (relative to project root)."""

    target: str
    """Target file path (relative to project root)."""

    relation_type: str
    """
    Type of relationship. One of:
    - 'imports': source imports from target
    - 'references': source references target (config, path, URL)
    - 'tests': source is a test file for target
    - 'documents': source documents/describes target
    """

    details: str = ""
    """Human-readable details, e.g., 'imports function calculate_tax'."""

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "source": self.source,
            "target": self.target,
            "relation_type": self.relation_type,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Relationship":
        """Deserialize from dictionary."""
        return cls(
            source=data["source"],
            target=data["target"],
            relation_type=data["relation_type"],
            details=data.get("details", ""),
        )


@dataclass
class KnowledgeMap:
    """
    The complete structural map of a project.

    This is the central data structure in RAH. It contains:
    - A node for every file with its summary and metadata
    - Relationships (direct connections) between files
    - A directory tree showing the project structure
    - A project-level summary

    The Knowledge Map is persisted as .rah.json and used to route
    queries to the most relevant files.
    """

    root_path: str
    """Absolute path to the project root."""

    nodes: dict[str, "FileNode"] = field(default_factory=dict)
    """Mapping of relative file path → FileNode."""

    relationships: list["Relationship"] = field(default_factory=list)
    """List of direct connections between files."""

    directory_tree: dict = field(default_factory=dict)
    """Nested dict representing the directory structure."""

    project_summary: str = ""
    """LLM-generated high-level summary of the entire project."""

    created_at: str = ""
    """ISO timestamp of when this map was first created."""

    updated_at: str = ""
    """ISO timestamp of the last update."""

    version: str = "0.1.0"
    """RAH version that created/updated this map."""

    total_files: int = 0
    """Total number of indexed files."""

    def get_connections(self, file_path: str) -> list["Relationship"]:
        """
        Get all DIRECT connections for a given file.

        This is single-hop only — returns relationships where the
        given file is either source or target. Does NOT follow
        connections of connected files.

        Args:
            file_path: Relative path of the file to get connections for.

        Returns:
            List of Relationships involving this file.
        """
        return [
            r
            for r in self.relationships
            if r.source == file_path or r.target == file_path
        ]

    def get_connected_files(self, file_path: str) -> list[str]:
        """
        Get paths of all files directly connected to the given file.

        Single-hop only. Returns file paths, not the connections themselves.

        Args:
            file_path: Relative path of the file.

        Returns:
            List of connected file paths.
        """
        connected = set()
        for r in self.relationships:
            if r.source == file_path:
                connected.add(r.target)
            elif r.target == file_path:
                connected.add(r.source)
        return list(connected)

    def get_file_summaries(self) -> list[dict]:
        """
        Get a compact list of all file summaries for routing.

        Returns a lightweight representation suitable for sending
        to the LLM for query routing.
        """
        return [
            {
                "path": node.path,
                "type": node.file_type,
                "summary": node.summary,
                "topics": node.key_topics,
                "exports": node.exports[:10],  # Limit to avoid token waste
            }
            for node in self.nodes.values()
        ]

    def to_dict(self) -> dict:
        """Serialize the entire map to a dictionary."""
        return {
            "rah_version": self.version,
            "root_path": self.root_path,
            "project_summary": self.project_summary,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "total_files": self.total_files,
            "directory_tree": self.directory_tree,
            "nodes": {
                path: node.to_dict() for path, node in self.nodes.items()
            },
            "relationships": [r.to_dict() for r in self.relationships],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeMap":
        """Deserialize from dictionary."""
        km = cls(
            root_path=data["root_path"],
            project_summary=data.get("project_summary", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            version=data.get("rah_version", "0.1.0"),
            total_files=data.get("total_files", 0),
            directory_tree=data.get("directory_tree", {}),
        )
        km.nodes = {
            path: FileNode.from_dict(node_data)
            for path, node_data in data.get("nodes", {}).items()
        }
        km.relationships = [
            Relationship.from_dict(r_data)
            for r_data in data.get("relationships", [])
        ]
        return km


@dataclass
class Answer:
    """
    The result of a RAH query.

    Contains the answer text along with metadata about which files
    were consulted and why.
    """

    text: str
    """The generated answer text."""

    sources: list[str] = field(default_factory=list)
    """File paths that were directly consulted for this answer."""

    connections: list[str] = field(default_factory=list)
    """File paths read as direct connections of the source files."""

    reasoning: str = ""
    """Explanation of why these specific files were chosen."""

    confidence: float = 0.0
    """Confidence score (0.0 to 1.0) from the routing step."""

    def __str__(self) -> str:
        return self.text
