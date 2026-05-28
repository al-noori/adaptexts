"""Many-valued formal context abstraction.

This module defines the ManyValuedContext class, representing a
many-valued formal context in the sense of Formal Concept Analysis (FCA).

A many-valued context is a quadruple (G, M, W, I), where:
- G is a set of objects,
- M is a set of attributes,
- W is a set of attribute values,
- I ⊆ G × M × W is a ternary incidence relation.
"""

from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
)

import numpy as np
import pandas as pd

from conexp_clj_py.models import ConexpManyValuedContext

from .base.formats import FormatMixin
from .base.utils import truncated_repr

if TYPE_CHECKING:
    from .context import Context
    from .tools.scaling.tool import ScalingTool

# Generic type variables
G = TypeVar("G")
M = TypeVar("M")
W = TypeVar("W")

ManyValuedIncidence = Iterable[Tuple[G, M, W]]


@dataclass
class ManyValuedContext(FormatMixin):
    G: Iterable
    M: Iterable
    W: Iterable
    I: ManyValuedIncidence  # noqa: E741
    name: str | None = None

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return truncated_repr(self)

    def values_of_attribute(self, m: M) -> list[W]:
        """Return all values associated with a given attribute.

        Parameters
        ----------
        m : attribute
            Attribute whose values are requested.

        Returns
        -------
        list
            Sorted list of values associated with the attribute.

        """
        vals = {val for obj, attr, val in self.I if attr == m}
        return sorted(vals)

    def scale(
        self,
        scale_map: dict[str, dict[str, Any]] | None = None,
        scaling_tool: Optional["ScalingTool"] = None,
        **kwargs,
    ) -> "Context":
        """Scale the many-valued context into a binary formal context.

        Parameters
        ----------
        scale_map : dict, optional
            Mapping from attribute names to scale specifications.

            Example
            -------
            {
                "att_1": {"name": "interordinal-scale"},
                "att_2": {"name": "ordinal-scale"},
                "att_3": {"name": "interordinal-scale", "thresholds": [3, 6, 8]},
                "att_4": {"name": "biordinal-scale", "n": 4},
            }

        scaling_tool : ScalingTool, optional
            ScalingTool instance to use. If None, creates a default tool.

        kwargs : dict, optional
            Used for tool creation. Not allowed when tool is passed.

        Returns
        -------
        Context
            Binary formal context obtained by scaling.

        Raises
        ------
        ScaleError
            If the scale name is invalid or the scale parameters are incorrect.

        Examples
        --------
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     'color': ['red', 'blue', 'green'],
        ...     'size': [3, 6, 9]
        ... })
        >>> mv_ctx = ManyValuedContext.from_df(df, "example")
        >>> scale_map = {
        ...     'color': {'name': 'nominal-scale'},
        ...     'size': {'name': 'ordinal-scale'}
        ... }
        >>> binary_ctx = mv_ctx.scale(scale_map)
        >>> isinstance(binary_ctx, Context)
        True
        """
        if scaling_tool is None:
            from .tools.scaling import ScalingTool

            with ScalingTool(**kwargs) as scaling_tool:
                return scaling_tool.scale(self, scale_map=scale_map)
        assert len(kwargs) == 0, ""
        return scaling_tool.scale(self, scale_map=scale_map)

    def automatic_scale(
        self, scaling_tool: Optional["ScalingTool"] = None, **kwargs
    ) -> "Context":
        """Automatically scale the many-valued context."""
        return self.scale(scaling_tool=scaling_tool, **kwargs)

    # ========== CONEXP FORMAT MIXIN IMPLEMENTATION ==========

    def _get_conexp_class(self):
        return ConexpManyValuedContext

    def _get_conexp_incidence(self) -> dict:
        """Get incidence in conexp many-valued format.

        Overrides default to return dict mapping "[object, attribute]" -> value
        as required by ConexpManyValuedContext.

        Returns
        -------
        dict
            Dict mapping "[object, attribute]" -> value.

        """
        incidence = {}
        for obj, attr, val in self.I:
            key = f"[{obj}, {attr}]"
            incidence[key] = val
        return incidence

    @staticmethod
    def _parse_conexp_incidence(obj: "ConexpManyValuedContext"):
        # Parse incidence dict "[object, attribute]" -> value
        i: set[tuple[Any, Any, Any]] = set()
        w: set[Any] = set()

        for key, value in obj.incidence.items():
            # Parse key format: "[object, attribute]"
            cleaned_key = key.strip("[]")
            parts = cleaned_key.split(", ", 1)  # Split only on first ", "
            if len(parts) == 2:
                obj_name, attr_name = parts
                i.add((obj_name, attr_name, value))
                w.add(value)

        return w, i

    @classmethod
    def _parse_conexp_context(
        cls, obj: "ConexpManyValuedContext", name=""
    ) -> "ManyValuedContext":
        objects = cls._parse_conexp_objects(obj)
        attributes = cls._parse_conexp_attributes(obj)
        domain, incidence = cls._parse_conexp_incidence(obj)
        return cls(
            objects,
            attributes,
            domain,
            incidence,
            name=name,
        )

    # ========== DATAFRAME FORMAT MIXIN IMPLEMENTATION ==========

    def to_df(self) -> pd.DataFrame:
        """Convert the many-valued context to a pandas DataFrame.

        Rows correspond to objects, columns correspond to attributes,
        and entries contain attribute values.

        Returns
        -------
        pandas.DataFrame
            DataFrame representation of the many-valued context.

        """
        df = pd.DataFrame(index=list(self.G), columns=list(self.M), dtype=object)
        for obj, attr, val in self.I:
            df.loc[obj, attr] = val
        return df

    @classmethod
    def from_df(
        cls: Type["ManyValuedContext"],
        df: pd.DataFrame,
        name: str = "",
    ) -> "ManyValuedContext":
        """Construct a many-valued context from a pandas DataFrame.

        Non-null entries are interpreted as values of the incidence relation.
        Missing values (NaN, None) in the DataFrame are silently skipped.

        Parameters
        ----------
        df : pandas.DataFrame
            DataFrame with objects as rows and attributes as columns.
        name : str, optional
            Optional name of the context.

        Returns
        -------
        ManyValuedContext
            Constructed many-valued context.

        Notes
        -----
        Missing values in the DataFrame (represented as NaN, None, or pandas NA)
        are silently skipped. This behavior ensures that only valid data
        contributes to the many-valued incidence relation.

        """
        g = list(df.index)
        m = list(df.columns)

        i: Set[Tuple[Any, Any, Any]] = set()
        w: Set[Any] = set()

        for _g in g:
            for _m in m:
                val = df.loc[_g, _m]
                # Defensive check: handle unexpected Series values gracefully
                if isinstance(val, pd.Series):
                    # val is a Series - take first non-NA value if available
                    if not val.empty:
                        first_val = val.iloc[0]
                        if pd.notna(first_val):
                            if isinstance(first_val, np.generic):
                                first_val = first_val.item()
                            i.add((_g, _m, first_val))
                            w.add(first_val)
                elif pd.notna(val):
                    if isinstance(val, np.generic):
                        val = val.item()
                    i.add((_g, _m, val))
                    w.add(val)
        return cls(g, m, w, i, name=name)

    # ========== JSON FORMAT MIXIN IMPLEMENTATION ==========

    def _get_json_type(self) -> str:
        """Get the JSON type identifier for many-valued contexts.

        Returns
        -------
        str
            The type identifier 'ManyValuedContext'.

        Notes
        -----
        Implementation required by JSONSerializationMixin.
        """
        return "ManyValuedContext"

    def _construct_json_data(self) -> dict:
        """Construct JSON data from ManyValuedContext state.

        Returns
        -------
        dict
            JSON-serializable dictionary representation.
        """
        return {
            "type": self._get_json_type(),
            "name": self.name or "",
            "objects": sorted(str(g) for g in self.G),
            "attributes": sorted(str(m) for m in self.M),
            "values": sorted(str(w) for w in self.W),
            "incidence": [[str(g), str(m), str(w)] for g, m, w in self.I],
        }

    @classmethod
    def _get_expected_json_type(cls) -> str:
        """Get the expected JSON type for deserialization.

        Returns
        -------
        str
            The type identifier 'ManyValuedContext'.

        Notes
        -----
        Implementation required by JSONSerializationMixin.
        """
        return "ManyValuedContext"

    @classmethod
    def _construct_from_json_data(
        cls: Type["ManyValuedContext"],
        json_data: dict,
    ) -> "ManyValuedContext":
        """Construct a many-valued context from parsed JSON data.

        Parameters
        ----------
        json_data : dict
            Parsed JSON data dictionary.

        Returns
        -------
        ManyValuedContext
            Deserialized many-valued context.

        Notes
        -----
        Implementation required by JSONSerializationMixin.
        """
        incidence = [(g, m, w) for g, m, w in json_data["incidence"]]
        return cls(
            g=json_data["objects"],
            m=json_data["attributes"],
            w=json_data["values"],
            i=incidence,
            name=json_data.get("name", ""),
        )
