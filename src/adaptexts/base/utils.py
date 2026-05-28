"""Utility functions for context adapter and FCA processing.

This module provides helper functions for:
- tokenizing structured strings
- extracting feature names from filenames

Note: ConExp-related utilities have been moved to adaptexts.tools.scaling.utils
Note: make_hashable has been moved to base.formats.base_mixin
"""

from dataclasses import fields
from pathlib import Path
from typing import List


def tokenize(s: str) -> List[str]:
    """Tokenize a string while respecting bracketed and quoted substrings.

    Tokens are split on whitespace unless the whitespace occurs inside
    brackets or quotes.

    Parameters
    ----------
    s : str
        Input string.

    Returns
    -------
    list[str]
        List of extracted tokens.

    Notes
    -----
    Unpaired brackets are included in tokens unmodified. Nested brackets are
    not nested in token output (flattened). Empty strings between consecutive
    whitespace are skipped.

    """
    tokens: List[str] = []
    buf: List[str] = []

    stack: List[str] = []
    pairs = {"]": "[", ")": "(", '"': '"'}

    i = 0
    while i < len(s):
        c = s[i]

        if c in '[("':
            stack.append(c)
            buf.append(c)

        elif c in '])"':
            if stack and stack[-1] == pairs[c]:
                stack.pop()
            buf.append(c)

        elif c.isspace() and not stack:
            if buf:
                tokens.append("".join(buf))
                buf.clear()

        else:
            buf.append(c)

        i += 1

    if buf:
        tokens.append("".join(buf))

    return tokens


def feats_from_filename(p: str, path: Path) -> set[str]:
    """Extract feature names from a filename.

    Parses a filename to extract comma-separated feature names after a
    given prefix.

    Parameters
    ----------
    p : str
        Prefix marker (e.g., "feats") that appears immediately before
        the feature list in the filename (format: "<prefix>=<feat1,feat2,...>").
    path : Path
        Path to the file.

    Returns
    -------
    set[str]
        Set of feature names extracted from the filename stem.
        Returns empty set if the prefix is not found.

    """
    prefix = p + "="
    stem = path.stem
    if not stem.startswith(prefix):
        return set()
    return set(stem[len(prefix) :].split(","))


def truncated_repr(obj, max_items=5):
    def format_value(value):
        if isinstance(value, set):
            value = list(value)
        if isinstance(value, (list, tuple)):
            if len(value) > max_items:
                return f"{value[:max_items]}... (total {len(value)})"
        return repr(value)

    cls_name = obj.__class__.__name__
    parts = []

    for f in fields(obj):
        val = getattr(obj, f.name)
        parts.append(f"{f.name}={format_value(val)}")

    return f"{cls_name}({', '.join(parts)})"
