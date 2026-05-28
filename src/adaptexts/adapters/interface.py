"""Abstract interface for context adapter.

This module defines the AdapterInterface, which specifies the common API
that all adapters must implement in order to expose data sources
as formal contexts.
"""

from abc import ABC, abstractmethod
from typing import Iterator, Union

from adaptexts.context import Context
from adaptexts.many_valued_context import ManyValuedContext


class AdapterInterface(ABC):
    """Abstract base class for all adapters.

    An adapter is responsible for providing access to a data source
    (e.g. Git repositories, datasets, files) and exposing it in a
    uniform, structured way to downstream context construction logic.

    Use mixins to extend default behavior.

    """

    def __init__(
        self,
        context_type: type[Context] | type[ManyValuedContext] | None = None,
    ):
        """Initialize the adapter.

        Parameters
        ----------
        context_type : Context, ManyValuedContext, optional
            Type of contexts provided by the adapter. Helpful for tool
            integration but not necessary. Defaults to unary contexts.

        """
        if context_type is None:
            context_type = Context
        self.context_type = context_type

    @abstractmethod
    def __iter__(self) -> Iterator[Union[Context, ManyValuedContext]]:
        """Iterate over all contexts in the adapter.

        Yields
        ------
        Union[Context, ManyValuedContext]
            Context objects with their name attribute set.
        """
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of contexts in the adapter.

        Returns
        -------
        int
            Number of contexts available.
        """
        pass

    @abstractmethod
    def is_sortable(self) -> bool:
        """Indicate whether the adapter supports deterministic sorting.

        Returns
        -------
        bool

        """
        pass

    @abstractmethod
    def is_versionable(self) -> bool:
        """Indicate whether the adapter supports versioning.

        Returns
        -------
        bool

        """
        pass

    @abstractmethod
    def is_deterministic(self) -> bool:
        """Indicate whether repeated runs yield identical results.

        Returns
        -------
        bool

        """
        pass

    @abstractmethod
    def is_stateless(self) -> bool:
        """Indicate whether the adapter maintains internal mutable state.

        Returns
        -------
        bool

        """
        pass

    @abstractmethod
    def has_metadata(self) -> bool:
        """Indicate whether the adapter exposes metadata.

        Returns
        -------
        bool
            True if metadata is available, False otherwise.

        """
        pass
