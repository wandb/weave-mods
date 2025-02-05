import csv
import os

import wandb
import weave
from fasthtml.common import Link, Meta, Request, Script, fast_app, serve, Div
from starlette.datastructures import FormData

from components import create_login_page

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
    return create_login_page()


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
    contents: FormData = await request.form()
    try:
        valid_key = validate_wandb(
            entity=contents["wandb_entity"],
            project=contents["wandb_project"],
            api_key=contents["wandb_key"],
        )
        if valid_key:
            _ = weave.init(f'{contents["wandb_entity"]}/{contents["wandb_project"]}')
            ds_name, dataset = await parse_file(contents["FileUpload"])
            ws_ds = weave.Dataset(name=ds_name, rows=dataset)
            ds_obj_ref = weave.publish(ws_ds)
            # TODO: Make this a more polished div
            return Div(f"Raw Weave Dataset Published at {ds_obj_ref.uri()}")
    except ValueError as e:
        return str(e)

    return "ok"


serve()
