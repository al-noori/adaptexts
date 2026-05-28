from typing import Set, Tuple, Type, TypeVar

from .base_mixin import BaseMixin

T = TypeVar("T", bound="ColibriFormatMixin")


class ColibriFormatMixin(BaseMixin):
    """Mixin for Colibri format serialization.

    Colibri format represents each object followed by its attributes
    in the form:

        object: attr1,attr2,...

    """

    # ========== PUBLIC API ==========

    @classmethod
    def from_colibri(
        cls: Type[T],
        string: str,
    ) -> T:
        """Parse a context from Colibri format.

        Parameters
        ----------
        string : str
            Colibri-formatted string.

        Returns
        -------
        Context
            Parsed formal context.

        Raises
        ------
        ContextFormatError
            If the input does not conform to the Colibri format.

        """
        components = cls._parse_colibri(string)
        return cls._from_components(**components)

    def to_colibri(self) -> str:
        """Serialize the context to Colibri format.

        Returns
        -------
        str
            Colibri-formatted string.

        """
        return self._build_colibri()

    # ========== PROTECTED: PARSING ==========

    @classmethod
    def _parse_colibri(cls, string: str) -> dict:
        """Parse Colibri format string into components.

        This protected method can be overridden to extend parsing
        (e.g., for attribute weights or metadata).

        Parameters
        ----------
        string : str
            Colibri-formatted string.

        Returns
        -------
        dict
            Dictionary with keys: g, m, i

        """
        objects: Set[str] = set()
        attributes: Set[str] = set()
        incidence: Set[Tuple[str, str]] = set()

        for line in string.strip().splitlines():
            if not line.strip():
                continue

            g_part, m_part = line.rsplit(":", 1)
            g = g_part.strip()
            objects.add(g)

            for m in (a.strip() for a in m_part.split(",") if a.strip()):
                attributes.add(m)
                incidence.add((g, m))

        return {
            "G": objects,
            "M": attributes,
            "I": incidence,
        }

    # ========== PROTECTED: BUILDING ==========

    def _build_colibri(self) -> str:
        """Build Colibri format string from context state.

        This protected method can be overridden to customize output
        (e.g., include attribute weights or metadata).

        Returns
        -------
        str
            Colibri-formatted string.

        """
        lines = []
        for g in self._sorted_objects:
            attrs = [m for m in self._sorted_attributes if (g, m) in self.I]
            attrs_str = ",".join(attrs)
            lines.append(f"{g}: {attrs_str}")
        return "\n".join(lines)

    # ========== PROTECTED: CONSTRUCTION ==========

    @classmethod
    def _from_components(
        cls: Type[T],
        G,
        M,
        I,  # noqa: E741
        **kwargs,
    ) -> T:
        """Construct context instance from parsed components.

        This protected method can be overridden in subclasses to
        customize construction logic.

        Parameters
        ----------
        G : iterable
            Objects.
        M : iterable
            Attributes.
        I : iterable
            Incidence relation.
        **kwargs
            Additional subclass-specific parameters.

        Returns
        -------
        T
            Constructed context instance.

        """
        return cls(G, M, I, **kwargs)
