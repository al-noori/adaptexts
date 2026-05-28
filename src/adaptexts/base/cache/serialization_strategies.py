"""Serialization strategies for cache backends.

This module provides legacy compatibility imports. Most strategies are now
imported from cacheable (generic) or adaptexts.base.cache.serializers (context-specific).
"""

from typing import Any

from cacheable.core.abstractions import SerializationStrategy

# Re-export generic strategies from cacheable
from cacheable.serializers import (
    BinaryStrategy,
    JSONStrategy,
    PassthroughStrategy,
    PickleStrategy,
)

# Re-export context-specific strategies from adaptexts
from adaptexts.base.cache.serializers import (
    BurmeisterStrategy,
    CSVStrategy,
    ColibriStrategy,
    JSONContextStrategy,
    create_strategy,
)


class DiskCacheNativeStrategy(SerializationStrategy):
    """No-op strategy for diskcache native serialization.

    This strategy passes values through without serialization, relying
    on diskcache's built-in serialization capabilities.

    Notes
    -----
    This should only be used with DiskDBCache backend.
    """

    def serialize(self, value: Any) -> Any:
        """Return value as-is (diskcache handles serialization)."""
        return value

    def deserialize(self, data: Any) -> Any:
        """Return data as-is (diskcache handles deserialization)."""
        return data


__all__ = [
    # Native strategy
    "DiskCacheNativeStrategy",
    # Re-exported from cacheable (generic strategies)
    "PickleStrategy",
    "JSONStrategy",
    "BinaryStrategy",
    "PassthroughStrategy",
    # Re-exported from adaptexts.base.cache.serializers (context-specific)
    "BurmeisterStrategy",
    "ColibriStrategy",
    "CSVStrategy",
    "JSONContextStrategy",
    "create_strategy",
]