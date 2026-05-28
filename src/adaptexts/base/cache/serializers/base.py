"""Base serialization strategy interface.

This module defines the ContextSerializer base class with shared utilities
for context serialization. SerializationStrategy is imported from cacheable.
"""

from typing import Any, Callable

from cacheable.core.abstractions import SerializationStrategy


class ContextSerializer(SerializationStrategy):
    """Base class for context serialization with shared utilities.

    This class provides common functionality for all context-specific
    serialization strategies:
    - Type validation for Context and ManyValuedContext
    - UTF-8 decoding with error handling
    - Consistent error wrapping for format parsing

    Subclasses should implement serialize() and deserialize() methods,
    using the protected helper methods to avoid duplication.
    """

    def _validate_context(
        self,
        value: Any,
        *,
        context_only: bool = False,
    ) -> None:
        """Validate that value is a supported context type.

        Parameters
        ----------
        value : Any
            The value to validate.
        context_only : bool, optional
            If True, only accepts Context instances.
            If False (default), accepts both Context and ManyValuedContext.

        Raises
        ------
        TypeError
            If value is not of the expected type(s).

        Examples
        --------
        >>> serializer = SomeContextStrategy()
        >>> serializer._validate_context(ctx, context_only=False)  # Accepts both
        >>> serializer._validate_context(ctx, context_only=True)  # Context only
        """
        from adaptexts.context import Context
        from adaptexts.many_valued_context import ManyValuedContext

        if context_only:
            accepted = (Context,)
            type_names = "Context"
        else:
            accepted = (Context, ManyValuedContext)
            type_names = "Context and ManyValuedContext"

        if not isinstance(value, accepted):
            raise TypeError(
                f"{self.__class__.__name__} only supports {type_names} objects, "
                f"got {type(value).__name__}"
            )

    def _decode_text(self, data: bytes, encoding: str = "utf-8") -> str:
        """Decode bytes to text with consistent error handling.

        Parameters
        ----------
        data : bytes
            The bytes to decode.
        encoding : str, optional
            The encoding to use. Default is "utf-8".

        Returns
        -------
        str
            Decoded text.

        Raises
        ------
        ValueError
            If decoding fails.
        """
        try:
            return data.decode(encoding)
        except UnicodeDecodeError as e:
            raise ValueError(f"Failed to decode {encoding} data: {e}") from e

    def _safe_from_format(
        self,
        from_format_fn: Callable[[str], Any],
        data: bytes,
        format_name: str | None = None,
    ) -> Any:
        """Call a format parsing function with consistent error handling.

        This helper wraps the common pattern of:
        1. Decoding bytes to text
        2. Calling a from_format() class method
        3. Catching and re-raising exceptions with context

        Parameters
        ----------
        from_format_fn : Callable
            The function to call with decoded text (e.g., Context.from_burmeister).
            Should be a class method that accepts a string and returns a context.
        data : bytes
            The serialized data to decode and parse.
        format_name : str, optional
            Name of the format for error messages. If None, uses function name.

        Returns
        -------
        Any
            The result of calling from_format_fn.

        Raises
        ------
        ValueError
            If decoding or parsing fails.

        Examples
        --------
        >>> def deserialize(self, data: bytes) -> Any:
        ...     from adaptexts.context import Context
        ...     return self._safe_from_format(
        ...         Context.from_burmeister, data, format_name="Burmeister"
        ...     )
        """
        text = self._decode_text(data)

        if format_name is None:
            # Use type: ignore[union-attr] because bound methods should have __name__
            format_name = from_format_fn.__name__.replace("from_", "").capitalize()  # type: ignore[union-attr]

        try:
            return from_format_fn(text)
        except Exception as e:
            raise ValueError(f"Failed to parse {format_name} format: {e}") from e


__all__ = ["SerializationStrategy", "ContextSerializer"]
