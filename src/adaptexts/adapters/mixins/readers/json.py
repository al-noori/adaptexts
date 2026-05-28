"""Reader for JSON format context files.

This module defines the JSONReaderMixin, which can parse JSON files
and convert them to binary or many-valued contexts.
"""

import json

from pathlib import Path
from typing import Union

from adaptexts.context import Context
from adaptexts.many_valued_context import ManyValuedContext

from ...exceptions import ContextParseError
from .base import ContextFileReaderMixin


class JSONReaderMixin(ContextFileReaderMixin):
    """Reader for JSON format context files.

    Supports both binary and many-valued contexts with explicit type field.

    Example JSON (Binary Context)
    -----------------------------
    {
      "type": "Context",
      "name": "example",
      "objects": ["o1", "o2"],
      "attributes": ["a1", "a2"],
      "incidence": [["o1", "a1"], ["o2", "a2"]]
    }

    Example JSON (Many-Valued Context)
    ----------------------------------
    {
      "type": "ManyValuedContext",
      "name": "example",
      "objects": ["o1", "o2"],
      "attributes": ["a1", "a2"],
      "incidence": [["o1", "a1", "value1"], ["o2", "a2", "value2"]]
    }

    Format Options
    --------------
    Configure via FileTreeConfig.format_options:

        format_options={
            "json": {
                "encoding": "utf-8",
            }
        }

    Default Format Options
    ----------------------
    - encoding: "utf-8"

    Examples
    --------
    Cached variant:
        >>> from adaptexts.adapters.git_repo import GitAdapter
        >>> from adaptexts.adapters.readers import JSONReaderMixin
        >>> from adaptexts.adapters.caching import CacheableAdapter
        >>>
        >>> class CachedGitJSONAdapter(CacheableAdapter, JSONReaderMixin, GitAdapter):
        ...     pass
        >>>
        >>> adapter = CachedGitJSONAdapter("https://github.com/user/repo.git")
        >>> for context in adapter:
        ...     print(context.name)

    Uncached variant:
        >>> class GitJSONAdapter(JSONReaderMixin, GitAdapter):
        ...     pass
        >>>
        >>> adapter = GitJSONAdapter("https://github.com/user/repo.git")
        >>> for context in adapter:
        ...     print(context.name)
    """

    def get_supported_extensions(self) -> tuple[str, ...]:
        """Return supported JSON file extensions.

        Returns
        -------
        tuple[str, ...]
            Tuple containing ".json" extension.
        """
        return (".json",)

    def can_handle_file(self, file_path: Path) -> bool:
        """Check if this is a JSON file.

        Parameters
        ----------
        file_path : Path
            Path to the file to check.

        Returns
        -------
        bool
            True if the file has .json extension.
        """
        return file_path.suffix.lower() == ".json"

    def _load_context(self, key: str) -> Union[Context, ManyValuedContext]:
        """Load a JSON file and return a context.

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
            If file cannot be parsed or contains invalid data or unknown type.
        FileNotFoundError
            If file doesn't exist.
        """
        # This mixin relies on FileTreeAdapter or subclass providing _ensure_tree_available()
        root = self._ensure_tree_available()  # type: ignore[attr-defined]
        file_path = root / key.replace("/", "/")

        if not file_path.exists():
            raise FileNotFoundError(f"File not found for key '{key}': {file_path}")

        # Get format options
        options = self._get_format_options()
        encoding = options.get("encoding", "utf-8")

        try:
            content = file_path.read_text(encoding=encoding)
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ContextParseError("JSON", file_path, e) from e
        except Exception as e:
            raise ContextParseError("JSON", file_path, e) from e

        # Determine context type from JSON
        ctx_type = data.get("type")
        if ctx_type == "Context":
            context = Context.from_json(content)
            context.name = key
            return context
        elif ctx_type == "ManyValuedContext":
            context = ManyValuedContext.from_json(content)
            context.name = key
            return context
        else:
            raise ContextParseError(
                "JSON",
                file_path,
                ValueError(
                    f"Unknown context type '{ctx_type}'. Expected 'Context' or 'ManyValuedContext'"
                ),
            )
