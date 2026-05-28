from typing import Type, TypeVar

from .base_mixin import BaseMixin

T = TypeVar("T", bound="FIMIFormatMixin")


class FIMIFormatMixin(BaseMixin):
    """Mixin for FIMI format serialization.

    FIMI format is a standard transaction/itemset format used in
    frequent itemset mining and formal concept analysis:
        obj1 attr1 attr2
        obj2 attr1
        obj3

    Lines starting with # are treated as comments.
    """

    # ========== PUBLIC API ==========

    @classmethod
    def from_fimi(cls: Type[T], string: str, comment: str = "") -> T:
        """Parse a context from FIMI format.

        Parameters
        ----------
        string : str
            FIMI-formatted string.
        comment : str, optional
            Optional comment to include in output. Ignored during parsing.

        Returns
        -------
        T
            Constructed context instance.

        Raises
        ------
        ValueError
            If parsing fails or data is empty.

        """
        components = cls._parse_fimi(string)
        return cls._from_components(**components)

    def to_fimi(self, comment: str = "") -> str:
        """Serialize the context to FIMI format.

        Parameters
        ----------
        comment : str, optional
            Optional comment to include as header line.

        Returns
        -------
        str
            FIMI-formatted string.

        """
        return self._build_fimi(comment)

    # ========== PROTECTED: PARSING ==========

    @classmethod
    def _parse_fimi(cls, string: str) -> dict:
        """Parse FIMI format string into components.

        This protected method can be overridden to extend parsing
        (e.g., for weight values or additional metadata).

        Parameters
        ----------
        string : str
            FIMI-formatted string.

        Returns
        -------
        dict
            Dictionary with keys: g, m, i

        Raises
        ------
        ValueError
            If parsing fails or data is empty.

        """
        # Remove comments and empty lines
        lines = [
            line.strip()
            for line in string.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        # Empty context is valid - return empty sets
        if not lines:
            return {
                "G": set(),
                "M": set(),
                "I": set(),
            }

        objects, attributes, incidence = cls._parse_fimi_lines(lines)

        return {
            "G": objects,
            "M": attributes,
            "I": incidence,
        }

    @classmethod
    def _parse_fimi_lines(
        cls, lines: list[str]
    ) -> tuple[set[str], set[str], set[tuple[str, str]]]:
        """Parse FIMI format lines into components.

        This protected method handles the core line-by-line parsing
        and can be overridden for custom extensions.

        Parameters
        ----------
        lines : list[str]
            List of non-empty, non-comment lines.

        Returns
        -------
        tuple[set[str], set[str], set[tuple[str, str]]]
            Objects, attributes, and incidence relation.

        """
        objects: set[str] = set()
        attributes: set[str] = set()
        incidence: set[tuple[str, str]] = set()

        for line in lines:
            parts = line.split()
            if not parts:
                continue

            g = parts[0]
            objects.add(g)

            # Multiple items in this transaction/object
            for m in parts[1:]:
                attributes.add(m)
                incidence.add((g, m))

        return objects, attributes, incidence

    # ========== PROTECTED: BUILDING ==========

    def _build_fimi(self, comment: str = "") -> str:
        """Build FIMI format string from context state.

        This protected method can be overridden to customize output
        (e.g., include weights or additional metadata).

        Parameters
        ----------
        comment : str, optional
            Optional comment to include as header line.

        Returns
        -------
        str
            FIMI-formatted string with trailing newline.

        """
        lines = self._build_fimi_lines()

        if comment:
            header = f"# {comment}"
            lines = [header] + lines

        fimi_str = "\n".join(map(str, list(lines)))
        if fimi_str:  # Ensure trailing newline for standards compliance
            fimi_str += "\n"

        return fimi_str

    def _build_fimi_lines(self) -> list[str]:
        """Build FIMI format lines from context state.

        This protected method handles the core line building
        and can be overridden for custom extensions.

        Returns
        -------
        list[str]
            List of FIMI format lines.

        """
        lines = []

        for g in self._sorted_objects:
            items = [str(m) for m in self._sorted_attributes if (g, m) in self.I]
            if items:
                lines.append(f"{g} {' '.join(items)}")
            else:
                lines.append(str(g))

        return lines

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
