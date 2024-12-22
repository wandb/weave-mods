import asyncio
from typing import List, Tuple

import pandas as pd
import streamlit as st
import tiktoken
from openai import AsyncOpenAI
from openai.types.embedding import Embedding
from sklearn.ensemble import IsolationForest

import mods

# Initialize the AsyncOpenAI client
openai = AsyncOpenAI()

EMBEDDING_MODEL = "text-embedding-3-small"
MAX_PARALLEL_TASKS = 10  # Default value, can be adjusted


async def fetch_openai_embedding(
    tokenized_content: List[List[int]], semaphore: asyncio.Semaphore
) -> List[Embedding]:
    async with semaphore:
        response = await openai.embeddings.create(
            model=EMBEDDING_MODEL,
            input=tokenized_content,
        )
        return response.data


async def process_dataframe(
    dataframe: pd.DataFrame,
    progress_bar: st.delta_generator.DeltaGenerator,
) -> Tuple[List[List[float]], List[int]]:
    embeddings = []
    ids = []
    semaphore = asyncio.Semaphore(MAX_PARALLEL_TASKS)
    total_records = len(dataframe)
    encoding = tiktoken.encoding_for_model(EMBEDDING_MODEL)

    async def process_batch(batch_df: pd.DataFrame):
        tokenized_content = []
        indices = []
        rows = 0
        for idx, record in batch_df.iterrows():
            content = None
            if record.get("output.choices"):
                if isinstance(record["output.choices"], list):
                    content = record["output.choices"][0]["message"]["content"]
            if content:
                tokens = encoding.encode(content)
                if len(tokens) >= 8192:
                    print("WARNING: Content too long, max is 8192 tokens, truncating")
                    tokens = tokens[:8192]
                tokenized_content.append(tokens)
                indices.append(idx)
                rows += 1
        if len(tokenized_content) > 0:
            embedding = await fetch_openai_embedding(tokenized_content, semaphore)
            progress_bar.progress(rows / total_records)
            return [e.embedding for e in embedding], indices
        return [], []

    progress_bar.progress(0)
    batch_size = 50
    batches = [
        dataframe.iloc[i : i + batch_size] for i in range(0, len(dataframe), batch_size)
    ]
    print(f"Processing {len(batches)} batches")
    tasks = [asyncio.create_task(process_batch(batch)) for batch in batches]
    results = await asyncio.gather(*tasks)

    for embeddingz, idxs in results:
        embeddings.extend(embeddingz)
        ids.extend(idxs)

    return embeddings, ids


@st.cache_data
def cache_embeddings_and_ids(
    dataframe: pd.DataFrame,
) -> Tuple[List[List[float]], List[int]]:
    progress_bar = st.progress(0)
    result = asyncio.run(process_dataframe(dataframe, progress_bar))
    progress_bar.empty()
    return result


def render_table(
    op_names: str | List[str], dataframe: pd.DataFrame | None = None
) -> Tuple[mods.api.query.Calls, int | None]:
    st.write(f"Calls table for: {op.name}")
    return mods.st.tracetable(op.ref().uri(), dataframe=dataframe)


st.set_page_config(layout="wide")

st.title("LLM Trace Data Anomalyzer")

with st.sidebar:
    st.title("Choose an op to anomalyze")
    op = mods.st.selectbox("Ops", mods.st.OP)
    if op:
        selected_ops = mods.st.multiselect("Versions", op)

if op:
    client = mods.st.current_client()
    ref = op.ref().uri()
    calls = mods.st.api.get_calls(client, selected_ops)
    status_container = st.empty()
    with status_container:
        ed = st.write("Embedding data...")
    embeddings, ids = cache_embeddings_and_ids(calls.df)

    scored_df = calls.df.copy()
    # Use Isolation Forest for anomaly detection
    iso_forest = IsolationForest(contamination="auto", random_state=42)
    iso_forest.fit(embeddings)

    # Get anomaly scores (negative scores mean anomalies)
    anomaly_scores = iso_forest.decision_function(embeddings)
    anomaly_labels = iso_forest.predict(embeddings)

    scored_df.loc[ids, "anomaly_score"] = anomaly_scores
    scored_df.loc[ids, "anomaly_label"] = anomaly_labels

    usage_columns = [
        col for col in scored_df.columns if col.startswith("summary.usage")
    ]
    scored_df = scored_df.drop(columns=usage_columns)

    calls, selected = render_table(op.ref().uri(), dataframe=scored_df)
    if selected is not None:
        call = calls.df.iloc[selected]
        mods.st.chat_thread(call)

    with status_container:
        st.write("Anomaly scores added!")
