import json
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from src.eval_classification import EvaluationClassifier

load_dotenv()


def initialize_session_state():
    if "wandb_project" not in st.session_state:
        st.session_state["wandb_project"] = os.environ["WANDB_PROJECT"]
    if "call_id" not in st.session_state:
        st.session_state["call_id"] = None
    if "failure_condition" not in st.session_state:
        st.session_state["failure_condition"] = None
    if "max_predict_and_score_calls" not in st.session_state:
        st.session_state["max_predict_and_score_calls"] = None
    if "classify_button" not in st.session_state:
        st.session_state["classify_button"] = False
    if "classifier" not in st.session_state:
        st.session_state["classifier"] = False
    if "n_jobs" not in st.session_state:
        st.session_state["n_jobs"] = 10
    if "summarization_type" not in st.session_state:
        st.session_state["summarization_type"] = False


initialize_session_state()
st.title("Eval Categorization")


wandb_project = st.sidebar.text_input(
    "Wandb project which the evaluation is from",
    value=st.session_state["wandb_project"],
)
st.session_state["wandb_project"] = wandb_project

call_id = st.sidebar.text_input("Evaluation Call ID")
st.session_state["call_id"] = call_id

failure_condition = st.sidebar.text_input("Failure Condition")
st.session_state["failure_condition"] = failure_condition

max_predict_and_score_calls = st.sidebar.number_input(
    "Max Predict and Score Calls", value=None
)
st.session_state["max_predict_and_score_calls"] = (
    int(max_predict_and_score_calls)
    if max_predict_and_score_calls is not None
    else None
)

# node_wise = st.sidebar.checkbox("Node-wise Summarization", value=False)
# st.session_state["node_wise"] = node_wise

summarization_type = st.sidebar.selectbox(
    "Summarization Type",
    options=["None", "Node-wise", "Call-wise"],
    index=0,
)
st.session_state["summarization_type"] = summarization_type

n_jobs = st.sidebar.slider(
    "Number of Jobs",
    min_value=1,
    max_value=(
        1000
        if st.session_state["max_predict_and_score_calls"] is None
        else st.session_state["max_predict_and_score_calls"]
    ),
    value=10,
)
st.session_state["n_jobs"] = n_jobs

classify_button = st.sidebar.button("Categorize Calls")
st.session_state["classify_button"] = classify_button

if st.session_state["classify_button"]:
    if (
        st.session_state["call_id"] is not None
        and st.session_state["failure_condition"] is not None
    ):
        st.session_state["classifier"] = EvaluationClassifier(
            project=st.session_state["wandb_project"],
            call_id=st.session_state["call_id"],
        )
        with st.spinner("Registering calls"):
            st.session_state["classifier"].register_predict_and_score_calls(
                failure_condition=st.session_state["failure_condition"],
                max_predict_and_score_calls=st.session_state[
                    "max_predict_and_score_calls"
                ],
                n_jobs=st.session_state["n_jobs"],
                save_filepath="evaluation.json",
            )
        if st.session_state["summarization_type"] != "None":
            with st.spinner("Summarizing calls"):
                summary = st.session_state["classifier"].summarize(
                    node_wise=st.session_state["summarization_type"] == "Node-wise",
                    n_jobs=st.session_state["n_jobs"],
                )

        summary_df = {
            "call_id": [
                call["id"]
                for call in st.session_state["classifier"].predict_and_score_calls
            ],
            "call_name": [
                call["call_name"]
                for call in st.session_state["classifier"].predict_and_score_calls
            ],
            "call_json": [
                json.dumps(call)
                for call in st.session_state["classifier"].predict_and_score_calls
            ],
        }

        if st.session_state["summarization_type"] != "None":
            summary_df["summary"] = st.session_state[
                "classifier"
            ].predict_and_score_call_summaries

        summary_df = pd.DataFrame(summary_df)

        with st.expander("Evaluation Call Summaries"):
            st.dataframe(summary_df)
