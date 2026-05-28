"""Pickle-based serialization strategy.

This module provides a unified PickleStrategy that can be configured
to work with any Python object or be restricted to Context and
ManyValuedContext objects only.
"""

from typing import Any

from cacheable.serializers import PickleStrategy as CacheablePickleStrategy


class PickleStrategy(CacheablePickleStrategy):
    """Pickle-based serialization strategy with optional context-only mode.

    This strategy uses Python's pickle module for serialization. It can
    operate in two modes:

    1. Generic mode (context_only=False): Serialize any Python object
    2. Context-only mode (context_only=True): Only serialize Context and
       ManyValuedContext objects (validates type, uses standard pickle)

    Parameters
    ----------
    context_only : bool, optional
        If True, only accepts Context and ManyValuedContext objects.
        If False, accepts any pickle-serializable object. Default is False.

    Notes
    -----
    Pickle is fast and supports most Python objects, but the format
    is Python-specific and may have security implications for untrusted data.

    When context_only=True, the strategy validates that the value is a
    Context or ManyValuedContext before serializing with standard pickle.
    """

    def __init__(self, context_only: bool = False):
        self._context_only = context_only

    def serialize(self, value: Any) -> bytes:
        """Serialize value using pickle.

        Parameters
        ----------
        value : Any
            The value to serialize.

        Returns
        -------
        bytes
            Pickled representation of the value.

        Raises
        ------
        TypeError
            If context_only=True and value is not Context or ManyValuedContext.
        """
        if self._context_only:
            # Lazy import to avoid circular imports at module load time
            from adaptexts.context import Context
            from adaptexts.many_valued_context import ManyValuedContext

            if not isinstance(value, (Context, ManyValuedContext)):
                raise TypeError(
                    f"PickleStrategy(context_only=True) only supports "
                    f"Context and ManyValuedContext objects, "
                    f"got {type(value).__name__}"
                )
        return super().serialize(value)

    def deserialize(self, data: bytes) -> Any:
        """Deserialize value using pickle.

        Parameters
        ----------
        data : bytes
            Pickled data.

        Returns
        -------
        Any
            The deserialized value.

        Raises
        ------
        TypeError
            If data is not bytes.
        pickle.UnpicklingError
            If deserialization fails.
        """
        value = super().deserialize(data)
        if self._context_only:
            # Lazy import to avoid circular imports at module load time
            from adaptexts.context import Context
            from adaptexts.many_valued_context import ManyValuedContext

            if not isinstance(value, (Context, ManyValuedContext)):
                raise TypeError(
                    f"PickleStrategy(context_only=True) only supports "
                    f"Context and ManyValuedContext objects, "
                    f"got {type(value).__name__}"
                )
        return value
