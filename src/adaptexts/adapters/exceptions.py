"""Adapter-specific exceptions.

This module defines the exception hierarchy used by the adapter system.
Exceptions are organized into:
- AdapterError and subclasses: For failures in accessing/download data sources
- ContextParseError: For failures in parsing context files

Design Notes
------------
The exception hierarchy separates concerns:
- AdapterError and its subclasses are raised when a source cannot be accessed
  or downloaded (SourceNotFoundError, DownloadError, AccessError, ValidationError)
- ContextParseError is raised by format readers when a file exists but cannot be
  parsed correctly
"""

from pathlib import Path


class AdapterError(Exception):
    """Base exception for all adapter-related errors.

    Users can catch this exception to handle any adapter failure, or catch
    specific subclasses for more granular error handling.

    Examples
    --------
    >>> try:
    ...     for context in adapter:
    ...         print(context.name)
    ... except AdapterError as e:
    ...     print(f"Adapter error: {e}")
    """


class SourceNotFoundError(AdapterError):
    """Raised when a data source cannot be found or accessed.

    Examples:
    - Git repository URL is invalid or doesn't exist
    - DOI is invalid or not found on Zenodo
    - Local directory does not exist
    """


class DownloadError(AdapterError):
    """Raised when downloading a source fails.

    Examples:
    - Network connection fails or times out
    - HTTP request returns error status
    - Download is interrupted
    - Downloaded file is corrupted or invalid
    """


class AccessError(AdapterError):
    """Raised when authentication or permission is denied.

    Examples:
    - Git repository requires authentication and no credentials provided
    - API token is invalid or expired
    - Filesystem permissions prevent reading/writing
    """


class ValidationError(AdapterError):
    """Raised when downloaded or cached data is invalid.

    Examples:
    - Downloaded archive is corrupted
    - File tree structure is unexpected
    - Required files are missing
    """


class ContextParseError(ValueError):
    """Raised when a context file cannot be parsed.

    Note: This is distinct from AdapterError - ContextParseError is raised
    by format readers when a file exists but cannot be parsed correctly.
    AdapterError and its subclasses are raised when the source cannot be
    accessed or downloaded.

    Attributes
    ----------
    format_name : str
        The format name (e.g., "Burmeister", "CSV", "JSON").
    file_path : Path
        Path to the file that failed to parse.
    original_error : Exception
        The original exception that caused the parse error.
    """

    def __init__(
        self,
        format_name: str,
        file_path: Path,
        original_error: Exception,
    ):
        """Initialize ContextParseError.

        Parameters
        ----------
        format_name : str
            The format name (e.g., "Burmeister", "CSV", "JSON").
        file_path : Path
            Path to the file that failed to parse.
        original_error : Exception
            The original exception that caused the parse error.
        """
        self.format_name = format_name
        self.file_path = file_path
        self.original_error = original_error
        super().__init__(
            f"Failed to parse {format_name} file {file_path}: {original_error}"
        )