"""Configuration for cache backends using data-home package.

This module provides the full CacheConfig class with context-specific serializers
used by adaptests. For generic cache configuration without context support,
use cacheable.config.CacheConfig.
"""

from dataclasses import dataclass, field

from pathlib import Path
from typing import Optional

from cacheable import CacheConfig as CacheableConfig


@dataclass(frozen=True)
class CacheConfig(CacheableConfig):
    """Configuration for cache backends.

    Cache directories are managed via:
        1. disk_cache_dir (explicit path, highest priority)
        2. {ADAPTER_NAME}_DATA environment variable
        3. platformdirs default locations via data-home package

    Attributes
    ----------
    enabled : bool
        Whether caching is enabled.
    backend : str
        Backend type: "memory", "disk", "two_tier".
    disk_cache_dir : Optional[Path]
        Explicit directory for disk cache. If None, uses data-home package.
    memory_max_size : Optional[int]
        Maximum items in memory cache. None = unlimited.
    memory_eviction_policy : str
        Eviction policy: "lru" or "lfu".
    disk_ttl : Optional[int]
        Time-to-live for disk entries in seconds.

    # Generic serializer (fallback)
    serializer : str
        Default serializer: "pickle", "burmeister", "colibri", "csv", "json".

    # Context-specific serializers
    unary_context_serializer : str
        Serializer for Context objects: "pickle", "burmeister", "colibri", "csv", "json".
    manyvalued_context_serializer : str
        Serializer for ManyValuedContext objects: "pickle", "csv", "json".

    Examples
    --------
    >>> # Use defaults (data-home)
    >>> config = CacheConfig()

    >>> # Explicit directory with Burmeister for binary contexts
    >>> from pathlib import Path
    >>> config = CacheConfig(
    ...     disk_cache_dir=Path("/tmp/cache"),
    ...     unary_context_serializer="burmeister"
    ... )

    >>> # Memory-only
    >>> config = CacheConfig(backend="memory")
    """

    # Inherited fields from CacheableConfig - redeclared to make them dataclass fields
    enabled: bool = field(default=True)
    backend: str = field(default="two_tier")
    disk_cache_dir: Optional[Path] = field(default=None)
    memory_max_size: Optional[int] = field(default=1000)
    memory_eviction_policy: str = field(default="lru")
    disk_ttl: Optional[int] = field(default=None)
    serializer: str = field(default="pickle")

    # Context-specific serializers
    unary_context_serializer: str = field(default="burmeister")
    manyvalued_context_serializer: str = field(default="pickle")

    # Context-aware two-tier cache options
    promotion_threshold_unary: int = field(default=2)
    promotion_threshold_manyvalued: int = field(default=4)
    size_promotion_threshold: int = field(default=10_000)
    enable_context_aware: bool = field(default=True)

    def __post_init__(self) -> None:
        """Validate configuration."""
        valid_backends = {"memory", "disk", "disk_db", "two_tier"}
        if self.backend not in valid_backends:
            raise ValueError(
                f"Invalid backend '{self.backend}'. Must be one of {valid_backends}"
            )

        valid_eviction_policies = {"lru", "lfu"}
        if self.memory_eviction_policy not in valid_eviction_policies:
            raise ValueError(
                f"Invalid eviction policy '{self.memory_eviction_policy}'. "
                f"Must be one of {valid_eviction_policies}"
            )

        # All serializers valid for generic
        all_valid_serializers = {"pickle", "burmeister", "colibri", "csv", "json", "json_context", "pickle_context"}
        if self.serializer not in all_valid_serializers:
            raise ValueError(
                f"Invalid serializer '{self.serializer}'. "
                f"Must be one of {all_valid_serializers}"
            )

        # Unary contexts support all formats
        if self.unary_context_serializer not in all_valid_serializers:
            raise ValueError(
                f"Invalid unary_context_serializer '{self.unary_context_serializer}'. "
                f"Must be one of {all_valid_serializers}"
            )

        # Many-valued contexts exclude burmeister/colibri
        valid_mv_serializers = {"pickle", "csv", "json", "json_context", "pickle_context"}
        if self.manyvalued_context_serializer not in valid_mv_serializers:
            raise ValueError(
                f"Invalid manyvalued_context_serializer '{self.manyvalued_context_serializer}'. "
                f"Must be one of {valid_mv_serializers} "
                f"(burmeister/colibri not supported for ManyValuedContext)"
            )

        # Convert disk_cache_dir to Path if it's a string
        object.__setattr__(
            self,
            "disk_cache_dir",
            Path(self.disk_cache_dir).expanduser() if self.disk_cache_dir else None,
        )

    def get_serializer_for_context_type(self, context_type: type) -> str:
        """Get appropriate serializer for a context type.

        Parameters
        ----------
        context_type : type
            Context class (Context or ManyValuedContext).

        Returns
        -------
        str
            Serializer name for the context type.

        Examples
        --------
        >>> from adaptexts.context import Context
        >>> config = CacheConfig(unary_context_serializer="burmeister")
        >>> config.get_serializer_for_context_type(Context)
        'burmeister'
        """
        # Lazy import to avoid circular dependency
        from adaptexts.context import Context
        from adaptexts.many_valued_context import ManyValuedContext

        if context_type is Context:
            return self.unary_context_serializer
        elif context_type is ManyValuedContext:
            return self.manyvalued_context_serializer
        else:
            return self.serializer

    def get_memory_config(self) -> dict:
        """Get memory cache configuration."""
        return {
            "max_size": self.memory_max_size,
            "eviction_policy": self.memory_eviction_policy,
        }

    def get_disk_config(self) -> dict:
        """Get disk cache configuration."""
        return {"ttl": self.disk_ttl}

    @property
    def is_two_tier(self) -> bool:
        """Check if this is a two-tier cache configuration."""
        return self.backend == "two_tier"
