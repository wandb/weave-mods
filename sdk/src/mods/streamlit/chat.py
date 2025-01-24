import pandas as pd
import streamlit as st


def chat_thread(call: pd.Series):
    """Renders a chat thread visualization in Streamlit for an OpenAI API call.

    This function creates a visual representation of a chat conversation, including
    system messages, user messages, and assistant responses. It handles various content
    types including text, images, HTML, and JSON.

    Args:
        call: A pandas Series containing chat data with the following expected fields:
            - id: The unique identifier for the chat
            - inputs.messages: List of message objects containing:
                - role: The message sender's role (system/user/assistant)
                - content: The message content (can be str, list, or dict)
            - output.choices: The model's responses

    The function handles several special cases:
    - System messages are displayed in an expandable section
    - Multi-modal content (text + images) is supported
    - HTML content is displayed as formatted code
    - JSON responses are pretty-printed
    - Plain text is rendered as-is

    Example:
        ```python
        chat_data = pd.Series({
            'id': '123',
            'inputs.messages': [{'role': 'user', 'content': 'Hello'}],
            'output.choices': [{'message': {'role': 'assistant', 'content': 'Hi!'}}]
        })
        chat_thread(chat_data)
        ```
    """
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
