"""Mixin for conexp-clj-py serialization.

This module provides the ConexpFormatMixin class which handles conversion
between adaptexts contexts and conexp-clj-py context representations.

The mixin uses a template method pattern with placeholder methods that
subclasses can override to customize behavior.
"""

from typing import Any, Type, TypeVar


from .base_mixin import BaseMixin

T = TypeVar("T", bound="ConexpFormatMixin")


class ConexpFormatMixin(BaseMixin):
    """Mixin for conexp-clj-py serialization.

    Provides default implementations for binary Context (G, M, I where I⊆G×M).
    Specialized owners have to overrides placeholder methods.

    Notes
    -----
    Should not be used as serializer for caching.

    """

    # ========== PUBLIC API ==========

    def to_conexp(self):
        """Convert context to appropriate conexp-clj-py context.

        Returns
        -------
        ConexpContext
            If called on binary Context.
        """
        return self._build_conexp_context()

    @classmethod
    def from_conexp(cls: Type[T], obj, name="") -> T:
        """Create context from conexp-clj-py context.

        Parameters
        ----------
        obj :
            Conexp-clj-py context to convert from.

        Returns
        -------
        T
            Constructed context instance.

        Raises
        ------
        TypeError
            If obj is not a recognized conexp type.

        """
        return cls._parse_conexp_context(obj, name=name)

    # ========== PROTECTED: PLACEHOLDER METHODS ==========

    def _get_conexp_class(self) -> type:
        raise NotImplementedError()

    def _get_conexp_objects(self) -> list[str]:
        """Get objects in conexp format.

        Default implementation converts all objects to strings.
        Subclasses can override for custom formatting.

        Returns
        -------
        list[str]
            List of object identifiers as strings.

        """
        return sorted(self.G)

    def _get_conexp_attributes(self) -> list[str]:
        """Get attributes in conexp format.

        Default implementation converts all attributes to strings.
        Subclasses can override for custom formatting.

        Returns
        -------
        list[str]
            List of attribute identifiers as strings.

        """
        return sorted(self.M)

    def _get_conexp_incidence(self):
        """Get incidence in appropriate conexp format.

        Default implementation returns list of (object, attribute) tuples
        for binary contexts.

        ManyValuedContext should override to return dict mapping
        "[object, attribute]" -> value.

        Returns
        -------
        list[tuple[str, str]]
            List of (object, attribute) tuples for binary contexts.
        dict[str, Any]
            Dict mapping "[object, attribute]" -> value for many-valued contexts.

        """
        raise NotImplementedError()

    def _build_conexp_context(self) -> T:
        """Build conexp context from components.

        Uses placeholder methods to get components, then constructs
        the appropriate conexp-clj-py context object.

        Parameters
        ----------
        conexp_class : type
            Either ConexpContext or ConexpManyValuedContext class.

        Returns
        -------
        ConexpContext | ConexpManyValuedContext
            Constructed conexp context.

        """
        objects = self._get_conexp_objects()
        attributes = self._get_conexp_attributes()
        incidence = self._get_conexp_incidence()

        return self._get_conexp_class()(
            objects=objects,
            attributes=attributes,
            incidence=incidence,
        )

    # ========== PROTECTED: FROM CONEXP HELPERS ==========

    @staticmethod
    def _parse_conexp_objects(obj: Any):
        return obj.objects

    @staticmethod
    def _parse_conexp_attributes(obj: Any):
        return obj.attributes

    @staticmethod
    def _parse_conexp_incidence(obj: Any):
        raise NotImplementedError()

    @classmethod
    def _parse_conexp_context(cls: Type[T], obj: Any, name="") -> T:
        """Create binary Context from ConexpContext.

        This is the default implementation for binary contexts.
        Subclasses can override if needed.

        Parameters
        ----------
        obj : Any
            A Conexp-clj-py context.

        Returns
        -------
        T
            Constructed context instance.

        """
        objects = cls._parse_conexp_objects(obj)
        attributes = cls._parse_conexp_attributes(obj)
        incidence = cls._parse_conexp_incidence(obj)
        return cls(objects, attributes, incidence, name=name)
