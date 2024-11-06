import os

import streamlit as st
import weave
from theme import tailwind_wrapper

st.set_page_config(layout="wide")
client = weave.init(os.getenv("WANDB_PROJECT"))

# Add this near the top of the file, after st.set_page_config()
st.markdown(
    """
    <style>
        .stMainBlockContainer  {
            padding-top: 2rem !important;
        }
        .scrolling-code {
            max-height: 300px;
            overflow-y: auto;
            border-radius: 0.25rem;
        }
    </style>
""",
    unsafe_allow_html=True,
)


# TODO: this will load everything, we should only grab 1 page...
@st.cache_resource
def get_calls():
    return [c for c in client.get_calls(filter={"trace_roots_only": True})]


calls = get_calls()


def get_call(idx):
    if 0 <= idx < len(calls):
        return calls[idx]
    return None


# TODO: is this needed?
if "current_idx" not in st.session_state:
    st.session_state.current_idx = 0

try:
    call = get_call(st.session_state.current_idx)
    if call is None:
        st.error("No more calls to display")
        st.stop()

    # Header
    st.title("HTML Rating Tool")

    # Create two rows - one for navigation/rating and one for status
    nav_col1, nav_col2, nav_col3 = st.columns([1, 3, 1])

    # Navigation and rating controls
    with nav_col1:
        if st.button(
            "⬅️ Prev",
            disabled=st.session_state.current_idx <= 0,
            use_container_width=True,
        ):
            st.session_state.current_idx -= 1
            st.rerun()

    # Centered rating with larger stars
    with nav_col2:
        rating_key = f"rating_widget_{st.session_state.current_idx}"

        def on_rating_change():
            if st.session_state.get(rating_key):
                rating_val = st.session_state[rating_key] + 1
                call.feedback.add("rating", {"value": rating_val})

        # Custom CSS to make stars bigger and center them
        st.markdown(
            """
            <style>
            /* Center the button group container */
            .stButtonGroup {
                display: flex;
                justify-content: center;
                margin: -10px 0;
            }

            /* Make the stars bigger */
            .stButtonGroup span[data-testid="stIconMaterial"] {
                font-size: 2.5rem !important;
            }

            /* Adjust spacing between stars */
            .stButtonGroup button {
                padding: 0 10px !important;
            }

            /* Center in the column */
            [data-testid="column"] {
                display: flex;
                justify-content: center;
                align-items: center;
            }
            </style>
        """,
            unsafe_allow_html=True,
        )

        rating = st.feedback(
            "stars",
            key=rating_key,
            on_change=on_rating_change,
        )

    with nav_col3:
        if st.button(
            "Next ➡️",
            disabled=st.session_state.current_idx >= len(calls) - 1,
            use_container_width=True,
        ):
            st.session_state.current_idx += 1
            st.rerun()

    # Status row with position and rating status
    status_col1, status_col2 = st.columns([1, 4])
    with status_col1:
        prefix = "⚠️ Please select a rating"
        if rating is not None:
            prefix = f"✅ Rated {rating+1}/5"
        st.caption(f"{prefix}  -  {st.session_state.current_idx + 1} of {len(calls)}")
        st.link_button(
            "View in Weave",
            url=f"{os.getenv('WANDB_BASE_URL')}/{os.getenv('WANDB_ENTITY', "vanpelt")}/{os.getenv('WANDB_PROJECT')}/weave/calls/{call.id}",
        )

    with status_col2:
        pass

    st.divider()  # Add a visual separator

    # Remove triple backticks if present
    payload = {}
    payload.update(call.inputs)
    payload.update(call.output)

    # Extract the assistant's response
    assistant_content = payload["choices"][0]["message"]["content"]

    # Separate frontmatter and HTML content
    content_parts = assistant_content.split("---")
    if len(content_parts) >= 3:
        frontmatter = content_parts[1]
        html_code = "---".join(content_parts[2:]).strip()
    else:
        html_code = assistant_content.strip()

    # Main Page
    messages = payload.get("messages", [])

    st.header("User Input:")
    for msg in messages:
        role = msg.get("role", "unknown").capitalize()
        if role == "User":
            content = msg.get("content", "")
            # Handle both string content and structured content
            if isinstance(content, str):
                st.write(content)
            elif isinstance(content, list):
                for item in content:
                    if item.get("type") == "text":
                        content = item.get("text", "")
                        if "Given the following HTML and image:" in content:
                            # find the last instance of ">"
                            idx = content.rfind(">")
                            if idx != -1:
                                st.write(content[:37])
                                with st.container(height=300):
                                    st.code(content[37 : idx + 1], language="html")
                                st.write(content[idx + 1 :])
                        else:
                            st.write(item.get("text", ""))
                    elif item.get("type") == "image_url":
                        image_url = item.get("image_url", {}).get("url", "")
                        if image_url.startswith("data:image/"):
                            st.image(image_url, width=760)
                        else:
                            st.image(image_url, use_column_width=True)

    st.components.v1.html(tailwind_wrapper(html_code), height=600, scrolling=True)
    # Show/Hide HTML toggle
    show_html = st.checkbox("Show generated HTML", value=False)
    if show_html:
        st.header("Generated HTML")
        st.code(html_code, language="html")


except Exception as e:
    st.error(f"An error occurred: {e}")
