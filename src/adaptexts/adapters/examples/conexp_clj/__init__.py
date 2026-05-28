"""Adapter for the conexp-clj repository's testing-data directory.

This package provides the ConexpCljAdapter which accesses formal contexts
from the conexp-clj repository, including Burmeister (.cxt) and Conexp
(.ctx) format files.
"""

from .conexp_clj import ConexpCljAdapter

__all__ = [
    "ConexpCljAdapter",
]
