from typing import Set, Tuple, Type, TypeVar

from adaptexts.base.utils import tokenize

from .base_mixin import BaseMixin

T = TypeVar("T", bound="DataTableFormatMixin")


class DataTableFormatMixin(BaseMixin):
    """Mixin for data table format serialization.

    Data table format represents contexts as ASCII tables:

        |[a] [b]
        ---+---
        x  |x .
        y  |. x

    Valid incidence is marked by a configurable marker (default 'x').
    """

    # ========== PUBLIC API ==========

    @classmethod
    def from_data_table(
        cls: Type[T],
        table_str: str,
        positive: str = "x",
    ) -> T:
        """Construct a context from a data table format.

        Example format:
                    |[>= large] [<= small] [>= very-large]
        -----------+--------------------------------------
        large      |x          .          .
        small      |.          x          .
        very-large |x          .          x

        Parameters
        ----------
        table_str : str
            String representation of a data table where 'positive' marks
            positive incidence.
        positive : str, optional
            Character marking positive incidence. Default is "x".

        Returns
        -------
        Context
            Constructed formal context.

        Raises
        ------
        ContextFormatError
            If the input does not conform to the data table format.

        """
        components = cls._parse_data_table(table_str, positive)
        return cls._from_components(**components)

    def to_data_table(self, positive: str = "x", negative: str = ".") -> str:
        """Serialize the context to data table format.

        Parameters
        ----------
        positive : str, optional
            Character for positive incidence. Default is "x".
        negative : str, optional
            Character for absence. Default is ".".

        Returns
        -------
        str
            Data table formatted string.

        Examples
        --------
        >>> ctx.to_data_table()
        '|[a] [b]\\n---+---\\nx  |x .\\ny  |. x'

        """
        return self._build_data_table(positive, negative)

    # ========== PROTECTED: PARSING ==========

    @classmethod
    def _parse_data_table(cls, table_str: str, positive: str) -> dict:
        """Parse data table format string into components.

        This protected method can be overridden to extend parsing
        (e.g., for missing value handling like '?' or 'n/a').

        Parameters
        ----------
        table_str : str
            Data table formatted string.
        positive : str
            Character marking positive incidence.

        Returns
        -------
        dict
            Dictionary with keys: g, m, i

        """
        lines = [line.strip() for line in table_str.splitlines() if table_str.strip()]

        _, header = lines[0].split("|", 1)
        attributes = tokenize(header)

        objects: list[str] = []
        incidence: Set[Tuple[str, str]] = set()

        for line in lines[2:]:
            obj, rest = line.split("|", 1)
            obj = obj.strip()
            objects.append(obj)

            values = tokenize(rest)
            for m, v in zip(attributes, values):
                if v == positive:
                    incidence.add((obj, m))

        return {
            "G": objects,
            "M": attributes,
            "I": incidence,
        }

    # ========== PROTECTED: BUILDING ==========

    def _build_data_table(self, positive: str, negative: str) -> str:
        """Build data table format string from context state.

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
            Data table formatted string.

        """
        # Build header with attributes
        header_attrs = " ".join(self._sorted_attributes)
        lines = [f"|{header_attrs}"]

        # Build separator line
        max_obj_len = max(
            (len(str(obj_name)) for obj_name in self._sorted_objects), default=0
        )
        separator = "-" * max_obj_len
        lines.append(f"{separator}+")

        # Build data rows
        for g in self._sorted_objects:
            row_vals = [
                positive if (g, m) in self.I else negative
                for m in self._sorted_attributes
            ]
            row_str = " ".join(row_vals)
            lines.append(f"{g}|{row_str}")

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
