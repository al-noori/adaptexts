from .interface import AdapterInterface
from .mixins import CacheIterationMixin


class CachedAdapter(CacheIterationMixin, AdapterInterface):
    """Base adapter combining caching with iteration.

    This class provides a complete caching + iteration base that adapters
    can inherit from. Subclasses only need to provide:
    - keys() method to enumerate items
    - _get() method to load individual items
    - Call _init_cache() in __init__

    Examples
    --------
    >>> from adaptexts.adapters.mixins import CachedAdapter
    >>>
    >>> class MyCachedAdapter(CachedAdapter):
    ...     def __init__(self, items, cache_config=None):
    ...         super().__init__()
    ...         self._items = items
    ...         self._init_cache(cache_config)
    ...
    ...     def keys(self) -> Iterator[str]:
    ...         yield from self._items.keys()
    ...
    ...     def _get(self, key: str) -> Context:
    ...         return Context.from_data(self._items[key])
    """

    pass
