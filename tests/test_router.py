import pytest
from hma.core.models import KnowledgeMap, FileNode
from hma.core.config import HMAConfig
from hma.querying.router import Router

def dummy_llm(prompt):
    return "FILES: main.py\nREASONING: Because it's the main entry point."

def test_router_pre_filtering():
    config = HMAConfig()
    router = Router(llm=dummy_llm, config=config)
    kmap = KnowledgeMap(root_path="/tmp")
    
    # Add dummy nodes
    kmap.nodes["main.py"] = FileNode(
        path="main.py", file_type="python", category="code", size_bytes=10, 
        summary="Main application entry", key_topics=["entry", "app"],
    )
    kmap.nodes["auth.py"] = FileNode(
        path="auth.py", file_type="python", category="code", size_bytes=10, 
        summary="Authentication logic", key_topics=["auth", "login"],
    )
    
    question = "How does login auth work?"
    filtered = router._pre_filter(question, kmap)
    
    # Should prioritize auth.py based on keywords
    assert filtered[0]["path"] == "auth.py"

def test_router_llm_parsing():
    config = HMAConfig()
    router = Router(llm=dummy_llm, config=config)
    kmap = KnowledgeMap(root_path="/tmp")
    kmap.nodes["main.py"] = FileNode(
        path="main.py", file_type="python", category="code", size_bytes=10, summary="",
    )
    
    files, reasoning = router.route("What is the entry point?", kmap)
    
    assert "main.py" in files
    assert "Because it's the main entry point." in reasoning
