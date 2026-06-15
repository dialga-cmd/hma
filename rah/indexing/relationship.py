"""
Inter-file relationship extractor for RAH.

Builds the connection graph between files using structural analysis:
- Import relationships (code imports)
- References (config files, path references)
- Test relationships (test files → source files)
- Documentation relationships (docs → code)

All done locally via AST/regex analysis — no LLM needed.
"""

import os
import re
from pathlib import Path

from rah.core.models import Relationship
from rah.core.config import RAHConfig
from rah.indexing.analyzer import AnalysisResult


class RelationshipExtractor:
    """
    Extracts direct relationships between files.

    Only builds single-hop connections — no recursive traversal.
    """

    def __init__(self, config: RAHConfig):
        self.config = config

    def extract(
        self,
        analyses: dict[str, AnalysisResult],
    ) -> list[Relationship]:
        """
        Extract all relationships from analyzed files.

        Args:
            analyses: Dict mapping relative_path → AnalysisResult.

        Returns:
            List of Relationship objects.
        """
        relationships: list[Relationship] = []
        all_paths = set(analyses.keys())

        for path, analysis in analyses.items():
            if analysis.category == "code":
                relationships.extend(
                    self._extract_import_relationships(path, analysis, all_paths)
                )

            # References from any file type
            relationships.extend(
                self._extract_reference_relationships(path, analysis, all_paths)
            )

            # Test file relationships
            test_rel = self._extract_test_relationship(path, analysis, all_paths)
            if test_rel:
                relationships.append(test_rel)

            # Documentation relationships
            doc_rel = self._extract_doc_relationship(path, analysis, all_paths)
            if doc_rel:
                relationships.append(doc_rel)

        # Deduplicate
        return self._deduplicate(relationships)

    def _extract_import_relationships(
        self,
        source_path: str,
        analysis: AnalysisResult,
        all_paths: set[str],
    ) -> list[Relationship]:
        """Extract relationships from import statements."""
        relationships = []

        for import_source in analysis.import_sources:
            target = self._resolve_import(source_path, import_source, all_paths)
            if target and target != source_path:
                # Determine what's being imported
                matching_imports = [
                    imp for imp in analysis.imports
                    if import_source in imp
                ]
                details = matching_imports[0] if matching_imports else f"imports from {import_source}"

                relationships.append(
                    Relationship(
                        source=source_path,
                        target=target,
                        relation_type="imports",
                        details=details,
                    )
                )

        return relationships

    def _resolve_import(
        self,
        source_path: str,
        import_source: str,
        all_paths: set[str],
    ) -> str | None:
        """
        Resolve an import source string to an actual file path.

        Handles:
        - Python: 'module.submodule' → 'module/submodule.py' or 'module/submodule/__init__.py'
        - JS/TS: './utils' → 'utils.js' or 'utils/index.js'
        - Relative imports: '../helpers' → resolved relative to source
        - C/C++: 'header.h' → search in project
        """
        source_dir = os.path.dirname(source_path)

        # Try direct path resolution for relative imports
        if import_source.startswith("."):
            candidates = self._get_relative_candidates(source_dir, import_source)
        else:
            candidates = self._get_absolute_candidates(import_source)

        for candidate in candidates:
            # Normalize path separators
            candidate = candidate.replace("\\", "/")
            if candidate in all_paths:
                return candidate

        return None

    def _get_relative_candidates(
        self, source_dir: str, import_source: str
    ) -> list[str]:
        """Generate candidate paths for relative imports."""
        candidates = []
        # Strip leading dots
        cleaned = import_source.lstrip(".")
        level = len(import_source) - len(cleaned)

        # Go up directories
        base = source_dir
        for _ in range(level - 1):
            base = os.path.dirname(base)

        if cleaned:
            base_path = os.path.join(base, cleaned.replace(".", os.sep))
        else:
            base_path = base

        # Python-style
        candidates.append(base_path + ".py")
        candidates.append(os.path.join(base_path, "__init__.py"))

        # JS/TS-style
        for ext in (".js", ".jsx", ".ts", ".tsx"):
            candidates.append(base_path + ext)
        candidates.append(os.path.join(base_path, "index.js"))
        candidates.append(os.path.join(base_path, "index.ts"))

        return candidates

    def _get_absolute_candidates(self, import_source: str) -> list[str]:
        """Generate candidate paths for absolute/package imports."""
        candidates = []
        # Convert dotted path to file path
        path_form = import_source.replace(".", os.sep)

        # Python-style
        candidates.append(path_form + ".py")
        candidates.append(os.path.join(path_form, "__init__.py"))

        # JS/TS-style
        for ext in (".js", ".jsx", ".ts", ".tsx"):
            candidates.append(path_form + ext)
        candidates.append(os.path.join(path_form, "index.js"))
        candidates.append(os.path.join(path_form, "index.ts"))

        # C/C++ style (direct filename)
        candidates.append(import_source)

        # Ruby-style
        candidates.append(import_source + ".rb")

        # Go-style (package path)
        candidates.append(os.path.join(path_form, "main.go"))

        return candidates

    def _extract_reference_relationships(
        self,
        source_path: str,
        analysis: AnalysisResult,
        all_paths: set[str],
    ) -> list[Relationship]:
        """Extract relationships from file references in content."""
        relationships = []

        # Check references from doc parser
        for ref in analysis.references:
            # Skip URLs
            if ref.startswith("http://") or ref.startswith("https://"):
                continue

            # Try to match to a known file
            ref_clean = ref.lstrip("./")
            if ref_clean in all_paths and ref_clean != source_path:
                relationships.append(
                    Relationship(
                        source=source_path,
                        target=ref_clean,
                        relation_type="references",
                        details=f"references {ref_clean}",
                    )
                )

        # Also scan content for file path patterns
        if analysis.content:
            for m in re.finditer(
                r"""['"]([a-zA-Z0-9_/\\.-]+\.(?:py|js|ts|json|yaml|yml|toml|md|css|html))['"]""",
                analysis.content,
            ):
                ref_path = m.group(1).replace("\\", "/").lstrip("./")
                if ref_path in all_paths and ref_path != source_path:
                    # Avoid duplicating import relationships
                    if not any(
                        r.target == ref_path and r.source == source_path
                        for r in relationships
                    ):
                        relationships.append(
                            Relationship(
                                source=source_path,
                                target=ref_path,
                                relation_type="references",
                                details=f"references path '{ref_path}'",
                            )
                        )

        return relationships

    def _extract_test_relationship(
        self,
        source_path: str,
        analysis: AnalysisResult,
        all_paths: set[str],
    ) -> Relationship | None:
        """Detect if this file is a test file and find what it tests."""
        filename = os.path.basename(source_path)
        dirname = os.path.dirname(source_path)

        # Common test file patterns
        test_patterns = [
            (r"^test_(.+)\.py$", lambda m: m.group(1) + ".py"),
            (r"^(.+)_test\.py$", lambda m: m.group(1) + ".py"),
            (r"^(.+)\.test\.(js|ts|jsx|tsx)$", lambda m: f"{m.group(1)}.{m.group(2)}"),
            (r"^(.+)\.spec\.(js|ts|jsx|tsx)$", lambda m: f"{m.group(1)}.{m.group(2)}"),
            (r"^Test(.+)\.java$", lambda m: m.group(1) + ".java"),
            (r"^(.+)Test\.java$", lambda m: m.group(1) + ".java"),
            (r"^(.+)_test\.go$", lambda m: m.group(1) + ".go"),
            (r"^(.+)_test\.rb$", lambda m: m.group(1) + ".rb"),
        ]

        for pattern, target_fn in test_patterns:
            match = re.match(pattern, filename)
            if match:
                target_name = target_fn(match)
                # Look for the source file in same dir, parent dir, or src/ dir
                candidates = [
                    os.path.join(dirname, target_name),
                    os.path.join(os.path.dirname(dirname), target_name),
                    os.path.join(os.path.dirname(dirname), "src", target_name),
                    os.path.join("src", target_name),
                    target_name,
                ]

                for candidate in candidates:
                    candidate = candidate.replace("\\", "/")
                    if candidate in all_paths:
                        return Relationship(
                            source=source_path,
                            target=candidate,
                            relation_type="tests",
                            details=f"test file for {candidate}",
                        )

        return None

    def _extract_doc_relationship(
        self,
        source_path: str,
        analysis: AnalysisResult,
        all_paths: set[str],
    ) -> Relationship | None:
        """Detect if this is a documentation file for code."""
        filename = os.path.basename(source_path).lower()
        dirname = os.path.dirname(source_path)

        # README files document their parent directory's code
        if filename.startswith("readme"):
            # Find code files in the same directory
            sibling_code = [
                p for p in all_paths
                if os.path.dirname(p) == dirname
                and p != source_path
                and analysis.category != "document"
            ]
            # Link to __init__.py or main file if exists
            for candidate in ["__init__.py", "main.py", "index.js", "index.ts", "mod.rs", "lib.rs"]:
                target = os.path.join(dirname, candidate) if dirname else candidate
                if target in all_paths:
                    return Relationship(
                        source=source_path,
                        target=target,
                        relation_type="documents",
                        details=f"README for {dirname or 'project root'}",
                    )

        return None

    def _deduplicate(self, relationships: list[Relationship]) -> list[Relationship]:
        """Remove duplicate relationships."""
        seen = set()
        unique = []
        for r in relationships:
            key = (r.source, r.target, r.relation_type)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique
