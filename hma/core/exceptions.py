"""
Custom exceptions for HMA.

All HMA-specific errors inherit from HMAError for easy catch-all handling.
"""


class HMAError(Exception):
    """Base exception for all HMA errors."""
    pass


class IndexingError(HMAError):
    """Raised when there's an error during the indexing phase."""
    pass


class QueryError(HMAError):
    """Raised when there's an error during the querying phase."""
    pass


class NoLLMError(HMAError):
    """Raised when no LLM callable is provided."""
    pass


class MapNotFoundError(HMAError):
    """Raised when a Knowledge Map cannot be found or loaded."""
    pass


class ParserError(HMAError):
    """Raised when a file parser encounters an error."""
    pass


class StorageError(HMAError):
    """Raised when there's an error saving or loading the map."""
    pass
