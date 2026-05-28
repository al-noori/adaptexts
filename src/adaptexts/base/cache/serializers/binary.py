"""Pass-through binary serialization strategy.

This module provides a binary pass-through strategy for data that is
already serialized or in binary format.
"""

from typing import Any

from adaptexts.base.cache.serializers.base import SerializationStrategy


class BinaryStrategy(SerializationStrategy):
    """Pass-through binary serialization strategy.

    This strategy expects values to already be bytes and passes
    them through without modification.

    Raises
    ------
    TypeError
        If value is not bytes.

    Notes
    -----
    Useful when data is already serialized or binary format.
    """

    def serialize(self, value: Any) -> bytes:
        """Return bytes as-is.

        Parameters
        ----------
        value : bytes
            Bytes to store.

        Returns
        -------
        bytes
            The same bytes.

        Raises
        ------
        TypeError
            If value is not bytes.
        """
        if not isinstance(value, bytes):
            raise TypeError(
                f"BinaryStrategy requires bytes, got {type(value).__name__}"
            )
        return value

    def deserialize(self, data: bytes) -> Any:
        """Return data as-is.

        Parameters
        ----------
        data : bytes
            Bytes to return.

        Returns
        -------
        bytes
            The same bytes.
        """
        return data