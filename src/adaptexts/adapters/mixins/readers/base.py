"""Base class for format-specific context file reader mixins.

This module defines the ContextFileReaderMixin, which is the abstract base
class for all format-specific reader mixins.

Design Principles
----------------
1. **Single Responsibility**: Each reader handles one format
2. **Open/Closed**: Open for extension (new formats), closed for modification
3. **Liskov Substitution**: Any reader can substitute the base
4. **Dependency Inversion**: Depends on abstract adapter interface

Import Notes
------------
The ContextFileReaderMixin base class should be imported from this module
when creating custom format readers:

    from adaptexts.adapters.readers.base import ContextFileReaderMixin

Concrete format readers (BurmeisterReaderMixin, CSVReaderMixin, etc.) are
exported from the package __init__.py for convenient access:

    from adaptexts.adapters.readers import BurmeisterReaderMixin
"""

from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Union

from adaptexts.context import Context
from adaptexts.many_valued_context import ManyValuedContext

if TYPE_CHECKING:
    pass


class ContextFileReaderMixin:
    """Base mixin for format-specific context file reading.

    This mixin is responsible ONLY for:
    1. Determining if a file can be handled
    2. Reading the file and returning a Context or ManyValuedContext

    Caching and serialization are handled separately by CacheableAdapter (opt-in).

    Design Principles
    ----------------
    1. **Single Responsibility**: Each reader handles one format
    2. **Open/Closed**: Open for extension (new formats), closed for modification
    3. **Liskov Substitution**: Any reader can substitute the base
    4. **Dependency Inversion**: Depends on abstract adapter interface

    Method Resolution Order (MRO)
    ----------------------------
    For CACHED adapters, CacheableAdapter must appear FIRST:

        class CachedMyAdapter(CacheableAdapter, BurmeisterReaderMixin, FileTreeAdapter):
            pass

    This ensures:
    - CacheableAdapter.__iter__() is called (not the uncached version)
    - BurmeisterReaderMixin._load_context() is called for cache misses

    For UNCACHED adapters, format reader must appear before tree adapter:

        class MyAdapter(BurmeisterReaderMixin, FileTreeAdapter):
            pass

    This ensures _load_context() is available for iteration.

    Configuration
    ------------
    Readers respect the following options from the `FileTreeConfig`:
    - config.format_options: Format-specific parsing options (e.g., delimiter, encoding)

    Usage Examples
    --------------
    Cached variant (DEFAULT for most users):
        >>> from adaptexts.adapters.readers import BurmeisterReaderMixin
        >>> from adaptexts.adapters.caching import CacheableAdapter
        >>> from adaptexts.adapters.git_repo import GitAdapter
        >>>
        >>> class CachedGitBurmeisterAdapter(CacheableAdapter, BurmeisterReaderMixin, GitAdapter):
        ...     pass
        >>>
        >>> adapter = CachedGitBurmeisterAdapter("https://github.com/user/repo.git")
        >>> for context in adapter:  # Automatically cached
        ...     print(context.name)

    Uncached variant (lightweight):
        >>> class GitBurmeisterAdapter(BurmeisterReaderMixin, GitAdapter):
        ...     pass
        >>> adapter = GitBurmeisterAdapter("https://github.com/user/repo.git")
        >>> for context in adapter:  # No caching, always loads from source
        ...     print(context.name)
    """

    def _get_format_options(self) -> dict:
        """Get format-specific options from config.

        Looks up options in config.format_options using the format name
        derived from the class name (e.g., BurmeisterReaderMixin → "burmeister").

        Derives format name from class name: BurmeisterReaderMixin → burmeister

        Returns
        -------
        dict
            Format-specific options for this reader. Empty dict if none configured.
        """
        # Derive format name from class name: BurmeisterReaderMixin → burmeister
        class_name = self.__class__.__name__
        format_name = class_name.replace("ReaderMixin", "").lower()

        config = getattr(self, "config", None)
        if (
            config is not None
            and hasattr(config, "format_options")
            and config.format_options is not None
            and format_name in config.format_options
        ):
            return config.format_options[format_name]
        return {}

    @abstractmethod
    def get_supported_extensions(self) -> tuple[str, ...]:
        """Return supported file extensions.

        This is used by FileTreeAdapter for pre-filtering files.

        Returns
        -------
        tuple[str, ...]
            File extensions including leading dot (e.g., (".cxt",) or (".csv",))
            Must be lowercase for consistent matching.
        """
        pass

    @abstractmethod
    def can_handle_file(self, file_path: Path) -> bool:
        """Check if this reader can handle the given file.

        This is used by multi-format adapters to delegate to the appropriate
        reader for each file.

        Parameters
        ----------
        file_path : Path
            Path to the file to check.

        Returns
        -------
        bool
            True if this reader can parse the file.

        Notes
        -----
        The default implementation checks file extension. Subclasses can
        override for content-based detection (magic bytes, headers, etc.).
        """
        pass

    def _load_context(self, key: str) -> Union[Context, ManyValuedContext]:
        """Load a context from the given cache key.

        This is the core method for format-specific reading. It resolves the key
        to a file path, reads the file, parses it, and returns a Context.

        Subclasses must implement this method to provide file-specific loading.

        Parameters
        ----------
        key : str
            Cache key (relative path from tree root).

        Returns
        -------
        Union[Context, ManyValuedContext]
            Parsed context.

        Raises
        ------
        FileNotFoundError
            If the file for the key doesn't exist.
        Exception
            If file parsing fails (should wrap in ContextParseError by subclass).

        Notes
        -----
        - This method is called by CacheableAdapter when caching is enabled
        - FileTreeAdapter.__iter__() will call this for uncached adapters
        - The context's `name` attribute should be set using the key (not from file)
        """
        # This mixin relies on FileTreeAdapter or subclass providing _ensure_tree_available()
        root = self._ensure_tree_available()  # type: ignore[attr-defined]
        file_path = root / key.replace("/", "/")

        if not file_path.exists():
            raise FileNotFoundError(f"File not found for key '{key}': {file_path}")

        # Subclasses override this to provide format-specific parsing
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _load_context()"
        )