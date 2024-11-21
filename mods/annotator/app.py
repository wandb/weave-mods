import os
import pandas as pd
import streamlit as st
import weave
from weave.wandb_interface import wandb_api

@st.cache_resource
def init_weave_client(project_name):
    try:
        client = weave.init(project_name)
        return client
    except Exception as e:
        st.error(f"Failed to initialize Weave client for project '{project_name}': {e}")
        return None

# Initialize session state to keep track of the current example index
if "index" not in st.session_state:
    st.session_state.index = 0
if "dataframe" not in st.session_state:
    st.session_state.dataframe = None

def display_example(idx, df, selected_columns):
    """Function to display the current example based on the index."""
    feedback = {}
    for col in selected_columns:
        with st.expander(f"{col} feedback"):
            # st.write(f"{col}: {df[col][idx]}")
            col1, col2 = st.columns(2)
            with col1:
                st.write(col)
                st.write(df[col][idx])
            with col2:
                feedback[f"{col}_feedback"] = st.text_area(label="feedback", key=f"{col}_feedback[{idx}]", value=df[f"{col}_feedback"][idx])
    return idx, feedback


selected_project = os.getenv("WANDB_PROJECT")
client = init_weave_client(selected_project)
if client is None:
    st.stop()

wandb_api.init()
api = wandb_api.get_wandb_api_sync()

# Configuration sidebar
st.sidebar.header("Settings")
wandb_entity = st.sidebar.text_input("Entity", value=api.default_entity_name(), disabled=True)
wandb_project = st.sidebar.text_input("Project", value=selected_project, disabled=True)

st.title("Annotator")
st.markdown("""
    This mod helps you annotate datasets quickly. To get started,
    select select the columns you want to annotate. Then provide your
    feedback, and submit when ready!
""")
st.subheader("Step 1: Enter a dataset ref", divider=True)
selected_dataset = st.text_input("Dataset Ref", disabled=True, value="my_sample_dataset")

st.subheader("Step 2: Select the columns to annotate", divider=True)
if st.session_state.get("dataframe") is None:
    dataset = weave.ref(f"{selected_dataset}:latest").get()
    st.session_state.dataframe = pd.DataFrame(dataset.rows)

dataframe = st.session_state.dataframe
col_sizes = [1, 3, 6]
# Create table with checkboxes
col1, col2, col3 = st.columns(col_sizes)
with col1:
    st.markdown("**Select**")
with col2:
    st.markdown("**Column Name**")
with col3:
    st.markdown("**Sample Value**")

selected_cols = []
for col_name in dataframe.columns:
    if col_name == "trace_id":
        continue
    if col_name.endswith("_feedback"):
        continue
    with col1:
        if st.checkbox(col_name, key=col_name, label_visibility="hidden"):
            selected_cols.append(col_name)
    with col2:
        st.write(col_name)
    with col3:
        dataframe[col_name][0]

# Add selected columns to dataframe
for col_name in selected_cols:
    if f"{col_name}_feedback" not in dataframe.columns:
        dataframe[f"{col_name}_feedback"] = ""

st.subheader("Step 3: Add your feedback", divider=True)

# Navigation buttons
col1, col2, col3 = st.columns([5, 5.5, 1.5])
with col1:
    if st.button("Previous") and st.session_state.index > 0:
        st.session_state.index -= 1
with col2:
    # Show the trace index and total number of calls
    st.write(f"Trace {st.session_state.index + 1}/{dataframe.shape[0]}")
with col3:
    if st.button("Next") and st.session_state.index < dataframe.shape[0] - 1:
        st.session_state.index += 1

# Display the current example based on session state
idx, feedback = display_example(st.session_state.index, dataframe, selected_cols)

for key, value in feedback.items():
    if value:
        st.session_state.dataframe.loc[idx, key] = value

with st.form("feedback_form"):
    st.subheader("Step 4: Review & Publish", divider=True)
    st.dataframe(dataframe)
    if st.form_submit_button("Save Feedback"):
        pass

st.stop()


# Display the inputs and outputs
input_key = st.selectbox("Input", options=st.session_state.inputs.keys())
st.write(st.session_state.inputs[input_key])
try:
    output_key = st.selectbox("Output", options=st.session_state.output.keys())
    st.write(st.session_state.output[output_key])
except:
    st.write("Output")
    st.write(st.session_state.output)

# Feedback section
feedback = st.radio("Was this completion good?", options=["👍", "👎"])
suggested_completion = st.text_area("Suggest a Better Completion (optional)")

# Save feedback
if st.button("Submit Feedback"):
    # Process the feedback (for now, we'll print it to the console)
    thumbs_up = feedback == "👍"
    print(f"Feedback for example {st.session_state.index}: Thumbs Up - {thumbs_up}, Suggested Completion - {suggested_completion}")
    st.success("Feedback submitted!")

    # Reset feedback inputs after submission
    st.session_state.feedback = ""
    st.session_state.suggested_completion = ""
