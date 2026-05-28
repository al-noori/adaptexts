import json

from typing import Type, TypeVar

from .base_mixin import BaseMixin

T = TypeVar("T", bound="JSONFormatMixin")


class JSONFormatMixin(BaseMixin):
    """Mixin for JSON format serialization.

    This mixin provides JSON serialization with type-driven dispatch.
    Subclasses must implement _get_json_type() and related methods.
    """

    # ========== PUBLIC API ==========

    def to_json(self, indent: int = 2) -> str:
        """Serialize the context to JSON format.

        Parameters
        ----------
        indent : int, optional
            JSON indentation level. Default is 2.

        Returns
        -------
        str
            JSON-formatted string.

        """
        return self._build_json(indent)

    @classmethod
    def from_json(cls: Type[T], string: str) -> T:
        """Parse a context from JSON format.

        Parameters
        ----------
        string : str
            JSON-formatted string.

        Returns
        -------
        T
            Constructed context instance.

        Raises
        ------
        ValueError
            If JSON is invalid or has wrong type field.

        """
        # _parse_json validates and returns the parsed JSON dict wrapped in a dict
        components = cls._parse_json(string)
        json_data = components["json_data"]
        return cls._construct_from_json_data(json_data)

    # ========== PROTECTED: PARSING ==========

    @classmethod
    def _parse_json(cls, string: str) -> dict:
        """Parse JSON format string into components.

        This protected method validates JSON structure and type,
        then delegates to _build_json_data() for actual parsing.

        Parameters
        ----------
        string : str
            JSON-formatted string.

        Returns
        -------
        dict
            Dictionary with parsed JSON data and any additional components.

        Raises
        ------
        ValueError
            If JSON is invalid or type doesn't match.

        """
        try:
            json_data = json.loads(string)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON: {e}") from e

        # Validate type field
        expected_type = cls._get_expected_json_type()
        actual_type = json_data.get("type")

        if actual_type != expected_type:
            raise ValueError(f"Expected type '{expected_type}', got '{actual_type}'")

        return {"json_data": json_data}

    # ========== PROTECTED: BUILDING ==========

    def _build_json(self, indent: int = 2) -> str:
        """Build JSON format string from context state.

        This protected method delegates to _construct_json_data()
        for the actual data structure.

        Parameters
        ----------
        indent : int
            JSON indentation level.

        Returns
        -------
        str
            JSON-formatted string.

        """
        data = self._construct_json_data()
        return json.dumps(data, indent=indent)

    # ========== PROTECTED: CONSTRUCTION ==========

    @classmethod
    def _from_components(
        cls: Type[T],
        json_data: dict,
        **kwargs,
    ) -> T:
        """Construct context instance from parsed JSON data.

        This protected method can be overridden in subclasses to
        customize construction logic.

        Parameters
        ----------
        json_data : dict
            Parsed JSON data.
        **kwargs
            Additional subclass-specific parameters.

        Returns
        -------
        T
            Constructed context instance.

        """
        return cls._construct_from_json_data(json_data)

    # ========== ABSTRACT: SUBCLASS MUST IMPLEMENT ==========

    def _get_json_type(self) -> str:
        """Get the type identifier for JSON serialization.

        Returns
        -------
        str
            Type string (e.g., "Context", "ManyValuedContext").

        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _get_json_type()"
        )

    def _construct_json_data(self) -> dict:
        """Construct JSON data from context state.

        Returns
        -------
        dict
            JSON-serializable dictionary representation.

        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _construct_json_data()"
        )

    @classmethod
    def _get_expected_json_type(cls) -> str:
        """Get expected type identifier for JSON deserialization.

        Returns
        -------
        str
            Expected type string.

        """
        raise NotImplementedError(
            f"{cls.__name__} must implement _get_expected_json_type()"
        )

    @classmethod
    def _construct_from_json_data(cls: Type[T], json_data: dict) -> T:
        """Construct context instance from JSON data.

        Parameters
        ----------
        json_data : dict
            Parsed JSON data.

        Returns
        -------
        T
            Constructed context instance.

        """
        raise NotImplementedError(
            f"{cls.__name__} must implement _construct_from_json_data()"
        )
