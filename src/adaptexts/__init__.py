"""Adaptexts: A Framework for Adapters of Formal Contexts.

This package provides a unified interface for converting various data sources
into formal contexts used in Formal Concept Analysis (FCA).
"""

from .adapters.interface import AdapterInterface
from .context import Context
from .many_valued_context import ManyValuedContext
from .tools.scaling import ScalingTool

__all__ = [
    "Context",
    "ManyValuedContext",
    "AdapterInterface",
    "ScalingTool",
]
