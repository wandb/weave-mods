import os
import importlib

import streamlit as st
import weave

from safeguards.llm import OpenAIModel
from safeguards.utils import initialize_guardrails_on_playground


def initialize_session_state():
    default_session_state = {
        "llm_model": None,
        "guardrails": [],
        "guardrail_names": [],
        "guardrails_manager": None,
        "initialize_guardrails_button": False,
        "start_chat_button": False,
        "prompt": "",
        "test_guardrails_button": False,
        "prompt_injection_llm_model": None,
        "prompt_injection_llama_guard_checkpoint_name": None,
        "presidio_entity_recognition_guardrail_should_anonymize": True,
        "regex_entity_recognition_guardrail_should_anonymize": True,
        "transformers_entity_recognition_guardrail_should_anonymize": True,
        "restricted_terms_judge_should_anonymize": True,
    }
    if st.session_state == {}:
        st.session_state.update(default_session_state)


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
