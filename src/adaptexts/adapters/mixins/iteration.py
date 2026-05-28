import logging

from typing import Iterator, Union

from adaptexts.context import Context
from adaptexts.many_valued_context import ManyValuedContext

logger = logging.getLogger(__name__)


class IterationMixin:
    """Mixin providing iteration behavior using keys() and _get().

    This mixin provides a base __iter__ implementation that:
    - Iterates through keys from a parent's keys() method
    - Calls _get(key) for each key to retrieve and yield contexts

    This mixin does NOT provide caching - it always calls _get() directly.
    For cached iteration, use CacheIterationMixin which combines this
    iteration logic with cache operations.

    This mixin relies on:
    - A parent class providing keys() method
    - A _get(key) method implementation (typically from a cache mixin or concrete adapter)

    Examples
    --------
    >>> from adaptexts.adapters.mixins import IterationMixin
    >>>
    >>> class MyUncachedAdapter(IterationMixin, AdapterInterface):
    ...     def keys(self) -> Iterator[str]:
    ...         yield from ["a", "b", "c"]
    ...
    ...     def _get(self, key: str) -> Context:
    ...         return Context(set(), set(), set(), name=key)
    >>>
    >>> adapter = MyUncachedAdapter()
    >>> for context in adapter:  # Always loads fresh contexts
    ...     print(context.name)
    """

    def __iter__(self) -> Iterator[Union[Context, ManyValuedContext]]:
        """Iterate through all keys, yielding contexts via _get().

        Yields
        ------
        Union[Context, ManyValuedContext]
            Context for each key yielded by keys().

        Examples
        --------
        >>> adapter = MyUncachedAdapter()
        >>> for context in adapter:
        ...     print(context.name)
        """
        logger.info("Starting iteration on %s", self.__class__.__name__)
        logger.debug("Using direct iteration (no caching)")
        for key in self.keys():  # type: ignore[attr-defined]
            yield self._get(key)  # type: ignore[attr-defined]
        logger.debug("Direct iteration completed")
        logger.info("Iteration completed on %s", self.__class__.__name__)
