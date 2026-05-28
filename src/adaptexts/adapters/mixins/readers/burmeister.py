"""Reader for Burmeister (.cxt) format context files.

This module defines the BurmeisterReaderMixin, which can parse Burmeister
binary context format files.
"""

import logging

from pathlib import Path

from adaptexts.context import Context

from ...exceptions import ContextParseError
from .base import ContextFileReaderMixin

logger = logging.getLogger(__name__)


class BurmeisterReaderMixin(ContextFileReaderMixin):
    """Reader for Burmeister (.cxt) format context files.

    Burmeister format is a binary context format used in Formal Concept Analysis.

    Supported Features
    ------------------
    - Standard Burmeister format with "X" and "." markers
    - Custom positive/negative markers via format_options
    - Binary contexts only (no many-valued support)

    Format Options
    --------------
    Configure via FileTreeConfig.format_options:

        format_options={
            "burmeister": {
                "positive": "X",
                "negative": ".",
                "sep_lines": "\\n",
            }
        }

    Examples
    --------
    Cached variant (default):
        >>> from adaptexts.adapters.git_repo import GitAdapter
        >>> from adaptexts.adapters.readers import BurmeisterReaderMixin
        >>> from adaptexts.adapters.caching import CacheableAdapter
        >>>
        >>> class CachedGitBurmeisterAdapter(CacheableAdapter, BurmeisterReaderMixin, GitAdapter):
        ...     pass
        >>>
        >>> adapter = CachedGitBurmeisterAdapter("https://github.com/user/repo.git")
        >>> for context in adapter:  # Cached
        ...     print(context.name)

    Uncached variant:
        >>> class GitBurmeisterAdapter(BurmeisterReaderMixin, GitAdapter):
        ...     pass
        >>>
        >>> adapter = GitBurmeisterAdapter("https://github.com/user/repo.git")
        >>> for context in adapter:  # Not cached
        ...     print(context.name)
    """

    def get_supported_extensions(self) -> tuple[str, ...]:
        """Return supported Burmeister file extensions.

        Returns
        -------
        tuple[str, ...]
            Tuple containing ".cxt" and ".ctx" extensions.
        """
        return (".cxt", ".ctx")

    def can_handle_file(self, file_path: Path) -> bool:
        """Check if this is a Burmeister file.

        Parameters
        ----------
        file_path : Path
            Path to the file to check.

        Returns
        -------
        bool
            True if the file has .cxt or .ctx extension.
        """
        return file_path.suffix.lower() in (".cxt", ".ctx")

    def _load_context(self, key: str) -> Context:
        """Load a Burmeister file and return a binary Context.

        Parameters
        ----------
        key : str
            Cache key (relative path).

        Returns
        -------
        Context
            Parsed binary context with name set from key.

        Raises
        ------
        ContextParseError
            If file cannot be parsed or contains invalid data.
        FileNotFoundError
            If file doesn't exist.
        """
        logger.debug("Loading Burmeister context from key: %s", key)

        # This mixin relies on FileTreeAdapter or subclass providing _ensure_tree_available()
        root = self._ensure_tree_available()  # type: ignore[attr-defined]
        file_path = root / key.replace("/", "/")

        if not file_path.exists():
            logger.error("File not found for key '%s': %s", key, file_path)
            raise FileNotFoundError(f"File not found for key '{key}': {file_path}")

        # Get format options if available
        kwargs = self._get_format_options()
        if kwargs:
            logger.debug("Using format options: %s", kwargs)

        try:
            content = file_path.read_text(encoding="utf-8")
            logger.debug("Read %d bytes from %s", len(content), file_path)
            context = Context.from_burmeister(content, **kwargs)
            context.name = key
            logger.debug("Successfully parsed Burmeister context '%s'", context.name)
            return context
        except Exception as e:
            logger.error("Failed to parse Burmeister file %s: %s", file_path, e)
            raise ContextParseError("Burmeister", file_path, e) from e
