import json
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
import streamlit as st
from weave.trace.urls import redirect_call
from weave.trace.weave_client import WeaveClient

from mods.api import query
from mods.streamlit.api import current_client, get_calls


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
                    content = None
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


def _format_table_for_openai(
    calls: query.Calls,
) -> Dict[str, Union[st.column_config.Column, None]]:
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
        "anomaly_score": st.column_config.NumberColumn(
            "Anomaly Score",
            format="%.3f",
        ),
        "anomaly_label": st.column_config.TextColumn(
            "Anomaly Label",
        ),
    }
    # "op_name": st.column_config.LinkColumn("Op", display_text=r".+/op/(.+):"),
    for col in calls.columns():
        if col.name not in column_config:
            column_config[col.name] = None
    return column_config


def tracetable(
    op_names: List[str] | str | None = None,
    input_refs: List[str] | str | None = None,
    dataframe: pd.DataFrame | None = None,
    cached: bool = True,
    client: WeaveClient | None = None,
) -> Tuple[query.Calls, Optional[int]]:
    """Creates an interactive Streamlit table for displaying and selecting trace data.

    This function generates a Streamlit dataframe component that displays trace data
    with configurable columns and single-row selection capability. It's primarily used
    for visualizing OpenAI chat traces and other operation traces.

    Args:
        op_names: A string or list of operation names to filter the traces.
            Example: "openai.chat.completions"
        input_refs: A string or list of input references to filter the traces.
        dataframe: An optional pandas DataFrame to use instead of fetching new data.
        client: An optional WeaveClient instance. If None, uses the current client.

    Returns:
        A tuple containing:
        - query.Calls object containing the trace data
        - Selected row index (int) if a row is selected, None otherwise

    Example:
        ```python
        calls, selected_row = tracetable(op_names="openai.chat.completions")
        if selected_row is not None:
            st.write(f"Selected row: {selected_row}")
        ```
    """
    if client is None:
        client = current_client()

    if dataframe is None:
        calls = get_calls(client, op_names, input_refs, cached)
    else:
        calls = query.Calls(dataframe)
    column_config = {}

    op_names_list: List[str] = []
    if isinstance(op_names, str):
        op_names_list = [op_names]
    elif isinstance(op_names, list):
        op_names_list = op_names

    # TODO: this is a hack, we should have a better way to detect if the table is for openai
    if op_names_list and "openai.chat" in op_names_list[0]:
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
        # row = calls.df.index[selected_row]
        return calls, selected_row  # calls.loc(row)
    return calls, None
