"""Formal context abstraction.

This module defines the Context class, which represents a formal context
(objects, attributes, and an incidence relation) in the sense of
Formal Concept Analysis (FCA).

A formal context is a triple (G, M, I), where:
- G is a set of objects,
- M is a set of attributes,
- I ⊆ G × M is a binary incidence relation.
"""

from dataclasses import dataclass
from typing import Iterable, Tuple, TypeVar

from conexp_clj_py import ConexpContext

from .base.formats import FormatMixin
from .base.utils import truncated_repr

# Generic type variables for objects and attributes
# No bound needed - typing will infer types from usage
G = TypeVar("G")
M = TypeVar("M")

Incidence = Iterable[Tuple[G, M]]


@dataclass
class Context(FormatMixin):
    G: Iterable
    M: Iterable
    I: Incidence  # noqa: E741
    name: str | None = None

    def __repr__(self):
        return truncated_repr(self)

    def _get_conexp_class(self):
        return ConexpContext

    def _get_conexp_incidence(self):
        return [(g, m) for g, m in self._sorted_incidence]

    @staticmethod
    def _parse_conexp_incidence(obj: ConexpContext):
        return [tuple(inc) for inc in obj.incidence]

    # ========== JSON FORMAT MIXIN IMPLEMENTATION ==========

    def _get_json_type(self) -> str:
        """Get the JSON type identifier for Context.

        Returns
        -------
        str
            The type identifier "Context".
        """
        return "Context"

    def _construct_json_data(self) -> dict:
        """Construct JSON data from Context state.

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
            "incidence": [[str(g), str(m)] for g, m in self.I],
        }

    @classmethod
    def _get_expected_json_type(cls) -> str:
        """Get expected JSON type for deserialization.

        Returns
        -------
        str
            The type identifier "Context".
        """
        return "Context"

    @classmethod
    def _construct_from_json_data(cls, json_data: dict) -> "Context":
        """Construct Context from JSON data.

        Parameters
        ----------
        json_data : dict
            Parsed JSON data.

        Returns
        -------
        Context
            Constructed Context instance.
        """
        incidence = [(g, m) for g, m in json_data["incidence"]]
        return cls(
            json_data["objects"],
            json_data["attributes"],
            incidence,
            name=json_data.get("name", ""),
        )
