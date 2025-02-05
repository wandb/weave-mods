import wandb
from components import create_login_page
from fasthtml.common import Link, Meta, Request, Script, fast_app, serve
from starlette.datastructures import FormData

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
    _api = wandb.Api(api_key=api_key, overrides={"entity": entity, "project": project})


@rt("/upload", methods=["POST"])
async def post(request: Request):
    contents: FormData = await request.form()
    print(contents)

    return "ok"


serve()
