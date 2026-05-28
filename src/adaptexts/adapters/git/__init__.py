"""Git repository adapters for the adaptexts library.

This subpackage provides adapters for accessing formal contexts from Git
repositories. All adapters follow the FileTreeAdapter pattern with support for
multiple formats.

Base Adapter
------------
- GitAdapter: Base adapter for Git repositories (format-agnostic)

Format-Specific Adapters
-------------------------
Burmeister (.cxt):
- GitBurmeisterAdapter

Usage Examples
--------------
>>> # Base adapter (format-agnostic)
>>> from adaptexts.adapters.git import GitAdapter
>>> adapter = GitAdapter("https://github.com/fcatools/contexts.git")
>>> for file_info in adapter:
...     print(file_info.path)

>>> # Burmeister format
>>> from adaptexts.adapters.git import GitBurmeisterAdapter
>>> adapter = GitBurmeisterAdapter("https://github.com/fcatools/contexts.git")
>>> for context in adapter:
...     print(context.name)
"""

from .base import GitAdapter
from .burmeister import GitBurmeisterAdapter

__all__ = ["GitAdapter", "GitBurmeisterAdapter"]
