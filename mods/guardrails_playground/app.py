import os
import importlib

import streamlit as st
import wandb
import weave

from safeguards.llm import OpenAIModel
from safeguards.utils import initialize_guardrails_on_playground


def initialize_session_state():
    if "llm_model" not in st.session_state:
        st.session_state.llm_model = None
    if "guardrails" not in st.session_state:
        st.session_state.guardrails = []
    if "guardrail_names" not in st.session_state:
        st.session_state.guardrail_names = []
    if "guardrails_manager" not in st.session_state:
        st.session_state.guardrails_manager = None
    if "initialize_guardrails_button" not in st.session_state:
        st.session_state.initialize_guardrails_button = False
    if "start_chat_button" not in st.session_state:
        st.session_state.start_chat_button = False
    if "prompt" not in st.session_state:
        st.session_state.prompt = ""
    if "test_guardrails_button" not in st.session_state:
        st.session_state.test_guardrails_button = False

    if "prompt_injection_llm_model" not in st.session_state:
        st.session_state.prompt_injection_llm_model = None
    if "prompt_injection_llama_guard_checkpoint_name" not in st.session_state:
        st.session_state.prompt_injection_llama_guard_checkpoint_name = None
    if "presidio_entity_recognition_guardrail_should_anonymize" not in st.session_state:
        st.session_state.presidio_entity_recognition_guardrail_should_anonymize = True
    if "regex_entity_recognition_guardrail_should_anonymize" not in st.session_state:
        st.session_state.regex_entity_recognition_guardrail_should_anonymize = True
    if (
        "transformers_entity_recognition_guardrail_should_anonymize"
        not in st.session_state
    ):
        st.session_state.transformers_entity_recognition_guardrail_should_anonymize = (
            True
        )
    if "restricted_terms_judge_should_anonymize" not in st.session_state:
        st.session_state.restricted_terms_judge_should_anonymize = True


wandb.login(key=os.environ.get("WANDB_API_KEY"), relogin=True)
weave.init(project_name=os.environ.get("WANDB_PROJECT"))
initialize_session_state()
st.title(":material/robot: Safeguards Playground")

llm_model = st.sidebar.selectbox("OpenAI LLM for Chat", ["gpt-4o-mini", "gpt-4o"])
st.session_state.llm_model = OpenAIModel(model_name=llm_model)

guardrail_names = st.sidebar.multiselect(
    label="Select Guardrails",
    options=[
        cls_name
        for cls_name, cls_obj in vars(
            importlib.import_module("safeguards.guardrails")
        ).items()
        if isinstance(cls_obj, type) and cls_name != "GuardrailManager"
    ],
)
st.session_state.guardrail_names = guardrail_names

initialize_guardrails_button = st.sidebar.button("Initialize Guardrails")
st.session_state.initialize_guardrails_button = (
    initialize_guardrails_button
    if not st.session_state.initialize_guardrails_button
    else st.session_state.initialize_guardrails_button
)

if st.session_state.initialize_guardrails_button:
    with st.sidebar.status("Initializing Guardrails..."):
        initialize_guardrails_on_playground()

    prompt = st.text_area("User Prompt", value="")
    st.session_state.prompt = prompt

    test_guardrails_button = st.button("Test Guardrails")
    st.session_state.test_guardrails_button = test_guardrails_button

    if st.session_state.test_guardrails_button:
        with st.sidebar.status("Running Guardrails..."):
            guardrails_response, call = st.session_state.guardrails_manager.guard.call(
                st.session_state.guardrails_manager,
                prompt=st.session_state.prompt,
            )

        if guardrails_response["safe"]:
            st.markdown(
                f"\n\n---\nPrompt is safe! Explore guardrail trace on [Weave]({call.ui_url})\n\n---\n"
            )

            with st.sidebar.status("Generating response from LLM..."):
                response, call = st.session_state.llm_model.predict.call(
                    st.session_state.llm_model,
                    user_prompts=st.session_state.prompt,
                )
            st.markdown(
                response.choices[0].message.content
                + f"\n\n---\nExplore LLM generation trace on [Weave]({call.ui_url})"
            )
        else:
            st.warning("Prompt is not safe!")
            st.markdown(guardrails_response["summary"])
            st.markdown(f"Explore guardrail trace on [Weave]({call.ui_url})")
