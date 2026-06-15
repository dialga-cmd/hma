"""
Query Router for HMA.

The router determines which files in the KnowledgeMap are most
relevant to the user's question. It uses a two-step approach:
1. Fast pre-filtering using topic/export matching.
2. LLM reasoning over the filtered summaries to pick the best files.
"""

import json
from typing import Callable

from hma.core.models import KnowledgeMap, FileNode
from hma.core.config import HMAConfig


class Router:
    """Routes queries to relevant files."""

    def __init__(self, llm: Callable[[str], str], config: HMAConfig):
        self.llm = llm
        self.config = config

    def route(self, question: str, kmap: KnowledgeMap) -> tuple[list[str], str]:
        """
        Determine which files best answer the question.

        Args:
            question: The user's question.
            kmap: The KnowledgeMap.

        Returns:
            Tuple of (list_of_file_paths, reasoning_string).
        """
        if not kmap.nodes:
            return [], "Knowledge Map is empty."

        # Step 1: Pre-filter files to avoid sending the whole project to the LLM
        filtered_summaries = self._pre_filter(question, kmap)

        # If project is small, just use all files
        if len(kmap.nodes) <= 15:
            filtered_summaries = kmap.get_file_summaries()
            
        if not filtered_summaries:
            return [], "No relevant files found during pre-filtering."

        # Step 2: Ask the LLM to route
        prompt = self._build_routing_prompt(question, filtered_summaries)
        
        try:
            response = self.llm(prompt)
            return self._parse_routing_response(response, kmap)
        except Exception as e:
            # Fallback: just return the top pre-filtered files
            paths = [s["path"] for s in filtered_summaries[:self.config.max_files_to_route]]
            return paths, f"LLM routing failed ({e}), using keyword matching fallback."

    def _pre_filter(self, question: str, kmap: KnowledgeMap) -> list[dict]:
        """
        Fast heuristic filtering based on keywords in the question.
        """
        question_words = set(
            w.lower().strip("?,.!") 
            for w in question.split() 
            if len(w) > 3
        )
        
        scored_files = []
        
        for path, node in kmap.nodes.items():
            score = 0
            
            # Check path
            path_lower = path.lower()
            for word in question_words:
                if word in path_lower:
                    score += 5
            
            # Check topics
            for topic in node.key_topics:
                for word in question_words:
                    if word in topic.lower():
                        score += 3
            
            # Check exports
            for exp in node.exports:
                for word in question_words:
                    if word in exp.lower():
                        score += 2
                        
            # Give a small base score to prioritize important files like __init__ or main
            if "main" in path_lower or "index" in path_lower or "__init__" in path_lower:
                score += 1
                
            scored_files.append((score, node))
            
        # Sort by score descending
        scored_files.sort(key=lambda x: x[0], reverse=True)
        
        # Take top N candidates for the LLM to consider (max 20 to save tokens)
        top_candidates = [node for score, node in scored_files[:20]]
        
        return [
            {
                "path": node.path,
                "summary": node.summary,
                "topics": node.key_topics,
            }
            for node in top_candidates
        ]

    def _build_routing_prompt(self, question: str, file_summaries: list[dict]) -> str:
        """Build the prompt for the LLM to select the best files."""
        summaries_json = json.dumps(file_summaries, indent=2)
        
        return (
            "You are an intelligent code router for a retrieval system.\n"
            f"A user has asked: '{question}'\n\n"
            "Below is a list of candidate files from the project, with their summaries "
            "and key topics.\n\n"
            f"FILES:\n{summaries_json}\n\n"
            f"Select the {self.config.max_files_to_route} most relevant files that "
            "are likely to contain the answer.\n"
            "Respond in EXACTLY the following format:\n"
            "FILES: file1.py, file2.js\n"
            "REASONING: I chose file1.py because..."
        )

    def _parse_routing_response(
        self, response: str, kmap: KnowledgeMap
    ) -> tuple[list[str], str]:
        """Parse the LLM's routing response."""
        files = []
        reasoning = "No reasoning provided."
        
        for line in response.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("FILES:"):
                files_str = line[len("FILES:"):].strip()
                # Clean up json artifacts if model outputs ["file.py"]
                files_str = files_str.replace('"', '').replace('[', '').replace(']', '')
                raw_files = [f.strip() for f in files_str.split(",")]
                
                # Only keep files that actually exist in the map
                for rf in raw_files:
                    if rf in kmap.nodes:
                        files.append(rf)
                    else:
                        # Try to find a partial match
                        for path in kmap.nodes:
                            if rf in path or path in rf:
                                files.append(path)
                                break
                                
            elif line.upper().startswith("REASONING:"):
                reasoning = line[len("REASONING:"):].strip()
                
        # Limit to configured max
        files = list(dict.fromkeys(files))[:self.config.max_files_to_route]
        return files, reasoning
