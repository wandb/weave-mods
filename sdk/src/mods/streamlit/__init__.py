import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
import weave
from weave.trace.refs import parse_uri
from weave.trace.urls import redirect_call
from weave.trace.weave_client import WeaveClient
from weave.wandb_interface import wandb_api

import mods.api.query as query

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
    print("project_stack", weave_clients)
    if len(weave_clients) == 0:
        return weave_client()
    return weave_client(list(weave_clients.keys())[-1])


def safe_df(df: pd.DataFrame):
    # Streamlit dies on some pyarrow code if there is a list column that
    # has non-uniform types in it. So attempt to extract useful text or
    # just convert those to json strings for display
    client = current_client()
    entity_name, project_name = client.entity, client.project

    def id_to_url(val):
        if isinstance(val, str):
            return redirect_call(entity_name, project_name, val)
        return val

    def to_json_string(val):
        if isinstance(val, list):
            try:
                # OpenAI chat messages / completion choices
                if len(val) > 1:
                    if isinstance(val[1], dict) and val[1].get("role") == "user":
                        content = val[1].get("content")
                    elif isinstance(val[0], dict):
                        content = val[0].get("content")
                    if isinstance(content, list):
                        return content[0].get("text", "...")
                    if content:
                        return content
                elif len(val) > 0:
                    if isinstance(val[0], dict):
                        if val[0].get("message"):
                            return val[0].get("message").get("content")
                        elif val[0].get("text"):
                            return val[0].get("text")
                return json.dumps(val)
            except TypeError:
                return str(val)
        return val

    # Apply the function to each element of the DataFrame
    df = df.map(to_json_string)

    # Add links to the actual call
    print("df_columns", df.columns)
    if "id" in df.columns:
        df["id"] = df["id"].map(id_to_url)
    return df


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
            "Project name must contain a slash with your username or team name"
        )
    if weave_clients.get(project) is None:
        weave_clients[project] = weave.init(project)
    return weave_clients[project]


def op_selectbox(
    label: str,
    sort_key: Optional[Callable[[query.Op], Any]] = None,
    client: WeaveClient | None = None,
):
    if client is None:
        client = current_client()
    ops = query.get_ops(client)
    if sort_key is None:

        def sort_key(x: query.Op):
            return x.name

    ops = sorted(ops, key=sort_key)
    selection = st.selectbox(
        label,
        options=ops,
        index=None,
        placeholder="Select an Op...",
        format_func=lambda x: f"{x.name} ({x.version_index + 1} versions)",
    )
    return selection


def obj_selectbox(
    label: str,
    types: List[str] | str = [],
    sort_key: Optional[Callable[[query.Obj], Any]] = None,
    client: WeaveClient | None = None,
):
    if client is None:
        client = current_client()
    objs = query.get_objs(client, types=types)
    if sort_key:
        objs = sorted(objs, key=sort_key)
    thing = "Object"
    if len(types) > 0:
        thing = types[0]
    return st.selectbox(
        label,
        options=objs,
        index=None,
        placeholder=f"Select an {thing}...",
        format_func=lambda o: f"{o.ref().name}:{o.ref().digest[:3]}",
    )


def dataset_selectbox(
    label: str,
    sort_key: Optional[Callable[[query.Obj], Any]] = None,
    client: WeaveClient | None = None,
):
    return obj_selectbox(label, types=["Dataset"], sort_key=sort_key, client=client)


def model_selectbox(
    label: str,
    sort_key: Optional[Callable[[query.Obj], Any]] = None,
    client: WeaveClient | None = None,
):
    return obj_selectbox(label, types=["Model"], sort_key=sort_key, client=client)


def _format_table_for_openai(calls: query.Calls) -> Dict[str, st.column_config.Column]:
    # id, trace_id
    column_config = {
        "id": st.column_config.LinkColumn("ID", display_text=r".+/call/(.+?)-"),
        "inputs.messages": "Input",
        "inputs.model": "Model",
        "output.choices": "Output",
        "started_at": st.column_config.DatetimeColumn(
            "Started At",
            format="MMM MM h:mm:ss",
        ),
        "summary.weave.status": "Status",
        "summary.weave.latency_ms": st.column_config.NumberColumn(
            "Latency",
            format="%.2f ms",
        ),
        "summary.usage.total_tokens": st.column_config.NumberColumn(
            "Total Tokens",
            format="%d",
        ),
    }
    # "op_name": st.column_config.LinkColumn("Op", display_text=r".+/op/(.+):"),
    for col in calls.columns():
        if col.name not in column_config:
            column_config[col.name] = None
    return column_config


def calls_table(
    op_names: List[str] | str | None = None,
    input_refs: List[str] | str | None = None,
    client: WeaveClient | None = None,
) -> Tuple[query.Calls, int | None]:
    if client is None:
        client = current_client()

    calls = query.cached_get_calls(client, op_names, input_refs)
    column_config = {}
    if not isinstance(op_names, list):
        op_names = [op_names]
    if op_names[0] and "openai.chat" in op_names[0]:
        column_config = _format_table_for_openai(calls)
    selected = st.dataframe(
        safe_df(calls.df),
        selection_mode="single-row",
        on_select="rerun",
        hide_index=True,
        column_config=column_config,
    )
    selected_rows = selected["selection"]["rows"]
    if selected_rows:
        selected_row = selected_rows[0]
        row = calls.df.index[selected_row]
        return calls, row  # calls.loc(row)
    return calls, None


def call_chat_thread(call: pd.Series):
    st.write(f"Call: {call.id}")
    if call["inputs.messages"]:
        for m in call["inputs.messages"]:
            if m["role"] == "system":
                with st.expander("System Message"):
                    with st.chat_message(m["role"]):
                        st.write(m["content"])
            else:
                with st.chat_message(m["role"]):
                    if isinstance(m["content"], list):
                        for c in m["content"]:
                            if c.get("text"):
                                st.write(c["text"])
                            elif c.get("image_url"):
                                st.image(c["image_url"]["url"])
                    else:
                        st.write(m["content"])
    if not isinstance(call["output.choices"], list):
        st.json(call["output.choices"])
    else:
        for c in call["output.choices"]:
            content = c["message"]["content"]
            with st.chat_message(c["message"]["role"]):
                if "</div>" in content:
                    st.code(content, language="html")
                # TODO: not sure if this is needed...
                elif content.strip().startswith(("{", "[")):
                    st.json(content)
                else:
                    st.write(content)


__all__ = [
    "weave_client",
    "op_selectbox",
    "obj_selectbox",
    "dataset_selectbox",
    "model_selectbox",
    "calls_table",
    "call_chat_thread",
]
