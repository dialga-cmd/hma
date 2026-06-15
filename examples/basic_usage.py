"""
Basic example of how to use RAH in a Python script.
"""

from rah import RAH
import os

# 1. Define your LLM wrapper.
# In a real project, this would call OpenAI, Gemini, Claude, Ollama, etc.
def dummy_llm(prompt: str) -> str:
    """A dummy LLM function that just returns static strings for demonstration."""
    if "You are an intelligent code router" in prompt:
        return "FILES: rah/core/models.py\nREASONING: The models file is central to the project structure."
    elif "You are answering a question" in prompt:
        return "Based on the provided context, the RAH Knowledge Map stores nodes and relationships."
    
    return "SUMMARY: A Python module in the RAH project.\nTOPICS: module, code"

def main():
    print("Initializing RAH...")
    # 2. Instantiate RAH with your LLM
    rah = RAH(llm=dummy_llm)

    # 3. Index a project directory. Let's index the RAH library itself!
    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    print(f"Indexing project: {project_dir}")
    
    knowledge_map = rah.index(project_dir)
    print(f"✅ Indexed {knowledge_map.total_files} files.")
    
    # 4. Ask a question
    question = "How are relationships stored in the Knowledge Map?"
    print(f"\nAsking: '{question}'")
    
    answer = rah.ask(question)
    
    print("\n--- Answer ---")
    print(answer.text)
    print("--------------")
    print(f"Sources consulted: {answer.sources}")
    print(f"Connections read: {answer.connections}")

if __name__ == "__main__":
    main()
