"""Factory function for creating serialization strategies.

This module provides a factory function to create strategy instances
by name, making it easy to configure caches dynamically.

Enhanced with strategy capability discovery and context type validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from adaptexts.base.cache.serializers.base import SerializationStrategy
from adaptexts.base.cache.serializers.binary import BinaryStrategy
from adaptexts.base.cache.serializers.context_strategies import (
    BurmeisterStrategy,
    ColibriStrategy,
    CSVStrategy,
    FIMIContextStrategy,
    JSONContextStrategy,
)
from adaptexts.base.cache.serializers.passthrough import PassthroughStrategy
from adaptexts.base.cache.serializers.pickle import PickleStrategy
from cacheable.serializers import JSONStrategy

if TYPE_CHECKING:
    # noqa: F401 - These are imported in function bodies to avoid circular imports
    pass


@dataclass(frozen=True)
class StrategyCapability:
    """Describes a serialization strategy's capabilities.

    Attributes
    ----------
    name : str
        Strategy name (canonical).
    aliases : tuple[str, ...]
        Alternative names for the strategy.
    description : str
        Human-readable description.
    supports_context : bool
        Whether the strategy supports Context objects.
    supports_manyvalued_context : bool
        Whether the strategy supports ManyValuedContext objects.
    supports_generic : bool
        Whether the strategy supports generic Python objects.
    requires_binary : bool
        Whether the strategy requires binary/bytes input.
    is_persistence_friendly : bool
        Whether the format is human-readable and suitable for long-term storage.
    """

    name: str
    aliases: tuple[str, ...]
    description: str
    supports_context: bool
    supports_manyvalued_context: bool
    supports_generic: bool
    requires_binary: bool
    is_persistence_friendly: bool


# Capability registry
_STRATEGY_CAPABILITIES: dict[str, StrategyCapability] = {
    # Context-specific strategies
    "burmeister": StrategyCapability(
        name="burmeister",
        aliases=("burmeister",),
        description="Burmeister formal context format",
        supports_context=True,
        supports_manyvalued_context=False,
        supports_generic=False,
        requires_binary=False,
        is_persistence_friendly=True,
    ),
    "colibri": StrategyCapability(
        name="colibri",
        aliases=("colibri",),
        description="Colibri formal context format",
        supports_context=True,
        supports_manyvalued_context=False,
        supports_generic=False,
        requires_binary=False,
        is_persistence_friendly=True,
    ),
    "fimi": StrategyCapability(
        name="fimi",
        aliases=("fimi",),
        description="FIMI frequent itemset mining format",
        supports_context=True,
        supports_manyvalued_context=False,
        supports_generic=False,
        requires_binary=False,
        is_persistence_friendly=True,
    ),
    # Pickle variants
    "pickle": StrategyCapability(
        name="pickle",
        aliases=("pickle",),
        description="Generic pickle for any Python object",
        supports_context=True,
        supports_manyvalued_context=True,
        supports_generic=True,
        requires_binary=False,
        is_persistence_friendly=False,
    ),
    "pickle_context": StrategyCapability(
        name="pickle_context",
        aliases=("pickle_context", "picklectx", "picklectxstrategy"),
        description="Pickle for Context/ManyValuedContext only",
        supports_context=True,
        supports_manyvalued_context=True,
        supports_generic=False,
        requires_binary=False,
        is_persistence_friendly=False,
    ),
    # CSV
    "csv": StrategyCapability(
        name="csv",
        aliases=("csv",),
        description="CSV format for contexts",
        supports_context=True,
        supports_manyvalued_context=True,
        supports_generic=False,
        requires_binary=False,
        is_persistence_friendly=True,
    ),
    # JSON variants
    "json": StrategyCapability(
        name="json",
        aliases=("json",),
        description="Generic JSON for JSON-serializable objects",
        supports_context=False,
        supports_manyvalued_context=False,
        supports_generic=True,
        requires_binary=False,
        is_persistence_friendly=True,
    ),
    "json_context": StrategyCapability(
        name="json_context",
        aliases=("json_context", "jsonctx"),
        description="JSON for Context/ManyValuedContext",
        supports_context=True,
        supports_manyvalued_context=True,
        supports_generic=False,
        requires_binary=False,
        is_persistence_friendly=True,
    ),
    # Binary/Passthrough
    "binary": StrategyCapability(
        name="binary",
        aliases=("binary",),
        description="Pass-through for binary data",
        supports_context=False,
        supports_manyvalued_context=False,
        supports_generic=True,
        requires_binary=True,
        is_persistence_friendly=False,
    ),
    "passthrough": StrategyCapability(
        name="passthrough",
        aliases=("passthrough", "pass-through", "noop"),
        description="No serialization (in-memory only)",
        supports_context=False,
        supports_manyvalued_context=False,
        supports_generic=True,
        requires_binary=True,
        is_persistence_friendly=False,
    ),
}


# Strategy registry maps names to (class, kwargs) tuples
_STRATEGY_REGISTRY: dict[str, tuple[type[SerializationStrategy], dict]] = {
    "pickle": (PickleStrategy, {"context_only": False}),
    "pickle_context": (PickleStrategy, {"context_only": True}),
    "picklectx": (PickleStrategy, {"context_only": True}),
    "burmeister": (BurmeisterStrategy, {}),
    "colibri": (ColibriStrategy, {}),
    "fimi": (FIMIContextStrategy, {}),
    "csv": (CSVStrategy, {}),
    "json": (JSONStrategy, {}),
    "json_context": (JSONContextStrategy, {}),
    "jsonctx": (JSONContextStrategy, {}),
    "picklectxstrategy": (PickleStrategy, {"context_only": True}),
    "binary": (BinaryStrategy, {}),
    "pass-through": (PassthroughStrategy, {}),
    "passthrough": (PassthroughStrategy, {}),
    "noop": (PassthroughStrategy, {}),
}


def _resolve_strategy_name(name: str) -> Optional[str]:
    """Resolve strategy name (including aliases) to canonical name.

    Parameters
    ----------
    name : str
        Strategy name to resolve.

    Returns
    -------
    str or None
        Canonical strategy name, or None if not found.
    """
    name = name.lower()

    # Check if it's already a canonical name
    if name in _STRATEGY_CAPABILITIES:
        return name

    # Check aliases
    for canonical_name, capability in _STRATEGY_CAPABILITIES.items():
        if name in capability.aliases:
            return canonical_name

    return None


def _validate_context_type_support(
    strategy_name: str,
    capability: StrategyCapability,
    context_type: type,
) -> None:
    """Validate that strategy supports the given context type.

    Parameters
    ----------
    strategy_name : str
        Strategy name.
    capability : StrategyCapability
        Strategy capabilities.
    context_type : type
        Context type to validate.

    Raises
    ------
    ValueError
        If strategy doesn't support the context type.
    """
    from adaptexts.context import Context
    from adaptexts.many_valued_context import ManyValuedContext

    if context_type is Context:
        if not capability.supports_context:
            supported = get_strategies_for_context_type(Context)
            raise ValueError(
                f"Strategy '{strategy_name}' does not support Context. "
                f"Supported strategies: {', '.join(supported)}"
            )
    elif context_type is ManyValuedContext:
        if not capability.supports_manyvalued_context:
            supported = get_strategies_for_context_type(ManyValuedContext)
            raise ValueError(
                f"Strategy '{strategy_name}' does not support ManyValuedContext. "
                f"Supported strategies: {', '.join(supported)}"
            )
    # Generic type
    elif not capability.supports_generic:
        raise ValueError(
            f"Strategy '{strategy_name}' does not support generic objects. "
            f"Try: pickle, json, binary, passthrough"
        )


def create_strategy(
    strategy_name: str,
    *,
    context_type: Optional[type] = None,
    **kwargs: object,
) -> SerializationStrategy:
    """Factory function to create serialization strategy instances.

    Parameters
    ----------
    strategy_name : str
        Name of the strategy to create. Valid options:
        - "pickle": Generic pickle (any object)
        - "pickle_context" or "picklectx": Pickle for Context/ManyValuedContext only
        - "burmeister": Burmeister format (Context only)
        - "colibri": Colibri format (Context only)
        - "fimi": FIMI format (Context only)
        - "csv": CSV format (Context and ManyValuedContext)
        - "json": Generic JSON (any JSON-serializable object)
        - "json_context" or "jsonctx": JSON for Context/ManyValuedContext
        - "binary": Pass-through binary (bytes only)
    context_type : type, optional
        Context type to validate against (Context or ManyValuedContext).
        If provided, validates that the strategy supports this type.
    **kwargs : dict
        Additional keyword arguments to pass to the strategy constructor.

    Returns
    -------
    SerializationStrategy
        Strategy instance.

    Raises
    ------
    ValueError
        If strategy name is unknown or doesn't support the context type.

    Examples
    --------
    >>> from adaptexts.base.cache.serializers import create_strategy
    >>> from adaptexts.context import Context
    >>>
    >>> # Create a generic pickle strategy (no validation)
    >>> strategy = create_strategy("pickle")
    >>>
    >>> # Create with context type validation
    >>> strategy = create_strategy("burmeister", context_type=Context)  # ✅ OK
    >>> strategy = create_strategy("burmeister", context_type=ManyValuedContext)  # ❌ Error
    """
    strategy_name = strategy_name.lower()

    # Resolve aliases
    canonical_name = _resolve_strategy_name(strategy_name)
    if canonical_name is None:
        valid_names = sorted(_STRATEGY_CAPABILITIES.keys())
        raise ValueError(
            f"Unknown strategy '{strategy_name}'. Must be one of: {valid_names}"
        )

    # Validate context type support if provided
    if context_type is not None:
        capability = _STRATEGY_CAPABILITIES[canonical_name]
        _validate_context_type_support(canonical_name, capability, context_type)

    # Create strategy (using existing registry)
    strategy_class, default_kwargs = _STRATEGY_REGISTRY[canonical_name]
    merged_kwargs = {**default_kwargs, **kwargs}

    return strategy_class(**merged_kwargs)


def get_strategies_for_context_type(context_type: type) -> list[str]:
    """Get strategies that support a specific context type.

    Parameters
    ----------
    context_type : type
        Context class (Context or ManyValuedContext).

    Returns
    -------
    list of str
        Strategy names that support the context type.

    Examples
    --------
    >>> from adaptexts.context import Context
    >>> get_strategies_for_context_type(Context)
    ['burmeister', 'colibri', 'csv', 'json_context', 'pickle', 'pickle_context']

    >>> from adaptexts.many_valued_context import ManyValuedContext
    >>> get_strategies_for_context_type(ManyValuedContext)
    ['csv', 'json_context', 'pickle', 'pickle_context']
    """
    from adaptexts.context import Context
    from adaptexts.many_valued_context import ManyValuedContext

    result = []

    for name, capability in _STRATEGY_CAPABILITIES.items():
        if context_type is Context and capability.supports_context:
            result.append(name)
        elif (
            context_type is ManyValuedContext and capability.supports_manyvalued_context
        ):
            result.append(name)

    return sorted(result)


def get_strategy_capabilities(strategy_name: str) -> StrategyCapability:
    """Get capabilities for a specific strategy.

    Parameters
    ----------
    strategy_name : str
        Strategy name.

    Returns
    -------
    StrategyCapability
        Capability metadata.

    Raises
    ------
    ValueError
        If strategy name is unknown.

    Examples
    --------
    >>> caps = get_strategy_capabilities("burmeister")
    >>> caps.supports_context
    True
    >>> caps.supports_manyvalued_context
    False
    >>> caps.is_persistence_friendly
    True
    """
    canonical_name = _resolve_strategy_name(strategy_name)
    if canonical_name is None:
        raise ValueError(f"Unknown strategy: {strategy_name}")

    return _STRATEGY_CAPABILITIES[canonical_name]


def validate_strategy_for_context_type(
    strategy_name: str,
    context_type: type,
) -> bool:
    """Check if a strategy supports a context type.

    Parameters
    ----------
    strategy_name : str
        Strategy name.
    context_type : type
        Context class to check.

    Returns
    -------
    bool
        True if strategy supports the context type.

    Examples
    --------
    >>> validate_strategy_for_context_type("burmeister", Context)
    True

    >>> validate_strategy_for_context_type("burmeister", ManyValuedContext)
    False
    """
    from adaptexts.context import Context
    from adaptexts.many_valued_context import ManyValuedContext

    canonical_name = _resolve_strategy_name(strategy_name)
    if canonical_name is None:
        return False

    capability = _STRATEGY_CAPABILITIES[canonical_name]

    if context_type is Context:
        return capability.supports_context
    elif context_type is ManyValuedContext:
        return capability.supports_manyvalued_context
    else:
        return capability.supports_generic


def list_all_strategies() -> dict[str, StrategyCapability]:
    """Get all available strategies with their capabilities.

    Returns
    -------
    dict[str, StrategyCapability]
        Mapping of strategy names to capabilities.
    """
    return dict(_STRATEGY_CAPABILITIES)


def get_available_strategies() -> list[str]:
    """Get list of available strategy names.

    Returns
    -------
    list of str
        Sorted list of available strategy names (legacy, for backward compatibility).

    Note
    ----
    For new code, prefer list_all_strategies() which includes capabilities.
    """
    return sorted(_STRATEGY_CAPABILITIES.keys())


__all__ = [
    "StrategyCapability",
    "create_strategy",
    "get_strategies_for_context_type",
    "get_strategy_capabilities",
    "validate_strategy_for_context_type",
    "list_all_strategies",
    "get_available_strategies",
]
