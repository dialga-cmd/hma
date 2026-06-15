import os
from pathlib import Path

def replace_in_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    # Order matters!
    content = content.replace("HMAError", "HMAError")
    content = content.replace("HMAConfig", "HMAConfig")
    content = content.replace(".hma.json", ".hma.json")
    content = content.replace("HMA - Hierarchical Mapping Architecture", "HMA - Hierarchical Mapping Architecture")
    content = content.replace("HMA", "HMA")
    content = content.replace("hma.core", "hma.core")
    content = content.replace("hma.indexing", "hma.indexing")
    content = content.replace("hma.querying", "hma.querying")
    content = content.replace("hma.parsers", "hma.parsers")
    content = content.replace("hma.storage", "hma.storage")
    content = content.replace("hma.cli", "hma.cli")
    content = content.replace("from hma import", "from hma import")
    content = content.replace("import hma", "import hma")
    content = content.replace("pip install hma", "pip install hma")
    content = content.replace("hma index", "hma index")
    content = content.replace("hma ask", "hma ask")
    content = content.replace("hma map", "hma map")
    content = content.replace('hma="hma', 'hma="hma') # in pyproject.toml
    content = content.replace('hma = "', 'hma = "')
    content = content.replace('name = "hma"', 'name = "hma"')

    if content != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {path}")

def main():
    root = Path("/home/dialgga/mapping")
    for ext in ["*.py", "*.md", "*.toml", "*.json"]:
        for path in root.rglob(ext):
            if ".venv" in path.parts or "node_modules" in path.parts or "__pycache__" in path.parts or ".git" in path.parts:
                continue
            replace_in_file(path)

if __name__ == "__main__":
    main()
