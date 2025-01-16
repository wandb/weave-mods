import os

import streamlit as st
from src.eval_classification import EvaluationClassifier


def initialize_session_state():
    if "wandb_project" not in st.session_state:
        st.session_state["wandb_project"] = os.environ["WANDB_PROJECT"]
    if "call_id" not in st.session_state:
        st.session_state["call_id"] = None
    if "failure_condition" not in st.session_state:
        st.session_state["failure_condition"] = None
    if "max_predict_and_score_calls" not in st.session_state:
        st.session_state["max_predict_and_score_calls"] = None
    if "register_calls_button" not in st.session_state:
        st.session_state["register_calls_button"] = False
    if "parser" not in st.session_state:
        st.session_state["parser"] = False
    if "n_registration_jobs" not in st.session_state:
        st.session_state["n_registration_jobs"] = 10


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

n_registration_jobs = st.sidebar.slider(
    "Number of Jobs",
    min_value=1,
    max_value=(
        1000
        if st.session_state["max_predict_and_score_calls"] is None
        else st.session_state["max_predict_and_score_calls"]
    ),
    value=10,
)
st.session_state["n_registration_jobs"] = n_registration_jobs

register_calls_button = st.sidebar.button("Register Calls")
st.session_state["register_calls_button"] = register_calls_button

if st.session_state["register_calls_button"]:
    if (
        st.session_state["call_id"] is not None
        and st.session_state["failure_condition"] is not None
    ):
        st.session_state["parser"] = EvaluationClassifier(
            project=st.session_state["wandb_project"],
            call_id=st.session_state["call_id"],
        )
        with st.spinner("Registering calls..."):
            st.session_state["parser"].register_predict_and_score_calls(
                failure_condition=st.session_state["failure_condition"],
                max_predict_and_score_calls=st.session_state[
                    "max_predict_and_score_calls"
                ],
                max_workers=st.session_state["n_registration_jobs"],
                save_filepath="evaluation.json",
            )
            st.write(st.session_state["parser"].predict_and_score_calls)
