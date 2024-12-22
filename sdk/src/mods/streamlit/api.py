import os
from typing import Dict, List

import pandas as pd
import streamlit as st
import weave
from weave.trace.weave_client import WeaveClient
from weave.wandb_interface import wandb_api

from mods.api.query import ST_HASH_FUNCS, Calls, Obj, Op, get_objs
from mods.api.query import get_calls as api_get_calls

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
    if len(weave_clients) == 0:
        return weave_client()
    return weave_client(list(weave_clients.keys())[-1])


def weave_client(project: str | None = None):
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


def get_calls(
    client: WeaveClient,
    op_name: str | List[str] | List[Op] | None,
    input_refs=None,
    cached=True,
) -> Calls:
    def progress(status, offset: int = 0):
        def _callback(calls_fetched: int):
            status.update(
                label=f"Fetching calls... ({calls_fetched + offset} calls fetched)"
            )

        return _callback

    if not cached:
        with st.status("Fetching calls...") as status:
            return api_get_calls(client, op_name, input_refs, callback=progress(status))

    @st.cache_data(persist="disk", hash_funcs=ST_HASH_FUNCS)
    def cached_get_calls(client, op_name, input_refs, _progress):
        return api_get_calls(client, op_name, input_refs, callback=_progress)

    status_container = st.empty()
    with status_container.status("Fetching calls...") as status:
        if not isinstance(op_name, list):
            calls = cached_get_calls(client, op_name, input_refs, progress(status))
            status.update(state="complete")
            status_container.empty()
            return calls

        df = pd.DataFrame()
        offset = 0
        for op in op_name:
            result = cached_get_calls(client, op, input_refs, progress(status, offset))
            result.df = result.df.dropna(subset=["id"])
            offset += result.df.shape[0]

            if df.empty:
                df = result.df.copy()
            else:
                df = pd.concat([df, result.df], ignore_index=True)
    status_container.empty()
    df = df.set_index("id", drop=False)
    return Calls(df)


def get_objects(
    client: WeaveClient,
    object_type: str,
    latest_only: bool = True,
    cached=True,
) -> List[Obj]:
    if not cached:
        return get_objs(client, object_type, latest_only)

    @st.cache_data(hash_funcs=ST_HASH_FUNCS)
    def _cached_get_objects(client, object_type, latest_only):
        return get_objs(client, object_type, latest_only)

    return _cached_get_objects(client, object_type, latest_only)
