"""
Traverser for RAH querying.

Finds and reads files that are DIRECTLY connected to the targeted files.
This is strictly single-hop traversal — it does not recurse.
"""

from rah.core.models import KnowledgeMap
from rah.core.config import RAHConfig
from rah.querying.reader import Reader


class Traverser:
    """Follows direct connections (single-hop) to gather related context."""

    def __init__(self, config: RAHConfig):
        self.config = config
        self.reader = Reader(config)

    def get_connected_context(
        self, 
        target_files: list[str], 
        kmap: KnowledgeMap
    ) -> tuple[dict[str, str], list[str]]:
        """
        Find and read files directly connected to the target files.

        Args:
            target_files: The initial files selected by the router.
            kmap: The KnowledgeMap.

        Returns:
            Tuple of (dict mapping connected_file_path to content, list of connected_paths).
        """
        if not self.config.include_connections:
            return {}, []

        connected_paths = set()
        
        # Gather single-hop connections
        for target in target_files:
            conns = kmap.get_connected_files(target)
            for c in conns:
                # Don't re-read files we already selected
                if c not in target_files:
                    connected_paths.add(c)
                    
        connected_list = list(connected_paths)
        
        if not connected_list:
            return {}, []

        # We give connected files a smaller character budget than primary files
        max_chars = 4000  # Give them about ~1000 tokens of context max
        
        # Read the connected files
        contents = self.reader.read_files(
            kmap.root_path, 
            connected_list, 
            max_chars_per_file=max_chars
        )
        
        return contents, connected_list
