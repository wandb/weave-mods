import csv
import os
from typing import Sized

import wandb
import weave

from components import create_annotation_page, create_layout
from fasthtml.common import fast_app, Script, Meta, Link, Request, serve, P, Div
from starlette.datastructures import FormData
from litellm import check_valid_key

from llm_ops import run_llms_pairwise

WS_DATA: Sized | None = None
MODELS_DICT: dict | None = None
app, rt = fast_app(
    # live=True,
    pico=True,
    htmx=True,
    hdrs=(
        Script(src="https://cdn.tailwindcss.com"),
        Meta(
            name="viewport",
            content="width=device-width, height=device-height, initial-scale=1.0",
        ),
        Link(
            rel="stylesheet",
            href="https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@300;400;500;600&display=swap",
        ),
    ),
)


@rt("/")
def get():
    return create_layout()


def validate_apis(wandb_api_key: str, model_a: dict[str, str], model_b: dict[str, str]):
    try:
        valid_wandb = wandb.login(key=wandb_api_key, verify=True)
        valid_model_a = check_valid_key(**model_a)
        if not valid_model_a:
            raise ValueError(f"Incorrect API Key set for Model: {model_a['model']}")
        valid_model_b = check_valid_key(**model_b)
        if not valid_model_b:
            raise ValueError(f"Incorrect API Key set for Model: {model_b['model']}")
    except ValueError as e:
        raise e
    return valid_wandb and valid_model_a and valid_model_b


async def parse_file(file_obj):
    ds_name = os.path.splitext(file_obj.filename)[0]
    file_contents = await file_obj.read()
    file_contents = file_contents.decode("utf-8").splitlines()
    reader = csv.DictReader(file_contents)
    assert (
        len(reader.fieldnames) <= 3
    ), "Only the following fields are supported: 'Prompt', 'Model A', 'Model B'"
    dataset = [line for line in reader]
    return ds_name, dataset


@rt("/upload", methods=["POST"])
async def post(request: Request):
    print("Upload endpoint hit!")  # Debug log
    contents: FormData = await request.form()
    try:
        print("Form contents:", contents)  # Debug log
        model_a = {
            "model": contents["primary_model"],
            "api_key": contents["primary_api_key"],
        }
        model_b = {
            "model": contents["challenger_model"],
            "api_key": contents["challenger_api_key"],
        }
        global MODELS_DICT
        MODELS_DICT = {"model_a": model_a, "model_b": model_b}
        validate_apis(
            wandb_api_key=contents["wandb_key"], model_a=model_a, model_b=model_b
        )

        _ = weave.init(f"{contents['wandb_entity']}/{contents['wandb_project']}")
        ds_name, dataset = await parse_file(contents["FileUpload"])
        ws_ds = weave.Dataset(name=ds_name, rows=dataset)
        ds_obj_ref = weave.publish(ws_ds)
        global WS_DATA
        WS_DATA = ds_obj_ref.get().rows
        print("Dataset published successfully")  # Debug log

        return await get_annotation(idx=0)
    except ValueError as e:
        print(f"Error occurred: {e}")  # Debug log
        return Div(
            P(
                f"API Authentication error: {e}",
                cls="text-red-500 text-sm p-4 bg-red-50 border border-red-200 rounded-md",
            ),
            id="main-content",
        )
    except Exception as e:
        print(f"Unexpected error: {e}")  # Debug log
        return str(e)


@rt("/annotate/{idx}")
async def get_annotation(idx: int):
    # Get the current dataset from weave
    try:
        # Get the most recent dataset
        rows = WS_DATA
        # Convert string idx to int and validate
        idx = int(idx)
        if idx < 0 or idx >= len(rows):
            return "Invalid index"
        prompt = rows[idx].get("prompt")
        response_dict = await run_llms_pairwise(
            model_a=MODELS_DICT["model_a"],
            model_b=MODELS_DICT["model_b"],
            prompt=prompt,
        )
        record = {
            "idx": idx,
            "total_length": len(rows),
            "prompt": prompt,
            "response_a": response_dict["response_a"],
            "response_b": response_dict["response_b"],
        }
        return create_annotation_page(record)
    except Exception as e:
        print(f"Error in get_annotation: {e}")  # Debug log
        return str(e)


serve()
