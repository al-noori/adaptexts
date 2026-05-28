"""Context-aware cache backends for FCA contexts.

This module provides cache backends optimized for FCA context types
(Context and ManyValuedContext) with intelligent promotion and eviction
based on context metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Optional

from cacheable.backends import TwoTierCache
from cacheable.core.abstractions import CacheBackend, CacheStats

if TYPE_CHECKING:
    # Imported in function bodies for cacheable backends
    pass


@dataclass(frozen=True)
class ContextMetadata:
    """Metadata for cached contexts.

    Attributes
    ----------
    context_type : str
        Type of context: "unary" (Context) or "manyvalued" (ManyValuedContext).
    num_objects : int
        Number of objects in the context.
    num_attributes : int
        Number of attributes in the context.
    size_bytes : int
        Approximate memory usage in bytes.
    access_count : int
        Number of times this context has been accessed.
    last_access_time : float
        Unix timestamp of last access.

    Notes
    -----
    This metadata is stored alongside cached contexts and used for:
    - Intelligent L1 promotion decisions
    - Size-aware eviction
    - Per-context-type statistics
    """

    context_type: str  # "unary" or "manyvalued"
    num_objects: int
    num_attributes: int
    size_bytes: int
    access_count: int = 0
    last_access_time: float = 0.0


@dataclass
class ContextAwareCacheStats(CacheStats):
    """Statistics for context-aware cache.

    Extends CacheStats with per-context-type tracking.

    Attributes
    ----------
    unary_hits : int
        Hit count for unary contexts.
    unary_misses : int
        Miss count for unary contexts.
    manyvalued_hits : int
        Hit count for many-valued contexts.
    manyvalued_misses : int
        Miss count for many-valued contexts.
    promotions_l2_to_l1 : int
        Number of items promoted from L2 to L1.
    l1_evictions : int
        Number of items evicted from L1.
    """

    unary_hits: int = 0
    unary_misses: int = 0
    manyvalued_hits: int = 0
    manyvalued_misses: int = 0
    promotions_l2_to_l1: int = 0
    l1_evictions: int = 0

    @property
    def total_hits(self) -> int:
        """Total hits across all context types."""
        return self.unary_hits + self.manyvalued_hits

    @property
    def total_misses(self) -> int:
        """Total misses across all context types."""
        return self.unary_misses + self.manyvalued_misses

    @property
    def unary_hit_rate(self) -> float:
        """Hit rate for unary contexts."""
        total = self.unary_hits + self.unary_misses
        return self.unary_hits / total if total > 0 else 0.0

    @property
    def manyvalued_hit_rate(self) -> float:
        """Hit rate for many-valued contexts."""
        total = self.manyvalued_hits + self.manyvalued_misses
        return (
            self.manyvalued_hits / total
            if total > 0
            else 0.0
        )

    @property
    def promotion_rate(self) -> float:
        """Rate of L2→L1 promotions."""
        total_accesses = self.total_hits + self.total_misses
        if total_accesses == 0:
            return 0.0
        # Promotions happen on L2 hits
        return self.promotions_l2_to_l1 / total_accesses


class ContextAwareTwoTierCache(TwoTierCache):
    """Two-tier cache with context-aware promotion and eviction.

    This cache enhances the basic TwoTierCache with:

    1. **Type-aware promotion**: Different promotion logic based on context type
       - Unary contexts: Promote if accessed > N times OR large size
       - Many-valued contexts: Promote if accessed > 2N times (usually larger)

    2. **Size-aware eviction**: Track memory usage by context type
       - Prefer keeping smaller contexts in L1
       - Evict large contexts first when L1 is full

    3. **Access-frequency tracking**: Count accesses per context
       - Track hot contexts that should stay in L1

    4. **Detailed statistics**: Per-type hit/miss tracking

    Parameters
    ----------
    l1_backend : CacheBackend
        L1 backend (typically MemoryCache).
    l2_backend : CacheBackend
        L2 backend (typically DiskFileCache or DiskDBCache).
    promotion_threshold_unary : int, optional
        Minimum access count for L1 promotion (unary contexts).
        Default is 2.
    promotion_threshold_manyvalued : int, optional
        Minimum access count for L1 promotion (many-valued contexts).
        Default is 4 (higher because they're typically larger).
    size_promotion_threshold : int, optional
        Minimum size (bytes) to promote on first access (large contexts).
        Default is 10000 bytes.

    Examples
    --------
    >>> from cacheable.backends import create_memory_cache, create_disk_file_cache
    >>> from pathlib import Path
    >>>
    >>> l1 = create_memory_cache(max_size=100)
    >>> l2 = create_disk_file_cache(cache_dir=Path("/tmp/cache"))
    >>> cache = ContextAwareTwoTierCache(l1, l2)
    >>>
    >>> # Use same interface as regular TwoTierCache
    >>> cache.set("key1", context1)
    >>> value = cache.get("key1")
    """

    def __init__(
        self,
        l1_backend: Any,  # Accept any backend (will be MemoryCache at runtime)
        l2_backend: Any,  # Accept any backend
        promotion_threshold_unary: int = 2,
        promotion_threshold_manyvalued: int = 4,
        size_promotion_threshold: int = 10_000,
    ):
        super().__init__(l1_backend, l2_backend)

        self._promotion_threshold_unary = promotion_threshold_unary
        self._promotion_threshold_manyvalued = promotion_threshold_manyvalued
        self._size_promotion_threshold = size_promotion_threshold

        # Metadata storage (key -> ContextMetadata)
        self._metadata: dict[str, ContextMetadata] = {}

        # Statistics
        self._stats = ContextAwareCacheStats()

    def _extract_metadata(self, value: Any) -> Optional[ContextMetadata]:
        """Extract metadata from a cached value.

        Parameters
        ----------
        value : Any
            The cached value (should be Context or ManyValuedContext).

        Returns
        -------
        ContextMetadata or None
            Metadata if value is a context, None otherwise.
        """
        # Lazy import to avoid circular dependency
        try:
            from adaptexts.context import Context
            from adaptexts.many_valued_context import ManyValuedContext
        except ImportError:
            return None

        if isinstance(value, Context):
            context_type = "unary"
            num_objects = len(value.G) if value.G else 0
            num_attributes = len(value.M) if value.M else 0
            # Estimate size: objects + attributes + intent data
            size_bytes = (
                sum(len(str(o)) for o in value.G if o)
                + sum(len(str(a)) for a in value.M if a) * 2
            ) * 50  # approximate per character

        elif isinstance(value, ManyValuedContext):
            context_type = "manyvalued"
            num_objects = len(value.G) if value.G else 0
            num_attributes = len(value.M) if value.M else 0
            # Many-valued contexts are typically larger
            size_bytes = num_objects * num_attributes * 100  # rough estimate

        else:
            # Not a context type we track
            return None

        return ContextMetadata(
            context_type=context_type,
            num_objects=num_objects,
            num_attributes=num_attributes,
            size_bytes=size_bytes,
            access_count=0,
            last_access_time=0.0,
        )

    def _should_promote_to_l1(self, key: str, metadata: ContextMetadata) -> bool:
        """Determine if an item should be promoted to L1.

        Promotion logic:
        1. Always promote on first access if above size threshold
        2. Promote after N accesses based on context type
        3. Unary contexts have lower threshold than many-valued

        Parameters
        ----------
        key : str
            Cache key.
        metadata : ContextMetadata
            Metadata for the cached item.

        Returns
        -------
        bool
            True if should promote to L1.
        """
        # Large contexts get promoted immediately
        if metadata.size_bytes >= self._size_promotion_threshold:
            return True

        # Access-based promotion
        if metadata.context_type == "unary":
            return metadata.access_count >= self._promotion_threshold_unary
        else:  # manyvalued
            return (
                metadata.access_count >= self._promotion_threshold_manyvalued
            )

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value, checking L1 first then L2.

        Updates access counts and promotes from L2 if appropriate.

        Parameters
        ----------
        key : str
            Cache key.
        default : Any, optional
            Value to return if key is not found. Default is None.

        Returns
        -------
        Any
            Cached value or default if not found.
        """
        import time

        # Check L1 first
        value = self._l1.get(key)

        if value is not None:
            # L1 hit
            self._stats.hits += 1

            # Update metadata
            metadata = self._metadata.get(key)
            if metadata:
                self._metadata[key] = replace(
                    metadata,
                    access_count=metadata.access_count + 1,
                    last_access_time=time.time(),
                )
                if metadata.context_type == "unary":
                    self._stats.unary_hits += 1
                elif metadata.context_type == "manyvalued":
                    self._stats.manyvalued_hits += 1

            return value

        # Check L2
        value = self._l2.get(key)

        if value is not None:
            # L2 hit
            self._stats.hits += 1

            # Extract metadata
            metadata = self._extract_metadata(value)
            if metadata:
                self._metadata[key] = replace(
                    metadata,
                    access_count=metadata.access_count + 1,
                    last_access_time=time.time(),
                )

                if metadata.context_type == "unary":
                    self._stats.unary_misses += (
                        1  # L2 hit counts as miss for L1
                    )
                    self._stats.unary_hits += 1
                elif metadata.context_type == "manyvalued":
                    self._stats.manyvalued_misses += 1
                    self._stats.manyvalued_hits += 1

                # Promote to L1 if appropriate
                if self._should_promote_to_l1(key, metadata):
                    self._l1.set(key, value)
                    self._stats.promotions_l2_to_l1 += 1
            else:
                self._stats.misses += 1

            return value

        # Miss
        self._stats.misses += 1
        return default

    def set(self, key: str, value: Any) -> None:
        """Store a value in both L1 and L2.

        Extracts and stores metadata for contexts.

        Parameters
        ----------
        key : str
            Cache key.
        value : Any
            Value to cache.
        """
        super().set(key, value)

        # Extract and store metadata
        metadata = self._extract_metadata(value)
        if metadata:
            self._metadata[key] = metadata

    def delete(self, key: str) -> bool:
        """Delete key from both tiers and metadata.

        Parameters
        ----------
        key : str
            Cache key to delete.

        Returns
        -------
        bool
            True if key was deleted.
        """
        deleted = super().delete(key)
        self._metadata.pop(key, None)
        return deleted

    def clear(self) -> None:
        """Clear both tiers and metadata."""
        super().clear()
        self._metadata.clear()
        self._stats = ContextAwareCacheStats()

    def get_stats(self) -> ContextAwareCacheStats:
        """Get context-aware cache statistics.

        Returns
        -------
        ContextAwareCacheStats
            Detailed statistics including per-context-type metrics.
        """
        # Update base stats
        l1_stats = self._l1.get_stats()
        l2_stats = self._l2.get_stats()

        self._stats.hits = l1_stats.hits + l2_stats.hits
        self._stats.misses = l1_stats.misses + l2_stats.misses
        self._stats.size = l1_stats.size + l2_stats.size
        self._stats.memory_bytes = (
            (l1_stats.memory_bytes if l1_stats.memory_bytes else 0)
            + (l2_stats.memory_bytes if l2_stats.memory_bytes else 0)
        )

        return self._stats

    def get_context_metadata(self, key: str) -> Optional[ContextMetadata]:
        """Get metadata for a cached context.

        Parameters
        ----------
        key : str
            Cache key.

        Returns
        -------
        ContextMetadata or None
            Metadata if key exists and is a context.
        """
        return self._metadata.get(key)

    def get_hot_contexts(
        self, limit: int = 10, context_type: Optional[str] = None
    ) -> list[tuple[str, ContextMetadata]]:
        """Get the most frequently accessed contexts.

        Parameters
        ----------
        limit : int, optional
            Maximum number of contexts to return.
        context_type : str, optional
            Filter by context type ("unary" or "manyvalued").

        Returns
        -------
        list of (str, ContextMetadata)
            List of (key, metadata) sorted by access count.
        """
        contexts = [
            (k, m)
            for k, m in self._metadata.items()
            if context_type is None or m.context_type == context_type
        ]

        return sorted(contexts, key=lambda x: x[1].access_count, reverse=True)[
            :limit
        ]

    def get_large_contexts(
        self, limit: int = 10, context_type: Optional[str] = None
    ) -> list[tuple[str, ContextMetadata]]:
        """Get the largest cached contexts.

        Parameters
        ----------
        limit : int, optional
            Maximum number of contexts to return.
        context_type : str, optional
            Filter by context type ("unary" or "manyvalued").

        Returns
        -------
        list of (str, ContextMetadata)
            List of (key, metadata) sorted by size.
        """
        contexts = [
            (k, m)
            for k, m in self._metadata.items()
            if context_type is None or m.context_type == context_type
        ]

        return sorted(contexts, key=lambda x: x[1].size_bytes, reverse=True)[
            :limit
        ]


def create_context_aware_two_tier(
    l1_backend: CacheBackend, l2_backend: CacheBackend, **kwargs
) -> ContextAwareTwoTierCache:
    """Create a context-aware two-tier cache.

    Convenience function for creating ContextAwareTwoTierCache instances.

    Parameters
    ----------
    l1_backend : CacheBackend
        L1 backend (typically MemoryCache).
    l2_backend : CacheBackend
        L2 backend (typically DiskFileCache or DiskDBCache).
    **kwargs
        Additional arguments passed to ContextAwareTwoTierCache constructor.

    Returns
    -------
    ContextAwareTwoTierCache
        Configured context-aware two-tier cache.

    Examples
    --------
    >>> from cacheable.backends import create_memory_cache, create_disk_file_cache
    >>> from pathlib import Path
    >>> from adaptexts.base.cache.context_backends import (
    ...     create_context_aware_two_tier
    ... )
    >>>
    >>> l1 = create_memory_cache(max_size=100)
    >>> l2 = create_disk_file_cache(cache_dir=Path("/tmp/cache"))
    >>> cache = create_context_aware_two_tier(l1, l2)
    """
    return ContextAwareTwoTierCache(l1_backend, l2_backend, **kwargs)


__all__ = [
    "ContextMetadata",
    "ContextAwareCacheStats",
    "ContextAwareTwoTierCache",
    "create_context_aware_two_tier",
]