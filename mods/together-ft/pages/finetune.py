import weave
import streamlit as st


from weave.trace.weave_client import WeaveClient
import os

from together import Together
import json
from together.utils import check_file
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import ObjQueryReq, ObjectVersionFilter


@st.cache_resource
def weave_get_dataset(dataset_name: str) -> weave.Dataset:
    return weave.ref(dataset_name).get()



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

def dataset_multiple_picker(weave_client: WeaveClient, title: str = "Select datasets") -> list[str]:
    available_datasets = load_available_datasets(weave_client)
    return st.multiselect(options=available_datasets, key='dataset_names', label=title)


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



def write_dataset_jsonl_for_together(dataset: weave.Dataset, input_column: str, output_column: str, system_prompt: str):
    dataset_name = dataset.name

    new_file_path = f"{dataset_name}.jsonl"

    # Define Llama-3 prompt and system prompt
    llama_format = """
    <|begin_of_text|><|start_header_id|>system<|end_header_id|>
    {system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>
    {user_question}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
    {model_answer}<|eot_id|>
    """
    formatted_data = []
    # system_prompt = "You're a helpful assistant that answers math problems."

    # Transform the data into the correct format and write it to a JSONL file
    with open(new_file_path, "w", encoding="utf-8") as new_file:
        for row in dataset.rows:
            temp_data = {
                "text": llama_format.format(
                    system_prompt=system_prompt,
                    user_question=row[input_column],
                    model_answer=row[output_column],
                )
            }
            new_file.write(json.dumps(temp_data))
            new_file.write("\n")

    report = check_file(new_file_path)
    assert report["is_check_passed"] == True
    return new_file_path

def upload_dataset_to_together(dataset_path: str, input_column: str, output_column: str, system_prompt: str):
    dataset_file_path = write_dataset_jsonl_for_together(dataset_path, input_column, output_column, system_prompt)

    client = Together()

    response = client.files.upload(file=dataset_file_path)
    return response.model_dump()["id"]

def write_dataset_to_together(dataset: weave.Dataset, eval_dataset: weave.Dataset | None, input_column: str, output_column: str,
                              base_model_name: str,
                              finetuned_model_name: str, system_prompt: str,
                            weave_client: WeaveClient, n_epochs: int = 5,
                              batch_size: int = 8, learning_rate: float = 1e-5):

    input_dataset_id = upload_dataset_to_together(dataset, input_column, output_column, system_prompt)
    if eval_dataset is not None:
        eval_dataset_id = upload_dataset_to_together(eval_dataset, input_column, output_column, system_prompt)
    else:
        print("No eval dataset provided")
        eval_dataset_id = None

    client = Together()
    # Verify that the file was uploaded successfully
    file_metadata = client.files.retrieve(input_dataset_id)
    assert(os.environ.get("WANDB_API_KEY") is not None)
    print(f"Triggering fine-tuning job for {finetuned_model_name} with base model {base_model_name}")
    # Trigger fine-tuning job
    resp = client.fine_tuning.create(
        suffix=f"{finetuned_model_name}",
        model=base_model_name,
        training_file=input_dataset_id,
        validation_file=eval_dataset_id,
        n_epochs=n_epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        wandb_api_key=os.environ.get("WANDB_API_KEY"),
        n_evals=10,
        lora=True
        # wandb_project=weave_client.project,
        # wandb_entity=weave_client.entity
    )
    return resp






def dataset_column_picker(dataset_name: str):
    weave_dataset = weave_get_dataset(dataset_name)
    input_column = output_column = None
    column_options = list(weave_dataset.rows[0].keys())

    if len(weave_dataset.rows) > 0:
        # Update column options when dataset changes

        # Find default indices for input and output columns
        input_default_idx = column_options.index('input') if 'input' in column_options else 0
        output_default_idx = column_options.index('output') if 'output' in column_options else 0

        col1, col2 = st.columns(2)
        with col1:
            input_column = st.selectbox("Input Column",
                                        column_options,
                                        index=input_default_idx,
                                        key="input_column")
        with col2:
            output_column = st.selectbox("Output Column",
                                         column_options,
                                         index=output_default_idx,
                                         key="output_column")

        # Show preview if both columns are selected
        if input_column and output_column:
            with st.expander("Preview", expanded=True):
                preview_data = {
                    input_column: [row[input_column] for row in weave_dataset.rows[:3]],
                    output_column: [row[output_column] for row in weave_dataset.rows[:3]]
                }
                st.dataframe(preview_data)
    else:
        st.warning("Selected dataset is empty")

    return input_column, output_column


def main():
    weave_client = init_weave_client('finetune')

    # Add title and description
    st.title("LLM Fine-tuning with together.ai")
    st.write("Fine-tune Llama model on weave dataset")

    if st.button("Reset Cache"):
        st.cache_data.clear()
        st.rerun()

    dataset_names = dataset_multiple_picker(weave_client, "Training Dataset Name")

    # if dataset_name:
    #    input_column, output_column = dataset_column_picker(dataset_name)

    eval_dataset_name = dataset_picker(weave_client, "Eval Dataset Name")
    system_prompt = st.text_input("System Prompt", value="You're a helpful assistant")

    training_mode = st.radio(
        "Training Mode",
        ["Fine-tune Base Model", "Resume from Checkpoint"],
        index=0
    )


    input_model_name = st.selectbox(
        "Base Model",
        ["meta-llama/Meta-Llama-3.1-8B-Instruct-Reference", "meta-llama/Meta-Llama-3.1-70B-Instruct-Reference"]
    )
    finetuned_model_name = st.text_input(
        "Output Model Name", value="llama-3.1-8b-finetuned")

    # Add training parameters
    with st.expander("Training Parameters", expanded=False):
        batch_size = 8 # st.number_input("Batch Size", min_value=1, value=2)
        n_epochs = st.number_input("Number of Epochs", min_value=1, value=5)
        learning_rate = st.number_input(
            "Learning Rate", min_value=0.0, value=2e-4, format="%.0e")

    def update_status(msg: str) -> None:
        status.update(label=msg)

    # Initialize wandb only when starting training
    if st.button("Start Training", disabled=len(dataset_names) == 0):
        status = st.status("Starting training...")

        datasets = []
        for dataset_name in dataset_names:
            datasets.append( weave.ref(dataset_name).get())
        input_column = "input"
        output_column = "output"
        # input_column, output_column = dataset_column_picker(dataset_name)
        eval_dataset = weave.ref(eval_dataset_name).get() if eval_dataset_name else None
        resume_flag = training_mode == "Resume from Checkpoint"
        resp = write_dataset_to_together(dataset=datasets[0],
                                          eval_dataset=eval_dataset,
                                          input_column=input_column,
                                          output_column=output_column,
                                          finetuned_model_name=finetuned_model_name ,
                                          base_model_name=input_model_name,
                                          system_prompt=system_prompt,
                                          weave_client=weave_client,
                                          n_epochs=n_epochs,
                                          batch_size=batch_size,
                                          learning_rate=learning_rate)

        print(resp)
        status.update(label=f"Find the together job at https://api.together.xyz/jobs/{resp.id}")
        status.write(resp)


if __name__ == "__main__":
    main()
