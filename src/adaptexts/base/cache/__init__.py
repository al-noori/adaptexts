"""New cache architecture with composable mixins.

This package provides a redesigned cache system with the following features:

- **Composable mixins** for storage, eviction, serialization, and metadata
- **Multiple storage backends**: Memory, DiskFile, DiskDB (using diskcache)
- **Unified serialization strategies**: Pickle, JSON, Context-aware, Binary
- **Two-tier composition** for memory + disk caching
- **Immutable builder data class** for cache configuration

Key Components
--------------
Re-exported from cacheable:
- cache_abstractions: Core interfaces (CacheBackend, SerializationStrategy)
- cache_backends: Concrete backend implementations
- cache_mixins: Mixin building blocks for composing backends
- serializers: Generic serialization strategies
- cache_builder: Immutable configuration data class for creating caches
- config: Generic cache configuration

Context-specific (stays in adaptests):
- ContextSerializer: Base class for context serialization
- Context-specific strategies: Burmeister, Colibri, CSV, JSONContext, PickleContext
- create_context_cache: Factory for context-type-specific caches
- CacheConfig: Full configuration with context serializers

Unified Serialization Strategies
---------------------------------
**Generic strategies** (from cacheable):
- PickleStrategy: Python pickle serialization
- JSONStrategy: JSON for JSON-serializable objects
- BinaryStrategy: Pass-through for bytes
- PassthroughStrategy: No serialization (in-memory only)
- DiskCacheNativeStrategy: Native diskcache serialization

**Context-specific strategies** (from adaptexts.base.cache.serializers):
- PickleContextStrategy: Pickle for Context/ManyValuedContext
- BurmeisterStrategy: Burmeister format (Context only)
- ColibriStrategy: Colibri format (Context only)
- CSVStrategy: CSV format (Context and ManyValuedContext)
- JSONContextStrategy: JSON for Context/ManyValuedContext

**Factory function**:
- create_strategy(name): Create a strategy by name

Example Usage
-------------
>>> from pathlib import Path
>>> from adaptexts.base.cache import CacheBuilder, compose_two_tier
>>> from adaptexts.base.cache.serializers import BurmeisterStrategy, create_strategy
>>>
>>> # Create a simple memory cache
>>> cache = CacheBuilder(storage_type="memory", max_size=100).build()
>>>
>>> # Create a disk file cache with Burmeister serializer
>>> cache = CacheBuilder(
...     storage_type="disk_file",
...     data_home_key="adaptexts",
...     serializer=BurmeisterStrategy(),
...     ttl=3600
... ).build()
>>>
>>> # Create a disk file cache using factory
>>> cache = CacheBuilder(
...     storage_type="disk_file",
...     cache_dir=Path("/tmp/cache"),
...     serializer=create_strategy("burmeister"),
...     ttl=3600
... ).build()
>>>
>>> # Create a two-tier cache (memory + disk)
>>> two_tier = compose_two_tier(
...     CacheBuilder(storage_type="memory", max_size=100),
...     CacheBuilder(storage_type="disk_db")  # Auto-resolves via data_home
... )
"""

# ============================================================================
# Re-exports from cacheable (generic functionality)
# ============================================================================

from cacheable.core.abstractions import (
    CacheBackend,
    CacheStats,
    SerializationStrategy,
)
from cacheable.backends import (
    DiskDBCache,
    DiskFileCache,
    MemoryCache,
    TwoTierCache,
    create_disk_db_cache,
    create_disk_file_cache,
    create_memory_cache,
)
from cacheable.builder import CacheBuilder
from cacheable.composers import compose_two_tier
from cacheable.config import CacheConfig as GenericCacheConfig
from cacheable.mixins import (
    BaseCache,
    DiskDBStorageMixin,
    DiskFileStorageMixin,
    EvictionMixin,
    MemoryStorageMixin,
    MetadataMixin,
    StorageMixin,
)
from cacheable.paths import (
    get_cache_dir as _get_cache_dir,
    get_default_cache_dir as _get_default_cache_dir,
    clear_cache_directory as _clear_cache_directory,
    create_cache_factory as _create_cache_factory,
    get_cache_size,
    validate_cache_consistency,
)

from cacheable.serializers import get_available_strategies

# Re-export specific serializers from cacheable and local
from cacheable.serializers import (
    BinaryStrategy,
    JSONStrategy,
    PassthroughStrategy,
)
from adaptexts.base.cache.serializers.pickle import (
    PickleStrategy,  # Local version with context_only support
)

# ============================================================================  
# Context-specific code (stays in adaptests)
# ============================================================================

# Context serializer base class
from adaptexts.base.cache.serializers.base import ContextSerializer

# Context-specific serializers
from adaptexts.base.cache.serializers.context_strategies import (
    BurmeisterStrategy,
    CSVStrategy,
    ColibriStrategy,
    JSONContextStrategy,
)

# Factory for context-specific cache creation
from adaptexts.base.cache.factory import create_context_cache

# CacheConfig with context-specific serializers (extends generic)
from adaptexts.base.cache.config import CacheConfig

# Legacy serialization strategies module (for backward compatibility)
from adaptexts.base.cache.serialization_strategies import DiskCacheNativeStrategy

# Cache factory for adaptexts-specific paths
from adaptexts.base.cache.paths import (
    clear_adapter_cache,
    create_cache_factory,
    get_cache_dir,
    get_default_cache_dir,
)

# create_strategy wrapper that includes context strategies
from adaptexts.base.cache.serializers.factory import (
    StrategyCapability,
    create_strategy,
    get_strategies_for_context_type,
    get_strategy_capabilities,
    validate_strategy_for_context_type,
    list_all_strategies,
)

# Context-aware backends
from adaptexts.base.cache.context_backends import (
    ContextAwareTwoTierCache,
    create_context_aware_two_tier,
    ContextMetadata,
    ContextAwareCacheStats,
)

# ============================================================================
# All exports
# ============================================================================

__all__ = [
    # Core abstractions (from cacheable)
    "CacheBackend",
    "CacheStats",
    "SerializationStrategy",
    # Backends (from cacheable)
    "MemoryCache",
    "DiskFileCache",
    "DiskDBCache",
    "TwoTierCache",
    # Backend creators (from cacheable)
    "create_memory_cache",
    "create_disk_file_cache",
    "create_disk_db_cache",
    # Mixins (from cacheable)
    "BaseCache",
    "StorageMixin",
    "MemoryStorageMixin",
    "DiskFileStorageMixin",
    "DiskDBStorageMixin",
    "MetadataMixin",
    "EvictionMixin",
    # Generic serialization strategies (adatexts-local with context_only support)
    "PickleStrategy",  # Use PickleStrategy(context_only=True) for contexts
    "JSONStrategy",
    "BinaryStrategy",
    "PassthroughStrategy",
    # Native strategy
    "DiskCacheNativeStrategy",
    # Context-specific serialization strategies (from adaptests.base.cache.serializers)
    "BurmeisterStrategy",
    "ColibriStrategy",
    "CSVStrategy",
    "JSONContextStrategy",
    "ContextSerializer",
    # Strategy factory functions
    "StrategyCapability",
    "create_strategy",
    "get_strategies_for_context_type",
    "get_strategy_capabilities",
    "validate_strategy_for_context_type",
    "list_all_strategies",
    "get_available_strategies",
    # Builder API (from cacheable)
    "CacheBuilder",
    "compose_two_tier",
    # Cache utilities
    "CacheConfig",  # Full version with context serializers
    "create_context_cache",
    # Path utilities (adaptexts-specific versions)
    "clear_adapter_cache",
    "create_cache_factory",
    "get_cache_dir",
    "get_default_cache_dir",
    # Generic path utilities (from cacheable, available via different names)
    "get_cache_size",
    "validate_cache_consistency",
    # Context-aware backends
    "ContextAwareTwoTierCache",
    "create_context_aware_two_tier",
    "ContextMetadata",
    "ContextAwareCacheStats",
]

def __getattr__(name: str):
    """Lazy import for deprecated imports."""
    if name in ("EvictionPolicy", "CacheBackendUnknown"):
        # These weren't in our exports, but provide helpful error
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")