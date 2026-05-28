"""Context-specific serialization strategies.

This module provides serialization strategies that delegate to Context
and ManyValuedContext class methods. Each strategy is strict and will
not fall back to pickle for unsupported types.
"""

from typing import TYPE_CHECKING, Any

import pandas as pd

from adaptexts.base.cache.serializers.base import ContextSerializer

# TYPE_CHECKING import is kept for type checkers, but we use lazy imports
# at runtime to avoid circular import issues.
if TYPE_CHECKING:
    pass


class BurmeisterStrategy(ContextSerializer):
    """Burmeister format serialization strategy for Context objects.

    Delegates to Context.to_burmeister() and Context.from_burmeister().

    Raises
    ------
    TypeError
        If value is not a Context instance.
    ValueError
        If deserialization fails (invalid Burmeister format).
    """

    file_ending = "ctx"

    def serialize(self, value: Any) -> bytes:
        """Serialize Context to Burmeister format.

        Parameters
        ----------
        value : Context
            The context to serialize.

        Returns
        -------
        bytes
            Burmeister-formatted context data.

        Raises
        ------
        TypeError
            If value is not a Context.
        """
        self._validate_context(value, context_only=True)
        return value.to_burmeister().encode("utf-8")

    def deserialize(self, data: bytes) -> Any:
        """Deserialize Burmeister format to Context.

        Parameters
        ----------
        data : bytes
            Burmeister-formatted context data.

        Returns
        -------
        Context
            Deserialized context object.

        Raises
        ------
        ValueError
            If data cannot be decoded or parsed as Burmeister format.
        """
        from adaptexts.context import Context

        return self._safe_from_format(
            Context.from_burmeister, data, format_name="Burmeister"
        )


class ColibriStrategy(ContextSerializer):
    """Colibri format serialization strategy for Context objects.

    Delegates to Context.to_colibri() and Context.from_colibri().

    Raises
    ------
    TypeError
        If value is not a Context instance.
    ValueError
        If deserialization fails.
    """

    file_ending = "colibri"

    def serialize(self, value: Any) -> bytes:
        """Serialize Context to Colibri format.

        Parameters
        ----------
        value : Context
            The context to serialize.

        Returns
        -------
        bytes
            Colibri-formatted context data.

        Raises
        ------
        TypeError
            If value is not a Context.
        """
        self._validate_context(value, context_only=True)
        return value.to_colibri().encode("utf-8")

    def deserialize(self, data: bytes) -> Any:
        """Deserialize Colibri format to Context.

        Parameters
        ----------
        data : bytes
            Colibri-formatted context data.

        Returns
        -------
        Context
            Deserialized context object.

        Raises
        ------
        ValueError
            If data cannot be decoded or parsed as Colibri format.
        """
        from adaptexts.context import Context

        return self._safe_from_format(Context.from_colibri, data, format_name="Colibri")


class CSVStrategy(ContextSerializer):
    """CSV format serialization strategy for Context and ManyValuedContext objects.

    Delegates to Context/ManyValuedContext.to_df() and from_df().

    Returns
    -------
    Context or ManyValuedContext
        Deserialization attempts Context first (binary values),
        falls back to ManyValuedContext if binary check fails.

    Raises
    ------
    TypeError
        If value is not Context or ManyValuedContext.
    ValueError
        If deserialization fails.
    """

    file_ending = "csv"

    def serialize(self, value: Any) -> bytes:
        """Serialize Context or ManyValuedContext to CSV.

        Parameters
        ----------
        value : Context or ManyValuedContext
            The context to serialize.

        Returns
        -------
        bytes
            CSV-encoded context data.

        Raises
        ------
        TypeError
            If value is not Context or ManyValuedContext.
        """
        import io

        self._validate_context(value, context_only=False)
        df = value.to_df()
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer)
        return csv_buffer.getvalue().encode("utf-8")

    def deserialize(self, data: bytes) -> Any:
        """Deserialize CSV to Context or ManyValuedContext.

        Parameters
        ----------
        data : bytes
            CSV-encoded context data.

        Returns
        -------
        Context or ManyValuedContext
            Deserialized context object.

        Raises
        ------
        ValueError
            If data cannot be decoded or parsed as CSV.
        """
        import io

        import pandas as pd

        from adaptexts.context import Context
        from adaptexts.many_valued_context import ManyValuedContext

        text = self._decode_text(data)

        try:
            df = pd.read_csv(io.StringIO(text), index_col=0)

            if self._is_binary_dataframe(df):
                return Context.from_df(df)

            return ManyValuedContext.from_df(df)
        except Exception as e:
            raise ValueError(f"Failed to parse CSV: {e}") from e

    @staticmethod
    def _is_binary_dataframe(df: pd.DataFrame) -> bool:
        """Check if DataFrame contains only binary values (0/1).

        Parameters
        ----------
        df : pd.DataFrame
            The DataFrame to check.

        Returns
        -------
        bool
            True if DataFrame contains only 0 and 1 values.
        """
        unique_values = set(df.values.flatten())
        return unique_values <= {0, 1}


class JSONContextStrategy(ContextSerializer):
    """JSON format serialization strategy for Context and ManyValuedContext objects.

    Delegates to Context/ManyValuedContext.to_json() and from_json() methods
    for consistency with other serializers.

    Raises
    ------
    TypeError
        If value is not Context or ManyValuedContext.
    ValueError
        If serialization/deserialization fails.
    """

    def serialize(self, value: Any) -> bytes:
        """Serialize Context or ManyValuedContext to JSON.

        Parameters
        ----------
        value : Context or ManyValuedContext
            The context to serialize.

        Returns
        -------
        bytes
            JSON-encoded context data.

        Raises
        ------
        TypeError
            If value is not a Context or ManyValuedContext.

        Notes
        -----
        Delegates to the context's to_json() method, then encodes to UTF-8 bytes.
        """
        self._validate_context(value, context_only=False)
        return value.to_json().encode("utf-8")

    def deserialize(self, data: bytes) -> Any:
        """Deserialize JSON to Context or ManyValuedContext.

        Parameters
        ----------
        data : bytes
            JSON-encoded context data.

        Returns
        -------
        Context or ManyValuedContext
            Deserialized context object.

        Raises
        ------
        UnicodeDecodeError
            If bytes cannot be decoded as UTF-8.
        ValueError
            If JSON is invalid or has wrong type field.
        Exception
            If context construction fails.

        Notes
        -----
        Decodes bytes to UTF-8 text, then uses the context's from_json() method.
        """
        text = self._decode_text(data)

        context_type = self._get_json_type_from_string(text)

        if context_type == "Context":
            from adaptexts.context import Context

            return Context.from_json(text)
        elif context_type == "ManyValuedContext":
            from adaptexts.many_valued_context import ManyValuedContext

            return ManyValuedContext.from_json(text)
        else:
            raise ValueError(f"Unknown context type in JSON: {context_type}")

    @staticmethod
    def _get_json_type_from_string(text: str) -> str:
        """Extract the type field from JSON text.

        Parameters
        ----------
        text : str
            JSON-formatted string.

        Returns
        -------
        str
            The value of the "type" field.

        Raises
        ------
        ValueError
            If JSON is invalid or missing type field.
        """
        import json

        try:
            json_data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON: {e}") from e

        context_type = json_data.get("type")
        if context_type is None:
            raise ValueError("JSON missing required 'type' field")

        return context_type


class FIMIContextStrategy(ContextSerializer):
    """FIMI format serialization strategy for Context objects.

    Delegates to Context.to_fimi() and Context.from_fimi() methods
    which are provided by the FIMIFormatMixin.

    The FIMI format is a standard in frequent itemset mining and
    formal concept analysis for representing transaction-like data.

    Examples
    --------
    >>> ctx = Context(["obj1", "obj2"], ["1", "2"], [("obj1", "1")])
    >>> strategy = FIMIContextStrategy()
    >>> data = strategy.serialize(ctx)  # b'obj1 1\\nobj2\\n'

    Raises
    ------
    TypeError
        If value is not a Context instance.
    ValueError
        If serialization/deserialization fails.

    References
    ----------
    http://fimi.ua.ac.be/data/
    """

    def serialize(self, value: Any) -> bytes:
        """Serialize Context to FIMI format.

        Parameters
        ----------
        value : Context
            The context to serialize.

        Returns
        -------
        bytes
            FIMI-formatted context data.

        Raises
        ------
        TypeError
            If value is not a Context.

        Notes
        -----
        Delegates to the context's to_fimi() method provided by
        the FIMIFormatMixin, then encodes to UTF-8 bytes.
        """
        self._validate_context(value, context_only=True)
        return value.to_fimi().encode("utf-8")

    def deserialize(self, data: bytes) -> Any:
        """Deserialize FIMI format to Context.

        Parameters
        ----------
        data : bytes
            FIMI-formatted context data.

        Returns
        -------
        Context
            Deserialized context object.

        Raises
        ------
        ValueError
            If data cannot be decoded or parsed as FIMI format.

        Notes
        -----
        Decodes bytes to UTF-8 text, then delegates to Context.from_fimi() method
        provided by the FIMIFormatMixin.
        """
        from adaptexts.context import Context

        text = self._decode_text(data)
        return Context.from_fimi(text)
