#!/usr/bin/env python3
"""Generate docs/data.json by running all adapters and collecting metrics.

Usage:
    python scripts/generate_data.py [--limit N] [--adapters uciml,rwc,ipc]

--limit N     Stop after N datasets per adapter (useful for testing)
--adapters    Comma-separated built-in adapters to include (default: all)
"""

import argparse
import importlib.util
import itertools
import json
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

OUTPUT_PATH = ROOT / "docs" / "data.json"

# Skip concept enumeration for contexts exceeding this cell count (n_obj * n_attr).
# Concept enumeration is exponential in the worst case; this guards against infeasible inputs.
MAX_CONCEPT_CELLS = 50_000


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _to_hashable(x):
    """Recursively convert lists to tuples so they can be used as dict keys."""
    if isinstance(x, list):
        return tuple(_to_hashable(v) for v in x)
    return x


def compute_concept_count(g: list, m: list, i: list) -> int | None:
    """Return the number of formal concepts, or None if the context is too large."""
    if len(g) * len(m) > MAX_CONCEPT_CELLS or not g or not m:
        return None
    try:
        from concepts import Context as ConceptsContext

        g_keys = [_to_hashable(obj) for obj in g]
        m_keys = [_to_hashable(attr) for attr in m]
        g_idx = {k: idx for idx, k in enumerate(g_keys)}
        m_idx = {k: idx for idx, k in enumerate(m_keys)}
        inc_set = set()
        for obj, attr in i:
            gk, mk = _to_hashable(obj), _to_hashable(attr)
            if gk in g_idx and mk in m_idx:
                inc_set.add((g_idx[gk], m_idx[mk]))
        bools = [
            tuple((gi, mi) in inc_set for mi in range(len(m)))
            for gi in range(len(g))
        ]
        # Prefix g/m to guarantee labels are disjoint (required by concepts library)
        g_str = [f"g:{g[i]}_{i}" for i in range(len(g))]
        m_str = [f"m:{m[j]}_{j}" for j in range(len(m))]
        ctx = ConceptsContext(g_str, m_str, bools)
        return len(list(ctx.lattice))
    except Exception:
        return None


def collect_metrics(ctx) -> dict:
    from adaptexts.many_valued_context import ManyValuedContext

    g = list(ctx.G)
    m = list(ctx.M)
    i = list(ctx.I)
    n_obj = len(g)
    n_attr = len(m)
    n_inc = len(i)
    denom = n_obj * n_attr
    density = round(n_inc / denom, 4) if denom > 0 else 0.0

    is_many_valued = isinstance(ctx, ManyValuedContext)

    result = {
        "n_objects": n_obj,
        "n_attributes": n_attr,
        "n_incidences": n_inc,
        "density": density,
        "context_type": "ManyValuedContext" if is_many_valued else "Context",
        "n_concepts": None if is_many_valued else compute_concept_count(g, m, i),
    }

    if is_many_valued:
        result["n_values"] = len(list(ctx.W))

    return result


def compute_lattice_metrics(g: list, m: list, i: list, n_concepts: int | None) -> dict:
    """Compute lattice height, irreducibles, and per-concept (extent, intent) sizes."""
    if n_concepts is None:
        return {}
    try:
        from collections import deque
        from concepts import Context as ConceptsContext

        g_keys = [_to_hashable(obj) for obj in g]
        m_keys = [_to_hashable(attr) for attr in m]
        g_idx = {k: idx for idx, k in enumerate(g_keys)}
        m_idx = {k: idx for idx, k in enumerate(m_keys)}
        inc_set = set()
        for obj, attr in i:
            gk, mk = _to_hashable(obj), _to_hashable(attr)
            if gk in g_idx and mk in m_idx:
                inc_set.add((g_idx[gk], m_idx[mk]))
        bools = [tuple((gi, mi) in inc_set for mi in range(len(m))) for gi in range(len(g))]
        g_str = [f"g:{g[i]}_{i}" for i in range(len(g))]
        m_str = [f"m:{m[j]}_{j}" for j in range(len(m))]
        ctx = ConceptsContext(g_str, m_str, bools)
        lat = ctx.lattice
        concepts = list(lat)

        # Height via BFS from infimum
        visited: dict[int, int] = {}
        q: deque = deque([(lat.infimum, 0)])
        while q:
            node, d = q.popleft()
            if id(node) in visited:
                continue
            visited[id(node)] = d
            for nb in node.upper_neighbors:
                q.append((nb, d + 1))
        height = max(visited.values()) if visited else 0

        join_irr = sum(1 for c in concepts if len(list(c.lower_neighbors)) == 1)
        meet_irr = sum(1 for c in concepts if len(list(c.upper_neighbors)) == 1)

        # Per-concept [extent_size, intent_size] — used for scatter plot
        concept_sizes = [[len(c.extent), len(c.intent)] for c in concepts]

        return {
            "height": height,
            "n_join_irreducibles": join_irr,
            "n_meet_irreducibles": meet_irr,
            "concept_sizes": concept_sizes,
        }
    except Exception:
        return {}


def serialize_metadata(raw) -> dict | None:
    """Serialize adapter-specific metadata to a JSON-compatible dict."""
    if raw is None:
        return None
    # UCIML: UCIMLMetadata dataclass (has .abstract attribute)
    if hasattr(raw, "abstract"):
        result = {}
        if raw.abstract:                  result["abstract"] = raw.abstract
        if raw.area:                      result["area"] = raw.area
        if raw.tasks:                     result["tasks"] = list(raw.tasks)
        if raw.year_of_dataset_creation:  result["year"] = raw.year_of_dataset_creation
        if raw.creators:                  result["creators"] = list(raw.creators)
        if raw.characteristics:           result["characteristics"] = list(raw.characteristics)
        if raw.feature_types:             result["feature_types"] = list(raw.feature_types)
        return result or None
    # RWC / others: dict from YAML
    if isinstance(raw, dict):
        result = {}
        for field in ("title", "description", "language", "note"):
            if raw.get(field):
                result[field] = raw[field]
        if raw.get("source"):
            src = raw["source"]
            result["source"] = [str(s) for s in (src if isinstance(src, list) else [src])]
        return result or None
    return None


def fetch_metadata(adapter, name: str) -> dict | None:
    """Call adapter.get_metadata() and return a serializable dict, or None."""
    if not adapter.has_metadata():
        return None
    try:
        from pathlib import Path as _Path
        key = _Path(name).stem if ("/" in name or "." in _Path(name).suffix) else name
        return serialize_metadata(adapter.get_metadata(key))
    except Exception:
        return None


MAX_SCALING_INCIDENCES = 5_000  # skip scaling for large many-valued contexts (avoids 413)


def _compute_concepts_full(g: list, m: list, i: list) -> dict:
    """Compute n_concepts + concept_sizes in one call (run in a subprocess for timeout safety)."""
    try:
        from concepts import Context as ConceptsContext
        g_keys = [_to_hashable(obj) for obj in g]
        m_keys = [_to_hashable(attr) for attr in m]
        g_idx = {k: idx for idx, k in enumerate(g_keys)}
        m_idx = {k: idx for idx, k in enumerate(m_keys)}
        inc_set = set()
        for obj, attr in i:
            gk, mk = _to_hashable(obj), _to_hashable(attr)
            if gk in g_idx and mk in m_idx:
                inc_set.add((g_idx[gk], m_idx[mk]))
        bools = [tuple((gi, mi) in inc_set for mi in range(len(m))) for gi in range(len(g))]
        g_str = [f"g:{g[i]}_{i}" for i in range(len(g))]
        m_str = [f"m:{m[j]}_{j}" for j in range(len(m))]
        ctx = ConceptsContext(g_str, m_str, bools)
        concepts = list(ctx.lattice)
        return {
            "n_concepts": len(concepts),
            "concept_sizes": [[len(c.extent), len(c.intent)] for c in concepts],
        }
    except Exception:
        return {"n_concepts": None, "concept_sizes": None}


def compute_scaled_metrics(ctx, scaling_tool, n_obj: int, n_attr: int) -> dict | None:
    import concurrent.futures
    from adaptexts.many_valued_context import ManyValuedContext
    if not isinstance(ctx, ManyValuedContext) or scaling_tool is None:
        return None
    if n_obj * n_attr > MAX_SCALING_INCIDENCES:
        return None
    # Hard cap: skip entire dataset if scaling + concept counting takes too long
    MAX_TOTAL_SECS = 120
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(scaling_tool.automatic_scale, ctx)
            try:
                scaled = future.result(timeout=MAX_TOTAL_SECS)
            except concurrent.futures.TimeoutError:
                print(f"      (scaling timed out after {MAX_TOTAL_SECS}s, skipping)", flush=True)
                return None
        g, m, i = list(scaled.G), list(scaled.M), list(scaled.I)
        denom = len(g) * len(m)
        # Skip concept counting if the scaled context exceeds the feasibility threshold.
        # Scaling can explode attribute count far beyond the original, making concept
        # enumeration intractable regardless of timeout.
        if denom > MAX_CONCEPT_CELLS:
            print(f"      (scaled context too large for concept count: {denom} cells)", flush=True)
            return {
                "n_objects": len(g), "n_attributes": len(m), "n_incidences": len(i),
                "density": round(len(i) / denom, 4) if denom > 0 else 0.0,
                "context_type": "Context", "n_concepts": None, "concept_sizes": None,
            }
        # Timeout: 60s fixed cap — scaled contexts within MAX_CONCEPT_CELLS are small enough.
        timeout = 60
        with concurrent.futures.ProcessPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_compute_concepts_full, g, m, i)
            try:
                lattice = future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                print(f"      (concept count timed out after {timeout:.0f}s)", flush=True)
                future.cancel()
                ex.shutdown(wait=False, cancel_futures=True)
                lattice = {"n_concepts": None, "concept_sizes": None}
        return {
            "n_objects": len(g),
            "n_attributes": len(m),
            "n_incidences": len(i),
            "density": round(len(i) / denom, 4) if denom > 0 else 0.0,
            "context_type": "Context",
            "n_concepts": lattice["n_concepts"],
            "concept_sizes": lattice["concept_sizes"],
        }
    except Exception as e:
        print(f"      (scaling failed: {e})", flush=True)
        return None



def process_adapter(display_name: str, adapter_id: str, adapter, limit: int | None, scaling_tool=None) -> dict:
    print(f"  {display_name}...")

    properties = {
        "is_sortable": adapter.is_sortable(),
        "is_versionable": adapter.is_versionable(),
        "is_deterministic": adapter.is_deterministic(),
        "is_stateless": adapter.is_stateless(),
        "has_metadata": adapter.has_metadata(),
    }

    datasets = []
    source = itertools.islice(adapter, limit) if limit else iter(adapter)

    for i, ctx in enumerate(source):
        name = ctx.name or f"dataset_{i}"
        print(f"    [{i + 1}] {name}", flush=True)
        try:
            metrics = collect_metrics(ctx)
            ds_id = slugify(name)
            g_list = list(ctx.G)
            m_list = list(ctx.M)
            i_list = list(ctx.I)
            lattice_metrics = compute_lattice_metrics(g_list, m_list, i_list, metrics.get("n_concepts"))
            scaled_metrics = compute_scaled_metrics(ctx, scaling_tool, metrics.get("n_objects", 0), metrics.get("n_attributes", 0))
            datasets.append({
                "id": ds_id,
                "name": name,
                "metrics": {**metrics, **lattice_metrics},
                "scaled_metrics": scaled_metrics,
                "metadata": fetch_metadata(adapter, name),
                "error": None,
            })
        except Exception as e:
            datasets.append({
                "id": slugify(name),
                "name": name,
                "metrics": None,
                "scaled_metrics": None,
                "metadata": None,
                "error": str(e),
            })

    print(f"    → {len(datasets)} dataset(s)")
    return {
        "id": adapter_id,
        "name": display_name,
        "properties": properties,
        "datasets": datasets,
    }


def builtin_adapters(names: list[str]) -> list[tuple[str, str, object]]:
    result = []

    if "uciml" in names:
        try:
            from adaptexts.adapters.examples.uciml import UCIMLAdapter
            from adaptexts.adapters.examples.uciml.uciml import UCIMLFilter
            result.append((
                "UCI ML Adapter",
                "uciml",
                UCIMLAdapter(uciml_filter=UCIMLFilter(include_missing=False, max_features=1000, max_instances=50000)),
            ))
        except Exception as e:
            print(f"  Warning: UCIML adapter unavailable: {e}", file=sys.stderr)

    if "rwc" in names:
        try:
            from adaptexts.adapters.examples.rwc import RWCAdapter
            result.append(("RWC Adapter", "rwc", RWCAdapter()))
        except Exception as e:
            print(f"  Warning: RWC adapter unavailable: {e}", file=sys.stderr)

    if "ipc" in names:
        try:
            from adaptexts.adapters.examples.ipc import IPCAdapter
            result.append(("IPC Adapter", "ipc", IPCAdapter(n=(2, 8))))
        except Exception as e:
            print(f"  Warning: IPC adapter unavailable: {e}", file=sys.stderr)

    return result


def load_user_adapters() -> list[tuple[str, str, object]]:
    path = ROOT / "user_adapters.py"
    if not path.exists():
        return []
    try:
        spec = importlib.util.spec_from_file_location("user_adapters", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        adapters = getattr(module, "ADAPTERS", [])
        if adapters:
            print(f"  Loaded {len(adapters)} user adapter(s) from user_adapters.py")
        return adapters
    except Exception as e:
        print(f"  Warning: Failed to load user_adapters.py: {e}", file=sys.stderr)
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None, metavar="N",
                        help="Max datasets per adapter")
    parser.add_argument("--adapters", default="uciml,rwc,ipc",
                        help="Built-in adapters to include (default: uciml,rwc,ipc)")
    parser.add_argument("--no-scaling", action="store_true",
                        help="Skip automatic scaling of many-valued contexts")
    args = parser.parse_args()

    names = [n.strip() for n in args.adapters.split(",")]
    print("Initializing adapters...")
    all_adapters = builtin_adapters(names) + load_user_adapters()

    if not all_adapters:
        print("No adapters found. Nothing to do.", file=sys.stderr)
        sys.exit(1)

    def _run(scaling_tool):
        result_adapters = []
        for display_name, adapter_id, adapter in all_adapters:
            try:
                result_adapters.append(process_adapter(display_name, adapter_id, adapter, args.limit, scaling_tool))
            except Exception as e:
                print(f"  Error processing {display_name}: {e}", file=sys.stderr)
                traceback.print_exc()
        return result_adapters

    if args.no_scaling:
        result_adapters = _run(scaling_tool=None)
    else:
        try:
            from adaptexts.tools.scaling import ScalingTool
            print("Starting scaling server...")
            with ScalingTool(auto_server=True) as scaling_tool:
                print("Scaling server ready.")
                result_adapters = _run(scaling_tool)
        except Exception as e:
            print(f"  Warning: scaling unavailable ({e}), continuing without.", file=sys.stderr)
            result_adapters = _run(scaling_tool=None)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "adapters": result_adapters,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))

    total = sum(len(a["datasets"]) for a in result_adapters)
    print(f"\nWrote {OUTPUT_PATH}")
    print(f"Total: {len(result_adapters)} adapter(s), {total} dataset(s)")


if __name__ == "__main__":
    main()
