"""
Custom exceptions for RAH.

All RAH-specific errors inherit from RAHError for easy catch-all handling.
"""


class RAHError(Exception):
    """Base exception for all RAH errors."""
    pass


class IndexingError(RAHError):
    """Raised when there's an error during the indexing phase."""
    pass


class QueryError(RAHError):
    """Raised when there's an error during the querying phase."""
    pass


class NoLLMError(RAHError):
    """Raised when no LLM callable is provided."""
    pass


class MapNotFoundError(RAHError):
    """Raised when a Knowledge Map cannot be found or loaded."""
    pass


class ParserError(RAHError):
    """Raised when a file parser encounters an error."""
    pass


class StorageError(RAHError):
    """Raised when there's an error saving or loading the map."""
    pass
