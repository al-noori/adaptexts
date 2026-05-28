"""Multi-format reader that delegates to format-specific readers.

This module defines the MultiFormatReaderMixin, which can handle multiple
file format types in a single adapter by delegating to format-specific readers.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Union

from adaptexts.context import Context
from adaptexts.many_valued_context import ManyValuedContext

from ...exceptions import ContextParseError
from .base import ContextFileReaderMixin

if TYPE_CHECKING:
    pass


class MultiFormatReaderMixin(ContextFileReaderMixin):
    """Reader that delegates reading to format-specific readers.

    Handles multiple file formats in a single adapter by delegating to
    format-specific readers based on file extension.

    Key Point: This mixin only handles file reading delegation.
    Cache serialization is handled separately by CacheableAdapter with
    runtime serializer selection based on the actual context type returned.

    Examples
    --------
    Cached variant:
        >>> from adaptexts.adapters.readers import (
        ...     MultiFormatReaderMixin,
        ...     BurmeisterReaderMixin,
        ...     CSVReaderMixin,
        ...     JSONReaderMixin,
        ... )
        >>> from adaptexts.adapters.caching import CacheableAdapter
        >>> from adaptexts.adapters.git_repo import GitAdapter
        >>>
        >>> class CachedGitMultiAdapter(CacheableAdapter, MultiFormatReaderMixin, GitAdapter):
        ...     def __init__(self, repo_url: str, **kwargs):
        ...         super().__init__(
        ...             repo_url=repo_url,
        ...             readers=[
        ...                 BurmeisterReaderMixin,
        ...                 CSVReaderMixin,
        ...                 JSONReaderMixin,
        ...             ],
        ...             **kwargs
        ...         )

    Uncached variant:
        >>> class GitMultiAdapter(MultiFormatReaderMixin, GitAdapter):
        ...     def __init__(self, repo_url: str, **kwargs):
        ...         super().__init__(
        ...             repo_url=repo_url,
        ...             readers=[
        ...                 BurmeisterReaderMixin,
        ...                 CSVReaderMixin,
        ...                 JSONReaderMixin,
        ...             ],
        ...             **kwargs
        ...         )
    """

    def __init__(
        self,
        readers: list[type[ContextFileReaderMixin]],
        **kwargs,
    ):
        """Initialize MultiFormatReaderMixin.

        Parameters
        ----------
        readers : list[type[ContextFileReaderMixin]]
            List of format reader classes to delegate to.
        **kwargs
            Additional arguments passed to parent __init__.
        """
        # Map extensions to reader classes for O(1) lookup
        self._readers_by_extension: dict[str, type[ContextFileReaderMixin]] = {}
        for reader_cls in readers:
            reader_inst = object.__new__(reader_cls)  # Instance without __init__
            for ext in reader_inst.get_supported_extensions():
                self._readers_by_extension[ext.lower()] = reader_cls

        super().__init__(**kwargs)

    def get_supported_extensions(self) -> tuple[str, ...]:
        """Return all supported extensions.

        Returns
        -------
        tuple[str, ...]
            All extensions from all configured reader classes.
        """
        return tuple(sorted(self._readers_by_extension.keys()))

    def can_handle_file(self, file_path: Path) -> bool:
        """Check if any reader can handle this file.

        Parameters
        ----------
        file_path : Path
            Path to the file to check.

        Returns
        -------
        bool
            True if any configured reader can handle the file.
        """
        ext = file_path.suffix.lower()
        return ext in self._readers_by_extension

    def _load_context(self, key: str) -> Union[Context, ManyValuedContext]:
        """Load file by delegating to appropriate format reader.

        Determines the file extension, selects the appropriate reader,
        creates a temporary reader instance, and delegates the loading.

        Parameters
        ----------
        key : str
            Cache key (relative path).

        Returns
        -------
        Union[Context, ManyValuedContext]
            Parsed context.

        Raises
        ------
        ContextParseError
            If no reader supports the file extension or reading fails.
        FileNotFoundError
            If file doesn't exist (raised by delegated reader).
        """
        ext = Path(key).suffix.lower()
        if ext not in self._readers_by_extension:
            raise ContextParseError(
                "MultiFormat",
                Path(key),
                ValueError(f"Unknown file extension: {ext}"),
            )

        reader_cls = self._readers_by_extension[ext]

        # Create instance for loading without calling __init__
        # Readers need access to self.config and self._ensure_tree_available()
        reader_inst = object.__new__(reader_cls)
        reader_inst.config = self.config  # type: ignore[attr-defined]
        reader_inst._tree_root = self._tree_root  # type: ignore[attr-defined]
        reader_inst._ensure_tree_available = self._ensure_tree_available  # type: ignore[attr-defined, assignment]

        return reader_inst._load_context(key)
