import asyncio
import json
import random
from collections import defaultdict
from typing import Any, DefaultDict, Dict, Generator, List, Tuple

import altair as alt
import faiss
import httpx
import numpy as np
import pandas as pd
import streamlit as st
import weave
from openai import AsyncOpenAI
from sklearn.decomposition import PCA

weave.init("embedding-classifier")

# Initialize the AsyncOpenAI client
openai = AsyncOpenAI()

MODEL = "gpt-4o-mini"
MAX_PARALLEL_TASKS = 10  # Default value, can be adjusted


def read_jsonl(file: Any) -> Generator[Dict[str, Any], None, None]:
    for line in file:
        yield json.loads(line)


async def fetch_embedding(content: str, semaphore: asyncio.Semaphore) -> Dict[str, Any]:
    async with semaphore:
        async with httpx.AsyncClient() as client:
            url = "http://host.docker.internal:11434/api/embeddings"
            payload = {"model": "nomic-embed-text", "prompt": content}
            response = await client.post(url, json=payload, timeout=20.0)
            return response.json()


@st.cache_data
def cache_embeddings_and_ids(
    embeddings: List[List[float]], ids: List[int]
) -> Tuple[List[List[float]], List[int]]:
    return embeddings, ids


async def process_jsonl(
    jsonl_data: List[Dict[str, Any]],
    progress_bar: st.delta_generator.DeltaGenerator,
) -> Tuple[List[List[float]], List[int]]:
    embeddings = []
    ids = []
    semaphore = asyncio.Semaphore(MAX_PARALLEL_TASKS)
    total_records = len(jsonl_data)

    async def process_record(record, idx):
        if record.get("output"):
            content = record["output"]["choices"][0]["message"]["content"]
            embedding = await fetch_embedding(content, semaphore)
            progress_bar.progress((idx + 1) / total_records)
            return embedding["embedding"], idx
        return None, None

    progress_bar.progress(0)
    tasks = [
        asyncio.create_task(process_record(record, i))
        for i, record in enumerate(jsonl_data)
    ]
    results = await asyncio.gather(*tasks)

    for embedding, idx in results:
        if embedding is not None:
            embeddings.append([float(x) for x in embedding])
            ids.append(idx)

    return embeddings, ids


@st.cache_resource
def build_faiss_index(embeddings: List[List[float]]) -> faiss.IndexFlatL2:
    dimension = len(embeddings[0])
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings).astype("float32"))
    return index


@st.cache_data
def cluster_embeddings(
    embeddings: List[List[float]], num_clusters: int = 10
) -> np.ndarray:
    dimension = len(embeddings[0])
    clustering = faiss.Clustering(dimension, num_clusters)
    index = faiss.IndexFlatL2(dimension)
    clustering.train(np.array(embeddings).astype("float32"), index)
    _, assignments = index.search(np.array(embeddings).astype("float32"), 1)
    return assignments.flatten()


@st.cache_data
def sample_from_clusters(
    assignments: np.ndarray,
    ids: List[int],
    jsonl_data: List[Dict[str, Any]],
    samples_per_cluster: int = 10,
) -> Dict[int, List[Dict[str, Any]]]:
    cluster_dict: DefaultDict[int, List[Dict[str, Any]]] = defaultdict(list)
    for idx, cluster_id in enumerate(assignments):
        cluster_dict[cluster_id].append(jsonl_data[ids[idx]])

    sampled_data = {}
    for cluster_id, items in cluster_dict.items():
        sampled_items = random.sample(items, min(len(items), samples_per_cluster))
        sampled_data[cluster_id] = sampled_items
    return sampled_data


async def classify_cluster(
    cluster_items: List[Dict[str, Any]], semaphore: asyncio.Semaphore
) -> str:
    # Concatenate or summarize the content of the cluster
    # TODO: handle clusters larger than 128k tokens...
    aggregated_content = " ".join(
        item["output"]["choices"][0]["message"]["content"]
        for item in cluster_items
        if "output" in item
    )
    # Classify the entire cluster based on this aggregated content
    classification = await async_classify_example(aggregated_content, semaphore)
    return classification


async def async_classify_clusters(
    sampled_data: Dict[int, List[Dict[str, Any]]],
    progress_bar: st.delta_generator.DeltaGenerator,
) -> Dict[int, str]:
    semaphore = asyncio.Semaphore(MAX_PARALLEL_TASKS)
    cluster_classifications = {}

    # Classify each cluster
    for idx, (cluster_id, items) in enumerate(sampled_data.items()):
        progress_bar.progress((idx + 1) / len(sampled_data))
        cluster_classifications[cluster_id] = await classify_cluster(items, semaphore)

    return cluster_classifications


def apply_cluster_classifications(
    cluster_classifications: Dict[int, str],
    sampled_data: Dict[int, List[Dict[str, Any]]],
) -> Dict[int, List[Dict[str, Any]]]:
    for cluster_id, items in sampled_data.items():
        cluster_category = cluster_classifications.get(cluster_id, "Unknown")
        for item in items:
            item["classification"] = cluster_category
    return sampled_data


@st.cache_data
def cached_classify_example(content: str) -> str:
    return asyncio.run(async_classify_example(content))


async def async_classify_example(content: str, semaphore: asyncio.Semaphore) -> str:
    async with semaphore:
        response = await openai.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that classifies HTML into a category.  These documents were created from a user query which we currently aren't exposing. Categories should be no more than 3 words, only respond with the category.",
                },
                {"role": "user", "content": content},
            ],
        )
        return response.choices[0].message.content


@st.cache_data
def cached_classify_samples(
    sampled_data: Dict[int, List[Dict[str, Any]]],
) -> Dict[int, List[Dict[str, Any]]]:
    return asyncio.run(async_classify_samples(sampled_data))


async def async_classify_samples(
    sampled_data: Dict[int, List[Dict[str, Any]]],
) -> Dict[int, List[Dict[str, Any]]]:
    semaphore = asyncio.Semaphore(MAX_PARALLEL_TASKS)

    async def process_item(item):
        content = item["output"]["choices"][0]["message"]["content"]
        classification = await async_classify_example(content, semaphore)
        item["classification"] = classification
        return item

    tasks = []
    for items in sampled_data.values():
        tasks.extend([asyncio.create_task(process_item(item)) for item in items])

    await asyncio.gather(*tasks)

    return sampled_data


@st.cache_data
def visualize_clusters(
    assignments: np.ndarray,
    embeddings: List[List[float]],
    original_data: List[Dict[str, Any]],
) -> alt.Chart:
    pca = PCA(n_components=2)
    reduced_embeddings = pca.fit_transform(np.array(embeddings))

    df = pd.DataFrame(reduced_embeddings, columns=["PCA1", "PCA2"])
    df["Cluster"] = assignments

    # Add the HTML content and a truncated version for the tooltip
    df["HTML"] = [
        item["output"]["choices"][0]["message"]["content"]
        for item in original_data
        if item.get("output")
    ]
    df["HTML_preview"] = df["HTML"].apply(
        lambda x: x[:100] + "..." if len(x) > 100 else x
    )

    # Create a selection that chooses the nearest point & selects based on x-value
    nearest = alt.selection(
        type="single",
        nearest=True,
        on="mouseover",
        fields=["PCA1", "PCA2"],
        empty="none",
    )

    # The basic scatter plot
    base = alt.Chart(df).encode(x="PCA1:Q", y="PCA2:Q", color="Cluster:N")

    scatter = (
        base.mark_circle(size=60)
        .encode(
            tooltip=[
                "PCA1:Q",
                "PCA2:Q",
                "Cluster:N",
                alt.Tooltip("HTML_preview:N", title="HTML Preview"),
            ]
        )
        .add_params(nearest)
    )

    # Add text labels for the selected point
    text = (
        base.mark_text(align="left", dx=5, dy=-5)
        .encode(text="HTML_preview:N")
        .transform_filter(nearest)
    )

    return (scatter + text).interactive()


@st.cache_data
def visualize_categories(sampled_data: Dict[int, List[Dict[str, Any]]]) -> alt.Chart:
    category_counts: DefaultDict[str, int] = defaultdict(int)
    for items in sampled_data.values():
        for item in items:
            category = item.get("classification", "Unknown")
            category_counts[category] += 1
    df = pd.DataFrame(list(category_counts.items()), columns=["Category", "Count"])

    pie_chart = (
        alt.Chart(df)
        .mark_arc()
        .encode(
            theta=alt.Theta(field="Count", type="quantitative"),
            color=alt.Color(field="Category", type="nominal"),
        )
    )
    return pie_chart


st.title("LLM Trace Data Analyzer")

uploaded_file = st.file_uploader("Upload JSONL file", type="jsonl")
if uploaded_file is not None:
    st.write("Processing file...")
    jsonl_data = list(read_jsonl(uploaded_file))

    st.write("Embedding data...")
    progress_bar = st.progress(0)
    raw_embeddings, raw_ids = asyncio.run(process_jsonl(jsonl_data, progress_bar))

    # Cache the results
    embeddings, ids = cache_embeddings_and_ids(raw_embeddings, raw_ids)

    st.write("Building FAISS index...")
    index = build_faiss_index(embeddings)

    st.write("Clustering embeddings...")
    assignments = cluster_embeddings(embeddings, num_clusters=10)

    st.write("Sampling from clusters...")
    sampled_data = sample_from_clusters(
        assignments, ids, jsonl_data, samples_per_cluster=10
    )

    # TODO: perhaps summarize the clusters first?
    st.write("Classifying clusters...")
    progress_bar = st.progress(0)
    cluster_classifications = asyncio.run(
        async_classify_clusters(sampled_data, progress_bar)
    )

    st.write("Applying cluster classifications to samples...")
    sampled_data = apply_cluster_classifications(cluster_classifications, sampled_data)

    st.write("Visualizing Clusters")
    cluster_chart = visualize_clusters(assignments, embeddings, jsonl_data)

    # Use streamlit's altair_chart to display the chart
    chart = st.altair_chart(cluster_chart, use_container_width=True)

    # Create a placeholder for the full HTML content
    full_html_placeholder = st.empty()
    selection = st.query_params.get_all("selected_point")
    selected_point = selection[0] if selection else None

    if selected_point is not None:
        # Parse the selected point
        pca1, pca2 = map(float, selected_point.split(","))

        # Find the nearest point in our data
        df = cluster_chart.data
        nearest_point = df.iloc[
            ((df["PCA1"] - pca1) ** 2 + (df["PCA2"] - pca2) ** 2).idxmin()
        ]

        # Display full HTML for selected point
        full_html_placeholder.write("Full HTML Content:")
        full_html_placeholder.code(nearest_point["HTML"], language="html")

    st.write("Visualizing Categories")
    category_chart = visualize_categories(sampled_data)
    st.altair_chart(category_chart, use_container_width=True)
