"""Git repository adapter.

This module defines the GitAdapter class, which provides a uniform
interface for working with Git repositories as data sources. It supports
both local and remote repositories, with optional revision checking.

The adapter is format-agnostic and does NOT include caching by default.
For caching, compose with CacheableAdapter.
"""

import logging

from pathlib import Path
from urllib.parse import urlparse

from adaptexts.base.cache import get_cache_dir

from git import Repo

from ..directory import DirectoryAdapter
from ..exceptions import (
    AccessError,
    AdapterError,
    DownloadError,
    SourceNotFoundError,
)
from ..mixins import FileTreeConfig

logger = logging.getLogger(__name__)


class GitAdapter(DirectoryAdapter):
    """Adapter for accessing Git repositories (format-agnostic, uncached).

    The GitAdapter provides a uniform interface for working with Git repositories
    as data sources. It supports both local repositories and remote repositories
    (e.g., GitHub, GitLab).

    If a local repository path is provided, it is used in-place.
    If a remote repository URL is provided, the repository is cloned into a
    per-user data directory or a user-specified location.

    The adapter supports deterministic access via Git revisions.

    This adapter is format-agnostic and does NOT include caching. To add format
    support, compose with format reader mixins. To add caching, compose with
    CacheableAdapter.

    Examples
    --------
    >>> # Use default cache location
    >>> from adaptexts.adapters.git_repo import GitAdapter
    >>> adapter = GitAdapter("https://github.com/fcatools/contexts.git")

    >>> # With a specific revision
    >>> adapter = GitAdapter(
    ...     "https://github.com/fcatools/contexts.git",
    ...     revision="main"
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
        """Initialize a GitAdapter.

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
            with the repository cache path.
        data_home : str, Path, optional
            Destination of the clone if repo_url is not local.
            Overwrites config.root if set.

        Examples
        --------
        >>> # With default options
        >>> adapter = GitAdapter("https://github.com/fcatools/contexts.git")

        >>> # With revision
        >>> adapter = GitAdapter(
        ...     "https://github.com/fcatools/contexts.git",
        ...     revision="main"
        ... )

        >>> # With custom config
        >>> from adaptexts.adapters.file_tree import FileTreeConfig
        >>> file_tree_config = FileTreeConfig(
        ...     include_patterns=["**/*.cxt"],
        ...     exclude_patterns=["**/test_*"],
        ... )
        >>> adapter = GitAdapter(
        ...     "https://github.com/fcatools/contexts.git",
        ...     file_tree_config=file_tree_config,
        ...     data_home="~/my-workspace/fcatools",
        ... )
        """
        logger.debug(
            "Initializing GitAdapter: repo_url=%s, revision=%s, shallow_clone=%s",
            repo_url,
            revision,
            shallow_clone,
        )

        self.repo_url = repo_url
        self.revision = revision
        self.shallow_clone = shallow_clone

        # Determine if this is a local path or remote URL
        local_path = Path(repo_url).expanduser().resolve()

        if local_path.exists() and (local_path / ".git").exists():
            # This is a local Git repository
            root = local_path
            logger.debug("Using local repository at %s", root)
        else:
            repo_name = self._repo_name_from_url(repo_url)
            # This is a remote URL - determine cache path
            if data_home is not None:
                root = Path(data_home).expanduser().resolve()
                logger.debug("Using specified repo_root: %s", root)
            else:
                root = get_cache_dir(
                    adapter_name="git_adapter",
                    identifier=repo_name,
                )
                logger.debug("Using remote repository, cache path: %s", root)

        # Create default config if not provided
        if file_tree_config is None:
            file_tree_config = FileTreeConfig(root=root)
            logger.debug("Created default FileTreeConfig")
        else:
            # Update config with root_path
            file_tree_config.root = root

        super().__init__(file_tree_config=file_tree_config)

        # Set self.root for easy access to the repository root path
        self.root = root
        logger.info("GitAdapter initialized successfully")

    def _ensure_tree_available(self) -> Path:
        """Ensure the Git repository is available locally.

        Clones the repository if it doesn't exist locally. Checks out the
        specified revision if provided. Caches the result in `self._tree_root`.

        Returns
        -------
        Path
            Path to the local repository root.

        Raises
        ------
        AccessError
            If there's a permission error accessing the repository.
        DownloadError
            If cloning the repository fails.
        SourceNotFoundError
            If the repository URL is invalid.
        AdapterError
            For other unexpected errors.
        """
        # Return cached result if available
        if self._tree_root is not None:
            logger.debug("Tree already available at %s", self._tree_root)
            return self._tree_root

        # Check if this is a local path
        local_path = Path(self.repo_url).expanduser().resolve()
        if local_path.exists() and (local_path / ".git").exists():
            # Use local repository in-place
            logger.debug("Using local repository at %s", local_path)
            repo = Repo(local_path)

            # Checkout revision if specified
            if self.revision is not None:
                logger.info(
                    "Checking out revision '%s' in local repository", self.revision
                )
                try:
                    repo.git.checkout(self.revision)
                    logger.debug("Checked out revision '%s'", self.revision)
                except Exception as e:
                    logger.error(
                        "Failed to checkout revision '%s': %s", self.revision, e
                    )
                    raise AdapterError(
                        f"Failed to checkout revision '{self.revision}' "
                        f"in local repository {local_path}: {e}"
                    ) from e

            self._tree_root = local_path
            self._repo = repo
            return local_path

        # This is a remote URL - clone to cache directory
        cache_path = Path(self.root)

        try:
            # Clone the repository
            logger.debug(
                "Ensuring repository %s is available at %s", self.repo_url, cache_path
            )
            self._repo = self._clone_repo(self.repo_url, cache_path)
            logger.debug("Repository available")
        except PermissionError as e:
            logger.error("Permission denied accessing repository %s", self.repo_url)
            raise AccessError(
                f"Permission denied accessing repository {self.repo_url}"
            ) from e
        except ConnectionError as e:
            logger.error(
                "Connection failed while cloning repository %s: %s", self.repo_url, e
            )
            raise DownloadError(
                f"Connection failed while cloning repository {self.repo_url}: {e}"
            ) from e
        except Exception as e:
            # Check for specific Git errors
            error_msg = str(e).lower()
            if "not found" in error_msg or "does not exist" in error_msg:
                logger.error("Repository not found: %s", self.repo_url)
                raise SourceNotFoundError(
                    f"Repository not found: {self.repo_url}"
                ) from e
            elif "permission" in error_msg or "denied" in error_msg:
                logger.error("Permission denied accessing repository %s", self.repo_url)
                raise AccessError(
                    f"Permission denied accessing repository {self.repo_url}"
                ) from e
            else:
                logger.error("Failed to clone repository %s: %s", self.repo_url, e)
                raise AdapterError(
                    f"Failed to clone repository {self.repo_url}: {e}"
                ) from e

        self._tree_root = cache_path
        return cache_path

    def _clone_repo(self, repo_url: str, repo_path: Path) -> Repo:
        """Clone or reuse a Git repository at the given path.

        If the repository does not yet exist at `repo_path`, it is cloned from
        `repo_url`. If it already exists, it is reused and the revision is
        checked out if specified.

        Parameters
        ----------
        repo_url : str
            Remote Git repository URL.
        repo_path : Path
            Target directory where the repository is stored.

        Returns
        -------
        Repo
            A GitPython repository instance.

        Notes
        -----
        Shallow clones are used when possible to reduce network and disk usage.
        """
        # Check if repository already exists
        if (repo_path / ".git").exists():
            logger.debug("Repository already exists at %s, reusing", repo_path)
            repo = Repo(repo_path)

            # Fetch latest if revision is specified
            if self.revision is not None:
                logger.debug("Fetching and checking out revision '%s'", self.revision)
                try:
                    # Fetch the specific revision
                    repo.git.fetch(
                        "origin", self.revision, depth=1 if self.shallow_clone else None
                    )
                    repo.git.checkout(self.revision)
                    logger.debug("Checked out revision '%s'", self.revision)
                except Exception as e:
                    logger.debug("Fetch failed, trying local checkout: %s", e)
                    # If fetch fails, try to checkout anyway (might already be present)
                    try:
                        repo.git.checkout(self.revision)
                        logger.debug(
                            "Checked out revision '%s' (local copy)", self.revision
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to checkout revision '%s': %s", self.revision, e
                        )
                        raise AdapterError(
                            f"Failed to checkout revision '{self.revision}': {e}"
                        ) from e
            else:
                logger.debug("Using existing repository without fetching")

            return repo

        # Clone the repository
        logger.info("Creating new clone (shallow=%s)", self.shallow_clone)
        try:
            if self.revision is None:
                # Clone with shallow checkout of default branch
                if self.shallow_clone:
                    logger.debug("Cloning default branch with depth=1")
                    repo = Repo.clone_from(repo_url, repo_path, depth=1)
                else:
                    logger.debug("Cloning default branch (full)")
                    repo = Repo.clone_from(repo_url, repo_path)
            else:
                # Clone without checkout, then fetch and check out specific revision
                if self.shallow_clone:
                    logger.debug(
                        "Cloning with no checkout, fetching revision '%s' with depth=1",
                        self.revision,
                    )
                    repo = Repo.clone_from(repo_url, repo_path, no_checkout=True)
                    repo.git.fetch("origin", self.revision, depth=1)
                else:
                    logger.debug(
                        "Cloning with no checkout, fetching revision '%s' (full)",
                        self.revision,
                    )
                    repo = Repo.clone_from(repo_url, repo_path, no_checkout=True)
                    repo.git.fetch("origin", self.revision)
                repo.git.checkout(self.revision)
                logger.debug("Checked out revision '%s'", self.revision)
        except Exception as e:
            logger.error("Failed to clone repository %s: %s", repo_url, e)
            raise DownloadError(f"Failed to clone repository {repo_url}: {e}") from e

        return repo

    @staticmethod
    def _repo_name_from_url(url: str) -> str:
        """Derive a stable local directory name from a Git repository URL.

        Parameters
        ----------
        url : str
            Remote Git repository URL.

        Returns
        -------
        str
            A filesystem-safe repository identifier of the form:
            "<domain>__<owner>__<repository>""
        """
        parsed = urlparse(url)
        domain = parsed.hostname or "local"

        # Extract owner and repo from path
        path = parsed.path.strip("/")
        parts = path.split("/")[:2]

        if len(parts) >= 2:
            owner, repo = parts[0], parts[1]
        elif len(parts) == 1:
            owner, repo = "unknown", parts[0]
        else:
            owner, repo = "unknown", "repo"

        # Remove .git suffix if present
        if repo.endswith(".git"):
            repo = repo[:-4]

        return f"{domain}__{owner}__{repo}"

    def is_versionable(self) -> bool:
        """Indicate whether this adapter supports versioning.

        Returns
        -------
        bool
            True if a Git revision is specified.
        """
        return self.revision is not None

    def is_deterministic(self) -> bool:
        """Indicate whether repeated runs yield identical results.

        Returns
        -------
        bool
            Always True for GitAdapter (Git revisions ensure determinism).
        """
        return True

    def is_stateless(self) -> bool:
        """Indicate whether the adapter maintains internal mutable state.

        Returns
        -------
        bool
            Always True for GitAdapter (no internal mutable state).
        """
        return True

    def has_metadata(self) -> bool:
        """Indicate whether the adapter exposes additional metadata.

        The base GitAdapter does not expose additional metadata. Subclasses
        may override this method to provide metadata access.

        Returns
        -------
        bool
            False, as the base GitAdapter does not expose metadata.
        """
        return False

    def get_repo(self) -> Repo:
        """Get the underlying GitPython repository object.

        Returns
        -------
        Repo
            The Git repository object.

        Raises
        ------
        AdapterError
            If the repository has not been initialized.
        """
        if not hasattr(self, "_repo"):
            self._ensure_tree_available()
        return self._repo
