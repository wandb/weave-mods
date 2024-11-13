import asyncio
import os
import random
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import weave
import yaml
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    DataFrameLoader,
)
from openai import AsyncOpenAI
from pydantic import PrivateAttr
from tqdm import tqdm


class ChatModel(weave.Model):
    """
    We define an extra ChatModel class to be able store and version more parameters than just the model name.
    Especially, relevant if we consider fine-tuning (locally or aaS) because of specific parameters.
    """

    chat_model: str
    cm_temperature: float
    cm_max_new_tokens: int
    cm_quantize: bool
    inference_batch_size: int
    _model: Any = PrivateAttr()

    def model_post_init(self, __context):
        # Initialize OpenAI client
        self._model = AsyncOpenAI()

    @weave.op()
    async def predict(self, query: List[str]) -> dict:
        response = await self._model.chat.completions.create(
            model=self.chat_model,
            messages=query,
            temperature=self.cm_temperature,
            max_tokens=self.cm_max_new_tokens,
        )

        # Return a copy of the message content and role
        return {
            "role": response.choices[0].message.role,
            "content": response.choices[0].message.content,
        }


# TODO: check if this necessary and how to make more general next to OpenAI Models
class PromptTemplate(weave.Object):
    system_prompt: str
    human_prompt: str

    @weave.op()
    def format_prompt(
        self,
        system_prompt_args: Optional[Dict[str, str]] = {},
        human_prompt_args: Optional[Dict[str, str]] = {},
    ):
        "A formatting function for OpenAI models"
        system_prompt_formatted = self.system_prompt.format(**system_prompt_args)
        human_prompt_formatted = self.human_prompt.format(**human_prompt_args)
        messages = [
            {"role": "system", "content": system_prompt_formatted},
            {"role": "user", "content": human_prompt_formatted},
        ]
        return messages


# TODO: replace langchain download and extraction with own functions
@weave.op()
def download_source_docs(
    source_files: list[str],
    raw_data_artifact: str,
    **kwargs,
) -> None:
    """Download sources and save them as table artifact to Weave using PyPDF2 for PDFs and direct reading for Markdown"""
    from pathlib import Path

    from PyPDF2 import PdfReader

    # Construct the dataframe
    sources_list_df = pd.DataFrame(source_files, columns=["url"])
    sources_list_df["type"] = sources_list_df["url"].apply(lambda x: Path(x).suffix[1:])
    downloaded_sources = []

    for source in tqdm(sources_list_df["url"], desc="Downloading sources"):
        try:
            file_type = Path(source).suffix.lower()

            if file_type in [".md", ".markdown", ".txt"]:
                # Handle Markdown files
                with open(source, "r", encoding="utf-8") as f:
                    text = f.read()
                    downloaded_sources.append(
                        {
                            "url": source,
                            "type": "markdown",
                            "page_content": text,
                            "metadata": str(
                                {
                                    "source": source,
                                    "page": 1,
                                    "total_pages": 1,
                                }
                            ),
                        }
                    )

            elif file_type == ".pdf":
                # Handle PDF files
                reader = PdfReader(source)
                for page_num in range(len(reader.pages)):
                    text = reader.pages[page_num].extract_text()
                    if text.strip():  # Only add non-empty pages
                        downloaded_sources.append(
                            {
                                "url": source,
                                "type": "pdf",
                                "page_content": text,
                                "metadata": str(
                                    {
                                        "source": source,
                                        "page": page_num + 1,
                                        "total_pages": len(reader.pages),
                                    }
                                ),
                            }
                        )

        except Exception as e:
            print(f"Error processing {source}: {str(e)}")
            continue

    # Convert to DataFrame and publish
    sources_df = pd.DataFrame(downloaded_sources)
    print(sources_df)
    dataset = weave.Dataset(
        name=raw_data_artifact, rows=sources_df.to_dict(orient="records")
    )
    publication = weave.publish(dataset)
    uri = publication.uri()

    # First extract the components
    _, path = uri.split("weave:///", 1)
    entity_project, rest = path.split("/object/", 1)
    obj_type, version = rest.split(":", 1)

    # Then reconstruct in the desired format
    url = (
        f"https://wandb.ai/{entity_project}/weave/objects/{obj_type}/versions/{version}"
    )
    return url


# TODO: replace langchain chunking with own functions
@weave.op()
async def gen_data(
    gen_model: ChatModel,
    prompt_template: PromptTemplate,
    raw_data_artifact: str,
    dataset_artifact: str,
    questions_per_chunk: int,
    max_chunks_considered: int,
    source_chunk_size: int,
    source_chunk_overlap: int,
    **kwargs,
) -> Tuple[str, weave.Dataset]:
    """Generate question-answer-source pairs for the provided sources and upload to Weave.
    Inspired by llamaindex.evaluation.DatasetGenerator that generates questions per document.
    We will assume a document to be the entirety of a given source. In contrary to LlamaIndex
    we will not first generate questions and the responses in a separate step but we will generate
    both questions and answers at the same time and use custom parsing to extract the pairs."""

    # weave: get sources and split into chunks (with :latest version)
    source_df = pd.DataFrame(weave.ref(raw_data_artifact).get().rows)
    source_docs = DataFrameLoader(source_df, page_content_column="page_content").load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=source_chunk_size, chunk_overlap=source_chunk_overlap
    )
    all_splits = text_splitter.split_documents(source_docs)

    # Sample uniformly from all splits
    sampled_docs = random.sample(
        all_splits, min(max_chunks_considered, len(all_splits))
    )
    # Generate questions and answers concurrently per sampled_doc
    queries, answers, sources = [], [], []

    async def generate_qa_pairs(doc):
        """Generate questions and answers for a given document."""
        messages = prompt_template.format_prompt(
            human_prompt_args={
                "questions_per_chunk": questions_per_chunk,
                "source_str": doc.page_content,
            }
        )
        output = await gen_model.predict(messages)

        # More flexible regex patterns that don't rely on newlines
        doc_queries = re.findall(
            r"QUESTION:\s*(.*?)\s*(?=ANSWER:|$)",
            output["content"],
            re.DOTALL | re.IGNORECASE,
        )
        doc_answers = re.findall(
            r"ANSWER:\s*(.*?)(?=QUESTION:|$)",
            output["content"],
            re.DOTALL | re.IGNORECASE,
        )

        # Ensure we have matching pairs
        min_pairs = min(len(doc_queries), len(doc_answers))
        doc_queries = doc_queries[:min_pairs]
        doc_answers = doc_answers[:min_pairs]
        doc_sources = [doc.metadata["url"]] * min_pairs

        # Clean up any extra whitespace
        doc_queries = [q.strip() for q in doc_queries]
        doc_answers = [a.strip() for a in doc_answers]

        print(f"Found {min_pairs} QA pairs")
        return doc_queries, doc_answers, doc_sources

    results = await asyncio.gather(*[generate_qa_pairs(doc) for doc in sampled_docs])
    # Aggregate results
    for doc_queries, doc_answers, doc_sources in results:
        queries.extend(doc_queries)
        answers.extend(doc_answers)
        sources.extend(doc_sources)

    # Create and publish the dataset
    dataset = weave.Dataset(
        name=dataset_artifact,
        rows=[
            {"query": query, "answer": answer, "main_source": source}
            for query, answer, source in zip(queries, answers, sources)
        ],
    )
    publication = weave.publish(dataset)
    uri = publication.uri()

    # First extract the components
    _, path = uri.split("weave:///", 1)
    entity_project, rest = path.split("/object/", 1)
    obj_type, version = rest.split(":", 1)

    # Then reconstruct in the desired format
    url = (
        f"https://wandb.ai/{entity_project}/weave/objects/{obj_type}/versions/{version}"
    )
    return url, dataset


def load_config():
    config = {}
    file_path = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(file_path, "configs/config.yaml"), "r") as file:
        config.update(yaml.safe_load(file))

    return config


def main(config, source_files: list[str]):
    # init weave experiment
    weave.init(config["entity"] + "/" + config["project_name"])
    print("Weave initialized.")

    # Convert source_files to the correct format before passing
    config_copy = config.copy()

    # Convert source_files to DataFrame more safely
    try:
        # Create DataFrame directly from the list
        sources_df = pd.DataFrame(source_files, columns=["url"])
        config_copy["source_files"] = sources_df
    except Exception as e:
        print(f"Error creating DataFrame: {e}")
        print(f"Source files content: {source_files}")
        raise

    # data extraction, object: source table
    print("Downloading source docs...")
    url_raw = download_source_docs(
        source_files=source_files, raw_data_artifact=config["raw_data_artifact"]
    )

    # dataset generation, object: generated dataset
    print("Setting up generation model...")
    gen_model_instance = ChatModel(
        name="GenModel",
        chat_model=config["gen_eval_model"],
        cm_max_new_tokens=config["gm_max_new_tokens"],
        cm_quantize=config["gm_quantize"],
        cm_temperature=config["gm_temperature"],
        inference_batch_size=config["inference_batch_size"],
    )

    print("Setting up prompt template...")
    prompt_template_instance = PromptTemplate(
        system_prompt=config["eval_system_prompt"],
        human_prompt=config["gen_eval_prompt"],
    )

    print("Generating dataset...")
    url_dataset, dataset = asyncio.run(
        gen_data(
            gen_model=gen_model_instance,
            prompt_template=prompt_template_instance,
            raw_data_artifact=config["raw_data_artifact"],
            dataset_artifact=config["dataset_artifact"],
            questions_per_chunk=config["questions_per_chunk"],
            max_chunks_considered=config["max_chunks_considered"],
            source_chunk_size=config["source_chunk_size"],
            source_chunk_overlap=config["source_chunk_overlap"],
        )
    )
    print("Dataset generated.")
    return url_raw, url_dataset, dataset
