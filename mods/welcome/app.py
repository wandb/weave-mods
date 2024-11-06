import streamlit as st
import itertools
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import weave
from datetime import datetime, timedelta
import itertools
import json
import os
import time

st.set_page_config(layout="wide", page_title="Weave Welcome Dashboard")
st.markdown(
    """
    <style>
    .main { padding: 0 50px; }
    .header { font-size: 2.5rem; font-weight: bold; text-align: center; margin-bottom: 30px; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def init_weave_client(project_name):
    try:
        client = weave.init(project_name)
        return client
    except Exception as e:
        st.error(f"Failed to initialize Weave client for project '{project_name}': {e}")
        return None


def fetch_calls(client, project_id, start_time, trace_roots_only, limit):
    filter_params = {
        "project_id": project_id,
        "filter": {"trace_roots_only": trace_roots_only},
        "columns": ["started_at", "trace_id", "display_name", "op_name"], # , "inputs", "output"
        # "expand_columns": ["inputs.example", "inputs.model"],
        "sort_by": [{"field": "started_at", "direction": "desc"}],
        "include_costs": True,
        "limit": limit,
    }
    try:
        start = time.perf_counter()
        calls_stream = client.server.calls_query_stream(filter_params)
        calls = list(itertools.islice(calls_stream, limit))
        end = time.perf_counter()
        st.write(f"Fetched {len(calls)} calls in {end - start:.2f} seconds.")
        return calls
    except Exception as e:
        if hasattr(e, "response"):
            st.error(f"Error fetching calls: {e.response.text}")
        st.error(f"Error fetching calls: {e}")
        return []


def process_calls(calls):
    records = []
    for call in calls:
        costs = call.summary.get("weave", {}).get("costs", {}) or {}
        total_tokens = sum(
            cost.get("prompt_tokens", 0) + cost.get("completion_tokens", 0)
            for cost in costs.values()
        )
        feedback = call.summary.get("weave", {}).get("feedback", [])
        thumbs_up = sum(
            1
            for item in feedback
            if isinstance(item, dict) and item.get("payload", {}).get("emoji") == "👍"
        )
        thumbs_down = sum(
            1
            for item in feedback
            if isinstance(item, dict) and item.get("payload", {}).get("emoji") == "👎"
        )

        records.append(
            {
                "Call ID": call.id,
                "Trace ID": call.trace_id,
                "Display Name": call.display_name,
                "Tokens": total_tokens,
                "Latency (ms)": call.summary.get("weave", {}).get("latency_ms", 0),
                "Thumbs Up": thumbs_up,
                "Thumbs Down": thumbs_down,
                "Started At": pd.to_datetime(getattr(call, "started_at", datetime.min)),
                "Inputs": json.dumps(call.inputs, default=str),
                "Outputs": json.dumps(call.output, default=str),
                "Call Name": call.op_name.split(":")[-2].split("/")[
                    -1
                ],  # if call.display_name else call.display_name
            }
        )
    return pd.DataFrame(records)


def plot_feedback_pie_chart(thumbs_up, thumbs_down):
    fig = go.Figure(
        data=[
            go.Pie(
                labels=["Thumbs Up", "Thumbs Down"],
                values=[thumbs_up, thumbs_down],
                marker=dict(colors=["#66b3ff", "#ff9999"]),
                hole=0.3,
            )
        ]
    )
    fig.update_traces(textinfo="percent+label", hoverinfo="label+percent")
    fig.update_layout(showlegend=False, title="Feedback Summary")
    return fig


def plot_token_usage(df):
    fig = px.area(
        df, x="Started At", y="Tokens", color="Call Name", title="Token Usage Over Time"
    )
    fig.update_layout(xaxis_title="Time", yaxis_title="Total Tokens", showlegend=True)
    return fig


def plot_latency_over_time(df):
    fig = px.bar(
        df,
        x="Started At",
        y="Latency (ms)",
        color="Call Name",
        title="Latency Over Time",
    )
    fig.update_layout(xaxis_title="Time", yaxis_title="Latency (ms)", showlegend=True)
    return fig


def plot_model_cost_distribution(df):
    fig = px.bar(
        df,
        x="llm_id",
        y="total_cost",
        color="llm_id",
        title="Cost Distribution by Model",
    )
    fig.update_layout(xaxis_title="Call Name", yaxis_title="Cost (USD)")
    return fig


def render_dashboard():
    # Configs panel
    st.markdown(
        "<div class='header'>Weave LLM Monitoring Dashboard</div>",
        unsafe_allow_html=True,
    )

    # Add custom Weave project URL input with default example
    default_project_url = os.getenv("WANDB_ENTITY", "vanpelt") + "/" + os.getenv("WANDB_PROJECT", "openui-hosted")
    custom_project_url = st.sidebar.text_input(
        "Custom Weave Project URL", value=default_project_url
    )

    # Add WandB API key input
    wandb_key = st.sidebar.text_input("WandB API Key", type="password")
    if wandb_key:
        os.environ["WANDB_API_KEY"] = wandb_key

    trace_roots_only = st.sidebar.toggle("Trace Roots Only", value=True)

    # Use custom project URL if provided, otherwise use the dropdown
    if custom_project_url != default_project_url:
        selected_project = custom_project_url
    else:
        selected_project = st.sidebar.selectbox(
            "Select Weave Project", [default_project_url, "foo", "bar"], index=0
        )

    client = init_weave_client(selected_project)
    if client is None:
        st.stop()

    start_date = st.sidebar.date_input(
        "Select Start Date", value=datetime.now().date() - timedelta(days=1)
    )
    start_time = datetime.combine(start_date, datetime.min.time())

    calls_limit = st.sidebar.number_input(
        "Set calls limit", min_value=1, max_value=10000, value=1000, step=100
    )

    st.write(
        f"Fetching data from **{start_time}** UTC for project **{selected_project}**."
    )
    st.write(f"Trace Roots Only: **{'Yes' if trace_roots_only else 'No'}**")
    st.write(f"Calls Limit: **{calls_limit}**")

    # Fetch and process calls from Weave
    with st.spinner("Fetching data from Weave..."):
        calls = fetch_calls(
            client, selected_project, start_time, trace_roots_only, calls_limit
        )
        if not calls:
            st.warning("No calls found for the selected time range.")
            return
        df_calls = process_calls(calls)
        st.success(f"Successfully fetched and processed {len(df_calls)} calls.")

    # Use project-level cost API to get costs from Weave
    costs = client.query_costs()
    df_costs = pd.DataFrame([cost.dict() for cost in costs])
    df_costs["total_cost"] = (
        df_costs["prompt_token_cost"] + df_costs["completion_token_cost"]
    )

    # String metrics
    total_calls = len(df_calls)
    total_cost = df_costs["total_cost"].sum()
    total_tokens = df_calls["Tokens"].sum()
    thumbs_up, thumbs_down = df_calls["Thumbs Up"].sum(), df_calls["Thumbs Down"].sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Calls", total_calls)
    col2.metric("Total Cost (USD)", f"${total_cost:.6f}")
    col3.metric("Total Tokens", f"{total_tokens}")
    col4.metric("Feedback 👍 / 👎", f"{thumbs_up} / {thumbs_down}")

    st.markdown("---")

    # First plots - feedback and cost distribution
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            plot_feedback_pie_chart(thumbs_up, thumbs_down), use_container_width=True
        )
    with col2:
        st.plotly_chart(
            plot_model_cost_distribution(df_costs), use_container_width=True
        )

    # Second plots - token usage and latency over time
    tab1, tab2 = st.tabs(["Token Usage", "Latency"])
    with tab1:
        st.plotly_chart(plot_token_usage(df_calls), use_container_width=True)
    with tab2:
        if not df_calls.empty:
            st.plotly_chart(plot_latency_over_time(df_calls), use_container_width=True)
        else:
            st.warning("No latency data available for the selected time range.")

    st.markdown("---")

    # Raw data expander
    with st.expander("Show Raw Data"):
        st.dataframe(df_calls)
        csv = df_calls.to_csv(index=False)
        st.download_button(
            label="Download raw data as CSV",
            data=csv,
            file_name="raw_calls_data.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    render_dashboard()
