import random
from typing import Sized

import weave


from components import create_annotation_page, create_layout
from fasthtml.common import (
    Div,
    Link,
    Meta,
    P,
    Request,
    Script,
    fast_app,
    serve,
    MarkdownJS,
)
from llm_ops import run_llms_pairwise
from starlette.datastructures import FormData
from utils import parse_file, validate_apis
from weave.trace.weave_client import WeaveClient

WS_DATA: Sized | None = None
MODELS_DICT: dict | None = None
WEAVE_CLIENT: WeaveClient | None = None
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
        MarkdownJS(),
    ),
)


@rt("/")
def get():
    return create_layout()


@rt("/upload", methods=["POST"])
async def post(request: Request):
    contents: FormData = await request.form()
    try:
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
        global WEAVE_CLIENT
        WEAVE_CLIENT = weave.init(
            f"{contents['wandb_entity']}/{contents['wandb_project']}"
        )
        ds_name, dataset = await parse_file(contents["FileUpload"])
        ws_ds = weave.Dataset(name=ds_name, rows=dataset)
        ds_obj_ref = weave.publish(ws_ds)
        global WS_DATA
        WS_DATA = ds_obj_ref.get().rows

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
        return str(e)


@rt("/annotate/{idx}")
async def get_annotation(idx: int):
    try:
        rows = WS_DATA
        idx = int(idx)
        if idx < 0 or idx >= len(rows):
            return "Invalid index"
        prompt = rows[idx].get("prompt")

        response_dict, call = await run_llms_pairwise.call(
            model_a=MODELS_DICT["model_a"],
            model_b=MODELS_DICT["model_b"],
            prompt=prompt,
        )

        # Randomly decide whether to swap the responses
        should_swap = random.choice([True, False])
        if should_swap:
            display_responses = {
                "response_a": response_dict["response_b"],
                "response_b": response_dict["response_a"],
            }
        else:
            display_responses = response_dict

        record = {
            "idx": idx,
            "total_length": len(rows),
            "prompt": prompt,
            "response_a": display_responses["response_a"],
            "response_b": display_responses["response_b"],
            "call_id": call.id,
            "swapped": should_swap,  # Add swap information to record
        }
        return create_annotation_page(record)
    except Exception as e:
        print(f"Error in get_annotation: {e}")  # Debug log
        return str(e)


@rt("/submit_preference/{idx}/{call_id}", methods=["POST"])
async def submit_preference(request: Request, idx: int, call_id: str):
    try:
        form_data = await request.form()
        preference = form_data.get("preference")
        was_swapped = form_data.get("swapped") == "True"  # Get swap info from form
        print(f"form_data_swapped: {form_data.get('swapped')}")
        print(f"was_swapped: {was_swapped}")
        # Adjust the preference based on whether responses were swapped
        if was_swapped:
            actual_preference = "model_b" if preference == "model_a" else "model_a"
        else:
            actual_preference = preference

        call = WEAVE_CLIENT.get_call(call_id)
        call.feedback.add(
            "preference", {"model": MODELS_DICT.get(actual_preference, {}).get("model")}
        )

        next_idx = idx + 1
        if next_idx < len(WS_DATA):
            return await get_annotation(next_idx)
        else:
            return Div("Annotation complete!", id="main-content")

    except Exception as e:
        print(f"Error in submit_preference: {e}")
        return str(e)


serve()
