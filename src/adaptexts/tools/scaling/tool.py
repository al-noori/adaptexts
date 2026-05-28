"""ScalingTool: Primary interface for scaling many-valued contexts.

This module provides the ScalingTool class, which encapsulates:
- ConexpClient management (auto_server and manual mode)
- Scale application (manual and automatic)
- Scale map inference
"""

import logging

from typing import TYPE_CHECKING, Any, Optional

from adaptexts.context import Context
from conexp_clj_py import ConexpClient
from conexp_clj_py.api.fca.many_valued_contexts import scale_mv_context

from .scales import infer_scale_map

if TYPE_CHECKING:
    from adaptexts.many_valued_context import ManyValuedContext

logger = logging.getLogger(__name__)


class ScalingTool:
    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        timeout: float = 30,
        retries: int = 3,
        auto_server: bool = False,
        server_port: int | None = None,
        server_location: str | None = None,
        server_auto_clone: bool = True,
        server_startup_timeout: int = 60,
        server_lein_command: str = "lein",
        server: Any = None,
    ):
        """Initialize ScalingTool.

        Parameters
        ----------
        base_url: Base URL of the conexp-clj API
        timeout: Request timeout in seconds
        retries: Maximum number of retries for failed requests
        auto_server: If True, automatically start an embedded server
              instance. Only works when used as Context Manager.
        server_port: Port for the auto-server (if None, extracts from base_url)
        server_location: Path to conexp-clj repository for auto-server
        server_auto_clone: If True, auto-clone conexp-clj repo if not found
        server_startup_timeout: Maximum seconds to wait for auto-server to start
        server_lein_command: Command to use for running Leiningen (default "lein").
        server: A ConexpServer instance to use. If provided, takes precedence over
              auto_server and server config options. The client will manage the
              server's lifecycle (shutdown on close).
              Only works when used as Context Manager.
        """
        self.client = ConexpClient(
            base_url=base_url,
            timeout=timeout,
            retries=retries,
            auto_server=auto_server,
            server_port=server_port,
            server_location=server_location,
            server_auto_clone=server_auto_clone,
            server_startup_timeout=server_startup_timeout,
            server_lein_command=server_lein_command,
            server=server,
        )
        logger.info("ScalingTool initialized")

    def scale(
        self,
        mv_ctx: "ManyValuedContext",
        scale_map: Optional[dict[str, dict[str, Any]]] = None,
    ) -> "Context":
        """Scale many-valued context to binary formal context.

        Parameters
        ----------
        mvc : ManyValuedContext
            Many-valued context to scale.
        scale_map : dict, optional
            Mapping from attribute names to scale specifications. Defaults to inferred scale map.

        Returns
        -------
        Context
            Binary formal context obtained by scaling.

        Raises
        ------
        ScaleError
            If scale name is invalid.
        """
        if scale_map is None:
            scale_map = infer_scale_map(mv_ctx)

        logger.info(f"Scaling context '{mv_ctx.name}' with {len(scale_map)} attributes")
        logger.debug(f"Scale map: {scale_map}")

        conexp_mv_ctx = mv_ctx.to_conexp()

        # Build scale contexts
        scales = {}
        for attr, scale_info in scale_map.items():
            values = mv_ctx.values_of_attribute(attr)
            logger.debug(
                f"Creating scale for attribute '{attr}' with {len(values)} values"
            )
            scales[attr] = self._create_scale(attr, values, scale_info)

        # Scale the context
        conexp_ctx = scale_mv_context(self.client, conexp_mv_ctx, scales)

        # Convert back to adaptexts Context
        ctx = Context.from_conexp(conexp_ctx)
        logger.info(f"Scaling complete: {len(ctx.G)} objects, {len(ctx.M)} attributes")
        return ctx

    def automatic_scale(self, mvc: "ManyValuedContext") -> "Context":
        """Automatically scale many-valued context.

        Parameters
        ----------
        mvc : ManyValuedContext
            Many-valued context to scale.

        Returns
        -------
        Context
            Binary formal context obtained by scaling.
        """
        return self.scale(mvc, scale_map=None)

    def _create_scale(self, attr: str, values: list, scale_info: dict[str, Any]):
        """Create a scale context from scale specification.

        Parameters
        ----------
        attr : str
            Attribute name.
        values : list
            Attribute values.
        scale_info : dict
            Scale specification with 'name' and optional parameters.

        Returns
        -------
        FormalContext
            Scale context from conexp-client.

        Raises
        ------
        ScaleError
            If scale name is invalid.
        """

        from .scales import create_scale_context

        scale_name = scale_info.get("name", "")
        scale_params = {k: v for k, v in scale_info.items() if k != "name"}

        return create_scale_context(
            self.client,
            scale_type=scale_name,
            values=values,
            **scale_params,
        )

    def start(self) -> None:
        logger.debug("Starting ConexpClient...")
        self.client.start()
        logger.info("ConexpClient started")

    def close(self) -> None:
        """Close the ConexpClient connection."""
        logger.debug("Closing ConexpClient...")
        self.client.close()
        logger.info("ConexpClient closed")

    def __enter__(self) -> "ScalingTool":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
