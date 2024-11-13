# WEDG (Weave Eval Data Generator)

Domain specific models require domain specific evaluation datasets. Domain experts are expensive, and benchmarks are time consuming to create. This mod (attempts to) automate the creation of domain specific evaluation datasets based on unpublished documents (no leakage). It's rudimentary in its current form, but it's a start!

WEDG is a Streamlit-based application that generates QA evaluation datasets from PDF, Markdown, and text source documents using LLMs. It's designed to help create ~~high-quality~~ question-answer pairs from your source documents for evaluation purposes.

## Features

- **Multiple File Format Support**: Upload and process PDF, Markdown, and text files
- **Configurable Parameters**: Customize generation settings through an intuitive UI
- **Weave Integration**: Automatic versioning and storage of both source documents and generated datasets
- **Interactive Interface**: Real-time processing status and results visualization
- **Flexible Output**: Generated datasets include questions, answers, and source tracking

## Configuration Options

### Project Settings
- **Entity**: Your Weights & Biases entity name
- **Project Name**: The project name in W&B
- **Raw Data Artifact Name**: Name for storing source documents
- **Dataset Artifact Name**: Name for storing generated Q&A pairs

### Generation Parameters
- **Questions per Chunk**: Number of Q&A pairs to generate per text chunk
- **Max Chunks Considered**: Maximum number of text chunks to process
- **Source Chunk Size**: Size of text chunks for processing
- **Source Chunk Overlap**: Overlap between consecutive chunks

### Prompts
- **System Prompt**: Base instructions for the LLM
- **Generation Prompt**: Specific instructions for Q&A generation

## Usage

1. Launch the application
2. Configure settings in the sidebar
3. Upload your documents using the drag-and-drop interface
4. Click "Process Documents" to start generation
5. View results and access generated datasets via provided W&B links

## Output Format

The tool generates two main artifacts:

1. **Raw Dataset**: Contains the processed source documents
   - URL
   - Document type
   - Page content
   - Metadata (source, page numbers, etc.)

2. **Evaluation Dataset**: Contains generated Q&A pairs
   - Query (generated question)
   - Answer (generated answer)
   - Main source (reference to source document)

## Architecture

The application follows a modular architecture:

- **Frontend**: Streamlit-based UI for configuration and file upload
- **Document Processing**: Handles multiple file formats and chunking
- **LLM Integration**: Uses OpenAI's API for Q&A generation
- **Data Management**: Weave integration for versioning and storage

## Dependencies

- Streamlit
- PyPDF2
- Pandas
- Weave
- OpenAI
- LangChain
- PyYAML

## Setup

1. Mods...
