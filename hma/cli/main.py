"""
Command-line interface for HMA.
"""

import argparse
import sys
import json
import os
from pathlib import Path

from hma import HMA
from hma.core.exceptions import HMAError

def _get_dummy_llm():
    """
    Returns a dummy LLM for testing the CLI without providing a real one.
    In a real scenario, the CLI should allow configuring an API key or a local model path.
    """
    def dummy_llm(prompt: str) -> str:
        # Check if it's a routing prompt
        if "You are an intelligent code router" in prompt:
            return "FILES: main.py\nREASONING: Fallback routing due to dummy LLM."
        # Check if it's an answer prompt
        elif "You are answering a question" in prompt:
            return "This is a dummy answer because no LLM was configured for the CLI."
        # Must be summarization
        return "SUMMARY: Dummy summary.\nTOPICS: dummy, test"
    
    return dummy_llm

def main():
    parser = argparse.ArgumentParser(
        description="HMA - Hierarchical Mapping Architecture. A smarter alternative to RAG."
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Index command
    index_parser = subparsers.add_parser("index", help="Index a project directory")
    index_parser.add_argument("path", type=str, help="Path to project directory")
    index_parser.add_argument(
        "--full", action="store_true", help="Force full re-index instead of incremental"
    )

    # Ask command
    ask_parser = subparsers.add_parser("ask", help="Ask a question about an indexed project")
    ask_parser.add_argument("question", type=str, help="Your question")
    ask_parser.add_argument("--project", type=str, default=".", help="Path to project directory")

    # Map command
    map_parser = subparsers.add_parser("map", help="View the knowledge map for a project")
    map_parser.add_argument("--project", type=str, default=".", help="Path to project directory")
    map_parser.add_argument("--stats", action="store_true", help="Show only statistics")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize HMA with a dummy LLM for now.
    # A real CLI would read credentials from env vars and instantiate OpenAI/Gemini/etc.
    rah = HMA(llm=_get_dummy_llm())

    try:
        if args.command == "index":
            print(f"Indexing {args.path}...")
            kmap = rah.index(args.path, incremental=not args.full)
            print(f"✅ Successfully indexed {kmap.total_files} files.")
            print(f"Map saved to {os.path.join(args.path, '.hma.json')}")

        elif args.command == "ask":
            print(f"Question: {args.question}")
            answer = rah.ask(args.question, project_path=args.project)
            print("\n" + "="*50)
            print(answer.text)
            print("="*50)
            print("\nSources consulted:")
            for src in answer.sources:
                print(f"  - {src}")
            if answer.connections:
                print("\nConnected files read (single-hop):")
                for conn in answer.connections:
                    print(f"  - {conn}")
            print(f"\nRouting Reasoning: {answer.reasoning}")

        elif args.command == "map":
            kmap = rah.get_map(project_path=args.project)
            if not kmap:
                print(f"No knowledge map found for {args.project}. Run 'hma index' first.")
                sys.exit(1)

            if args.stats:
                print(f"Project: {kmap.root_path}")
                print(f"Total Files Indexed: {kmap.total_files}")
                print(f"Total Relationships: {len(kmap.relationships)}")
                print(f"Last Updated: {kmap.updated_at}")
            else:
                # Pretty print summary
                print(f"Project Summary:\n{kmap.project_summary}\n")
                print(f"Indexed {kmap.total_files} files. (Run with --stats for brief info)")

    except HMAError as e:
        print(f"❌ HMA Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
