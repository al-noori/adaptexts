"""Real-World Contexts (RWC) adapter.

This module defines the RWCAdapter class, which specializes the
CachedGitBurmeisterAdapter to work with the Real-World Contexts repository.

In addition to Burmeister (.cxt) contexts, this adapter exposes
metadata files (typically YAML) associated with contexts.
"""

import logging

from pathlib import Path
from typing import Any

import yaml

from ...exceptions import AdapterError
from ...git import GitBurmeisterAdapter
from ...mixins import FileTreeConfig

logger = logging.getLogger(__name__)


class RWCAdapter(GitBurmeisterAdapter):
    """Adapter for the Real-World Contexts (RWC) dataset.

    This adapter loads Burmeister-formatted formal contexts from a Git
    repository and provides access to accompanying metadata files.

    Examples
    --------
    >>> # With default caching
    >>> from adaptexts.adapters.examples.rwc import RWCAdapter
    >>> adapter = RWCAdapter()
    >>> for context in adapter:
    ...     print(context.name)
    ...
    >>> # Get metadata
    >>> metadata = adapter.get_metadata("context_name")
    """

    base_url = "https://github.com/fcatools/contexts.git"

    def __init__(
        self,
        revision: str | None = None,
        shallow_clone: bool = True,
        file_tree_config: FileTreeConfig | None = None,
        data_home: Path | str | None = None,
    ):
        """Initialize the RWC adapter.

        Parameters
        ----------
        revision : str, optional
            Git revision to checkout. If None, uses "dev" branch.
            The conexp-clj repository stores testing-data in the "dev" branch.
        shallow_clone : bool, optional
            Whether to use shallow clones (depth=1). Default: True.
        file_tree_config : FileTreeConfig, optional
            File tree configuration. If None, creates a default config
            with the repository cache path.
        data_home : str, Path, optional
            Destination of the clone if repo_url is not local.
            Overwrites file_tree_config.root if set.


        """
        logger.info("Initializing RWCAdapter")

        super().__init__(
            repo_url=self.base_url,
            revision=revision,
            shallow_clone=shallow_clone,
            file_tree_config=file_tree_config,
            data_home=data_home,
        )

        logger.info("RWCAdapter initialized successfully")

    def has_metadata(self) -> bool:
        """Indicate whether this adapter provides metadata.

        Returns
        -------
        bool
            Always True for RWCAdapter.
        """
        return True

    def get_metadata(self, name: str, frmt: str = "yaml") -> str | dict[str, Any]:
        """Load metadata associated with a context.

        Uses glob pattern matching to find files containing the specified
        name substring and with the specified format extension.

        Parameters
        ----------
        name : str
            Substring that must occur in the file name.
        frmt : str, optional
            Metadata file format / extension (default: "yaml").

        Returns
        -------
        str | dict
            Metadata content as string (for non-YAML files) or parsed dict (for YAML).

        Raises
        ------
        AdapterError
            If no matching file is found, if multiple files match, or if the
            repository path is invalid.
        OSError
            If the file cannot be read.
        """
        logger.debug("Loading metadata for name=%s, format=%s", name, frmt)

        # Get the Git repository
        repo = self.get_repo()

        # Get repository path
        repo_path = Path(repo.working_tree_dir or ".")
        if not repo_path.exists():
            raise AdapterError(f"Repository path does not exist: {repo_path}")
        if not repo_path.is_dir():
            raise AdapterError(f"Repository path is not a directory: {repo_path}")

        # Find matching files using glob pattern
        pattern = f"*{name}*.{frmt}"
        matches = list(repo_path.rglob(pattern))

        # Filter out .git directory
        matches = [m for m in matches if ".git" not in m.parts]

        logger.debug("Found %d matching file(s) for pattern %s", len(matches), pattern)

        if len(matches) == 0:
            raise AdapterError(
                f"No {frmt} file matching {name!r} found in repository "
                f"{repo.working_tree_dir or repo.git_dir}"
            )

        if len(matches) > 1:
            raise AdapterError(
                f"Multiple {frmt} files matching {name!r} found in repository "
                f"{repo.working_tree_dir or repo.git_dir}: "
                f"{[f.name for f in matches]}; use a more specific name"
            )

        # Read the file
        try:
            with open(matches[0], "r", encoding="utf-8") as f:
                content = f.read()
            logger.debug("Successfully loaded metadata from %s", matches[0])
        except OSError as e:
            raise AdapterError(f"Failed to read file {matches[0]}: {e}") from e

        # Parse YAML if requested
        if frmt == "yaml":
            try:
                parsed = yaml.safe_load(content)
                logger.debug("Successfully parsed YAML metadata")
                return parsed
            except yaml.YAMLError as e:
                raise AdapterError(
                    f"Failed to parse YAML file {matches[0]}: {e}"
                ) from e

        return content
