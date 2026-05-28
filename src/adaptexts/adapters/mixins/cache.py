"""Mixin classes for adding caching capabilities to adapters.

This module provides separated mixin classes for caching functionality:
- CacheMixin: Cache backend initialization and storage operations
- IterationMixin: Iteration behavior using keys() and _get()
- CacheIterationMixin: Cached iteration behavior combining CacheMixin + IterationMixin
- KeyConversionMixin: Key-to-string conversion utilities

Design Philosophy
-----------------
By splitting caching into separate mixins, adapters can compose exactly the
behaviors they need without MRO conflicts.

Examples
--------
>>> # Full caching + iteration behavior
>>> from adaptexts.adapters.mixins import CacheIterationMixin
>>> class MyCachedAdapter(CacheIterationMixin, AdapterInterface):
...     def __init__(self, cache_config=None):
...         super().__init__()
...         self._init_cache(cache_config)
...     def keys(self) -> Iterator[str]:
...         yield from ["a", "b", "c"]
...     def _get(self, key: str) -> Context:
...         return Context(set(), set(), set(), name=key)

>>> # Mix and match individual behaviors
>>> from adaptexts.adapters.mixins import (
...     CacheMixin, IterationMixin, CacheIterationMixin
... )
>>> class StorageOnlyAdapter(CacheMixin, AdapterInterface):
...     has_cache = True
...     # Has cache operations but no iteration behavior
...
>>> class UncachedIterationAdapter(IterationMixin, AdapterInterface):
...     # Has iteration but no caching
...     def keys(self) -> Iterator[str]:
...         yield from ["a", "b", "c"]
...     def _get(self, key: str) -> Context:
...         return Context(set(), set(), set(), name=key)
"""

import fnmatch
import json
import logging

from typing import TYPE_CHECKING, Any, Iterator, Optional, Protocol, Union

from adaptexts.base.cache import CacheConfig, create_context_cache
from adaptexts.context import Context
from adaptexts.many_valued_context import ManyValuedContext
from cacheable.core.abstractions import CacheStats

from .iteration import IterationMixin

if TYPE_CHECKING:
    from pathlib import Path  # noqa: F401

logger = logging.getLogger(__name__)


class HasKeys(Protocol):
    """Protocol for objects that provide a keys() method.

    This protocol is used to indicate that cache mixins expect keys()
    to be provided by another class in the MRO chain.
    """

    def keys(self) -> Iterator[Any]:
        """Yield keys for all available items."""
        ...


class KeyConversionMixin:
    """Mixin for converting cache keys to string representations.

    This mixin provides utilities for converting various key types to strings
    for use with cache backends. Adapters can override _key_to_str() for
    custom key serialization.

    Key Type Support
    ----------------
    - str: Returns as-is
    - int, float: Returns str(key)
    - tuple: Joins elements with ':' separator
    - dict: JSON encoding with sorted keys
    - Other types: Falls back to str(key)
    """

    def _key_to_str(self, key: Any) -> str:
        """Convert a key to its string representation for cache storage.

        This method handles conversion of various key types to strings.
        Adapters can override this method for custom key types.

        Parameters
        ----------
        key : Any
            The key to convert to string.

        Returns
        -------
        str
            String representation suitable for use as a cache key.

        Notes
        -----
        Default implementations:
        - **str**: Returns as-is
        - **int, float**: Returns str(key)
        - **tuple**: Joins elements with ':' separator
        - **dict**: JSON encoding with sorted keys
        - **Other types**: Returns str(key) as fallback

        Override this method for custom key types that require
        special serialization logic.

        Examples
        --------
        >>> # Default behavior for common types
        >>> adapter._key_to_str("dataset1")  # Returns "dataset1"
        >>> adapter._key_to_str(42)  # Returns "42"
        >>> adapter._key_to_str(("branch", "file.txt"))  # Returns "branch:file.txt"
        >>>
        >>> # Custom override for enum keys
        >>> class MyAdapter(KeyConversionMixin):
        ...     def _key_to_str(self, key: MyEnum) -> str:
        ...         return f"myenum:{key.value}"
        """
        if isinstance(key, str):
            return key
        elif isinstance(key, (int, float)):
            return str(key)
        elif isinstance(key, tuple):
            # Join tuple elements with ':' separator
            return ":".join(str(k) for k in key)
        elif isinstance(key, dict):
            # Encode dicts as JSON with sorted keys for consistency
            try:
                return json.dumps(key, sort_keys=True)
            except (TypeError, ValueError):
                # Fallback to string representation if JSON encoding fails
                return str(key)
        else:
            # Fallback for other types
            logger.debug(
                "Using string conversion fallback for key type %s: %s",
                type(key).__name__,
                key,
            )
            return str(key)


class CacheMixin(KeyConversionMixin):
    """Mixin providing cache backend initialization and storage operations.

    This mixin handles:
    - Cache backend initialization via _init_cache()
    - Cache storage operations: get(), set(), delete(), clear_cache()
    - Cache statistics via cache_stats property
    - Cache warming and eviction utilities

    This mixin does NOT provide iteration behavior. Use CacheIterationMixin
    for cached iteration, or implement custom iteration logic that uses
    the cache operations provided by this mixin.

    Attributes
    ----------
    _cache : Optional[CacheBackend]
        The cache backend instance, or None if caching is disabled.
    _cache_config : Optional[CacheConfig]
        The cache configuration used to initialize the backend.

    Examples
    --------
    >>> from adaptexts.adapters.caching import CacheMixin
    >>>
    >>> class MyAdapter(CacheMixin, AdapterInterface):
    ...     def __init__(self, cache_config=None):
    ...         super().__init__()
    ...         self._init_cache(cache_config)
    ...
    ...     def __iter__(self):
    ...         # Custom iteration that uses cache.get()
    ...         for key in self.keys():
    ...             if self.is_cache_enabled:
    ...                 yield self.get(key)
    ...             else:
    ...                 yield self._load_context(key)
    """

    def _init_cache(self, cache_config: Optional[CacheConfig] = None) -> None:
        """Initialize cache backend if caching is enabled.

        Parameters
        ----------
        cache_config : Optional[CacheConfig]
            Cache configuration object. If None, cache initialization is skipped
            and caching is disabled. If provided and enabled is True, creates
            a cache backend using the specified configuration.

        Notes
        -----
        This method must be called by the adapter's __init__ method to enable
        caching. The cache backend type is determined by config.backend, which
        supports "memory", "disk", "disk_db", or "two_tier". The serializer is
        selected based on the adapter's context_type attribute.
        """
        logger.debug(
            "Initializing cache for %s with config: %s",
            self.__class__.__name__,
            cache_config,
        )

        if cache_config is None:
            logger.debug("Cache config is None, skipping cache initialization")
            return

        if not cache_config.enabled:
            logger.info("Caching disabled for %s", self.__class__.__name__)
            self._cache = None
            return

        context_type = getattr(self, "context_type", Context)
        serializer = cache_config.get_serializer_for_context_type(context_type)
        logger.debug(
            "Creating cache backend: context_type=%s, backend=%s, "
            "disk_cache_dir=%s, serializer=%s",
            context_type.__name__,
            cache_config.backend,
            cache_config.disk_cache_dir,
            serializer,
        )
        self._cache = create_context_cache(
            context_type, cache_config, cache_name=self.__class__.__name__
        )
        self._cache_config = cache_config
        logger.info("Cache initialized for %s", self.__class__.__name__)

    def get(self, key: Any) -> Union[Context, ManyValuedContext]:
        """Get context with caching.

        Checks cache first. On cache hit, returns the cached context.
        On cache miss, generates a new context using _get(), stores it
        in cache, and returns it.

        Parameters
        ----------
        key : Any
            Cache key for the context to retrieve. Can be any hashable type
            supported by the adapter's keys() method.

        Returns
        -------
        Union[Context, ManyValuedContext]
            Cached or newly generated context.

        Raises
        ------
        ValueError
            If cache is not initialized (caching is disabled).

        Examples
        --------
        >>> adapter = MyAdapter(cache_config=CacheConfig())
        >>> context = adapter.get("my_key")
        >>> print(context.name)
        >>>
        >>> # With integer key
        >>> context = adapter.get(42)
        >>>
        >>> # With tuple key
        >>> context = adapter.get(("branch", "file.txt"))
        """
        # Convert key to string for cache lookup
        cache_key = self._key_to_str(key)

        logger.debug(
            "get() called on %s with original key=%s, cache_key=%s",
            self.__class__.__name__,
            key,
            cache_key,
        )

        cache = getattr(self, "_cache", None)
        if cache is None:
            logger.error("Cache is None in %s.get()", self.__class__.__name__)
            raise ValueError("no cache")

        context = cache.get(cache_key)
        if context is not None:
            # Cache hit - return cached instance
            logger.debug(
                "Cache HIT for key=%s (cache_key=%s) in %s (context: %s)",
                key,
                cache_key,
                self.__class__.__name__,
                getattr(context, "name", "unnamed"),
            )
            return context

        # Cache miss - store and return new instance
        logger.debug(
            "Cache MISS for key=%s (cache_key=%s) in %s, generating context",
            key,
            cache_key,
            self.__class__.__name__,
        )
        context = self._get(key)
        self._set_with_cache_key(key, cache_key, context)
        logger.debug(
            "Stored new context for key=%s (cache_key=%s) in %s (context: %s)",
            key,
            cache_key,
            self.__class__.__name__,
            getattr(context, "name", "unnamed"),
        )
        return context

    def set(self, key: Any, context: Union[Context, ManyValuedContext]) -> None:
        """Store a context in cache.

        Parameters
        ----------
        key : Any
            Cache key for the context. Can be any hashable type.
        context : Union[Context, ManyValuedContext]
            Context to store in cache.

        Raises
        ------
        ValueError
            If cache is not initialized (caching is disabled).

        Notes
        -----
        The key will be converted to a string via _key_to_str() before
        storage. This method is typically called automatically by the get()
        method on cache misses, but can also be used manually to pre-populate
        the cache.
        """
        cache_key = self._key_to_str(key)
        self._set_with_cache_key(key, cache_key, context)

    def _set_with_cache_key(
        self,
        original_key: Any,
        cache_key: str,
        context: Union[Context, ManyValuedContext],
    ) -> None:
        """Internal method to store a context in cache with pre-computed cache key.

        This method is called by get() to avoid double conversion of the key.

        Parameters
        ----------
        original_key : Any
            The original key in its native type (for logging).
        cache_key : str
            The string representation of the key for cache storage.
        context : Union[Context, ManyValuedContext]
            Context to store in cache.

        Raises
        ------
        ValueError
            If cache is not initialized (caching is disabled).
        """
        logger.debug(
            "set() called on %s with key=%s (cache_key=%s), context=%s",
            self.__class__.__name__,
            original_key,
            cache_key,
            getattr(context, "name", "unnamed"),
        )

        cache = getattr(self, "_cache", None)
        if cache is None:
            logger.error("Cache is None in %s.set()", self.__class__.__name__)
            raise ValueError("no cache")

        cache.set(cache_key, context)
        logger.debug(
            "Successfully stored context in cache for key=%s (cache_key=%s)",
            original_key,
            cache_key,
        )

    def _get(self, key: Any) -> Union[Context, ManyValuedContext]:
        """Generate a context without caching.

        This method must be implemented by concrete adapters and should
        contain pure context generation logic with no cache awareness.

        Parameters
        ----------
        key : Any
            Key for the context to generate. The key is one of those
            yielded by the keys() method and will be in its original type
            (not converted to string).

        Returns
        -------
        Union[Context, ManyValuedContext]
            Newly generated context instance.

        Raises
        ------
        NotImplementedError
            If the concrete adapter does not implement this method.

        Notes
        -----
        This method should not access or modify the cache. The caching layer
        is handled entirely by the get() and __iter__() methods.
        The key parameter will be in its original type as yielded by keys().

        Examples
        --------
        >>> # String key
        >>> def _get(self, key: str) -> Context:
        ...     data = self._items[key]
        ...     return Context.from_data(data)
        >>>
        >>> # Integer key
        >>> def _get(self, key: int) -> Context:
        ...     return self.datasets[key].to_context()
        >>>
        >>> # Tuple key
        >>> def _get(self, key: tuple[str, str]) -> Context:
        ...     branch, filename = key
        ...     return self.load_file(branch, filename)
        """
        logger.debug(
            "_get() called on %s with key=%s (type: %s)",
            self.__class__.__name__,
            key,
            type(key).__name__,
        )
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _get() method"
        )

    def delete(self, key: Any) -> bool:
        """Delete a specific context from cache.

        Parameters
        ----------
        key : Any
            The cache key to remove. Can be any hashable type supported
            by the adapter's keys() method.

        Returns
        -------
        bool
            True if the context was deleted, False if it was not cached.

        Notes
        -----
        The key will be converted to a string via _key_to_str() for cache lookup.
        This method does not raise an exception if the key is not found;
        it simply returns False.

        Examples
        --------
        >>> adapter = MyAdapter(cache_config=CacheConfig())
        >>> key = list(adapter.keys())[0]
        >>> adapter.delete(key)
        True
        """
        cache_key = self._key_to_str(key)

        logger.debug(
            "delete() called on %s with key=%s (cache_key=%s)",
            self.__class__.__name__,
            key,
            cache_key,
        )

        cache = getattr(self, "_cache", None)
        if cache is None:
            logger.debug(
                "Cannot delete key %s: cache not enabled for %s",
                key,
                self.__class__.__name__,
            )
            return False

        result = cache.delete(cache_key)
        if result:
            logger.debug(
                "Successfully deleted key=%s (cache_key=%s) from cache", key, cache_key
            )
        else:
            logger.debug(
                "Key=%s (cache_key=%s) not found in cache, nothing deleted",
                key,
                cache_key,
            )
        return result

    def clear_cache(self) -> None:
        """Clear all cached contexts for this adapter.

        Removes all cached contexts from the cache backend. This does not
        affect contexts that have already been yielded to the caller.

        Raises
        ------
        RuntimeError
            If caching is not enabled.

        Examples
        --------
        >>> adapter = MyAdapter(cache_config=CacheConfig())
        >>> adapter.clear_cache()
        """
        logger.info("clear_cache() called on %s", self.__class__.__name__)
        cache = getattr(self, "_cache", None)
        if cache is None:
            logger.warning(
                "Attempted to clear cache on %s but caching is not enabled",
                self.__class__.__name__,
            )
            raise RuntimeError("Caching is not enabled for this adapter")

        stats_before = cache.get_stats()
        logger.debug(
            "Cache stats before clear: hits=%d, misses=%d, size=%d",
            stats_before.hits,
            stats_before.misses,
            stats_before.size,
        )
        cache.clear()
        logger.info("Cache cleared successfully for %s", self.__class__.__name__)

    @property
    def cache_stats(self) -> CacheStats:
        """Get cache performance statistics.

        Returns
        -------
        CacheStats
            Object containing cache statistics with the following attributes:
            - hits: int - Number of cache hits
            - misses: int - Number of cache misses
            - hit_rate: float - Cache hit rate (0.0 to 1.0)
            - size: int - Number of items currently cached

        Raises
        ------
        RuntimeError
            If caching is not enabled.

        Examples
        --------
        >>> adapter = MyAdapter(cache_config=CacheConfig())
        >>> stats = adapter.cache_stats
        >>> print(f"Hit rate: {stats.hit_rate:.2%}")
        """
        logger.debug("cache_stats property accessed on %s", self.__class__.__name__)
        cache = getattr(self, "_cache", None)
        if cache is None:
            logger.warning(
                "Attempted to get cache stats on %s but caching is not enabled",
                self.__class__.__name__,
            )
            raise RuntimeError("Caching is not enabled for this adapter")

        stats = cache.get_stats()
        logger.debug(
            "Cache stats for %s: hits=%d, misses=%d, hit_rate=%.2f%%, size=%d",
            self.__class__.__name__,
            stats.hits,
            stats.misses,
            stats.hit_rate * 100,
            stats.size,
        )
        return stats

    @property
    def is_cache_enabled(self) -> bool:
        """Check if caching is enabled for this adapter.

        Returns
        -------
        bool
            True if caching is enabled and the cache backend is initialized,
            False otherwise.

        Examples
        --------
        >>> adapter = MyAdapter(cache_config=CacheConfig())
        >>> adapter.is_cache_enabled
        True
        >>> adapter_no_cache = MyAdapter(cache_config=CacheConfig(enabled=False))
        >>> adapter_no_cache.is_cache_enabled
        False
        """
        enabled = hasattr(self, "_cache") and self._cache is not None
        logger.debug(
            "is_cache_enabled check on %s: %s", self.__class__.__name__, enabled
        )
        return enabled

    def evict_contexts(self, pattern: str) -> int:
        """Evict contexts matching a glob pattern.

        Parameters
        ----------
        pattern : str
            Glob pattern for cache keys to evict.
            Examples: "MyAdapter:*", "*:dataset1", "*.csv", "*:main:*"

        Returns
        -------
        int
            Number of contexts that were evicted from the cache.

        Raises
        ------
        RuntimeError
            If caching is not enabled.

        Notes
        -----
        The pattern matching uses Unix shell-style wildcards as implemented
        by the fnmatch module. Common patterns:
        - "*" matches anything
        - "?" matches any single character
        - "[seq]" matches any character in seq
        - "[!seq]" matches any character not in seq

        For composite keys (tuples), the pattern matches against the
        string representation. For example, a key ("main", "file.txt")
        becomes "main:file.txt", which can be matched with "main:*".

        Examples
        --------
        >>> adapter = MyAdapter(cache_config=CacheConfig())
        >>> # Evict all cached contexts from this adapter
        >>> count = adapter.evict_contexts("MyAdapter:*")
        >>> # Evict contexts for a specific dataset
        >>> count = adapter.evict_contexts("*:dataset1")
        >>> # Evict contexts from a specific branch (tuple key example)
        >>> count = adapter.evict_contexts("*:main:*")
        """
        logger.info(
            "evict_contexts() called on %s with pattern='%s'",
            self.__class__.__name__,
            pattern,
        )
        cache = getattr(self, "_cache", None)
        if cache is None:
            logger.warning(
                "Cannot evict contexts on %s: caching is not enabled",
                self.__class__.__name__,
            )
            raise RuntimeError("Caching is not enabled for this adapter")

        # Access the internal _metadata dict to get all keys
        metadata = getattr(cache, "_metadata", None)
        if not isinstance(metadata, dict):
            logger.debug("No metadata dict found, no keys to evict")
            return 0

        # Find all keys matching the pattern
        keys_to_delete = [
            key for key in metadata.keys() if fnmatch.fnmatch(key, pattern)
        ]
        logger.debug(
            "Found %d keys matching pattern '%s'", len(keys_to_delete), pattern
        )

        # Delete matching keys
        for key in keys_to_delete:
            cache.delete(key)
            logger.debug("Evicted key: %s", key)

        logger.info(
            "Evicted %d contexts matching pattern '%s' from %s",
            len(keys_to_delete),
            pattern,
            self.__class__.__name__,
        )
        return len(keys_to_delete)


class CacheIterationMixin(CacheMixin, IterationMixin):
    """Mixin providing cached iteration behavior.

    This mixin provides an __iter__ implementation that:
    - Uses parent's keys() method
    - Uses CacheMixin operations (get(), is_cache_enabled)
    - Overrides IterationMixin's __iter__ to add caching logic

    The iteration behavior is:
    - If caching is enabled: call get() for each key (uses cache if available)
    - If caching is disabled: call _get() directly for each key (bypasses cache)

    This mixin relies on:
    - A parent class providing keys() method
    - CacheMixin providing get() and _get() methods
    - IterationMixin providing base iteration behavior
    - The adapter providing _get() implementation

    Examples
    --------
    >>> from adaptexts.adapters.caching import CacheIterationMixin
    >>>
    >>> class MyCachedAdapter(CacheIterationMixin, AdapterInterface):
    ...     def __init__(self, cache_config=None):
    ...         super().__init__()
    ...         self._init_cache(cache_config)
    ...
    ...     def keys(self) -> Iterator[str]:
    ...         yield from ["a", "b", "c"]
    ...
    ...     def _get(self, key: str) -> Context:
    ...         return Context(set(), set(), set(), name=key)
    """

    def __iter__(self) -> Iterator[Union[Context, ManyValuedContext]]:
        """Iterate with per-element caching.

        If caching is enabled, each yielded element is processed as follows:
        1. Retrieve a key from keys()
        2. Convert key to string via _key_to_str()
        3. Check cache for the string key
        4. If cached: yield the cached context
        5. If not cached: call _get() with original key, store the new context, and yield it

        If caching is disabled, directly calls _get() for each key without
        any caching operations.

        Yields
        ------
        Union[Context, ManyValuedContext]
            Cached or newly computed context for each iteration.

        Examples
        --------
        >>> adapter = MyAdapter(cache_config=CacheConfig())
        >>> for context in adapter:  # Uses cached iteration if enabled
        ...     print(context.name)
        """
        logger.info(
            "Starting iteration on %s, cache enabled: %s",
            self.__class__.__name__,
            self.is_cache_enabled,
        )
        if self.is_cache_enabled:
            # With per-element caching
            logger.debug("Cache enabled, using cached iteration")
            for key in self.keys():  # type: ignore[attr-defined]
                yield self.get(key)
            logger.debug("Cached iteration completed")
        else:
            # No caching - delegate to raw iteration (call parent Implementation)
            logger.debug("Cache disabled, using direct iteration")
            yield from super().__iter__()
            logger.debug("Direct iteration completed")
        logger.info("Iteration completed on %s", self.__class__.__name__)
