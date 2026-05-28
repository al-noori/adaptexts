"""Scaling tool for many-valued contexts.

This package provides:
- ScalingTool: Primary interface for scaling operations
- Scale inference utilities: infer_feature_scales, infer_scale
- ScaleError: Exception for scale-related errors

Internally it manages:
- ConexpClient: REST API client for conexp-clj
"""

from .scales import ScaleError, infer_feature_scales, infer_scale, infer_scale_map
from .tool import ScalingTool

__all__ = [
    "ScalingTool",
    "ScaleError",
    # Public utilities
    "infer_feature_scales",
    "infer_scale",
    "infer_scale_map",
]