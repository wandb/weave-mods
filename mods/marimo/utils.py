"""Utility functions for the W&B marimo dashboard."""

import os


# ============================================================================
# Environment & Configuration
# ============================================================================


def resolve_entity_project():
    """Parse WANDB_PROJECT env var into (entity, project) tuple.

    Returns:
        tuple: (entity, project) where either can be None
    """
    proj = os.getenv("WANDB_PROJECT")
    if not proj:
        return None, None
    if "/" in proj:
        entity, project = proj.split("/", 1)
        return entity, project
    return os.getenv("WANDB_ENTITY"), proj


# ============================================================================
# API Setup
# ============================================================================


def api():
    """Create and return a wandb.Api instance."""
    import wandb

    return wandb.Api()


# ============================================================================
# Data Fetching
# ============================================================================


def fetch_runs(entity, project, per_page=200):
    """Fetch runs from W&B.

    Args:
        entity: W&B entity name (can be None)
        project: W&B project name
        per_page: Number of runs to fetch per page

    Returns:
        list of runs on success, or mo.md error message on failure
    """
    if not project:
        return []
    a = api()
    path = f"{entity}/{project}" if entity else project
    try:
        return list(a.runs(path, per_page=per_page))
    except Exception as e:
        import marimo as mo

        return mo.md(f"❌ **Error:** Failed to list runs for {path}: {e}")


def fetch_artifacts(entity, project, type_filter=None, per_page=200):
    """Fetch artifacts from W&B.

    Args:
        entity: W&B entity name (can be None)
        project: W&B project name
        type_filter: Optional artifact type filter (str or callable)
        per_page: Number of artifacts to fetch per page

    Returns:
        list of artifacts on success, or mo.md error message on failure
    """
    if not project:
        return []
    a = api()
    tf = (
        type_filter
        if isinstance(type_filter, str) or type_filter is None
        else type_filter()
    )
    try:
        if tf is None:
            types = a.artifact_types(project=project)
        else:
            types = [a.artifact_type(type_name=tf, project=project)]
        arts = []
        for type in types:
            for c in type.collections():
                arts.extend(list(c.artifacts()))
        return list(arts)
    except Exception as e:
        import marimo as mo

        return mo.md(f"❌ **Error:** Failed to list artifacts for {project}: {e}")


# ============================================================================
# Data Transformations
# ============================================================================


def short_run_row(run):
    """Convert a run object to a dict for table display.

    Args:
        run: W&B run object

    Returns:
        dict with run metadata and top metrics
    """
    name = getattr(run, "name", "") or run.id
    state = getattr(run, "state", "")
    created = getattr(run, "created_at", None)
    tags = ", ".join(getattr(run, "tags", []) or [])
    summary = dict(getattr(run, "summary", {}) or {})
    metrics = {k: v for k, v in summary.items() if isinstance(v, (int, float))}
    return {
        "name": name,
        "id": run.id,
        "state": state,
        "created_at": str(created) if created else "",
        **({k: metrics[k] for k in sorted(metrics.keys())[:4]} if metrics else {}),
        "tags": tags,
    }


def apply_run_filters(
    rows, search_query="", states=None, tag_query="", metric="", sort_desc=True
):
    """Filter and sort run rows.

    Args:
        rows: List of run row dicts
        search_query: Search string for name/id/tags
        states: Set or list of state strings to filter by
        tag_query: Comma-separated tags to filter by
        metric: Metric name to sort by
        sort_desc: Whether to sort descending

    Returns:
        Filtered and sorted list of run row dicts
    """
    q = (search_query or "").strip().lower()
    states_set = set(states or [])
    tags = [t.strip().lower() for t in (tag_query or "").split(",") if t.strip()]

    def ok(row):
        text = f"{row['name']} {row['id']} {row.get('tags', '')}".lower()
        if q and q not in text:
            return False
        if states_set and row["state"] not in states_set:
            return False
        if tags:
            row_tags = {
                t.strip().lower()
                for t in (row.get("tags", "") or "").split(",")
                if t.strip()
            }
            if not set(tags).issubset(row_tags):
                return False
        return True

    out = [r for r in rows if ok(r)]
    metric_key = (metric or "").strip()
    if metric_key:
        out.sort(key=lambda r: r.get(metric_key), reverse=bool(sort_desc))
    return out
