import hashlib
import json

from logging import getLogger
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd

from adaptexts.exceptions import ScaleError
from conexp_clj_py import ConexpContext
from conexp_clj_py.api.fca.many_valued_contexts import (
    biordinal_scale,
    dichotomic_scale,
    interordinal_scale,
    interval_scale,
    nominal_scale,
    ordinal_scale,
)

if TYPE_CHECKING:
    from adaptexts.many_valued_context import ManyValuedContext

logger = getLogger(__name__)


def infer_feature_scales(
    features: pd.DataFrame,
    variables: pd.DataFrame,
) -> Dict[str, Dict[str, Optional[str]]]:
    """
    Infer FCA scales for features based on variable metadata.

    Parameters
    ----------
    features : pandas.DataFrame
        Feature matrix.
    variables : pandas.DataFrame
        Variable metadata containing at least 'name' and 'type' columns.

    Returns
    -------
    dict
        Mapping from feature names to inferred scale specifications.
    """
    scales: Dict[str, Dict[str, Optional[str]]] = {}

    for _, row in variables.iterrows():
        feature = row["name"]
        if feature in features.columns:
            scales[feature] = {"name": infer_scale(row["type"])}

    return scales


def infer_scale(type: str) -> Optional[str]:
    """
    Infer an FCA scale name from a variable type

    Parameters
    ----------
    type : str
        Variable type (e.g. 'Categorical', 'Integer').

    Returns
    -------
    str or None
        Inferred scale name, or None if the type is unsupported.
    """
    match type:
        case "Categorical":
            return "nominal"
        case "Integer" | "Continuous":
            return "interordinal"
        case "Binary":
            return "dichotomic"
    return None


def infer_scale_map(mvc: "ManyValuedContext") -> dict[str, dict[str, Any]]:
    """Infer scale map from many-valued context values.

    Parameters
    ----------
    mvc : ManyValuedContext
        Many-valued context to analyze.

    Returns
    -------
    dict
        Mapping from attribute names to scale specifications.
    """
    from numbers import Number

    logger.info(
        f"Inferring scales for context '{mvc.name}' with {len(mvc.M)} attributes"
    )

    scale_map = {}
    for m in mvc.M:
        values = mvc.values_of_attribute(m)
        unique_values = set(values)
        n_unique = len(unique_values)
        n_total = len(values)
        unique_ratio = n_unique / n_total if n_total > 0 else 0

        if n_unique == 2:
            scale_map[m] = {"name": "dichotomic"}
            logger.debug(f"  Attribute '{m}': dichotomic (2 values)")
        elif all(isinstance(v, str) for v in unique_values):
            scale_map[m] = {"name": "nominal"}
            logger.debug(f"  Attribute '{m}': nominal (string values)")
        elif all(
            isinstance(v, Number) and not isinstance(v, bool) for v in unique_values
        ):
            if n_unique <= 10 or unique_ratio <= 0.05:
                scale_map[m] = {"name": "nominal"}
                logger.debug(f"  Attribute '{m}': nominal (numeric, {n_unique} unique)")
            else:
                scale_map[m] = {"name": "interordinal"}
                logger.debug(
                    f"  Attribute '{m}': interordinal (numeric, {n_unique} unique)"
                )
        else:
            scale_map[m] = {"name": "nominal"}
            logger.debug(f"  Attribute '{m}': nominal (mixed types)")

    logger.debug(f"Inferred scale map: {scale_map}")
    return scale_map


def hash_scale_map(scale_map: dict[str, dict[str, Any]]) -> str:
    """Generate a deterministic hash for a scale map.

    Parameters
    ----------
    scale_map : dict
        Mapping from attribute names to scale specifications.

    Returns
    -------
    str
        32-character hexadecimal hash (MD5) of the scale map.
    """
    logger.debug(f"Hashing scale map: {scale_map}")
    # Convert to sorted JSON string for deterministic hashing
    sorted_json = json.dumps(scale_map, sort_keys=True)
    hash_value = hashlib.md5(sorted_json.encode()).hexdigest()
    logger.debug(f"Hash result: {hash_value}")
    return hash_value


def create_scale_context(
    client, scale_type: str, values: List[Any], **kwargs
) -> ConexpContext:
    """Create a scale context using conexp-clj-py API.

    Parameters
    ----------
    client : ConexpClient
        The conexp-clj-py client instance.
    scale_type : str
        Scale type: 'nominal', 'ordinal', 'interordinal', 'biordinal', 'interval', 'dichotomic'
    values : list
        Attribute values to scale.
    **kwargs
        Additional parameters for the scale type.

    Returns
    -------
    ConexpContext
        The scale context.

    Raises
    ------
    ScaleError
        If scale type is unknown.
    """

    # Normalize scale_type (remove -scale suffix if present)
    if scale_type.endswith("_scale"):
        scale_type = scale_type.removesuffix("_scale")
    elif scale_type.endswith("-scale"):
        scale_type = scale_type.removesuffix("-scale")

    # Convert values to strings for API
    value_strs = [str(v) for v in values]
    value_strs = values

    # Map scale types to API calls
    if scale_type == "nominal":
        others = kwargs.get("others")
        if others is None:
            result = nominal_scale(client, value_strs)
        else:
            result = nominal_scale(
                client,
                value_strs,
                others,
            )

    elif scale_type == "ordinal":
        others = kwargs.get("others")
        if others is None:
            result = ordinal_scale(client, value_strs)
        else:
            result = ordinal_scale(
                client,
                value_strs,
                None,
                others,
            )

    elif scale_type == "interordinal":
        others = kwargs.get("others")
        if others is None:
            result = interordinal_scale(client, value_strs)
        else:
            result = interordinal_scale(
                client,
                value_strs,
                None,
                None,
                others,
            )

    elif scale_type == "biordinal":
        n = kwargs.get("n", len(values))
        others = kwargs.get("others")
        if others is None:
            # biordinal requires n parameter
            result = biordinal_scale(client, value_strs, n)
        else:
            result = biordinal_scale(
                client,
                value_strs,
                n,
                others,
            )

    elif scale_type == "interval":
        others = kwargs.get("others")
        if others is None:
            result = interval_scale(client, value_strs)
        else:
            result = interval_scale(
                client,
                value_strs,
                others,
            )

    elif scale_type == "dichotomic":
        if len(values) != 2:
            raise ValueError(
                f"Dichotomic scale requires exactly 2 values, got {len(values)}"
            )
        result = dichotomic_scale(client, value_strs)

    else:
        raise ScaleError(f"Unknown scale type: {scale_type}")

    return result
