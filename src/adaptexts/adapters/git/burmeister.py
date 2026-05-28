"""Git repository adapters for Burmeister (.cxt) format contexts.

This module provides adapters for accessing Burmeister-formatted formal
contexts from Git repositories. Two variants are provided:

- GitBurmeisterAdapter: Uncached, lightweight adapter
- CachedGitBurmeisterAdapter: Cached adapter (default for most users)
"""

import logging

from pathlib import Path
from typing import TYPE_CHECKING

from ..mixins import CacheMixin, FileTreeConfig
from ..mixins.readers import BurmeisterReaderMixin
from .base import GitAdapter

logger = logging.getLogger(__name__)


class GitBurmeisterAdapter(GitAdapter, BurmeisterReaderMixin):
    """Git repository adapter for Burmeister (.cxt) format contexts (uncached).

    This adapter combines Git repository access with Burmeister format file
    reading. It does NOT include caching, making it lightweight and suitable
    for one-time iterations or when memory usage is a concern.

    Use CachedGitBurmeisterAdapter for cached access (default for most users).

    Examples
    --------
    >>> # Basic usage (uncached - always loads from source)
    >>> from adaptexts.adapters.git_burmeister import GitBurmeisterAdapter
    >>> adapter = GitBurmeisterAdapter("https://github.com/fcatools/contexts.git")
    >>> for context in adapter:
    ...     print(context.name)

    >>> # With specific revision
    >>> adapter = GitBurmeisterAdapter(
    ...     "https://github.com/fcatools/contexts.git",
    ...     revision="main"
    ... )

    >>> # With custom file filtering
    >>> from adaptexts.adapters.mixins import FileTreeConfig
    >>> file_tree_config = FileTreeConfig(
    ...     include_patterns=["**/*.cxt"],
    ...     exclude_patterns=["**/test_*"],
    ... )
    >>> adapter = GitBurmeisterAdapter(
    ...     "https://github.com/fcatools/contexts.git",
    ...     file_tree_config=file_tree_config
    ... )
    """

    def __init__(
        self,
        repo_url: str,
        revision: str | None = None,
        shallow_clone: bool = True,
        file_tree_config: FileTreeConfig | None = None,
        data_home: Path | str | None = None,
    ):
        """Initialize a GitBurmeisterAdapter.

        Parameters
        ----------
        repo_url : str
            Git repository URL or local path.
        revision : str, optional
            Git revision to checkout. If None, uses default branch.
        shallow_clone : bool, optional
            Whether to use shallow clones (depth=1). Default: True.
        file_tree_config : FileTreeConfig, optional
            File tree configuration. If None, creates a default config
            with the repository cache path that includes .cxt/.ctx files.
        data_home : str, Path, optional
            Destination of the clone if repo_url is not local.
            Overwrites file_tree_config.root if set.
        """
        logger.debug(
            "Initializing GitBurmeisterAdapter: repo_url=%s, revision=%s, shallow_clone=%s",
            repo_url,
            revision,
            shallow_clone,
        )

        # Create default config that filters for .cxt files if not provided
        if file_tree_config is None:
            file_tree_config = FileTreeConfig(
                root="",  # Placeholder - GitAdapter will set this
                include_patterns=["**/*.cxt", "**/*.ctx"],
                exclude_patterns=["**/.git/**", "**/__pycache__/**"],
            )
            logger.debug("Created default FileTreeConfig for .cxt/.ctx files")

        super().__init__(
            repo_url=repo_url,
            revision=revision,
            shallow_clone=shallow_clone,
            file_tree_config=file_tree_config,
            data_home=data_home,
        )

        logger.info("GitBurmeisterAdapter initialized successfully")

    def _get(self, key: str):
        """Load a context from the given key without caching.

        Delegates to appropriate format reader's _load_context() method based on file extension.

        Parameters
        ----------
        key : str
            Cache key (relative path to the file).

        Returns
        -------
        Context | ManyValuedContext
            The loaded context.

        Raises
        ------
        ContextParseError
            If file extension is not supported or reading fails.
        """
        logger.debug("Loading context for key=%s", key)

        context = self._load_context(key)
        logger.info(
            "Loaded context %s: %d objects, %d attributes, %d incidences",
            context.name,
            len(list(context.G)),
            len(list(context.M)),
            len(list(context.I)),
        )
        return context


__all__ = ["GitBurmeisterAdapter"]
