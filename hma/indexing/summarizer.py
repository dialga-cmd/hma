"""
LLM-powered file summarizer for HMA.

Uses the USER's LLM callable to generate file summaries and
extract key topics. HMA does not bundle any LLM — this module
calls whatever function the user provides.
"""

import json
from typing import Callable

from hma.core.config import HMAConfig
from hma.indexing.analyzer import AnalysisResult


class Summarizer:
    """
    Generates file summaries and key topics using the user's LLM.

    Supports batching small files together to minimize LLM calls.
    """

    def __init__(self, llm: Callable[[str], str], config: HMAConfig):
        self.llm = llm
        self.config = config

    def summarize_file(self, analysis: AnalysisResult) -> tuple[str, list[str]]:
        """
        Generate a summary and key topics for a single file.

        Args:
            analysis: The analysis result from the Analyzer.

        Returns:
            Tuple of (summary_text, list_of_key_topics).
        """
        prompt = self._build_single_prompt(analysis)

        try:
            response = self.llm(prompt)
            return self._parse_response(response)
        except Exception as e:
            # Fallback: use docstring/preview or generate a basic summary
            return self._fallback_summary(analysis), self._fallback_topics(analysis)

    def summarize_batch(
        self, analyses: list[AnalysisResult]
    ) -> list[tuple[str, list[str]]]:
        """
        Summarize multiple small files in a single LLM call.

        Args:
            analyses: List of analysis results for small files.

        Returns:
            List of (summary, topics) tuples, one per file.
        """
        if not analyses:
            return []

        if len(analyses) == 1:
            return [self.summarize_file(analyses[0])]

        prompt = self._build_batch_prompt(analyses)

        try:
            response = self.llm(prompt)
            results = self._parse_batch_response(response, len(analyses))
            return results
        except Exception:
            # Fallback: summarize individually
            return [
                (self._fallback_summary(a), self._fallback_topics(a))
                for a in analyses
            ]

    def summarize_project(
        self, file_summaries: list[dict[str, str]]
    ) -> str:
        """
        Generate a project-level summary from individual file summaries.

        Args:
            file_summaries: List of dicts with 'path' and 'summary' keys.

        Returns:
            A high-level project summary string.
        """
        summaries_text = "\n".join(
            f"- {fs['path']}: {fs['summary']}" for fs in file_summaries[:50]
        )

        prompt = (
            "Based on the following file summaries from a software project, "
            "write a concise 3-5 sentence summary describing what this project "
            "does, its main purpose, and key components.\n\n"
            f"File summaries:\n{summaries_text}\n\n"
            "Project summary:"
        )

        try:
            return self.llm(prompt).strip()
        except Exception:
            return "Project summary could not be generated."

    def _build_single_prompt(self, analysis: AnalysisResult) -> str:
        """Build a prompt for summarizing a single file."""
        content_section = self._prepare_content(analysis)

        return (
            "Analyze the following file and provide:\n"
            "1. A concise 2-3 sentence summary of what this file does.\n"
            "2. A list of 5-10 key topics/keywords.\n\n"
            f"File: {analysis.relative_path}\n"
            f"Type: {analysis.file_type} ({analysis.category})\n"
            f"Lines: {analysis.line_count}\n"
            f"{content_section}\n\n"
            "Respond in EXACTLY this format:\n"
            "SUMMARY: <your summary here>\n"
            "TOPICS: <comma-separated list of topics>"
        )

    def _build_batch_prompt(self, analyses: list[AnalysisResult]) -> str:
        """Build a prompt for summarizing multiple files at once."""
        files_section = ""
        for i, analysis in enumerate(analyses):
            content = self._prepare_content(analysis)
            files_section += (
                f"\n--- FILE {i + 1}: {analysis.relative_path} ---\n"
                f"Type: {analysis.file_type}\n"
                f"{content}\n"
            )

        return (
            f"Analyze the following {len(analyses)} files and provide a summary "
            "and key topics for EACH file.\n"
            f"{files_section}\n\n"
            "For EACH file, respond in this format:\n"
            "FILE <number>:\n"
            "SUMMARY: <2-3 sentence summary>\n"
            "TOPICS: <comma-separated keywords>\n"
        )

    def _prepare_content(self, analysis: AnalysisResult) -> str:
        """Prepare file content for the prompt."""
        parts = []

        if analysis.docstring:
            parts.append(f"Docstring: {analysis.docstring[:300]}")

        if analysis.exports:
            exports_str = ", ".join(analysis.exports[:15])
            parts.append(f"Exports: {exports_str}")

        if analysis.imports:
            imports_str = ", ".join(analysis.imports[:10])
            parts.append(f"Imports: {imports_str}")

        if analysis.headings:
            headings_str = ", ".join(analysis.headings[:10])
            parts.append(f"Headings: {headings_str}")

        if analysis.key_sections:
            sections_str = ", ".join(analysis.key_sections[:10])
            parts.append(f"Sections: {sections_str}")

        # Include content preview or truncated full content
        content = analysis.content
        if len(content) > 3000:
            content = content[:3000] + "\n[... truncated ...]"

        if content:
            parts.append(f"Content:\n{content}")

        return "\n".join(parts)

    def _parse_response(self, response: str) -> tuple[str, list[str]]:
        """Parse LLM response for a single file summary."""
        summary = ""
        topics = []

        for line in response.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("SUMMARY:"):
                summary = line[len("SUMMARY:"):].strip()
            elif line.upper().startswith("TOPICS:"):
                topics_str = line[len("TOPICS:"):].strip()
                topics = [t.strip() for t in topics_str.split(",") if t.strip()]

        # Fallback: if format wasn't followed, use full response as summary
        if not summary:
            summary = response.strip()[:500]

        return summary, topics

    def _parse_batch_response(
        self, response: str, expected_count: int
    ) -> list[tuple[str, list[str]]]:
        """Parse LLM response for a batch of files."""
        results = []
        current_summary = ""
        current_topics = []

        for line in response.strip().split("\n"):
            line = line.strip()

            if line.upper().startswith("FILE") and ":" in line:
                # Save previous entry if exists
                if current_summary:
                    results.append((current_summary, current_topics))
                current_summary = ""
                current_topics = []

            elif line.upper().startswith("SUMMARY:"):
                current_summary = line[len("SUMMARY:"):].strip()

            elif line.upper().startswith("TOPICS:"):
                topics_str = line[len("TOPICS:"):].strip()
                current_topics = [
                    t.strip() for t in topics_str.split(",") if t.strip()
                ]

        # Don't forget the last entry
        if current_summary:
            results.append((current_summary, current_topics))

        # Pad with fallbacks if we got fewer results than expected
        while len(results) < expected_count:
            results.append(("Summary not available.", []))

        return results[:expected_count]

    def _fallback_summary(self, analysis: AnalysisResult) -> str:
        """Generate a basic summary without an LLM."""
        if analysis.docstring:
            return analysis.docstring[:300]
        if analysis.content_preview:
            return f"Document file containing: {analysis.content_preview[:200]}"
        if analysis.exports:
            exports = ", ".join(analysis.exports[:5])
            return f"{analysis.file_type.title()} file defining: {exports}"
        return f"{analysis.file_type.title()} file ({analysis.line_count} lines)."

    def _fallback_topics(self, analysis: AnalysisResult) -> list[str]:
        """Generate basic topics without an LLM."""
        topics = [analysis.file_type]
        topics.extend(analysis.exports[:5])
        topics.extend(analysis.headings[:5])
        return topics[:10]
