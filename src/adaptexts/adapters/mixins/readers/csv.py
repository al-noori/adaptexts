"""Reader for CSV format context files.

This module defines the CSVReaderMixin, which can parse CSV files
and convert them to binary or many-valued contexts.
"""

from pathlib import Path
from typing import Union

from adaptexts.context import Context
from adaptexts.many_valued_context import ManyValuedContext

from ...exceptions import ContextParseError
from .base import ContextFileReaderMixin


class CSVReaderMixin(ContextFileReaderMixin):
    """Reader for CSV format context files.

    Supports both binary and many-valued contexts through Context.from_df().
    Binary detection: checks if unique values in DataFrame are {0, 1} or {True, False}.

    Supported Features
    ------------------
    - Binary contexts (0/1 or True/False values)
    - Many-valued contexts (any values)
    - Configurable delimiter via format_options
    - UTF-8 encoding

    Format Options
    --------------
    Configure via FileTreeConfig.format_options:

        format_options={
            "csv": {
                "delimiter": ",",
                "encoding": "utf-8",
                "header": 0,
            }
        }

    Default Format Options
    ----------------------
    - delimiter: ","
    - encoding: "utf-8"
    - header: 0

    Dependency
    ----------
    Requires pandas for CSV parsing.

    Examples
    --------
    Cached variant:
        >>> from adaptexts.adapters.git_repo import GitAdapter
        >>> from adaptexts.adapters.readers import CSVReaderMixin
        >>> from adaptexts.adapters.caching import CacheableAdapter
        >>>
        >>> class CachedGitCSVAdapter(CacheableAdapter, CSVReaderMixin, GitAdapter):
        ...     pass
        >>>
        >>> adapter = CachedGitCSVAdapter("https://github.com/user/repo.git")
        >>> for context in adapter:
        ...     print(context.name)

    Uncached variant:
        >>> class GitCSVAdapter(CSVReaderMixin, GitAdapter):
        ...     pass
        >>>
        >>> adapter = GitCSVAdapter("https://github.com/user/repo.git")
        >>> for context in adapter:
        ...     print(context.name)
    """

    def get_supported_extensions(self) -> tuple[str, ...]:
        """Return supported CSV file extensions.

        Returns
        -------
        tuple[str, ...]
            Tuple containing ".csv" extension.
        """
        return (".csv",)

    def can_handle_file(self, file_path: Path) -> bool:
        """Check if this is a CSV file.

        Parameters
        ----------
        file_path : Path
            Path to the file to check.

        Returns
        -------
        bool
            True if the file has .csv extension.
        """
        return file_path.suffix.lower() == ".csv"

    def _load_context(self, key: str) -> Union[Context, ManyValuedContext]:
        """Load a CSV file and return a context.

        Parameters
        ----------
        key : str
            Cache key (relative path).

        Returns
        -------
        Union[Context, ManyValuedContext]
            Parsed context (type auto-detected).

        Raises
        ------
        ImportError
            If pandas is not installed.
        ContextParseError
            If file cannot be parsed or contains invalid data.
        FileNotFoundError
            If file doesn't exist.
        """
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError(
                "pandas is required for CSV parsing. Install with: pip install pandas"
            ) from e

        # This mixin relies on FileTreeAdapter or subclass providing _ensure_tree_available()
        root = self._ensure_tree_available()  # type: ignore[attr-defined]
        file_path = root / key.replace("/", "/")

        if not file_path.exists():
            raise FileNotFoundError(f"File not found for key '{key}': {file_path}")

        # Get format options
        kwargs: dict = {"index_col": 0}  # Default

        options = self._get_format_options()
        if "delimiter" in options:
            kwargs["sep"] = options["delimiter"]
        else:
            kwargs["sep"] = ","  # Explicit default

        if "encoding" in options:
            kwargs["encoding"] = options["encoding"]
        else:
            kwargs["encoding"] = "utf-8"  # Explicit default

        if "header" in options:
            kwargs["header"] = options["header"]
        else:
            kwargs["header"] = 0  # Explicit default

        try:
            df = pd.read_csv(file_path, **kwargs)
            context = Context.from_df(df)
            context.name = key
            return context
        except Exception as e:
            raise ContextParseError("CSV", file_path, e) from e
