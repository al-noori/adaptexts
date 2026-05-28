"""Adapter implementations for various data sources.

This package contains concrete adapters that implement the AdapterInterface
to convert different data sources into formal contexts.
"""

from .cached import CachedAdapter
from .directory import DirectoryAdapter
from .exceptions import (
    AccessError,
    AdapterError,
    ContextParseError,
    DownloadError,
    SourceNotFoundError,
    ValidationError,
)
from .git import GitAdapter, GitBurmeisterAdapter
from .interface import AdapterInterface

__all__ = [
    # Base classes
    "AdapterInterface",
    "DirectoryAdapter",
    "CachedAdapter",
    # Configuration
    "FileTreeConfig",
    "FileInfo",
    # Exceptions
    "AdapterError",
    "SourceNotFoundError",
    "DownloadError",
    "AccessError",
    "ValidationError",
    "ContextParseError",
    # Git adapters
    "GitAdapter",
    "GitBurmeisterAdapter",
]
