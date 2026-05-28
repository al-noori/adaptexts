"""Base mixin providing shared utilities for format serialization.

This module provides the BaseMixin class which contains common methods
for sorting and standardizing context data to ensure reproducible and
consistent output across format mixins.
"""

from typing import Any


def make_hashable(x: Any) -> Any:
    """Convert an object into a hashable representation.

    This utility ensures that objects can be safely used in sets
    and as dictionary keys.

    Parameters
    ----------
    x : Any
        Input object.

    Returns
    -------
    Any
        Hashable representation of the object.

    Raises
    ------
    Does not raise. Always returns a hashable result.

    """
    if isinstance(x, (str, int, float, bool, type(None))):
        return x

    if isinstance(x, tuple):
        return tuple(make_hashable(i) for i in x)

    if isinstance(x, list):
        return tuple(make_hashable(i) for i in x)

    if isinstance(x, set):
        return tuple(sorted((make_hashable(i) for i in x), key=str))

    if isinstance(x, dict):
        return tuple(sorted((make_hashable(k), make_hashable(v)) for k, v in x.items()))

    try:
        hash(x)
        return x
    except TypeError:
        return repr(x)


class BaseMixin:
    """Base mixin providing shared utilities for format serialization.

    This mixin provides common methods for sorting and standardizing context
    data to ensure reproducible and consistent output across different formats.

    """

    @property
    def _sorted_objects(self):
        """Get objects in a sorted order for reproducible output.

        Returns
        -------
        list
            Sorted list of objects from context.G.

        """
        return sorted(make_hashable(g) for g in self.G)

    @property
    def _sorted_attributes(self):
        """Get attributes in a sorted order for reproducible output.

        Returns
        -------
        list
            Sorted list of attributes from context.M.

        """
        return sorted(make_hashable(m) for m in self.M)

    @property
    def _sorted_incidence(self):
        """Get incidence tuples in a sorted order (by object, then attribute).

        Returns
        -------
        list
            Sorted list of incidence tuples (g, m) sorted first by object,
            then by attribute.

        """
        return sorted((make_hashable(i) for i in self.I), key=lambda x: (x[0], x[1]))
