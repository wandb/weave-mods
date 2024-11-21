import os
import json
import streamlit as st
import pandas as pd
import weave
from weave.wandb_interface import wandb_api
from weave.trace.vals import WeaveObject
from weave import Dataset

@st.cache_resource
def init_weave_client(project_name):
    try:
        client = weave.init(project_name)
        return client
    except Exception as e:
        st.error(f"Failed to initialize Weave client for project '{project_name}': {e}")
        return None

@st.cache_resource
def get_traces(_client):
    calls = _client.get_calls()
    # FIXME: This seems silly
    traces = {}
    for call in calls:
        name = call.summary["weave"]["trace_name"]
        if name not in traces.keys():
            traces[name] = []
        traces[name].append(call)
    return traces

def flatten_traces(traces):
    items = []
    for call in traces:
        item = {}
        item["trace_id"] = call.trace_id
        item = item | flatten(call.inputs, "input")
        item = item | flatten(call.output, "output")
        items.append(item)
    return items

selected_project = os.getenv("WANDB_PROJECT")
client = init_weave_client(selected_project)
if client is None:
    st.stop()

wandb_api.init()
api = wandb_api.get_wandb_api_sync()

traces = get_traces(client)

# Configuration sidebar
st.sidebar.header("Settings")
wandb_entity = st.sidebar.text_input("Entity", value=api.default_entity_name(), disabled=True)
wandb_project = st.sidebar.text_input("Project", value=selected_project, disabled=True)

# st.title("TraceCraft")
st.header("Turn your traces into custom datasets")
st.markdown("""
    This mod helps you build a dataset from your weave traces. To get started,
    select a trace to show its fields, and type in a name for each field that
    you would like to include in the dataset. Finally, click the "Save Dataset"
""")
st.subheader("Step 1: Select a trace", divider=True)
selected_trace = st.selectbox("Trace", options=traces.keys(), index=0)

# Flatten nested trace for table-like display
def flatten(root, parent_key=""):
    items = {}
    if isinstance(root, dict):
        for k, v in root.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            items = items | flatten(v, new_key)
    elif isinstance(root, list):
        for i, item in enumerate(root):
            items = items | flatten(item, f"{parent_key}[{i}]")
    elif isinstance(root, WeaveObject):
        keys = root._val.__dict__.keys()
        fields = {}
        for k in keys:
            if k.startswith("_"):
                continue
            val = getattr(root, k)
            fields[k] = val
        items = items | flatten(fields, parent_key)
    else:
        items[parent_key] = root
    return items

# Create dataframe from selected trace
st.session_state["items"] = flatten_traces(traces[selected_trace])
item = st.session_state["items"][-1]

# st.write(st.session_state["items"])

st.subheader("Step 2: Name selected fields", divider=True)
col_sizes = [3, 3, 3]
# Create table with checkboxes
col2, col3, col4 = st.columns(col_sizes)
with col2:
    st.markdown("**Key Path**")
with col3:
    st.markdown("**Sample Value**")
with col4:
    st.markdown("**Name**")

input_selected = []
for key in item.keys():
    col2, col3, col4 = st.columns(col_sizes)
    with col2:
        st.markdown(f"`{key}`")
    with col3:
        st.write(item[key])
    with col4:
        if key == "trace_id":
            continue
        rename = st.text_input("Name", key=f"name_{key}", label_visibility="hidden")
        if rename:
            input_selected.append((key, rename))

# st.write(input_selected)
# Create a dataframe with selected columns
selected_columns = ["trace_id"]
selected_columns = selected_columns + [item[0] for item in input_selected]
df = pd.DataFrame(st.session_state["items"])
df = df[selected_columns]

# Rename columns
for item in input_selected:
    key, rename = item
    df = df.rename(columns={key: rename})


with st.form("dataset_form"):
    weave_dataset = None
    st.subheader("Step 3: Review & Publish")
    st.dataframe(df)
    save_as = st.text_input("Save As:", key=f"save_as")
    if st.form_submit_button("Save Dataset"):
        with st.spinner("Creating dataset..."):
            # Convert df to list of dicts
            data = df.to_dict(orient="records")
            # Save to Weave
            dataset = Dataset(name=save_as, rows=data)
            weave_dataset = weave.publish(dataset)

    if weave_dataset:
        # st.write(weave_dataset)
        # st.write(weave_dataset.as_param_dict())
        st.markdown(f"📦 `{save_as}` [published to Weave](https://wandb.ai/{weave_dataset.entity}/{weave_dataset.project}/weave/datasets?peekPath=%2F{weave_dataset.entity}%2F{weave_dataset.project}%2Fobjects%2F{weave_dataset.name}%2Fversions%2F{weave_dataset._digest}%3F%26)")


