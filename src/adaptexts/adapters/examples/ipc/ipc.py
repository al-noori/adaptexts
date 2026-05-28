"""Integer Partition Context (IPC) adapter.

This module defines the IPCAdapter class, which constructs formal contexts
based on the dominance order of integer partitions of a given integer n.

Computed contexts are cached using the adapter caching system to avoid
recomputation across runs.
"""

import logging

from itertools import accumulate
from typing import Iterator, Optional

from adaptexts.base.cache import CacheConfig
from adaptexts.context import Context

from ...interface import AdapterInterface
from ...mixins import CacheIterationMixin
from .utils import integer_partitions

logger = logging.getLogger(__name__)


class IPCAdapter(CacheIterationMixin, AdapterInterface):
    """Adapter for constructing formal contexts from integer partitions.

    Given an integer n, the adapter constructs the formal context whose
    objects and attributes are the integer partitions of n, ordered by
    the dominance (prefix-sum) relation.

    """

    def __init__(
        self,
        n: int | list[int] | tuple[int, int],
        cache_config: Optional[CacheConfig] = None,
    ) -> None:
        """Initialize the IPC adapter.

        Parameters
        ----------
        n : int or list[int] or tuple[int, int]
            Integer(s) for partition contexts.
        cache_config : CacheConfig, optional
            Cache configuration. If None, uses default with two-tier caching
            and Burmeister serialization.

        Examples
        --------
        >>> # Using defaults (data-home package)
        >>> adapter = IPCAdapter(n=5)

        >>> # Custom cache directory
        >>> from adaptexts.base.cache import CacheConfig
        >>> from pathlib import Path
        >>> config = CacheConfig(disk_cache_dir=Path("/tmp/ipc_cache"))
        >>> adapter = IPCAdapter(n=5, cache_config=config)

        """
        logger.info("Initializing IPCAdapter")

        if isinstance(n, tuple):
            start, end = n
            self.n_values = list(range(start, end + 1))
            logger.debug(
                "Initialized with tuple range: n=(%d, %d) -> n_values=%s",
                start,
                end,
                self.n_values,
            )
        elif isinstance(n, list):
            self.n_values = n
            logger.debug("Initialized with list: n_values=%s", self.n_values)
        else:
            self.n_values = [n]
            logger.debug("Initialized with single value: n_values=[%d]", n)

        if cache_config is None:
            cache_config = CacheConfig(
                backend="disk",
                unary_context_serializer="pickle",
            )
            logger.debug(
                "Using default cache config: backend=%s, serializer=%s",
                cache_config.backend,
                cache_config.unary_context_serializer,
            )
        else:
            logger.debug(
                "Using custom cache config: backend=%s, serializer=%s",
                cache_config.backend,
                cache_config.unary_context_serializer,
            )

        AdapterInterface.__init__(self, context_type=Context)
        self._init_cache(cache_config)
        logger.info(
            "IPCAdapter initialized successfully with %d value(s) for n",
            len(self.n_values),
        )

    def keys(self) -> Iterator[str]:
        yield from [str(n) for n in self.n_values]

    def _get(self, key: str) -> Context:
        logger.debug("Generating context for key=%s", key)

        partitions = integer_partitions(int(key))
        logger.debug("Generated %d partition(s) for n=%s", len(partitions), key)

        prefix = [list(accumulate(p)) for p in partitions]
        logger.debug("Computed prefix sums for %d partition(s)", len(prefix))

        incidence_count = 0
        incidence = []
        for a, pa in zip(partitions, prefix):
            for b, pb in zip(partitions, prefix):
                if all(x <= y for x, y in zip(pa, pb)):
                    incidence.append((a, b))
                    incidence_count += 1

        logger.debug("Computed %d incidence relation(s) for n=%s", incidence_count, key)

        context = Context(
            partitions,
            partitions,
            incidence,
            name=f"IPC(n={key})",
        )
        logger.info(
            "Generated context IPC(n=%s): %d objects, %d attributes, %d incidences",
            key,
            len(list(context.G)),
            len(list(context.M)),
            len(list(context.I)),
        )
        return context

    def __len__(self) -> int:
        """Return the number of context values.

        Returns
        -------
        int
            Number of n values to generate contexts for.
        """
        return len(self.n_values)

    # adapter properties

    def is_sortable(self) -> bool:
        """Indicate whether this adapter supports deterministic sorting.

        Returns
        -------
        bool
            Always True for IPCAdapter.

        """
        return True

    def is_versionable(self) -> bool:
        """Indicate whether this adapter supports versioning.

        Returns
        -------
        bool
            Always True for IPCAdapter.

        """
        return False

    def is_deterministic(self) -> bool:
        """Indicate whether repeated runs yield identical results.

        Returns
        -------
        bool
            Always True for IPCAdapter.

        """
        return True

    def is_stateless(self) -> bool:
        """Indicate whether the adapter maintains internal mutable state.

        Returns
        -------
        bool
            Always True for IPCAdapter.

        """
        return True

    def has_metadata(self) -> bool:
        """Indicate whether the adapter exposes additional metadata.

        Returns
        -------
        bool
            Always False for IPCAdapter.

        """
        return False
