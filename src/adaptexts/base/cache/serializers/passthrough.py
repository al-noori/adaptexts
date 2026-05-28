"""Pass-through serialization strategy.

This module provides a serialization strategy that stores Python objects
directly without serialization, useful for in-memory caching where
persistence is not required.
"""

from typing import Any

from adaptexts.base.cache.serializers.base import SerializationStrategy


class PassthroughStrategy(SerializationStrategy):
    """Pass-through serialization for non-persistent caching.

    This strategy stores and returns Python objects as-is without any
    serialization. This is useful for in-memory caching where the fastest
    possible performance is required and persistence across process
    restarts is not needed.

    Warning
    -------
    This strategy should only be used with in-memory backends (MemoryCache).
    Using with disk backends will fail when trying to write non-bytes to disk.

    Examples
    --------
    >>> from adaptexts.base.cache import MemoryCache, PassthroughStrategy
    >>>
    >>> # Fast in-memory cache without serialization
    >>> cache = MemoryCache(
    ...     serializer=PassthroughStrategy(),
    ...     max_size=1000
    ... )
    >>>
    >>> # Works with any Python object
    >>> cache.set("key", {"nested": ["data", 1, 2, 3]})
    >>> assert cache.get("key") == {"nested": ["data", 1, 2, 3]}
    """

    def serialize(self, value: Any) -> Any:
        """Return value as-is (no serialization).

        Parameters
        ----------
        value : Any
            Any Python object.

        Returns
        -------
        Any
            The same object unchanged.
        """
        return value

    def deserialize(self, data: Any) -> Any:
        """Return data as-is (no deserialization).

        Parameters
        ----------
        data : Any
            Any Python object.

        Returns
        -------
        Any
            The same object unchanged.
        """
        return data