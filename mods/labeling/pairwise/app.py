import csv
import os

import wandb
import weave

from components import create_annotation_page, create_layout
from fasthtml.common import fast_app, Script, Meta, Link, Request, serve, P, Div
from starlette.datastructures import FormData

WS_DS = None

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


def validate_wandb(entity: str, project: str, api_key: str):
    try:
        logged_in = wandb.login(key=api_key, verify=True)

    except ValueError as e:
        raise e
    return logged_in


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
        valid_key = validate_wandb(
            entity=contents["wandb_entity"],
            project=contents["wandb_project"],
            api_key=contents["wandb_key"],
        )
        if valid_key:
            _ = weave.init(f"{contents['wandb_entity']}/{contents['wandb_project']}")
            ds_name, dataset = await parse_file(contents["FileUpload"])
            global WS_DS
            WS_DS = weave.Dataset(name=ds_name, rows=dataset)
            ds_obj_ref = weave.publish(WS_DS)
            print("Dataset published successfully")  # Debug log
            return create_annotation_page(ds_obj_ref.get().rows)
    except ValueError as e:
        print(f"Error occurred: {e}")  # Debug log
        return Div(
            P(
                f"W&B API Validation error: {e}",
                cls="text-red-500 text-sm p-4 bg-red-50 border border-red-200 rounded-md",
            ),
            id="main-content",
        )
    except Exception as e:
        print(f"Unexpected error: {e}")  # Debug log
        return str(e)
    return "ok"


@rt("/annotate/{idx}")
async def get_annotation(idx: int):
    # Get the current dataset from weave
    try:
        # Get the most recent dataset
        global WS_DS
        latest_dataset = weave.ref(f"{WS_DS}:latest").get()
        rows = latest_dataset.get().rows

        # Convert string idx to int and validate
        idx = int(idx)
        if idx < 0 or idx >= len(rows):
            return "Invalid index"

        return create_annotation_page(rows, idx)
    except Exception as e:
        print(f"Error in get_annotation: {e}")  # Debug log
        return str(e)


serve()
