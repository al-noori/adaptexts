"""Cache path resolution utilities using data-home package.

This module provides cache directory management using the data-home package,
which offers cross-platform cache directories with environment variable support.

Cache directory resolution priority:
1. disk_cache_dir in CacheConfig (explicit path)
2. {ADAPTER_NAME}_DATA environment variable
3. Platform-specific cache directory via platformdirs

Environment Variables:
    {ADAPTER_NAME}_DATA: Override cache for specific adapter
    ADAPTERS_DATA: Global override for all adaptexts caches
    ADAPTEXTS_DATA: Alternative global override for all adaptexts caches
"""

import logging

from pathlib import Path
from typing import Optional

from data_home import data_home_factory, get_data_home

logger = logging.getLogger(__name__)


# get_data_home, clear_data_home = data_home_factory("adaptexts")
# from data_home import data_home_factory


def get_cache_dir(
    *,
    adapter_name: str,
    identifier: Optional[str] = None,
) -> Path:
    """Get cache directory for an adapter using data-home package.

    Parameters
    ----------
    adapter_name : str
        Name of the adapter (e.g., "git_adapter", "ipcadapter").
    identifier : str, optional
        Stable identifier for the data source (e.g., repo name, dataset name).
        Creates nested directory structure: {adapter_name}/{identifier}.

    Returns
    -------
    pathlib.Path
        Path to the adapter-specific cache directory.

    Examples
    --------
    >>> get_cache_dir(adapter_name="test_adapter")
    PosixPath('/home/user/.cache/adaptexts/test_adapter')

    >>> get_cache_dir(adapter_name="test_adapter", identifier="dataset_v1")
    PosixPath('/home/user/.cache/adaptexts/test_adapter/dataset_v1')
    """
    import os

    # Check for adapter-specific environment variable override first
    env_var_name = f"{adapter_name.upper()}_DATA"
    if env_var_name in os.environ:
        base_path = Path(os.environ[env_var_name])
        logger.debug(f"Using environment variable {env_var_name}: {base_path}")
    else:
        # Use the adaptexts namespace
        base_path = get_data_home(data_home_key="adaptexts") / adapter_name

    if identifier:
        cache_dir = base_path / identifier
    else:
        cache_dir = base_path

    cache_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Cache directory for {adapter_name}: {cache_dir}")
    return cache_dir


def get_default_cache_dir() -> Path:
    """Get the default adaptexts cache directory.

    Returns
    -------
    Path
        Path to the default adaptexts cache directory.

    Examples
    --------
    >>> get_default_cache_dir()
    PosixPath('/home/user/.cache/adaptexts')
    """
    return get_data_home(data_home_key="adaptexts")


def clear_adapter_cache(
    *,
    adapter_name: Optional[str] = None,
    identifier: Optional[str] = None,
) -> None:
    """Clear cache for an adapter or all adapters.

    Parameters
    ----------
    adapter_name : str, optional
        Name of the adapter to clear.
    identifier : str, optional
        Specific identifier to clear.

    Examples
    --------
    >>> clear_adapter_cache()  # Clear all
    >>> clear_adapter_cache(adapter_name="ipcadapter")
    >>> clear_adapter_cache(adapter_name="ipcadapter", identifier="n=5")
    """
    import os
    import shutil

    # Check for adapter-specific environment variable override
    if adapter_name is not None:
        env_var_name = f"{adapter_name.upper()}_DATA"
        if env_var_name in os.environ:
            adapter_cache_dir = Path(os.environ[env_var_name])
        else:
            # Use adaptexts namespace
            adaptables_base = get_data_home(data_home_key="adaptexts")
            adapter_cache_dir = adaptables_base / adapter_name
    else:
        # No adapter specified - check for global overrides
        if "ADAPTERS_DATA" in os.environ:
            global_cache_dir = Path(os.environ["ADAPTERS_DATA"])
            if global_cache_dir.exists():
                shutil.rmtree(global_cache_dir)
            return
        elif "ADAPTEXTS_DATA" in os.environ:
            global_cache_dir = Path(os.environ["ADAPTEXTS_DATA"])
            if global_cache_dir.exists():
                shutil.rmtree(global_cache_dir)
            return
        else:
            # Clear all adaptexts caches
            adaptables_base = get_data_home(data_home_key="adaptexts")
            if adaptables_base.exists():
                shutil.rmtree(adaptables_base)
            return

    if identifier is None:
        if adapter_cache_dir.exists():
            shutil.rmtree(adapter_cache_dir)
    else:
        cache_dir = adapter_cache_dir / identifier
        if cache_dir.exists():
            shutil.rmtree(cache_dir)


def create_cache_factory(adapter_name: str):
    """Create a cache factory for a specific adapter.

    Parameters
    ----------
    adapter_name : str
        Name of the adapter.

    Returns
    -------
    tuple
        (get_cache, clear_cache) functions for the adapter.

    Examples
    --------
    >>> get_ipc_cache, clear_ipc_cache = create_cache_factory("ipcadapter")
    >>> cache_dir = get_ipc_cache(identifier="n=5")
    >>> clear_ipc_cache()
    """
    return data_home_factory(adapter_name)


def get_cache_size(cache_dir: Path) -> int:
    """Calculate total size of a cache directory.

    Parameters
    ----------
    cache_dir : Path
        Path to the cache directory.

    Returns
    -------
    int
        Total size in bytes.
    """
    if not cache_dir.exists():
        return 0

    total_size = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file())
    return total_size


def validate_cache_consistency(cache_dir: Path) -> bool:
    """Validate cache consistency by checking for orphaned files.

    A cache is consistent if .cache and .meta files match.

    Parameters
    ----------
    cache_dir : Path
        Path to the cache directory.

    Returns
    -------
    bool
        True if cache is consistent, False otherwise.
    """
    if not cache_dir.exists():
        return True

    cache_files = set(f.stem for f in cache_dir.glob("*.cache"))
    meta_files = set(f.stem for f in cache_dir.glob("*.meta"))

    return cache_files == meta_files
