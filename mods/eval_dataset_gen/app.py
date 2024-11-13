import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from weave_utils import load_config, main

config = load_config()

st.title("Welcome to WEDG (Weave Eval Data Generator)!")

# Create sections for different config parameters
st.sidebar.header("Configuration")

# Project Settings Section
st.sidebar.subheader("Project Settings")
config["entity"] = st.sidebar.text_input("Entity", value=config["entity"])
config["project_name"] = st.sidebar.text_input(
    "Project Name", value=config["project_name"]
)
config["raw_data_artifact"] = st.sidebar.text_input(
    "Raw Data Artifact Name", value=config["raw_data_artifact"]
)
config["dataset_artifact"] = st.sidebar.text_input(
    "Dataset Artifact Name", value=config["dataset_artifact"]
)

# Prompts Section
st.sidebar.subheader("Prompts")
config["gen_eval_prompt"] = st.sidebar.text_area(
    "Generation Prompt", value=config["gen_eval_prompt"], height=200
)

# Tunable Parameters Section
st.sidebar.subheader("Chunk Parameters")
config["questions_per_chunk"] = st.sidebar.number_input(
    "Questions per Chunk", min_value=1, value=config["questions_per_chunk"]
)
config["max_chunks_considered"] = st.sidebar.number_input(
    "Max Chunks Considered", min_value=1, value=config["max_chunks_considered"]
)
config["source_chunk_size"] = st.sidebar.number_input(
    "Source Chunk Size", min_value=100, value=config["source_chunk_size"]
)
config["source_chunk_overlap"] = st.sidebar.number_input(
    "Source Chunk Overlap", min_value=0, value=config["source_chunk_overlap"]
)

# Main content area
# File uploader with drag and drop
uploaded_files = st.file_uploader(
    "Drop your PDF or Markdown documents here",
    type=["pdf", "md", "markdown", "txt"],
    accept_multiple_files=True,
    help="Supported formats: PDF, Markdown, TXT",
)

# Only show submit button if files are uploaded
if uploaded_files:
    if st.button("Process Documents"):
        # Create a temporary directory to store uploaded files
        with tempfile.TemporaryDirectory() as temp_dir:
            source_files = []

            for uploaded_file in uploaded_files:
                # Save uploaded files to temp directory
                file_path = Path(temp_dir) / uploaded_file.name
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getvalue())

                # Add file info to source_files list
                source_files.append(str(file_path))

                # Show processing status
                st.write(f"Processing: {uploaded_file.name}")

            # Process all documents at once
            url_raw, url_dataset, dataset = main(config, source_files=source_files)

            # Convert dataset to pandas DataFrame and display
            try:
                # Display the dataset in a table
                st.markdown("### Generated Content")
                st.markdown(f"- [Raw Dataset]({url_raw})")
                st.markdown(f"- [Generated Evaluation Dataset]({url_dataset})")
                st.dataframe(pd.DataFrame(dataset.rows.rows), use_container_width=True)
            except AttributeError:
                st.warning("Dataset format not supported for visualization")

        st.success("All documents processed successfully!")
else:
    st.info("Please upload one or more PDF documents to begin")
