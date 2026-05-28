"""Format-specific context file readers.

This package provides format-specific reader mixins for loading contexts from
different file formats. Use these mixins with any file tree adapter.

Exported Classes
----------------
- BurmeisterReaderMixin: Reader for Burmeister (.cxt) format
- CSVReaderMixin: Reader for CSV format
- JSONReaderMixin: Reader for JSON format
- MultiFormatReaderMixin: Reader that delegates to format-specific readers

Creating Custom Readers
-----------------------
To create a custom format reader, import the base class:

    from adaptexts.adapters.readers.base import ContextFileReaderMixin

And implement the abstract methods:
    - get_supported_extensions()
    - can_handle_file()
    - _load_context()

Examples
--------
Cached variant (default for most users):
    >>> from adaptexts.adapters.git_repo import GitAdapter
    >>> from adaptexts.adapters.readers import BurmeisterReaderMixin
    >>> from adaptexts.adapters.caching import CacheableAdapter
    >>>
    >>> class CachedGitBurmeisterAdapter(
    ...     CacheableAdapter, BurmeisterReaderMixin, GitAdapter
    ... ):
    ...     pass
    >>>
    >>> adapter = CachedGitBurmeisterAdapter("https://github.com/user/repo.git")
    >>> for context in adapter:
    ...     print(context.name)

Uncached variant (lightweight):
    >>> from adaptexts.adapters.git_repo import GitAdapter
    >>> from adaptexts.adapters.readers import BurmeisterReaderMixin
    >>>
    >>> class GitBurmeisterAdapter(BurmeisterReaderMixin, GitAdapter):
    ...     pass
    >>>
    >>> adapter = GitBurmeisterAdapter("https://github.com/user/repo.git")
    >>> for context in adapter:
    ...     print(context.name)

Multiple formats:
    >>> from adaptexts.adapters.readers import (
    ...     MultiFormatReaderMixin,
    ...     BurmeisterReaderMixin,
    ...     CSVReaderMixin,
    ...     JSONReaderMixin,
    ... )
    >>>
    >>> class CachedGitMultiAdapter(
    ...     CacheableAdapter, MultiFormatReaderMixin, GitAdapter
    ... ):
    ...     def __init__(self, repo_url: str, **kwargs):
    ...         super().__init__(
    ...             repo_url=repo_url,
    ...             readers=[BurmeisterReaderMixin, CSVReaderMixin, JSONReaderMixin],
    ...             **kwargs
    ...         )
"""

from .burmeister import BurmeisterReaderMixin
from .csv import CSVReaderMixin
from .json import JSONReaderMixin
from .multi_format import MultiFormatReaderMixin

__all__ = [
    "BurmeisterReaderMixin",
    "CSVReaderMixin",
    "JSONReaderMixin",
    "MultiFormatReaderMixin",
]