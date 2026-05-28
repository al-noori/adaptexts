"""Configuration classes for scaling operations.

This module provides dataclasses for configuring scaling behavior,
supporting both manual and automatic scaling modes.
"""

from dataclasses import dataclass, replace
from typing import Any, Literal, Optional


@dataclass
class ScalingConfig:
    """Configuration for scaling operations.

    Parameters
    ----------
    mode : Literal["automatic", "manual"]
        Scaling mode to use.
    scale_map : dict, optional
        Manual scale mapping (required when mode="manual").
    suffix : str
        Suffix to append to context names after scaling.
    name_template : str, optional
        Template for naming scaled contexts (supports {name} and {suffix} placeholders).

    Examples
    --------
    >>> config = ScalingConfig.automatic(suffix="auto")
    >>> config = ScalingConfig.manual(
    ...     scale_map={"color": {"name": "nominal-scale"}},
    ...     suffix="manual"
    ... )

    """

    mode: Literal["automatic", "manual"] = "automatic"
    scale_map: Optional[dict[str, dict[str, Any]]] = None
    suffix: str = "scaled"
    name_template: Optional[str] = None

    @classmethod
    def automatic(
        cls,
        suffix: str = "auto",
    ) -> "ScalingConfig":
        """Create automatic scaling config.

        Parameters
        ----------
        suffix : str
            Suffix to append to context names.

        Returns
        -------
        ScalingConfig
            Automatic scaling configuration.

        """
        return cls(mode="automatic", suffix=suffix)

    @classmethod
    def manual(
        cls,
        scale_map: dict[str, dict[str, Any]],
        suffix: str = "manual",
    ) -> "ScalingConfig":
        """Create manual scaling config.

        Parameters
        ----------
        scale_map : dict
            Manual scale mapping.
        suffix : str
            Suffix to append to context names.

        Returns
        -------
        ScalingConfig
            Manual scaling configuration.

        """
        return cls(mode="manual", scale_map=scale_map, suffix=suffix)

    def with_suffix(self, suffix: str) -> "ScalingConfig":
        """Return a new config with updated suffix.

        Parameters
        ----------
        suffix : str
            New suffix value.

        Returns
        -------
        ScalingConfig
            New configuration with updated suffix.

        """
        return replace(self, suffix=suffix)

    def get_name(self, original_name: str) -> str:
        """Generate scaled context name from original name.

        Parameters
        ----------
        original_name : str
            Original context name.

        Returns
        -------
        str
            Scaled context name.

        """
        if self.name_template:
            return self.name_template.format(name=original_name, suffix=self.suffix)
        return f"{original_name}__{self.suffix}" if self.suffix else original_name