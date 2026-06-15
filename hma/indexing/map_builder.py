"""
Orchestrator for the indexing phase.

Coordinates the walker, analyzer, summarizer, and relationship extractor
to build a complete KnowledgeMap of a project.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from hma.core.models import FileNode, KnowledgeMap
from hma.core.config import HMAConfig
from hma.core.exceptions import IndexingError
from hma.indexing.walker import Walker
from hma.indexing.analyzer import Analyzer, AnalysisResult
from hma.indexing.summarizer import Summarizer
from hma.indexing.relationship import RelationshipExtractor


class MapBuilder:
    """Orchestrator for building a KnowledgeMap."""

    def __init__(self, llm: Callable[[str], str], config: HMAConfig):
        self.config = config
        self.walker = Walker(config)
        self.analyzer = Analyzer(config)
        self.summarizer = Summarizer(llm, config)
        self.relationship_extractor = RelationshipExtractor(config)

    def build(self, root_path: Path, existing_map: Optional[KnowledgeMap] = None) -> KnowledgeMap:
        """
        Build or update a KnowledgeMap for the given project root.

        Args:
            root_path: Absolute path to the project root.
            existing_map: Optional existing map for incremental updates.

        Returns:
            A new or updated KnowledgeMap.
        """
        root_path_str = str(root_path.resolve())
        now_iso = datetime.now(timezone.utc).isoformat()

        # Initialize or reuse map
        if existing_map and existing_map.root_path == root_path_str:
            kmap = existing_map
            kmap.updated_at = now_iso
            # We don't overwrite created_at
        else:
            kmap = KnowledgeMap(
                root_path=root_path_str,
                created_at=now_iso,
                updated_at=now_iso,
            )

        # 1. Walk file system
        files = self.walker.walk(root_path)
        kmap.directory_tree = self.walker.build_directory_tree(root_path, files)
        kmap.total_files = len(files)

        # Separate files into 'needs processing' vs 'unchanged'
        to_process = []
        unchanged_paths = set()

        for file_info in files:
            path = file_info.relative_path
            
            # Fast check: does it exist and is it small enough?
            if file_info.size_bytes > self.config.max_file_size_bytes:
                continue

            # Need to read at least to hash it for incremental check
            file_type, category = self.config.get_file_type(file_info.extension)
            # Analyzer does the reading and hashing
            analysis = self.analyzer.analyze(file_info)

            is_changed = True
            if path in kmap.nodes:
                old_node = kmap.nodes[path]
                if old_node.content_hash == analysis.content_hash:
                    is_changed = False
            
            if is_changed:
                to_process.append(analysis)
            else:
                unchanged_paths.add(path)

        # Remove deleted files from map
        current_paths = {f.relative_path for f in files}
        deleted_paths = set(kmap.nodes.keys()) - current_paths
        for p in deleted_paths:
            del kmap.nodes[p]

        # 2. Process changed/new files (Analyze & Summarize)
        analyses_dict: dict[str, AnalysisResult] = {}
        
        # We process in batches for summarization to be efficient
        small_files = []
        large_files = []

        for analysis in to_process:
            analyses_dict[analysis.relative_path] = analysis
            if (
                self.config.batch_small_files
                and analysis.size_bytes <= self.config.small_file_threshold_bytes
            ):
                small_files.append(analysis)
            else:
                large_files.append(analysis)

        # Summarize large files individually
        for analysis in large_files:
            summary, topics = self.summarizer.summarize_file(analysis)
            self._add_node_to_map(kmap, analysis, summary, topics, now_iso)

        # Summarize small files in batches
        for i in range(0, len(small_files), self.config.max_batch_size):
            batch = small_files[i : i + self.config.max_batch_size]
            results = self.summarizer.summarize_batch(batch)
            for analysis, (summary, topics) in zip(batch, results):
                self._add_node_to_map(kmap, analysis, summary, topics, now_iso)

        # 3. Rebuild Relationships
        # For relationships, we need all analyses, even unchanged ones, if we want
        # to correctly extract relationships. For a true incremental update of relationships,
        # it gets complex. For this version, if there are changes, we might miss some 
        # relationships if we don't re-analyze unchanged files.
        # Simple approach: If any file changed, we re-run relation extraction on ALL files.
        # This requires re-reading unchanged files.
        
        if to_process or deleted_paths:
            # We need full analyses dict for accurate relationship extraction
            for file_info in files:
                if file_info.relative_path in unchanged_paths:
                    analysis = self.analyzer.analyze(file_info)
                    analyses_dict[file_info.relative_path] = analysis
                    
            kmap.relationships = self.relationship_extractor.extract(analyses_dict)

        # 4. Project Summary (if new or significantly changed)
        # We generate a project summary if it doesn't exist or if more than 10% of files changed
        change_ratio = len(to_process) / max(1, len(files))
        if not kmap.project_summary or change_ratio > 0.1:
            file_summaries = [
                {"path": node.path, "summary": node.summary}
                for node in kmap.nodes.values()
            ]
            kmap.project_summary = self.summarizer.summarize_project(file_summaries)

        return kmap

    def _add_node_to_map(
        self,
        kmap: KnowledgeMap,
        analysis: AnalysisResult,
        summary: str,
        topics: list[str],
        timestamp: str,
    ) -> None:
        """Create a FileNode and add it to the KnowledgeMap."""
        node = FileNode(
            path=analysis.relative_path,
            file_type=analysis.file_type,
            category=analysis.category,
            size_bytes=analysis.size_bytes,
            summary=summary,
            key_topics=topics,
            exports=analysis.exports,
            imports=analysis.imports,
            last_indexed=timestamp,
            content_hash=analysis.content_hash,
            line_count=analysis.line_count,
        )
        kmap.nodes[node.path] = node
