"""Unified serialization strategies for cache backends.

This package provides various serialization strategies that implement the
SerializationStrategy interface from cache_abstractions.py. All strategies
are named consistently with the "Strategy" suffix.

The strategies are organized by purpose:
- Generic strategies: work with any Python object
- Context-specific strategies: work with Context and/or ManyValuedContext objects

Example Usage
-------------
>>> from adaptexts.base.cache.serializers import PickleStrategy, BurmeisterStrategy
>>> from adaptexts.base.cache import CacheBuilder, create_strategy
>>>
>>> # Generic pickle strategy (any object)
>>> generic_pickle = PickleStrategy()
>>>
>>> # Context-specific strategies
>>> burmeister = BurmeisterStrategy()
>>> colibri = create_strategy("colibri")
"""

from adaptexts.base.cache.serializers.base import SerializationStrategy
from adaptexts.base.cache.serializers.binary import BinaryStrategy
from adaptexts.base.cache.serializers.context_strategies import (
    BurmeisterStrategy,
    ColibriStrategy,
    CSVStrategy,
    FIMIContextStrategy,
    JSONContextStrategy,
)
from adaptexts.base.cache.serializers.factory import (
    StrategyCapability,
    create_strategy,
    get_available_strategies,
    get_strategies_for_context_type,
    get_strategy_capabilities,
    list_all_strategies,
    validate_strategy_for_context_type,
)
from adaptexts.base.cache.serializers.passthrough import PassthroughStrategy
from adaptexts.base.cache.serializers.pickle import PickleStrategy

__all__ = [
    # Base interface
    "SerializationStrategy",
    # Generic strategies
    "PickleStrategy",
    "BinaryStrategy",
    "PassthroughStrategy",
    # Context-specific strategies
    "BurmeisterStrategy",
    "ColibriStrategy",
    "CSVStrategy",
    "FIMIContextStrategy",
    "JSONContextStrategy",
    # Factory functions
    "StrategyCapability",
    "create_strategy",
    "get_strategies_for_context_type",
    "get_strategy_capabilities",
    "validate_strategy_for_context_type",
    "list_all_strategies",
    "get_available_strategies",
]
