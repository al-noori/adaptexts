"""Factory for creating context-type-specific cache backends.

This module provides a factory function to create cache backends optimized
for specific context types (Context or ManyValuedContext).

Uses cacheable backends (MemoryCache, DiskFileCache, TwoTierCache) with
context-specific serialization strategies.
"""

from pathlib import Path

# Import context-aware backends
from adaptexts.base.cache.context_backends import ContextAwareTwoTierCache
from adaptexts.base.cache.serializers import (
    create_strategy,
    get_strategies_for_context_type,
    validate_strategy_for_context_type,
)

# Import generic backends from cacheable
from cacheable.backends import create_disk_file_cache, create_memory_cache
from cacheable.builder import CacheBuilder
from cacheable.core.abstractions import CacheBackend

from .config import CacheConfig
from .paths import get_cache_dir


def _create_disk_cache_for_context(
    context_type: type,
    cache_dir: Path | str,
    serializer_name: str,
    disk_ttl: int | None,
) -> CacheBackend:
    """Create a disk cache backend with validation for the given context type.

    Validates that the serializer supports the context type before creating
    the cache backend.

    Parameters
    ----------
    context_type : type
        Context class (Context or ManyValuedContext).
    cache_dir : Path | str
        Directory path for disk cache storage.
    serializer_name : str
        Name of the serialization strategy to use.
    disk_ttl : int | None
        Time-to-live for cached items in seconds.

    Returns
    -------
    CacheBackend
        Configured disk file cache backend.

    Raises
    ------
    ValueError
        If the serializer does not support the given context type.
    """
    # Validate serializer supports context type
    if not validate_strategy_for_context_type(serializer_name, context_type):
        supported = get_strategies_for_context_type(context_type)
        raise ValueError(
            f"Serializer '{serializer_name}' is not supported for "
            f"{context_type.__name__}. Supported: {', '.join(supported)}"
        )

    # Ensure cache_dir is a Path
    if isinstance(cache_dir, str):
        cache_dir = Path(cache_dir)

    return create_disk_file_cache(
        cache_dir=cache_dir,
        ttl=disk_ttl,
        serializer=create_strategy(serializer_name),
    )


def create_context_cache(
    context_type: type,
    config: CacheConfig,
    cache_name: str = "default",
) -> CacheBackend:
    """Create a cache backend optimized for a specific context type.

    Uses the data-home package for cache directory resolution when
    `config.disk_cache_dir` is None.

    Uses cacheable backends with context-specific serialization for
    flexibility and composability.

    Parameters
    ----------
    context_type : type
        Context class to optimize for (Context or ManyValuedContext).
    config : CacheConfig
        Cache configuration.
    cache_name : str, optional
        Name for cache subdirectory. Defaults to "default".

    Returns
    -------
    CacheBackend
        Configured cache backend with type-appropriate settings.

    Notes
    -----
    - For memory backend: Uses MemoryCache from cacheable
    - For disk backend: Uses DiskFileCache from cacheable with context-specific serialization
    - For two_tier backend: Combines memory + disk caches

    Examples
    --------
    >>> from adaptexts.base.cache import CacheConfig
    >>> from adaptexts.context import Context
    >>> config = CacheConfig(unary_context_serializer="burmeister")
    >>> cache = create_context_cache(Context, config, "myadapter")
    >>> isinstance(cache, CacheBackend)

    >>> # Memory-only cache
    >>> config = CacheConfig(backend="memory", memory_max_size=500)
    >>> cache = create_context_cache(Context, config)
    """
    # Lazy import to avoid circular dependency at module load time

    # Disabled cache - return empty memory cache
    if not config.enabled:
        return CacheBuilder(
            storage_type="memory",
            max_size=0,
            eviction_policy=config.memory_eviction_policy,
        ).build()

    serializer_name = config.get_serializer_for_context_type(context_type)

    # Memory backend - use cacheable's create_memory_cache
    if config.backend == "memory":
        return create_memory_cache(
            max_size=config.memory_max_size,
            eviction_policy=config.memory_eviction_policy,
            serializer=create_strategy(serializer_name),
        )

    # Resolve cache directory using data-home package
    if config.disk_cache_dir is None and config.backend in ("disk", "two_tier"):
        base_name = context_type.__name__
        cache_dir = get_cache_dir(
            adapter_name=f"adaptexts/{base_name}", identifier=cache_name
        )
    else:
        cache_dir = config.disk_cache_dir

    # Disk backend - create context-specific disk cache
    if config.backend == "disk":
        if cache_dir is None:
            raise ValueError("cache_dir is required for disk backend")

        return _create_disk_cache_for_context(
            context_type=context_type,
            cache_dir=cache_dir,
            serializer_name=serializer_name,
            disk_ttl=config.disk_ttl,
        )

    # Two-tier backend - combine memory and disk caches
    if config.backend == "two_tier":
        if cache_dir is None:
            raise ValueError("cache_dir is required for two_tier backend")

        # L1: Memory cache
        l1_cache = create_memory_cache(
            max_size=config.memory_max_size,
            eviction_policy=config.memory_eviction_policy,
            serializer=create_strategy(serializer_name),
        )

        # L2: Disk cache
        l2_cache = _create_disk_cache_for_context(
            context_type=context_type,
            cache_dir=cache_dir,
            serializer_name=serializer_name,
            disk_ttl=config.disk_ttl,
        )

        # Use ContextAwareTwoTierCache for context-aware caching
        return ContextAwareTwoTierCache(
            l1_cache,
            l2_cache,
            promotion_threshold_unary=getattr(config, "promotion_threshold_unary", 2),
            promotion_threshold_manyvalued=getattr(
                config, "promotion_threshold_manyvalued", 4
            ),
            size_promotion_threshold=getattr(
                config, "size_promotion_threshold", 10_000
            ),
        )

    raise ValueError(f"Unknown cache backend: {config.backend}")
