"""Exceptions for adaptexts.

This module provides domain-specific exception classes for error handling
throughout the adaptexts package.
"""


class AdaptextsError(Exception):
    """Base exception for all adaptexts errors.

    This is the root exception class for the adaptexts package. All
    other exceptions inherit from this class.
    """

    pass


class ContextFormatError(AdaptextsError):
    """Raised when context parsing fails.

    This exception is raised when attempting to parse a context from
    a file format (e.g., Burmeister, Colibri) and the content does not
    conform to the expected format structure.
    """

    pass


class RepositoryError(AdaptextsError):
    """Raised when repository access fails.

    This exception is raised when operations on a git repository fail,
    including invalid URLs, clone failures, checkout errors, or file
    access issues within the repository.
    """

    pass



class ScaleError(AdaptextsError):
    """Raised when scaling operation fails.

    This exception is raised when scaling a many-valued context fails,
    such as when an invalid scale type is specified or when the scale
    parameters are incorrect.
    """

    pass
