"""File tree mixin for adapter composition.

This module provides:
- FileTreeConfig: Configuration for file tree-based adapters
- FileInfo: Metadata about files in the tree
- FileTreeMixin: Mixin providing file tree traversal and key enumeration

Design Notes
------------
- FileTreeMixin provides reusable file tree behavior (traversal, filtering, keys())
- Works with any base class that provides _ensure_tree_available()
- Can be composed with CacheIterationMixin for caching
- Format readers provide _load_context() implementation

Examples
--------
>>> from adaptexts.adapters.mixins import FileTreeMixin
>>> from adaptexts.adapters.interface import AdapterInterface
>>>
>>> class MyAdapter(FileTreeMixin, AdapterInterface):
...     def __init__(self, root_path, file_tree_config=None):
...         super().__init__(file_tree_config=file_tree_config or FileTreeConfig(
...             root=root_path, source_type="local"
...         ))
...
...     def _ensure_tree_available(self) -> Path:
...         if self._tree_root is None:
...             self._tree_root = Path(self._file_tree_config.root)
...         return self._tree_root
"""

import fnmatch
import os

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Protocol


@dataclass
class FileTreeConfig:
    """Configuration for file tree adapter behavior.

    Attributes
    ----------
    root : str | Path
        Root path of the file tree (can be absolute or relative).
    include_patterns : list[str]
        Glob patterns for files to include (default: all files).
    exclude_patterns : list[str]
        Glob patterns for files to exclude (default: none).
    max_depth : int | None
        Maximum directory depth for traversal (default: unlimited).
    enable_tree_view : bool
        Whether to enable tree view generation (default: True).
    format_options : dict[str, dict] | None
        Format-specific parsing options (e.g., delimiter, encoding).
    validate_on_load : bool
        Enable full validation on context load (default: False, extension-only).
    respect_file_name : bool
        Use file's own name if available (default: False, use key).

    Examples
    --------
    >>> from adaptexts.adapters.mixins import FileTreeConfig
    >>> config = FileTreeConfig(
    ...     root="/path/to/source",
    ...     include_patterns=["**/*.cxt"],
    ...     exclude_patterns=["**/test_*"],
    ...     max_depth=3,
    ... )
    """

    # Source specification
    root: str | Path

    # File filtering
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    max_depth: int | None = None

    # Tree view options
    enable_tree_view: bool = True

    # Format-specific options
    format_options: dict[str, dict] | None = None

    # Context file type options
    validate_on_load: bool = False
    respect_file_name: bool = False


@dataclass
class FileInfo:
    """Metadata about a file in the tree.

    Attributes
    ----------
    path : Path
        Full path from root.
    relative_path : str
        Relative path as string (used as key).
    size : int
        File size in bytes.
    last_modified : float
        Unix timestamp of last modification.
    is_symlink : bool
        Whether file is a symlink.
    symlink_target : Path | None
        Original path if symlink, None otherwise.

    Examples
    --------
    >>> from adaptexts.adapters.mixins import FileInfo
    >>> info = FileInfo(
    ...     path=Path("/root/data/file.cxt"),
    ...     relative_path="data/file.cxt",
    ...     size=1024,
    ...     last_modified=1678900000.0,
    ...     is_symlink=False,
    ...     symlink_target=None,
    ... )
    """

    path: Path
    relative_path: str
    size: int
    last_modified: float
    is_symlink: bool
    symlink_target: Path | None


class HasTreeRoot(Protocol):
    """Protocol for objects that provide _ensure_tree_available() method.

    This protocol is used to indicate that FileTreeMixin expects
    _ensure_tree_available() to be provided by another class in the MRO.
    """

    _tree_root: Path | None

    def _ensure_tree_available(self) -> Path:
        """Ensure the tree is available and return the root path."""
        ...


class FileTreeMixin:
    """Mixin providing file tree traversal and key enumeration.

    This mixin adds:
    - File tree traversal with glob pattern filtering
    - keys() method that yields relative file paths
    - Tree view generation (hierarchical structure)
    - File metadata via get_file_info()
    - Symlink following with path tracking
    - OS-native case sensitivity for patterns

    Requires:
    - A parent class providing _ensure_tree_available() method
    - _tree_root attribute to cache the tree location

    Examples
    --------
    >>> from adaptexts.adapters.mixins import FileTreeMixin
    >>>
    >>> class MyAdapter(FileTreeMixin, AdapterInterface):
    ...     def __init__(self, root_path, file_tree_config=None):
    ...         super().__init__(file_tree_config=file_tree_config or FileTreeConfig(
    ...             root=root_path
    ...         ))
    ...
    ...     def _ensure_tree_available(self) -> Path:
    ...         if self._tree_root is None:
    ...             self._tree_root = Path(self._file_tree_config.root)
    ...         return self._tree_root
    """

    def __init__(self, *args, file_tree_config: FileTreeConfig | None = None, **kwargs):
        """Initialize file tree mixin.

        Parameters
        ----------
        file_tree_config : FileTreeConfig | None
            Configuration for the file tree behavior.
        """
        super().__init__(*args, **kwargs)
        if file_tree_config is None:
            file_tree_config = FileTreeConfig(root=".")
        self._file_tree_config = file_tree_config
        self._tree_root: Path | None = None

    def __len__(self) -> int:
        """Return the number of files matching the filters.

        Returns
        -------
        int
            Number of files in the tree that match include/exclude patterns.
        """
        return sum(1 for _ in self.keys())

    def is_sortable(self) -> bool:
        """Indicate whether the adapter supports deterministic sorting.

        File systems provide deterministic file ordering, so sorting is supported.

        Returns
        -------
        bool
            Always True for file tree adapters.
        """
        return True

    def keys(self) -> Iterator[str]:
        """Generate cache keys for all files matching filters.

        Keys are relative paths from root with full file extension.
        Preserves directory hierarchy to avoid key collisions.

        Key Generation Rules
        --------------------
        Keys are generated as:
            1. Get relative path: path.relative_to(root)
            2. Normalize to forward slashes
            3. Keep full file extension (no stripping)

        Examples
        --------
        >>> # Assuming adapter with files:
        >>> # repo/data/file1.cxt -> "data/file1.cxt"
        >>> # repo/data/file2.csv -> "data/file2.csv"
        >>> # repo/test/file1.cxt -> "test/file1.cxt"
        >>> # repo/.hidden.cxt -> ".hidden.cxt"
        >>> keys = list(adapter.keys())

        Collision Avoidance
        -------------------
        Full relative paths with extensions prevent key collisions:
            repo/data/file1.cxt  -> "data/file1.cxt"
            repo/test/file1.cxt  -> "test/file1.cxt"  # Different keys

        Yields
        ------
        str
            Cache key for each matching file (includes extension).
        """
        root = self._ensure_tree_available()  # type: ignore[attr-defined]
        max_depth = self._file_tree_config.max_depth

        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue

            # Check depth
            if max_depth is not None:
                rel_path = file_path.relative_to(root)
                if len(rel_path.parts) > max_depth:
                    continue

            # Generate key: full relative path with extension
            rel_path = file_path.relative_to(root)
            key = str(rel_path).replace(os.path.sep, "/")

            if self._matches_include(key):
                if not self._matches_exclude(key):
                    yield key

    def get_tree_view(self) -> dict:
        """Get hierarchical representation of the file tree.

        Returns structure only (no metadata). Use get_file_info() for details.

        Returns
        -------
        dict
            Nested dictionary representing directory structure.
            Example: {"data": {"file1.cxt": {}, "file2.cxt": {}}, "root.cxt": {}}

        Examples
        --------
        >>> tree = adapter.get_tree_view()
        >>> # {"data": {"file1.cxt": {}, "file2.cxt": {}}, "root.cxt": {}}
        >>> print(tree["data"]["file1.cxt"])
        {}
        """
        self._ensure_tree_available()  # type: ignore[attr-defined]
        tree = {}

        for key in self.keys():
            parts = key.split("/")
            current = tree

            for i, part in enumerate(parts):
                if i == len(parts) - 1:  # File
                    current[part] = {}
                else:  # Directory
                    if part not in current:
                        current[part] = {}
                    current = current[part]

        return tree

    def filter_files(self, patterns: list[str]) -> Iterator[str]:
        """Yield keys for files matching additional patterns.

        Parameters
        ----------
        patterns : list[str]
            Glob patterns to match.

        Yields
        ------
        str
            Keys matching the patterns.

        Examples
        --------
        >>> # Filter for specific files
        >>> for key in adapter.filter_files(["**/test_*.cxt"]):
        ...     print(key)
        "data/test_context.cxt"
        """
        for key in self.keys():
            for pattern in patterns:
                # Simple glob matching
                if Path(key).match(pattern):
                    yield key
                    break

    def get_file_info(self, key: str) -> FileInfo:
        """Get metadata about a file (path, size, last modified, etc.).

        Parameters
        ----------
        key : str
            Cache key (relative path).

        Returns
        -------
        FileInfo
            File metadata.

        Raises
        ------
        FileNotFoundError
            If no file found for the given key.

        Examples
        --------
        >>> info = adapter.get_file_info("data/file1.cxt")
        >>> print(info.path)
        /path/to/root/data/file1.cxt
        >>> print(info.size)
        1024
        >>> print(info.is_symlink)
        False
        """
        root = self._ensure_tree_available()  # type: ignore[attr-defined]
        file_path = root / key.replace("/", "/")

        if not file_path.exists():
            raise FileNotFoundError(f"No file found for key '{key}'")

        stat = file_path.stat()
        is_symlink = file_path.is_symlink()
        symlink_target = Path(file_path.readlink()) if is_symlink else None

        return FileInfo(
            path=file_path,
            relative_path=key,
            size=stat.st_size,
            last_modified=stat.st_mtime,
            is_symlink=is_symlink,
            symlink_target=symlink_target,
        )

    # Helper methods (private)
    def _matches_include(self, key: str) -> bool:
        """Check if key matches include patterns.

        Parameters
        ----------
        key : str
            Cache key to check.

        Returns
        -------
        bool
            True if key matches any include pattern or if no patterns configured.
        """
        if not self._file_tree_config.include_patterns:
            return True

        for pattern in self._file_tree_config.include_patterns:
            # Convert ** to * for fnmatch since keys are already relative paths
            # and fnmatch doesn't treat ** specially
            normalized_pattern = pattern.replace("**/", "*").replace("**", "*")
            if fnmatch.fnmatch(key, normalized_pattern):
                return True
        return False

    def _matches_exclude(self, key: str) -> bool:
        """Check if key matches exclude patterns.

        Parameters
        ----------
        key : str
            Cache key to check.

        Returns
        -------
        bool
            True if key matches any exclude pattern.
        """
        for pattern in self._file_tree_config.exclude_patterns:
            normalized_pattern = pattern.replace("**/", "*").replace("**", "*")
            if fnmatch.fnmatch(key, normalized_pattern):
                return True
        return False
