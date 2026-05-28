"""UCI Machine Learning Repository adapter.

Fetch logic based on https://github.com/uci-ml-repo/ucimlrepo
"""

import hashlib
import json
import logging
import pickle
import ssl
import urllib.parse
import urllib.request

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from urllib.error import HTTPError, URLError

import certifi

from adaptexts.base.cache import CacheConfig
from adaptexts.many_valued_context import ManyValuedContext
from data_home import data_home_factory
from dateparser import parse as parse_date
from pandas import DataFrame, concat, read_csv

from ...interface import AdapterInterface
from ...mixins import CacheIterationMixin

get_data_home, clear_data_home = data_home_factory("uciml-archive")

logger = logging.getLogger(__name__)


def _urlopen(url: str) -> Any:
    """Open a URL with SSL cert verification, falling back to unverified on expired certs."""
    ctx = ssl.create_default_context(cafile=certifi.where())
    try:
        return urllib.request.urlopen(url, context=ctx)
    except URLError as e:
        if not isinstance(e.reason, ssl.SSLCertVerificationError):
            raise
        logger.warning("SSL certificate verification failed for %s; retrying without verification", url)
        ctx_unverified = ssl.create_default_context()
        ctx_unverified.check_hostname = False
        ctx_unverified.verify_mode = ssl.CERT_NONE
        return urllib.request.urlopen(url, context=ctx_unverified)


API_BASE_URL = "https://archive.ics.uci.edu/api/dataset"
API_LIST_URL = "https://archive.ics.uci.edu/api/datasets/list"
DATASET_FILE_BASE_URL = "https://archive.ics.uci.edu/static/public"


class DatasetNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class AdditionalInfo:
    """Additional descriptive information about a dataset.

    Provides dict-like access via to_dict() method with typed fields.

    Attributes
    ----------
    summary : str
        Brief summary description of the dataset.
    variable_info : str
        Information about the variables/features in the dataset.
    citation : str | None
        Citation information for the dataset.
    funded_by : str | None
        Information about funding sources.
    instances_represent : str | None
        Description of what the instances represent.
    preprocessing_description : str | None
        Description of any preprocessing applied.
    purpose : str | None
        Purpose or intended use of the dataset.
    recommended_data_splits : str | None
        Recommended train/validation/test splits.
    sensitive_data : str | None
        Information about any sensitive data contained.
    """

    summary: str
    variable_info: str
    citation: str | None = None
    funded_by: str | None = None
    instances_represent: str | None = None
    preprocessing_description: str | None = None
    purpose: str | None = None
    recommended_data_splits: str | None = None
    sensitive_data: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "AdditionalInfo":
        return cls(**data)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class IntroPaper:
    """Metadata for the introductory paper of a dataset.

    Mirrors the JSON structure returned by the UCI API under the `intro_paper`
    key. All fields are optional because the API does not guarantee the presence
    of every attribute for every dataset.

    Provides dict-like access via to_dict() method with typed fields.

    Attributes
    ----------
    doi : str | None
        Digital object identifier.
    id : int | None
        Paper identifier.
    url : str | None
        URL to the paper.
    acl : str | None
        ACL identifier.
    arxiv : str | None
        arXiv identifier.
    authors : str | None
        Author names.
    corpus : str | None
        Corpus identifier.
    journal : str | None
        Journal name.
    mag : str | None
        Microsoft Academic Graph identifier.
    pmcid : str | None
        PubMed Central identifier.
    pmid : str | None
        PubMed identifier.
    sha : str | None
        SHA hash.
    title : str | None
        Paper title.
    type : str | None
        Paper type.
    venue : str | None
        Publication venue.
    year : int | None
        Year of publication.
    """

    doi: str | None = None
    id: int | None = None
    url: str | None = None
    acl: str | None = None
    arxiv: str | None = None
    authors: str | None = None
    corpus: str | None = None
    journal: str | None = None
    mag: str | None = None
    pmcid: str | None = None
    pmid: str | None = None
    sha: str | None = None
    title: str | None = None
    type: str | None = None
    venue: str | None = None
    year: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "IntroPaper":
        return cls(**{key.lower(): value for key, value in data.items()})

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class UCIMLMetadata:
    """Dataset metadata.

    Attributes
    ----------
    uci_id : int
        Unique UCI repository identifier for the dataset.
    name : str
        Name of the dataset.
    data_url : str
        URL to download the dataset data.
    abstract : str | None
        Abstract or description of the dataset.
    additional_info : AdditionalInfo | None
        Additional descriptive information about the dataset.
    area : str | None
        Research area or domain of the dataset.
    characteristics : list[str]
        List of dataset characteristics.
    creators : list[str]
        List of dataset creators.
    dataset_doi : str | None
        Digital object identifier for the dataset.
    demographics : list[str]
        List of demographic information.
    external_url : str | None
        External URL for the dataset.
    feature_types : list[str]
        List of feature types.
    has_missing_values : bool | None
        Whether the dataset has missing values.
    index_col : list[str]
        List of index column names.
    intro_paper : IntroPaper | None
        Metadata for the introductory paper.
    last_updated : datetime | None
        Last updated date of the dataset.
    missing_values_symbol : str | None
        Symbol used for missing values.
    num_features : int | None
        Number of features in the dataset.
    num_instances : int | None
        Number of instances in the dataset.
    repository_url : str | None
        URL to the dataset in the UCI repository.
    target_col : list[str]
        List of target column names.
    tasks : list[str]
        List of tasks the dataset can be used for.
    variables : DataFrame
        Variable metadata as a pandas DataFrame.
    year_of_dataset_creation : int | None
        Year the dataset was created.
    """

    uci_id: int
    name: str
    data_url: str
    abstract: str | None = None
    additional_info: AdditionalInfo | None = None
    area: str | None = None
    characteristics: list[str] | None = None
    creators: list[str] | None = None
    dataset_doi: str | None = None
    demographics: list[str] | None = None
    external_url: str | None = None
    feature_types: list[str] | None = None
    has_missing_values: bool | None = None
    index_col: list[str] | None = None
    intro_paper: IntroPaper | None = None
    last_updated: datetime | None = None
    missing_values_symbol: str | None = None
    num_features: int | None = None
    num_instances: int | None = None
    repository_url: str | None = None
    target_col: list[str] | None = None
    tasks: list[str] | None = None
    variables: DataFrame | None = None
    year_of_dataset_creation: int | None = None

    @classmethod
    def from_dict(cls, data: dict, detailed=True) -> "UCIMLMetadata":
        """Create Metadata instance from API response dictionary.

        Handles type conversions for boolean, integer, date fields, and nested
        data structures.

        Parameters
        ----------
        data : dict
            Raw metadata dictionary from the UCI API.

        Returns
        -------
        Metadata
            New Metadata instance with parsed and converted fields.

        Raises
        ------
        ValueError
            If `has_missing_values` contains an invalid value or if unknown
            fields are present in the API response.
        """
        if not detailed:
            return cls(**data)

        metadata_fields = data.copy()

        additional_info = metadata_fields.get("additional_info")
        if additional_info is not None:
            metadata_fields["additional_info"] = AdditionalInfo.from_dict(
                additional_info
            )

        has_missing_values = metadata_fields.get("has_missing_values")
        if has_missing_values is not None:
            bool_map = {"yes": True, "no": False}
            if has_missing_values not in bool_map:
                raise ValueError(f"{has_missing_values=}")
            metadata_fields["has_missing_values"] = bool_map[has_missing_values]

        intro_paper = metadata_fields.get("intro_paper")
        if intro_paper is not None:
            metadata_fields["intro_paper"] = IntroPaper.from_dict(intro_paper)

        last_updated = metadata_fields.get("last_updated")
        if last_updated is not None:
            metadata_fields["last_updated"] = parse_date(last_updated)

        int_fields = [
            "num_features",
            "num_instances",
            "year_of_dataset_creation",
        ]
        for field_name in int_fields:
            if (value := metadata_fields.get(field_name)) is not None:
                metadata_fields[field_name] = int(value)

        # Handle optional variables field
        if "variables" in metadata_fields:
            metadata_fields["variables"] = DataFrame(metadata_fields["variables"])

        known_fields = {
            "uci_id",
            "name",
            "data_url",
            "abstract",
            "additional_info",
            "area",
            "characteristics",
            "creators",
            "dataset_doi",
            "demographics",
            "external_url",
            "feature_types",
            "has_missing_values",
            "index_col",
            "intro_paper",
            "last_updated",
            "missing_values_symbol",
            "num_features",
            "num_instances",
            "repository_url",
            "target_col",
            "tasks",
            "variables",
            "year_of_dataset_creation",
        }

        unknown_fields = set(metadata_fields.keys()) - known_fields
        if unknown_fields:
            raise ValueError(
                f"Unknown fields in API response: {unknown_fields}. "
                f"These fields are not recognized by the Metadata class."
            )

        return cls(**metadata_fields)

    def to_dict(self) -> dict:
        """Convert Metadata instance to dictionary format.

        This method serializes the Metadata instance back to a dictionary
        format compatible with Metadata.from_dict() for round-trip serialization.

        Returns
        -------
        dict
            Dictionary representation of the metadata instance.
        """
        dict_data: dict[str, Any] = {
            "uci_id": self.uci_id,
            "name": self.name,
            "data_url": self.data_url,
        }

        if self.abstract is not None:
            dict_data["abstract"] = self.abstract
        if self.area is not None:
            dict_data["area"] = self.area
        if self.characteristics:
            dict_data["characteristics"] = self.characteristics
        if self.creators:
            dict_data["creators"] = self.creators
        if self.dataset_doi is not None:
            dict_data["dataset_doi"] = self.dataset_doi
        if self.demographics:
            dict_data["demographics"] = self.demographics
        if self.external_url is not None:
            dict_data["external_url"] = self.external_url
        if self.feature_types:
            dict_data["feature_types"] = self.feature_types
        if self.has_missing_values is not None:
            dict_data["has_missing_values"] = self.has_missing_values
        if self.index_col:
            dict_data["index_col"] = self.index_col
        if self.missing_values_symbol is not None:
            dict_data["missing_values_symbol"] = self.missing_values_symbol
        if self.num_features is not None:
            dict_data["num_features"] = self.num_features
        if self.num_instances is not None:
            dict_data["num_instances"] = self.num_instances
        if self.repository_url is not None:
            dict_data["repository_url"] = self.repository_url
        if self.target_col:
            dict_data["target_col"] = self.target_col
        if self.tasks:
            dict_data["tasks"] = self.tasks
        if self.year_of_dataset_creation is not None:
            dict_data["year_of_dataset_creation"] = self.year_of_dataset_creation
        if self.last_updated is not None:
            dict_data["last_updated"] = self.last_updated.isoformat()

        # Handle variables DataFrame
        if not self.variables.empty:
            dict_data["variables"] = self.variables.to_dict("records")
        else:
            dict_data["variables"] = []

        # Handle additional_info if present
        if self.additional_info is not None:
            dict_data["additional_info"] = self.additional_info.to_dict()
        else:
            dict_data["additional_info"] = None

        # Handle intro_paper if present
        if self.intro_paper is not None:
            dict_data["intro_paper"] = self.intro_paper.to_dict()
        else:
            dict_data["intro_paper"] = None

        return dict_data

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the metadata.

        Args
        ----
        key : str
            The key to look up.
        default : Any, optional
            Default value to return if key is not found.

        Returns
        -------
        Any
            The value for the key, or the default value.
        """
        dict_data = self.to_dict()
        return dict_data.get(key, default)

    def items(self) -> Any:
        """Return items for key-value iteration.

        Returns
        -------
        Any
            Dictionary items view.
        """
        return self.to_dict().items()


@dataclass(frozen=True)
class UCIMLFilter:
    """Filters for dataset selection from UCI ML Repository.

    This class provides a frozen dataclass for defining filter criteria when
    selecting datasets from the UCI Machine Learning Repository. Filters can
    be applied at the selection stage (collection, search, area) or at the
    metadata filtering stage (instance count, feature count, year, missing values).

    Parameters
    ----------
    collection : str | None, default=None
        UCI repository collection filter expression (e.g., "aim-ahead", "python").
        If None, no collection filter is applied. The selection() method defaults
        to "python" when None.
    search : str | None, default=None
        Substring search by dataset name. Finds datasets where the search term
        appears in the dataset name.
    area : str | None, default=None
        Research area or subject area filter. Matches datasets tagged with
        this research area in the repository.
    exclude : list[str | int] | set[str | int] | tuple[str | int, ...] | None, default=None
        Dataset names or IDs to exclude from the selection. Can be a list, set,
        or tuple of strings (names) and/or integers (IDs). Integrated with
        ExcludeSet for unified filtering logic.
    max_instances : int | None, default=None
        Maximum number of samples/instances a dataset can have. If None, there
        is no upper limit.
    max_features : int | None, default=None
        Maximum number of features/attributes a dataset can have. If None, there
        is no upper limit.
    min_instances : int, default=0
        Minimum number of samples/instances a dataset must have.
    min_features : int, default=0
        Minimum number of features/attributes a dataset must have.
    min_year : int, default=0
        Minimum year of dataset creation. Datasets created before this year
        are excluded.
    max_year : int | None, default=None
        Maximum year of dataset creation. If None, there is no upper limit.
    include_missing : bool, default=True
        Include datasets with missing values. Both include_missing and
        include_non_missing are True by default to include all datasets
        regardless of missing value status. Set to False to exclude datasets
        with missing values.
    include_non_missing : bool, default=True
        Include datasets without missing values. Both include_missing and
        include_non_missing are True by default to include all datasets
        regardless of missing value status. Set to False to exclude datasets
        without missing values.
    include_numerical : bool, default=True
        Include datasets with numerical features (Integer, Real). Both
        include_numerical and include_categorical are True by default to
        include all datasets regardless of feature type. Set to False to
        exclude datasets with only numerical features.
    include_categorical : bool, default=True
        Include datasets with categorical features. Both include_numerical
        and include_categorical are True by default to include all datasets
        regardless of feature type. Set to False to exclude datasets with
        only categorical features.
    pure_feature_types_only : bool, default=False
        If True, only include datasets with a single feature type
        (pure numerical or pure categorical). Mixed datasets (those with
        both numerical and categorical features) are excluded. If False
        (default), mixed datasets are included when at least one of the
        include_numerical or include_categorical flags is True.

    Raises
    ------
    TypeError
        If fields have incorrect types.
    ValueError
        If constraints are inconsistent (e.g., max < min) or invalid.

    Notes
    -----
    Both `include_missing` and `include_non_missing` are True by default,
    meaning datasets are included regardless of missing value status. To
    filter by missing values, set one of these to False (e.g., to include
    only datasets with missing values, set `include_missing=True,
    include_non_missing=False`).

    Similarly, both `include_numerical` and `include_categorical` are True
    by default, meaning datasets are included regardless of feature type.
    To filter by feature type, set one of these to False (e.g., to include
    only datasets with numerical features, set `include_numerical=True,
    include_categorical=False`). Note that datasets with mixed feature types
    (both numerical and categorical) are included when at least one of the
    flags is True. To exclude mixed datasets and only include pure feature
    type datasets, set `pure_feature_types_only=True`.

    Examples
    --------
    >>> filter = UCIMLFilter(
    ...     collection="python",
    ...     search="iris",
    ...     min_instances=100,
    ...     max_instances=10000,
    ... )
    >>> filter = UCIMLFilter(
    ...     area="Computer Science",
    ...     min_year=2010,
    ...     include_missing=False,
    ... )
    >>> filter = UCIMLFilter(
    ...     include_categorical=False,
    ...     max_instances=1000,
    ... )  # Only numerical datasets with <= 1000 instances
    >>> filter = UCIMLFilter(
    ...     include_categorical=False,
    ...     pure_feature_types_only=True,
    ...     max_instances=1000,
    ... )  # Only pure numerical datasets with <= 1000 instances (excludes mixed)
    """

    collection: str | None = None
    search: str | None = None
    area: str | None = None
    exclude: list[str | int] | set[str | int] | tuple[str | int, ...] | None = None
    min_instances: int = 0
    max_instances: int | None = None
    min_features: int = 0
    max_features: int | None = None
    min_year: int = 0
    max_year: int | None = None
    include_missing: bool = True
    include_non_missing: bool = True
    include_numerical: bool = True
    include_categorical: bool = True
    pure_feature_types_only: bool = False

    def __post_init__(self):
        exclude = object.__getattribute__(self, "exclude")
        if not isinstance(exclude, frozenset):
            if exclude is None:
                exclude = set()
            else:
                exclude = set(exclude)
            for always_excluded in [
                "Drug Reviews (Drugs.com)",
                "Toxicity",
                "Land Mines",
            ]:
                exclude.add(always_excluded)
            exclude = frozenset(exclude)
            object.__setattr__(self, "exclude", exclude)

        # Validate feature type combinations
        include_numerical = object.__getattribute__(self, "include_numerical")
        include_categorical = object.__getattribute__(self, "include_categorical")
        if not include_numerical and not include_categorical:
            raise ValueError(
                "Invalid feature type combination: "
                "both include_numerical and include_categorical cannot be False"
            )

    @staticmethod
    def _matches_range(
        value: int | None, min_value: int, max_value: int | None
    ) -> bool:
        """Check if a numeric value matches min/max range constraints.

        Parameters
        ----------
        value : int | None
            The value to check. If None, returns True (no constraint).
        min_value : int
            Minimum allowed value (inclusive).
        max_value : int | None
            Maximum allowed value (inclusive). If None, no maximum
            constraint is applied.

        Returns
        -------
        bool
            True if value matches constraints, False otherwise.
        """
        if value is None:
            return True
        if value < min_value:
            return False
        if max_value is not None and max_value < value:
            return False
        return True

    def _matches_instance_count(self, meta_data: UCIMLMetadata) -> bool:
        """Check if metadata matches instance count constraints.

        Parameters
        ----------
        meta_data : Metadata
            Dataset metadata to check.

        Returns
        -------
        bool
            True if metadata matches instance count constraints, False otherwise.
        """
        matches = self._matches_range(
            meta_data.num_instances, self.min_instances, self.max_instances
        )
        if not matches:
            logger.debug(
                f"Dataset {meta_data.name} instance count {meta_data.num_instances} "
                f"does not match range [{self.min_instances}, {self.max_instances}]"
            )
        return matches

    def _matches_variable_count(self, meta_data: UCIMLMetadata) -> bool:
        """Check if metadata matches variable count constraints.

        Parameters
        ----------
        meta_data : Metadata
            Dataset metadata to check.

        Returns
        -------
        bool
            True if metadata matches variable count constraints, False otherwise.
        """
        matches = self._matches_range(
            meta_data.num_features, self.min_features, self.max_features
        )
        if not matches:
            logger.debug(
                f"Dataset {meta_data.name} variable count {meta_data.num_features} "
                f"does not match range [{self.min_features}, {self.max_features}]"
            )
        return matches

    def _matches_creation_year(self, meta_data: UCIMLMetadata) -> bool:
        """Check if metadata matches creation year constraints.

        Parameters
        ----------
        meta_data : Metadata
            Dataset metadata to check.

        Returns
        -------
        bool
            True if metadata matches creation year constraints, False otherwise.
        """
        matches = self._matches_range(
            meta_data.year_of_dataset_creation, self.min_year, self.max_year
        )
        if not matches:
            logger.debug(
                f"Dataset {meta_data.name} creation year {meta_data.year_of_dataset_creation} "
                f"does not match range [{self.min_year}, {self.max_year}]"
            )
        return matches

    def _matches_missing_values(self, meta_data: UCIMLMetadata) -> bool:
        """Check if metadata matches missing values constraints.

        Parameters
        ----------
        meta_data : Metadata
            Dataset metadata to check.

        Returns
        -------
        bool
            True if metadata matches missing values constraints, False otherwise.
        """
        if self.include_missing and not self.include_non_missing:
            matches = meta_data.has_missing_values is True
        elif not self.include_missing and self.include_non_missing:
            matches = meta_data.has_missing_values is False
        else:
            matches = True

        if not matches:
            logger.debug(
                f"Dataset {meta_data.name} missing values status "
                f"{meta_data.has_missing_values} does not match criteria"
            )
        return matches

    def _matches_feature_type(self, meta_data: UCIMLMetadata) -> bool:
        """Check if metadata matches feature type constraints.

        Datasets are classified by their feature types from the UCI API:
        - Numerical features: Integer, Real
        - Categorical features: Categorical

        A dataset can be:
        - Pure numerical: only Integer and/or Real feature types
        - Pure categorical: only Categorical feature type
        - Mixed: both categorical and numerical feature types
        - Unknown: feature_types is None or empty (included by default)

        Parameters
        ----------
        meta_data : Metadata
            Dataset metadata to check.

        Returns
        -------
        bool
            True if metadata matches feature type constraints, False otherwise.
        """
        # If feature_types is None or empty, can't determine - include by default
        # but only if not filtered by it
        if not self.include_categorical or not self.include_numerical:
            if not meta_data.feature_types:
                return True

        # Determine the composition of feature types
        has_categorical = "Categorical" in meta_data.feature_types
        has_numerical = any(ft in meta_data.feature_types for ft in ["Integer", "Real"])
        is_pure_numerical = has_numerical and not has_categorical
        is_pure_categorical = has_categorical and not has_numerical

        # Evaluate based on filter flags
        if self.include_numerical and not self.include_categorical:
            # Only numerical datasets (including mixed ones unless pure_feature_types_only)
            matches = (
                is_pure_numerical if self.pure_feature_types_only else has_numerical
            )
        elif not self.include_numerical and self.include_categorical:
            # Only categorical datasets (including mixed ones unless pure_feature_types_only)
            matches = (
                is_pure_categorical if self.pure_feature_types_only else has_categorical
            )
        else:
            # Both flags are True - include all types, but respect pure_feature_types_only
            if self.pure_feature_types_only:
                matches = is_pure_numerical or is_pure_categorical
            else:
                matches = True

        if not matches:
            logger.debug(
                f"Dataset {meta_data.name} feature types "
                f"{meta_data.feature_types} does not match criteria"
            )
        return matches

    def _matches_excluded(self, meta_data: UCIMLMetadata) -> bool:
        """Check if dataset should be excluded.

        Parameters
        ----------
        meta_data : Metadata
            Dataset metadata to check.

        Returns
        -------
        bool
            True if dataset should be included (not excluded), False otherwise.
        """
        if self.exclude is None:
            return True
        included = (
            meta_data.name not in self.exclude and meta_data.uci_id not in self.exclude
        )
        if not included:
            logger.debug(
                f"Dataset {meta_data.name} (id={meta_data.uci_id}) is excluded"
            )
        return included

    def matches(self, entry: dict, detailed=True) -> bool:
        """Check if metadata matches all filter criteria.

        Parameters
        ----------
        meta_data : Metadata
            Dataset metadata to check.

        Returns
        -------
        bool
            True if metadata matches all filter criteria, False otherwise.
        """
        if detailed:
            metadata = fetch_metadata(name=entry["name"])
            return (
                self._matches_instance_count(metadata)
                and self._matches_variable_count(metadata)
                and self._matches_creation_year(metadata)
                and self._matches_missing_values(metadata)
                and self._matches_feature_type(metadata)
                and self._matches_excluded(metadata)
            )
        return self._matches_excluded(UCIMLMetadata.from_dict(entry, detailed=False))

    @classmethod
    def from_dict(cls, data: dict) -> "UCIMLFilter":
        return cls(**data)

    def to_dict(self, detailed: bool = False) -> dict:
        """Convert filters to dictionary for API/Cache usage.

        Parameters
        ----------
        detailed : bool, default=False
            If True, include detailed filtering criteria (instance counts,
            variable counts, year ranges, missing values, feature types) in
            addition to selection criteria.

        Returns
        -------
            dict
        Dictionary representation of filter criteria.
        """
        if detailed:
            return asdict(self)
        return {
            "collection": self.collection,
            "search": self.search,
            "area": self.area,
        }

    def make_key(self, detailed: bool = False, length: int = 6) -> str:
        criteria = self.to_dict(detailed=detailed)
        criteria["exclude"] = list(criteria["exclude"])
        return hash_dict(criteria, length=length)


def hash_dict(obj: dict, length: int = 6) -> str:
    key = json.dumps(obj, sort_keys=True)
    return hashlib.sha256(key.encode()).hexdigest()[:length]


def normalize_name(name):
    name = name.lower()
    replace_symbols = ["(", ")", " ", ",", "'", ";", ":", ".", "/"]
    for symbol in replace_symbols:
        name = name.replace(symbol, "_")
    return name


def normalize_id(_id):
    return f"{_id:04d}"


def fetch_list(
    collection: str | None = None,
    search: str | None = None,
    area: str | None = None,
    data_home: Path | str | None = None,
    force: bool = False,
) -> list[dict]:
    """
    Get the list of all datasets that can be imported via fetch_ucirepo
    function.

    The result will be cached.

    Parameters
    ----------
    collection : str
        Optional query to filter available datasets based on a label
    search : str
        Optional query to search for available datasets by name
    area : str
        Optional query to filter available datasets based on subject area
    data_home : str or path-like, default=None
        The path to ucimlrepo data directory.
        If `None`, it defaults to the folder 'ucimlrepo in the
        `user_cache_dir`.
    force: boolean
        Download again even if the corresponding file is found in
        `data_home`.

    Returns
    -------
    list_data: dict
        A list of dict, each with values for keys 'name', 'id', 'url'.
    """
    # validate filter input
    if collection:
        if not isinstance(collection, str):
            raise ValueError("collection must be a string")
        collection = collection.lower()

    # validate search input
    if search:
        if not isinstance(search, str):
            raise ValueError("Search query must be a string")
        search = search.lower()

    # construct endpoint URL
    api_list_url = API_LIST_URL
    query_params = {}
    if collection:
        query_params["filter"] = collection
    else:
        query_params["filter"] = "python"  # default filter should be 'python'
    if search:
        query_params["search"] = search
    if area:
        query_params["area"] = area

    api_list_url += "?" + urllib.parse.urlencode(query_params)

    data_home = get_data_home(data_home)

    list_location = data_home / f"list/{collection}_{search}_{area}.json"

    logger.debug(f"{list_location=}")

    # fetch list of datasets from API
    list_data = None
    try:
        if list_location.exists() and not force:
            logger.debug("loading list ...")
            with open(list_location, mode="r") as f:
                list_data = json.load(f)
        else:
            logger.debug("creating list ...")
            response = _urlopen(api_list_url)
            resp_json = json.load(response)

            if resp_json["status"] != 200:
                error_msg = (
                    resp_json["message"]
                    if "message" in resp_json
                    else "Internal Server Error"
                )
                raise ValueError(error_msg)

            list_data = resp_json["data"]

            logger.debug("done creating list")

            # cache meta_data
            list_location.parent.mkdir(exist_ok=True)
            with open(list_location, mode="w") as f:
                json.dump(list_data, f, indent=4, sort_keys=True)
                f.write("\n")

    except (URLError, HTTPError):
        raise ConnectionError("Error connecting to server")

    list_data = [
        {"uci_id": entry["id"], "data_url": entry["url"], "name": entry["name"]}
        for entry in list_data
    ]

    return list_data


def fetch_metadata(
    name: str | None = None,
    uci_id: int | None = None,
    data_home: Path | str | None = None,
    force: bool = False,
) -> UCIMLMetadata:
    """
    Loads metadata for a dataset from the UCI ML Repository.

    Parameters
    ----------
    id : int
        Dataset ID for UCI ML Repository
    name : str
        Dataset name, or substring of name. (Only provide id or name, not both)
    data_home : str or path-like, default=None
        The path to ucimlrepo data directory.
        If `None`, it defaults to the folder 'ucimlrepo in the
        `user_cache_dir`.
    force: boolean
        Download again even if the corresponding files are found in
        `data_home`.
    """

    # check that only one argument is provided
    if name and uci_id:
        raise ValueError("Only specify either dataset name or ID, not both")

    # validate types of arguments and add them to the endpoint query string
    api_url = API_BASE_URL
    if name:
        if not isinstance(name, str):
            raise ValueError("Name must be a string")
        api_url += "?name=" + urllib.parse.quote(name)
    elif uci_id:
        if not isinstance(uci_id, int):
            raise ValueError("ID must be an integer")
        api_url += "?id=" + str(uci_id)
    else:
        # no arguments provided
        raise ValueError("Must provide a dataset name or ID")

    data_home = get_data_home(data_home)

    if name is None:
        md = normalize_id(uci_id)
    else:
        md = normalize_name(name)
    metadata_location = data_home / f"meta/{md}.json"

    # fetch metadata from API
    data = None
    try:
        if metadata_location.exists() and not force:
            # reuse cached
            with open(metadata_location, mode="r") as f:
                return UCIMLMetadata.from_dict(json.load(f))
        else:
            # obtain
            response = _urlopen(api_url)
            data = json.load(response)

            # verify that dataset exists
            if data["status"] != 200:
                error_msg = (
                    data["message"]
                    if "message" in data
                    else "Dataset not found in repository"
                )
                raise DatasetNotFoundError(error_msg)

            metadata = data["data"]

    except (URLError, HTTPError):
        raise ConnectionError("Error connecting to server")

    # extract ID, name, and URL from metadata
    if not uci_id:
        uci_id = metadata["uci_id"]
        md_other = normalize_id(uci_id)
    elif not name:
        name = metadata["name"]
        md_other = normalize_name(name)

    metadata_location.parent.mkdir(exist_ok=True)
    with open(metadata_location, mode="w") as f:
        json.dump(metadata, f, indent=4, sort_keys=True)
        f.write("\n")

    other_metadata_location = data_home / f"meta/{md_other}.json"
    if not other_metadata_location.exists():
        other_metadata_location.symlink_to(metadata_location)

    return UCIMLMetadata.from_dict(metadata)


def fetch_selection(
    uciml_filter: UCIMLFilter,
    data_home: Path | str | None = None,
    force: bool = False,
):
    logger.debug(f"fetching selection for {uciml_filter=}")

    key = uciml_filter.make_key(detailed=True)

    logger.debug(f"filter {key=}")

    data_home = get_data_home(data_home)

    location = data_home / "selections" / f"{key}.pickle"

    logger.debug(f"filter {location=}")

    if location.exists() and not force:
        logger.debug("loading...")
        with open(location, "rb") as fd:
            return pickle.load(fd)

    logger.debug("creating selection...")

    selection = fetch_list(
        **uciml_filter.to_dict(),
        data_home=data_home,
        force=force,
    )

    selection = [
        entry
        for entry in selection
        if uciml_filter.matches(entry, detailed=False) and uciml_filter.matches(entry)
    ]

    logger.debug("finished creating selection")

    location.parent.mkdir(exist_ok=True)
    with open(location, "wb") as fd:
        pickle.dump(selection, fd)

    return selection


def fetch_data_set(
    name: str | None = None,
    uci_id: int | None = None,
    data_home: Path | str | None = None,
    force: bool = False,
) -> Any:
    """
    Loads a dataset from the UCI ML Repository, including the dataframes and metadata information.

    Metadata and data are cached.

    Parameters
    ----------
    id : int
        Dataset ID for UCI ML Repository
    name : str
        Dataset name, or substring of name. (Only provide id or name, not both)
    data_home : str or path-like, default=None
        The path to ucimlrepo data directory.
        If `None`, it defaults to the folder 'ucimlrepo in the
        `user_cache_dir`.
    force: boolean
        Download again even if the corresponding files are found in
        `data_home`.

    Returns
    -------
    result : dotdict
        Object containing dataset metadata, dataframes, and variable info in its properties.
    """

    metadata = fetch_metadata(
        name=name, uci_id=uci_id, data_home=data_home, force=force
    )

    uci_id = normalize_id(metadata.get("uci_id"))
    name = normalize_name(metadata.get("name"))
    key = f"{uci_id}_{name}"

    data_url = metadata.get("data_url")

    # no data URL means that the dataset cannot be imported into Python
    # i.e. it does not yet have a standardized CSV file for pandas to parse
    if not data_url:
        raise DatasetNotFoundError(
            '"{}" dataset (id={}) exists in the repository, but is not available for import. Please select a dataset from this list: https://archive.ics.uci.edu/datasets?skip=0&take=10&sort=desc&orderBy=NumHits&search=&Python=true'.format(
                name, uci_id
            )
        )

    data_home = get_data_home(data_home)

    dataset_location = data_home / f"data/{key}.csv"

    # parse into dataframe using pandas
    df = None
    try:
        if dataset_location.exists() and not force:
            df = read_csv(dataset_location)
        else:
            import io
            response = _urlopen(data_url)
            df = read_csv(io.BytesIO(response.read()))

            if df.empty:
                raise DatasetNotFoundError(
                    'Error reading data csv file for "{}" dataset (id={}).'.format(
                        name, uci_id
                    )
                )

            dataset_location.parent.mkdir(exist_ok=True)
            df.to_csv(dataset_location, index=False)
    except (URLError, HTTPError):
        raise DatasetNotFoundError(
            'Error reading data csv file for "{}" dataset (id={}).'.format(name, uci_id)
        )

    # header line should be variable names
    headers = df.columns

    # feature information, class labels
    variables = metadata.get("variables")

    # organize variables into IDs, features, or targets
    variables_by_role = {"ID": [], "Feature": [], "Target": [], "Other": []}
    for variable in variables:
        if variable["role"] not in variables_by_role:
            raise ValueError(
                'Role must be one of "ID", "Feature", or "Target", or "Other"'
            )
        variables_by_role[variable["role"]].append(variable["name"])

    # extract dataframes for each variable role
    ids_df = df[variables_by_role["ID"]] if len(variables_by_role["ID"]) > 0 else None

    features_df = (
        df[variables_by_role["Feature"]]
        if len(variables_by_role["Feature"]) > 0
        else None
    )
    targets_df = (
        df[variables_by_role["Target"]]
        if len(variables_by_role["Target"]) > 0
        else None
    )

    data = {
        "ids": ids_df,
        "features": features_df,
        "targets": targets_df,
        "original": df,
        "headers": headers,
    }

    return data


def select_features_columns(
    dataset: dict,
    exclude_targets: bool = True,
    exclude_ids: bool = True,
    column_types: list[str] | None = None,
) -> DataFrame:
    """Select feature columns based on dataset metadata.

    Parameters
    ----------
    dataset : dict
        Data of an UCI Repository Dataset.
    exclude_targets : bool, default=True
        Exclude target columns identified in metadata.
    exclude_ids : bool, default=True
        Exclude ID columns identified in metadata.
    column_types : list[str], optional
        Only include columns of specific types (e.g., ["Real", "Integer", "Categorical"]).
        If None, include all.

    Returns
    -------
    pd.DataFrame
        DataFrame with selected columns.
    """

    if not exclude_ids and not exclude_targets and column_types is None:
        return dataset["original"]

    include = []

    if not exclude_ids and dataset["ids"] is not None:
        include.append(dataset["ids"])

    include.append(dataset["features"])

    if not exclude_targets and dataset["targets"] is not None:
        include.append(dataset["targets"])

    df = concat(include, axis=1)

    logger.debug(f"After excluding targets/IDs: {len(df.columns)} columns remain")

    if column_types:
        pre_filter = len(df.columns)
        df = df.select_dtypes(include=column_types)
        logger.debug(
            f"Filtered by column types {column_types}: "
            f"{pre_filter} -> {len(df)} columns"
        )

    logger.debug(f"After filtering column types: {len(df.columns)} columns remain")

    if df.empty:
        logger.warning("Obtained empty dataframe after applying filters")

    return df


class UCIMLAdapter(CacheIterationMixin, AdapterInterface):
    """Adapter for datasets from the UCI Machine Learning Repository.

    This adapter yields Many-Valued Contexts for each filtered dataset.
    Scaling should be applied separately using ScalingTool.

    Caching is enabled by default. Use CacheConfig(enabled=False) to disable.

    Examples
    --------
    >>> # Default two-tier caching
    >>> adapter = UCIMLAdapter()

    >>> # Disable caching
    >>> adapter = UCIMLAdapter(cache_config=CacheConfig(enabled=False))

    >>> # Memory-only caching
    >>> adapter = UCIMLAdapter(cache_config=CacheConfig(backend="memory"))
    """

    def __init__(
        self,
        cache_config: CacheConfig | None = None,
        exclude_targets: bool = False,
        allowed_column_types: list[str] | None = None,
        uciml_filter: UCIMLFilter | dict[str, Any] | None = None,
        data_home: str | None = None,
        force_refresh: bool = False,
    ) -> None:
        """Initialize the UCI ML adapter.

        Parameters
        ----------
        cache_config : CacheConfig, optional
            Cache configuration. Defaults to two-tier caching.
        exclude_targets : bool, default=False
            Whether to exclude target columns.
        allowed_column_types : list of str, optional
            Allowed column types for feature selection. Defaults to all.
        uciml_filter : UCIMLFilter or dict-like, default=None
            Define a sub selection. See UCIMLFilter of what is available.
        data_home : str or path-like, default=None
            The path to ucimlrepo data directory.
            If `None`, it defaults to the folder `ucimlrepo` in the
            `user_cache_dir`. To control context cache use CacheConfig.
        force_refresh: boolean
            Download again even if the corresponding file is found in
            `data_home`.
        """
        AdapterInterface.__init__(self, context_type=ManyValuedContext)

        self.exclude_targets = exclude_targets
        if allowed_column_types is None:
            allowed_column_types = []
        self.allowed_column_types = sorted(allowed_column_types)

        logger.info(
            "Initialized UCIMLAdapter, "
            f"exclude_targets={exclude_targets}, "
            f"allowed_column_types={allowed_column_types}"
        )

        if cache_config is None:
            cache_config = CacheConfig(
                backend="disk",
                manyvalued_context_serializer="pickle",
            )

        self.data_home = data_home
        self.force_refresh = force_refresh

        if uciml_filter is None:
            uciml_filter = {}

        if isinstance(uciml_filter, dict):
            uciml_filter = UCIMLFilter.from_dict(uciml_filter)  # type:ignore

        self.selection = fetch_selection(
            uciml_filter, data_home=data_home, force=force_refresh
        )

        self._init_cache(cache_config)
        logger.debug(f"Cache initialized with backend: {cache_config.backend}")

    def keys(self) -> Iterator[dict]:
        for entry in self.selection:
            key = {
                "uci_id": entry["uci_id"],
                "name": entry["name"],
                "exclude_targets": self.exclude_targets,
                "allowed_column_types": self.allowed_column_types,
            }
            yield key

    def _key_to_str(self, key: dict) -> str:
        return hash_dict(key)

    def _get(self, key) -> ManyValuedContext:
        """Generate context without caching.

        Parameters
        ----------
        key : str or int
            Dataset name (str) or UCI ID (int) to generate context for.
            The name should be the original dataset name as returned by keys().

        Returns
        -------
        ManyValuedContext
            Newly generated Many-Valued Context.

        Raises
        ------
        ValueError
            If dataset is not found in selection.
        """
        logger.debug(f"Getting dataset: {key}")
        data_set = fetch_data_set(
            uci_id=key["uci_id"],
            data_home=self.data_home,
            force=self.force_refresh,
        )
        dataset_name = key["name"]
        logger.debug(f"Building context for '{dataset_name}'")
        features_df = select_features_columns(
            data_set,
            exclude_targets=self.exclude_targets,
            exclude_ids=True,
            column_types=self.allowed_column_types,
        )
        if features_df is None or len(features_df.columns) == 0:
            error_msg = f"No feature columns found in dataset '{dataset_name}'"
            logger.error(error_msg)
            raise ValueError(error_msg)
        logger.debug(
            f"Selected {len(features_df.columns)} feature columns from '{dataset_name}'"
        )
        mvc = ManyValuedContext.from_df(features_df, name=dataset_name)
        logger.debug(f"Successfully built context for {key}")
        return mvc

    def __len__(self) -> int:
        """Return number of filtered datasets.

        Returns
        -------
        int
            Number of datasets available under current filters.
        """
        return len(self.selection)

    def __contains__(self, uci_id_or_name: str) -> bool:
        """Check if a dataset is available under current filters.

        Returns
        -------
        bool
            True if dataset is available, False otherwise.
        """
        try:
            if isinstance(uci_id_or_name, int) or (
                isinstance(uci_id_or_name, str) and uci_id_or_name.isdigit()
            ):
                self.selection.get_by_id(int(uci_id_or_name))
            else:
                self.selection.get_by_name(uci_id_or_name)
            return True
        except Exception:
            return False

    def is_sortable(self) -> bool:
        """Indicate whether adapter supports deterministic sorting."""
        return True

    def is_versionable(self) -> bool:
        """Indicate whether adapter supports versioning."""
        return True

    def is_deterministic(self) -> bool:
        """Indicate whether repeated runs yield identical results."""
        return True

    def is_stateless(self) -> bool:
        """Indicate whether adapter maintains internal mutable state."""
        return False

    def has_metadata(self) -> bool:
        """Indicate whether adapter exposes additional metadata."""
        return True

    def get_metadata(self, uci_id_or_name: int | str) -> UCIMLMetadata:
        """Get detailed information about a dataset without loading full features.

        Parameters
        ----------
        uci_id_or_name : int or str
            UCI dataset ID (int) or name (str).

        Returns
        -------
        dict
            Dataset metadata information.

        Examples
        --------
        >>> adapter = UCIMLAdapter()
        >>> info = adapter.get_dataset_info("Iris")
        >>> print(info["name"])
        'Iris'
        """
        found = None
        if isinstance(uci_id_or_name, int) or (
            isinstance(uci_id_or_name, str) and uci_id_or_name.isdigit()
        ):
            uci_id_or_name = int(uci_id_or_name)
            for entry in self.selection:
                if entry["uci_id"] == uci_id_or_name:
                    found = {"uci_id": uci_id_or_name}
                    break
        else:
            for entry in self.selection:
                if entry["name"] == uci_id_or_name:
                    found = {"name": uci_id_or_name}
                    break
        if found is not None:
            return fetch_metadata(**found)  # type:ignore

        raise KeyError(f"Dataset '{uci_id_or_name}' not found in selection")

    def get_context(self, uci_id_or_name: int | str) -> ManyValuedContext:
        found = None
        if isinstance(uci_id_or_name, int) or (
            isinstance(uci_id_or_name, str) and uci_id_or_name.isdigit()
        ):
            uci_id_or_name = int(uci_id_or_name)
            for entry in self.keys():
                if entry["uci_id"] == uci_id_or_name:
                    found = entry
                    break
        else:
            for entry in self.selection:
                if entry["name"] == uci_id_or_name:
                    found = entry
                    break
        if found is not None:
            return self.get(found)  # type:ignore

        raise KeyError(f"Dataset '{uci_id_or_name}' not found in selection")

    def list_available_areas(self) -> list[str]:
        """List all available subject areas in cached dataset list.

        Returns
        -------
        list of str
            Sorted list of unique subject areas.

        Examples
        --------
        >>> adapter = UCIMLAdapter()
        >>> areas = adapter.list_available_areas()
        >>> print(areas[:5])
        ['Biology', 'Business', ...]
        """
        areas: set[str] = set()
        for entry in self.selection:
            area = fetch_metadata(entry["name"]).get("area")
            if area is not None:
                areas.add(area)
        return sorted(list(areas))
