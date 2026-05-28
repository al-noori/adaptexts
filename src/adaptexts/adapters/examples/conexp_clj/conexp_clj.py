"""Conexp-clj testing-data adapter.

This module defines the ConexpCljAdapter class, which provides access to
the testing-contexts from the conexp-clj repository. This repository contains
 Formal Concept Analysis contexts in multiple formats (.cxt, .ctx, .csv, .json).

The contexts cover various domains including:
- Seven-segment digit display representation
- Geometric shapes (triangles)
- Bodies of water classification
- Living beings classification
- Zoo animals
- And many more test/education contexts

See: https://github.com/tomhanika/conexp-clj/tree/dev/testing-data
"""

import logging

from pathlib import Path

from ...git import GitBurmeisterAdapter
from ...mixins import FileTreeConfig

logger = logging.getLogger(__name__)


class ConexpCljAdapter(GitBurmeisterAdapter):
    """Adapter for the conexp-clj testing-data repository.

    This adapter loads formal contexts from the conexp-clj testing-data
    repository, supporting Burmeister (.cxt) and Conexp (.ctx) format files.

    Note: The conexp-clj repository also contains contexts in CSV and JSON formats,
    but these use a different structure than the standard formats supported by
    adaptexts and are excluded from this adapter.

    The repository contains test and educational contexts for Formal Concept
    Analysis, with domains such as:

    - **Digit contexts**: Seven-segment display representations of digits 0-9
    - **Geometric shapes**: Triangle types and properties
    - **Water classification**: Bodies of water (lake, river, sea, etc.)
    - **Living beings**: Plants and animals with various properties
    - **Zoo data**: Animal classification dataset
    - **And more**: Various other FCA test contexts

    Examples
    --------
    >>> # Create adapter with default settings
    >>> from adaptexts.adapters.examples.conexp_clj import ConexpCljAdapter
    >>> adapter = ConexpCljAdapter()
    >>> for context in adapter:
    ...     print(f"{context.name}: {len(context.objects)} objects, {len(context.attributes)} attributes")
    ...
    testing-data/digits.cxt: 10 objects, 7 attributes
    testing-data/triangles.cxt: 8 objects, 9 attributes
    ...

    >>> # Customize
    >>> from adaptexts.adapters.examples import ConexpCljAdapter
    >>>
    >>> class ConexpCljForkAdapter(ConexpCljAdapter):
    ...     base_url = "https://github.com/githubuser/my-conexp-clj-fork.git"
    ...     def __init__(self):
    ...         super().__init__(
    ...             self.base_url,
    ...             revision="main",
    ...             shallow_clone=False,
    ...             file_tee_config=FileTreeConfig(
    ...                 include_patterns=["**/*.cxt", "**/*.ctx"],
    ...                 exclude_patterns=[],
    ...             ),
    ...             data_home="~/my-workspace/conexp-clj",
    ...         )
    >>>
    >>> adapter = ConexpCljForkAdapter()
    >>> for context in adapter:
    ...     print(context.name)
    """

    base_url = "https://github.com/tomhanika/conexp-clj.git"
    default_revision = "dev"

    def __init__(
        self,
        revision: str | None = None,
        shallow_clone: bool = True,
        file_tree_config: FileTreeConfig | None = None,
        data_home: Path | str | None = None,
    ):
        """Initialize the ConexpClj adapter.

        Parameters
        ----------
        revision : str, optional
            Git revision to checkout. If None, uses "dev" branch.
            The conexp-clj repository stores testing-data in the "dev" branch.
        shallow_clone : bool, optional
            Whether to use shallow clones (depth=1). Default: True.
        file_tree_config : FileTreeConfig, optional
            File tree configuration. If None, creates a default config
            with the repository cache path.
        data_home : str, Path, optional
            Destination of the clone if repo_url is not local.
            Overwrites file_tree_config.root if set.

        """
        logger.info("Initializing ConexpCljAdapter")

        if revision is None:
            revision = self.default_revision

        logger.debug("Using revision: %s", revision)

        # Create default config for testing-data directory
        if file_tree_config is None:
            file_tree_config = FileTreeConfig(
                root="",  # Placeholder - GitAdapter will set this
                include_patterns=[
                    "testing-data/*.cxt",
                    "testing-data/*.ctx",
                ],
                exclude_patterns=[
                    "**/.git/**",
                    "**/__pycache__/**",
                    "**/*.bin.xml",
                    "**/*.cex",
                    "**/*.csx",
                    "**/*.csc",
                    "**/*.csv",  # conexp-clj CSV format is pair-based, not table-based
                    "**/*.json",  # conexp-clj JSON format is incompatible
                    # "testing-data/mushroom.cxt",  # Very large file
                    # "testing-data/mushroom.ctx",  # Very large file
                    # "testing-data/endos.cxt",  # Very large file
                    "testing-data/my.cxt",  # XML format, not Burmeister
                    "testing-data/myctx.cxt",  # May have format issues
                ],
            )

        super().__init__(
            repo_url=self.base_url,
            revision=revision,
            shallow_clone=shallow_clone,
            file_tree_config=file_tree_config,
            data_home=data_home,
        )

        logger.info("ConexpCljAdapter initialized successfully")

    def has_metadata(self) -> bool:
        """Indicate whether this adapter provides metadata.

        The conexp-clj repository includes an org-mode file with context
        descriptions and references.

        Returns
        -------
        bool
            Always True for ConexpCljAdapter.
        """
        return True

    def get_metadata(self, context_name: str) -> str:
        """Get context descriptions from the repository.

        Reads the context-descriptions.org file to retrieve descriptions
        of the available contexts and their source citations.

        Returns
        -------
        str
            Description of context with given name.

        Raises
        ------
        AdapterError
            If the descriptions file cannot be read or parsed.

        """
        from adaptexts.adapters.exceptions import AdapterError

        # Get the Git repository
        repo = self.get_repo()

        # Get repository path
        repo_path = Path(repo.working_tree_dir or ".")
        if not repo_path.exists():
            raise AdapterError("Repository working tree not available")

        descriptions_file = repo_path / "testing-data" / "context-descriptions.org"

        if not descriptions_file.exists():
            raise AdapterError(
                f"Context descriptions file not found: {descriptions_file}"
            )

        try:
            content = descriptions_file.read_text(encoding="utf-8")
            return self._parse_descriptions(content)[context_name]
        except OSError as e:
            raise AdapterError(f"Failed to read context descriptions file: {e}") from e

    def _parse_descriptions(self, content: str) -> dict[str, str]:
        """Parse context descriptions from org-mode content.

        Parameters
        ----------
        content : str
            Content of the context-descriptions.org file.

        Returns
        -------
        dict[str, str]
            Mapping from context names to descriptions.
        """
        descriptions: dict[str, str] = {}

        # Simple parsing: look for headings with file names
        current_file = None
        current_desc = []

        for line in content.split("\n"):
            # Look for file references
            if (
                line.startswith("*")
                and ".cxt" in line
                or ".ctx" in line
                or ".csv" in line
            ):
                # Save previous entry
                if current_file is not None:
                    descriptions[current_file] = " ".join(current_desc).strip()

                # Extract filename from heading
                parts = line.split()
                for part in parts:
                    if ".cxt" in part or ".ctx" in part or ".csv" in part:
                        current_file = part.strip("[]:")
                        current_desc = []
                        break
            elif current_file is not None:
                # Collect description text
                if line and not line.startswith("*"):
                    current_desc.append(line.strip())

        # Save last entry
        if current_file is not None:
            descriptions[current_file] = " ".join(current_desc).strip()

        return descriptions
