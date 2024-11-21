import os
from typing import Dict, List

import pandas as pd
import streamlit as st
import weave
from weave.trace.weave_client import WeaveClient
from weave.wandb_interface import wandb_api

from mods.api.query import ST_HASH_FUNCS, Calls, Op
from mods.api.query import get_calls as api_get_calls

default_entity: str | None = os.getenv("WANDB_ENTITY")
weave_clients: Dict[str, WeaveClient] = {}


@st.cache_data
def get_default_entity():
    wandb_api.init()
    api = wandb_api.get_wandb_api_sync()
    return api.default_entity_name()


# TODO: this is unfortunate, but get's the job done for now
if os.getenv("WANDB_API_KEY") is not None:
    if default_entity is None:
        default_entity = get_default_entity()


def current_client():
    if len(weave_clients) == 0:
        return weave_client()
    return weave_client(list(weave_clients.keys())[-1])


@st.cache_resource()
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
    if weave_clients.get(project) is None:
        weave_clients[project] = weave.init(project)
    return weave_clients[project]


@st.cache_data(hash_funcs=ST_HASH_FUNCS)
def cached_calls_for_op(client: WeaveClient, op_name: str | Op | None, input_refs=None):
    return api_get_calls(client, op_name, input_refs)


def get_calls(
    client: WeaveClient,
    op_name: str | List[str] | List[Op] | None,
    input_refs=None,
    cached=True,
):
    if not cached:
        return api_get_calls(client, op_name, input_refs)
    if not isinstance(op_name, list):
        return cached_calls_for_op(client, op_name, input_refs)
    df = pd.DataFrame()
    for op in op_name:
        result = cached_calls_for_op(client, op, input_refs)
        result.df = result.df.dropna(subset=["id"])

        if df.empty:
            df = result.df.copy()
        else:
            df = pd.concat([df, result.df], ignore_index=True)
    df = df.set_index("id", drop=False)
    return Calls(df)
