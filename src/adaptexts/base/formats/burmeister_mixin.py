from typing import Set, Tuple, Type, TypeVar

from adaptexts.exceptions import ContextFormatError

from .base_mixin import BaseMixin

T = TypeVar("T", bound="BurmeisterFormatMixin")


class BurmeisterFormatMixin(BaseMixin):
    """Mixin for Burmeister (.cxt) format serialization.

    Burmeister format is a standard formal context representation with:
    - Header line with "B"
    - Context name
    - Number of objects and attributes
    - Object names
    - Attribute names
    - Binary incidence matrix

    """

    # ========== PUBLIC API ==========

    @classmethod
    def from_burmeister(
        cls: Type[T],
        string: str,
        positive: str = "X",
        negative: str = ".",
    ) -> T:
        """Parse a context from Burmeister format.

        Parameters
        ----------
        string : str
            Burmeister-formatted string.
        positive : str, optional
            Character indicating positive incidence. Default is "X".
        negative : str, optional
            Character indicating absence. Default is ".".

        Returns
        -------
        T
            Constructed context instance.

        Raises
        ------
        ContextFormatError
            If the input does not conform to Burmeister format.

        """
        components = cls._parse_burmeister(string, positive, negative)
        return cls._from_components(**components)

    def to_burmeister(self, positive: str = "X", negative: str = ".") -> str:
        """Serialize the context to Burmeister format.

        Parameters
        ----------
        positive : str, optional
            Character for positive incidence. Default is "X".
        negative : str, optional
            Character for absence. Default is ".".

        Returns
        -------
        str
            Burmeister-formatted string.

        """
        return self._build_burmeister(positive, negative)

    # ========== PROTECTED: PARSING ==========

    @classmethod
    def _parse_burmeister(
        cls,
        string: str,
        positive: str,
        negative: str,
    ) -> dict:
        """Parse Burmeister format string into components.

        This protected method can be overridden to extend parsing
        (e.g., for missing value handling).

        Parameters
        ----------
        string : str
            Burmeister-formatted string.
        positive : str
            Character for positive incidence.
        negative : str
            Character for absence.

        Returns
        -------
        dict
            Dictionary with keys: name, g, m, i

        Raises
        ------
        ContextFormatError
            If parsing fails.

        """
        lines = [line.strip() for line in string.splitlines()]

        if not lines or lines[0] != "B":
            raise ContextFormatError("Invalid Burmeister format: must start with 'B'")

        name = lines[1]
        n_objects = int(lines[2])
        n_attributes = int(lines[3])

        objects = list(lines[5 : 5 + n_objects])
        attrs_start = 5 + n_objects
        attributes = list(lines[attrs_start : attrs_start + n_attributes])

        rel_start = attrs_start + n_attributes
        matrix_lines = lines[rel_start : rel_start + n_objects]

        if len(matrix_lines) != n_objects:
            raise ContextFormatError(
                "Number of relation lines does not match number of objects"
            )

        incidence: Set[Tuple[str, str]] = set()
        for g, row in zip(objects, matrix_lines):
            for m, val in zip(attributes, row):
                # Check case-insensitively for positive match
                if val.lower() in positive.lower():
                    incidence.add((g, m))
                elif val.lower() not in negative.lower():
                    raise ContextFormatError(
                        f"Invalid character '{val}' in relation matrix"
                    )

        return {
            "name": name,
            "G": objects,
            "M": attributes,
            "I": incidence,
        }

    # ========== PROTECTED: BUILDING ==========

    def _build_burmeister(self, positive: str, negative: str) -> str:
        """Build Burmeister format string from context state.

        This protected method can be overridden to customize output
        (e.g., for extended formats with missing values).

        Parameters
        ----------
        positive : str
            Character for positive incidence.
        negative : str
            Character for absence.

        Returns
        -------
        str
            Burmeister-formatted string.

        """
        lines = ["B", self.name, str(len(self.G)), str(len(self.M)), ""]
        lines.extend(self.G)
        lines.extend(self.M)

        for g in self.G:
            row = [positive if (g, m) in self.I else negative for m in self.M]
            lines.append("".join(row))

        return "\n".join(map(str, lines))

    # ========== PROTECTED: CONSTRUCTION ==========

    @classmethod
    def _from_components(
        cls: Type[T],
        G,
        M,
        I,  # noqa: E741
        name: str | None = None,
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
        name : str, optional
            Context name.
        **kwargs
            Additional subclass-specific parameters.

        Returns
        -------
        T
            Constructed context instance.

        """
        return cls(G, M, I, name=name, **kwargs)
