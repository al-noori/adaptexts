"""Example adapter implementations.

This package provides ready-to-use adapter implementations for a few
datasets and data sources for showcasing various provided paradigms.
"""

from .conexp_clj import ConexpCljAdapter
from .ipc import IPCAdapter
from .rwc import RWCAdapter
from .uciml import UCIMLAdapter

__all__ = [
    "ConexpCljAdapter",
    "IPCAdapter",
    "RWCAdapter",
    "UCIMLAdapter",
]
