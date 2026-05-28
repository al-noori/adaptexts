from typing import Type, TypeVar

import pandas as pd

from pandas import DataFrame

from .base_mixin import BaseMixin

T = TypeVar("T", bound="DataFrameFormatMixin")


class DataFrameFormatMixin(BaseMixin):
    """Mixin for pandas DataFrame format serialization.

    This mixin provides conversion between formal contexts and
    pandas DataFrames, useful for data analysis and visualization.
    """

    # ========== PUBLIC API ==========

    def to_df(self) -> DataFrame:
        """Convert the context to a pandas DataFrame.

        The DataFrame represents the incidence relation as a binary matrix
        with objects as rows and attributes as columns.

        Returns
        -------
        pandas.DataFrame
            Binary incidence matrix (0/1) with sorted objects and attributes.

        """
        return self._build_dataframe()

    @classmethod
    def from_df(
        cls: Type[T],
        df: DataFrame,
        name: str = "",
    ) -> T:
        """Construct a context from a pandas DataFrame.

        Non-zero entries are interpreted as positive incidence.

        Parameters
        ----------
        df : pandas.DataFrame
            Binary incidence matrix with objects as index and attributes as columns.
        name : str, optional
            Optional context name.

        Returns
        -------
        Context
            Constructed formal context.

        Examples
        --------
        >>> import pandas as pd
        >>> df = pd.DataFrame([[1, 0], [0, 1]], columns=['a', 'b'])
        >>> ctx = Context.from_df(df, name="example")
        >>> ctx.name
        'example'
        >>> list(ctx.G)
        [0, 1]
        >>> list(ctx.M)
        ['a', 'b']
        >>> set(ctx.I)
        {(0, 'a'), (1, 'b')}

        """
        components = cls._parse_dataframe(df, name)
        return cls._from_components(**components)

    # ========== PROTECTED: PARSING ==========

    @classmethod
    def _parse_dataframe(cls, df: DataFrame, name: str) -> dict:
        """Parse DataFrame into context components.

        This protected method can be overridden to extend parsing
        (e.g., for handling NaN as missing values or many-valued data).

        Parameters
        ----------
        df : pandas.DataFrame
            DataFrame to parse.
        name : str
            Context name.

        Returns
        -------
        dict
            Dictionary with keys: g, m, i, name

        """
        g = set(df.index)
        m = set(df.columns)

        incidence = {(_g, _m) for _g in g for _m in m if df.loc[_g, _m]}

        return {
            "G": g,
            "M": m,
            "I": incidence,
            "name": name,
        }

    # ========== PROTECTED: BUILDING ==========

    def _build_dataframe(self) -> DataFrame:
        """Build DataFrame from context state.

        This protected method can be overridden to customize output
        (e.g., for many-valued contexts with actual values instead of binary).

        Returns
        -------
        pandas.DataFrame
            Binary incidence matrix (0/1) with sorted objects and attributes.

        """
        matrix = [
            [
                1 if (g, m) in self._sorted_incidence else 0
                for m in self._sorted_attributes
            ]
            for g in self._sorted_objects
        ]

        return pd.DataFrame(
            matrix, index=self._sorted_objects, columns=self._sorted_attributes
        )

    # ========== PROTECTED: CONSTRUCTION ==========

    @classmethod
    def _from_components(cls: Type[T], **kwargs) -> T:
        """Construct context instance from parsed components.

        This protected method can be overridden in subclasses to
        customize construction logic.

        Parameters
        ----------
        **kwargs

        Returns
        -------
        T
            Constructed context instance.

        """
        return cls(**kwargs)
