import pytest
from pathlib import Path
from hma.core.config import HMAConfig
from hma.indexing.walker import Walker

def test_walker_finds_python_files(tmp_path):
    config = HMAConfig()
    walker = Walker(config)
    
    # Create a dummy structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "README.md").write_text("# Project")
    
    # Excluded dirs
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("core")
    
    files = walker.walk(tmp_path)
    
    # Assert
    assert len(files) == 2
    extensions = [f.extension for f in files]
    assert ".py" in extensions
    assert ".md" in extensions
    
    # Ensure .git is excluded
    assert not any(f.relative_path.startswith(".git") for f in files)
