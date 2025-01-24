import os
from typing import Any, Dict, List

import pandas as pd
import streamlit as st
import weave
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import CallsFilter
from weave.wandb_interface import wandb_api

from mods.api.query import ST_HASH_FUNCS, Calls, Obj, Op, get_objs
from mods.api.query import get_calls as api_get_calls
from mods.api.query import get_op_versions as api_get_op_versions
from mods.api.query import get_ops as api_get_ops
from mods.api.weave_api_next import weave_client_get_batch

default_entity: str | None = os.getenv("WANDB_ENTITY")
weave_clients: Dict[str, WeaveClient] = {}


def get_default_entity():
    global default_entity
    if default_entity is None:
        wandb_api.init()
        api = wandb_api.get_wandb_api_sync()
        default_entity = api.default_entity_name()
    return default_entity


# TODO: this is unfortunate, but get's the job done for now
if os.getenv("WANDB_API_KEY") is not None:
    if default_entity is None:
        default_entity = get_default_entity()


def current_client():
    """Get the most recently used WeaveClient instance.

    Returns:
        WeaveClient: If no clients exist, creates a new client using environment variables.
            Otherwise returns the most recently created client.
    """
    if len(weave_clients) == 0:
        return weave_client()
    return weave_client(list(weave_clients.keys())[-1])


def weave_client(project: str | None = None):
    """Initialize or retrieve a cached WeaveClient for a given project.

    Args:
        project: Optional project name or path. If None, uses WANDB_PROJECT environment variable.
            Can be in format "project" or "entity/project".

    Returns:
        WeaveClient: A cached WeaveClient instance for the specified project.

    Raises:
        AssertionError: If WANDB_PROJECT environment variable is not set when project is None.
        ValueError: If entity cannot be determined from project or environment variables.
    """
    global weave_clients
    if project is None:
        project = os.getenv("WANDB_PROJECT")
    assert project is not None, "WANDB_PROJECT environment variable is not set"
    if "/" not in project and default_entity is not None:
        project = f"{default_entity}/{project}"
    elif "/" not in project:
        raise ValueError(
            "Couldn't determine your team or username, check your WANDB_API_KEY env variable, or set WANDB_ENTITY"
        )

    @st.cache_resource()
    def _cached_weave_client(project: str):
        if weave_clients.get(project) is None:
            weave_clients[project] = weave.init(project)
        return weave_clients[project]

    return _cached_weave_client(project)


def current_project_id(client: WeaveClient | None = None):
    """Get the current project ID from the WeaveClient.

    Args:
        client: Optional WeaveClient instance. If None, uses the current client.

    Returns:
        str: The project ID associated with the WeaveClient
    """
    if client is None:
        client = current_client()
    return client._project_id()


def to_ref(name: str, project_id: str | None = None, type: str = "op"):
    """Convert a name into a fully qualified Weave reference URI.

    Args:
        name: Name to convert to a reference
        project_id: Optional project ID. If None, uses the current project ID.
        type: Type of reference (defaults to "op")

    Returns:
        str: Fully qualified Weave reference URI in the format weave:///{project_id}/{type}/{name}
    """
    if project_id is None:
        project_id = current_project_id()
    if ":" not in name:
        name = name + ":*"
    return f"weave:///{project_id}/{type}/{name}"


def simple_val(v: Any) -> str | List[str] | Dict[str, Any]:
    if isinstance(v, dict):
        return {k: simple_val(v) for k, v in v.items()}
    elif isinstance(v, list):
        return [simple_val(v) for v in v]
    elif hasattr(v, "uri"):
        return v.uri()
    # elif hasattr(v, "__dict__"):
    #     return {k: simple_val(v) for k, v in v.__dict__.items()}
    else:
        return v


def resolve_refs(refs: List[str], client: WeaveClient | None = None) -> pd.DataFrame:
    if client is None:
        client = current_client()

    @st.cache_data(hash_funcs=ST_HASH_FUNCS)
    def _cached_resolve_refs(client, refs):
        # Resolve the refs and fetch the message.text field
        # Note we do do this after grouping, so we don't over-fetch refs
        ref_vals = weave_client_get_batch(client, refs)
        ref_vals = simple_val(ref_vals)
        ref_val_df = pd.json_normalize(ref_vals)
        ref_val_df.index = refs
        return ref_val_df

    return _cached_resolve_refs(client, refs)


def get_calls(
    op_name: str | List[str] | List[Op] | None = None,
    input_refs: Dict[str, Any] | None = None,
    calls_filter: CallsFilter | None = None,
    cached: bool = True,
    client: WeaveClient | None = None,
) -> Calls:
    """Fetch operation calls from Weave with optional caching and progress tracking.

    Args:
        op_name: Operation name(s) to fetch. Can be a single operation or list of operations
        input_refs: Optional dictionary of input references to filter calls
        calls_filter: Optional CallsFilter to filter calls by
        cached: Whether to use cached results (defaults to True)
        client: WeaveClient instance

    Returns:
        Calls object containing the fetched operation calls
    """
    if client is None:
        client = current_client()

    def progress(status, offset: int = 0):
        def _callback(calls_fetched: int):
            total = calls_fetched + offset
            if status is not None:
                status.update(
                    label=f"Fetching calls... ({total:,} found)",
                )

        return _callback

    if not cached:
        with st.status("Fetching calls...", expanded=True) as status:
            return api_get_calls(
                client, op_name, input_refs, calls_filter, callback=progress(status)
            )

    @st.cache_data(persist="disk", hash_funcs=ST_HASH_FUNCS, ttl=3600)
    def cached_get_calls(client, op_name, input_refs, calls_filter, _progress):
        return api_get_calls(
            client, op_name, input_refs, calls_filter, callback=_progress
        )

    status_container = st.empty()
    try:
        with status_container.status("Fetching calls...", expanded=True) as status:
            if not isinstance(op_name, list):
                calls = cached_get_calls(
                    client, op_name, input_refs, calls_filter, progress(status)
                )
                if status is not None:
                    status.update(state="complete")
                return calls

            df = pd.DataFrame()
            offset = 0
            for op in op_name:
                result = cached_get_calls(
                    client, op, input_refs, calls_filter, progress(status, offset)
                )
                if result.df is not None and not result.df.empty:
                    result.df = result.df.dropna(subset=["id"])
                    offset += len(result.df)
                    df = (
                        pd.concat([df, result.df], ignore_index=True)
                        if not df.empty
                        else result.df.copy()
                    )
            if status is not None:
                status.update(state="complete")
    except Exception as e:
        status_container.error(f"Error: {str(e)}")
        raise
    finally:
        status_container.empty()

    return Calls(df.set_index("id", drop=False) if not df.empty else df)


def get_objects(
    object_type: str,
    latest_only: bool = True,
    cached: bool = True,
    client: WeaveClient | None = None,
) -> List[Obj]:
    """Fetch objects of a specific type from Weave with optional caching.

    Args:
        client: WeaveClient instance
        object_type: Type of objects to fetch
        latest_only: Whether to fetch only the latest version of each object
        cached: Whether to use cached results (defaults to True)

    Returns:
        List of Obj instances
    """
    if client is None:
        client = current_client()
    if not cached:
        return get_objs(client, object_type, latest_only)

    @st.cache_data(hash_funcs=ST_HASH_FUNCS)
    def cached_get_objects(client, object_type, latest_only):
        return get_objs(client, object_type, latest_only)

    return cached_get_objects(client, object_type, latest_only)


def get_ops(
    latest_only: bool = True,
    cached: bool = True,
    client: WeaveClient | None = None,
) -> List[Op]:
    """Fetch operations from Weave with optional caching.

    Args:
        latest_only: Whether to fetch only the latest version of each operation (defaults to True)
        cached: Whether to use cached results (defaults to True)
        client: Optional WeaveClient instance

    Returns:
        List of operations
    """
    if client is None:
        client = current_client()
    if not cached:
        return api_get_ops(client, latest_only=latest_only)

    @st.cache_data(hash_funcs=ST_HASH_FUNCS)
    def cached_get_ops(client: WeaveClient, latest_only: bool):
        return api_get_ops(client, latest_only=latest_only)

    return cached_get_ops(client, latest_only)


def get_op_versions(
    op: Op,
    include_call_counts: bool = False,
    cached: bool = True,
    client: WeaveClient | None = None,
) -> List[Op]:
    """Fetch versions of a specific operation from Weave with optional caching.

    Args:
        op: Operation to fetch versions for
        include_call_counts: Whether to include call counts for each version (defaults to False)
        cached: Whether to use cached results (defaults to True)
        client: Optional WeaveClient instance

    Returns:
        List of operation versions with optional call counts
    """
    if client is None:
        client = current_client()
    if not cached:
        return api_get_op_versions(client, op, include_call_counts)

    @st.cache_data(hash_funcs=ST_HASH_FUNCS)
    def cached_get_op_versions(client: WeaveClient, op: Op, include_call_counts: bool):
        return api_get_op_versions(client, op, include_call_counts)

    return cached_get_op_versions(client, op, include_call_counts)


__all__ = [
    "get_calls",
    "get_objects",
    "get_ops",
    "get_op_versions",
    "current_project_id",
    "to_ref",
    "resolve_refs",
    "weave_client",
    "current_client",
    "CallsFilter",
]
