import streamlit as st
from mods.streamlit.api import current_client, get_objects


def main():
    st.set_page_config(
        page_title="Fine Tune with Together.ai",
        page_icon=":robot:",
        initial_sidebar_state="collapsed",
    )

    st.title("Fine Tuning")
    st.text("This will help you automatically fine tune a model on a weave dataset.")
    st.text(
        "You can either fine tune on a dataset you have already created, or fine tune on a new dataset."
    )

    st.write("---")

    col1, col2 = st.columns(2)
    ds = get_objects(current_client(), "Dataset", cached=False)

    with col1:
        st.write(f"##### Step 1 {'(*optional*)' if len(ds) > 0 else ''}")
        st.write("Create a new dataset:")
        st.page_link(
            "pages/Generate_Training_Data.py", icon="🚅", label="Generate Training Data"
        )

    with col2:
        st.write("##### Step 2")
        st.write("Fine tune on an existing dataset:")
        if len(ds) == 0:
            st.warning("No datasets found. Please create a dataset first.")
        st.page_link(
            "pages/Finetune.py", label="Fine Tune", icon="🤖", disabled=len(ds) == 0
        )


if __name__ == "__main__":
    main()
