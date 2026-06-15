"""
Query engine that orchestrates the RAH querying phase.

Coordinates the Router, Reader, and Traverser to assemble context,
then calls the user's LLM to generate the final answer.
"""

from typing import Callable

from rah.core.models import KnowledgeMap, Answer
from rah.core.config import RAHConfig
from rah.querying.router import Router
from rah.querying.reader import Reader
from rah.querying.traverser import Traverser


class QueryEngine:
    """Orchestrates the querying phase of RAH."""

    def __init__(self, llm: Callable[[str], str], config: RAHConfig):
        self.llm = llm
        self.config = config
        self.router = Router(llm, config)
        self.reader = Reader(config)
        self.traverser = Traverser(config)

    def query(self, question: str, kmap: KnowledgeMap) -> Answer:
        """
        Answer a question using the Knowledge Map.

        1. Route question to best files.
        2. Read those files.
        3. Read directly connected files (single-hop).
        4. Assemble context and ask LLM.
        """
        # 1. Route to primary files
        primary_files, reasoning = self.router.route(question, kmap)
        
        if not primary_files:
            return Answer(
                text="I could not identify any relevant files in the project to answer this question.",
                sources=[],
                reasoning=reasoning,
            )

        # 2. Read primary files
        primary_content = self.reader.read_files(kmap.root_path, primary_files)

        # 3. Get connected files (single-hop)
        connected_content, connected_files = self.traverser.get_connected_context(
            primary_files, kmap
        )

        # 4. Assemble context and generate answer
        prompt = self._build_answer_prompt(
            question, primary_content, connected_content
        )
        
        try:
            answer_text = self.llm(prompt)
        except Exception as e:
            answer_text = f"[LLM Error while generating answer: {e}]"

        return Answer(
            text=answer_text,
            sources=primary_files,
            connections=connected_files,
            reasoning=reasoning,
        )

    def _build_answer_prompt(
        self, 
        question: str, 
        primary_content: dict[str, str], 
        connected_content: dict[str, str]
    ) -> str:
        """Build the final prompt for answering the user's question."""
        context_parts = []
        
        # Add primary files
        context_parts.append("--- PRIMARY TARGET FILES ---")
        for path, content in primary_content.items():
            context_parts.append(f"### File: {path}\n```\n{content}\n```\n")
            
        # Add connected files
        if connected_content:
            context_parts.append("--- DIRECTLY CONNECTED FILES (For Additional Context) ---")
            for path, content in connected_content.items():
                context_parts.append(f"### Connected File: {path}\n```\n{content}\n```\n")
                
        context_str = "\n".join(context_parts)
        
        return (
            "You are answering a question about a codebase or document repository.\n"
            "Below is the relevant file context retrieved for the question.\n\n"
            f"{context_str}\n\n"
            f"QUESTION: {question}\n\n"
            "Please provide a detailed and accurate answer based ONLY on the provided context. "
            "If the context does not contain enough information to fully answer the question, say so. "
            "Cite the file names when you reference specific parts of the code/docs."
        )
