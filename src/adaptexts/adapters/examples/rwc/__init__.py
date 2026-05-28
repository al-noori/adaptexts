"""Adapter for the Real-World Contexts (RWC) repository.

This package provides the RWCAdapter which accesses formal contexts
from the fcatools/contexts Git repository, including metadata files
(typically YAML) associated with contexts.
"""

from .rwc import RWCAdapter

__all__ = [
    "RWCAdapter",
]