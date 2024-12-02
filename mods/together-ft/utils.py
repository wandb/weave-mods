import weave
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import ObjQueryReq, ObjectVersionFilter

import streamlit as st
import os

def weave_client_hash(weave_client: WeaveClient):
    return weave_client.project

@st.cache_data(hash_funcs={WeaveClient: weave_client_hash})
def load_available_datasets(weave_client: WeaveClient) -> list[str]:
    print(
        f"Loading available datasets for project {weave_client.entity}/{weave_client.project}")
    try:
        trace_server = weave_client.server
        res = trace_server.objs_query(ObjQueryReq(
            project_id=f"{weave_client.entity}/{weave_client.project}",
            filter=ObjectVersionFilter(
                base_object_classes=["Dataset"],
                latest_only=True,
                is_op=False
            )
        ))

        # Sort the list alphabetically
        return sorted([obj.object_id for obj in res.objs])
    except Exception as e:
        print(str(e))
        st.error(f"Error loading datasets: {str(e)}")
        return []


def dataset_picker(weave_client: WeaveClient, title: str = "Select a dataset") -> str:
    available_datasets = load_available_datasets(weave_client)

    # Add None as the first option
    dataset_options = [None] + available_datasets

    dataset_name = st.selectbox(
        title,
        dataset_options,
        key=title
    )
    return dataset_name


# @st.cache_resource
def init_weave_client_cached(default_project="example", default_entity="l2k2"):
    return weave.init(f"{default_entity}/{default_project}")


def init_weave_client(default_project="example"):

    with st.sidebar:
        weave_entity, weave_project = weave_settings_picker(
            default_entity='l2k2', default_project=default_project)
        try:
            os.environ['WANDB_PROJECT'] = weave_project
            os.environ['WANDB_ENTITY'] = weave_entity
            weave_client = init_weave_client_cached(default_entity=weave_entity, default_project=weave_project)
            st.write("Connected to Weave")
        except Exception as e:
            st.error(f"Error connecting to Weave: {str(e)}")
            st.stop()

    return weave_client

def weave_settings_picker(default_entity="l2k2", default_project="rag-builder"):
    st.title("Weave Settings")
    weave_entity = st.text_input("Entity", value=default_entity)
    weave_project = st.text_input("Project", value=default_project)
    return weave_entity, weave_project

