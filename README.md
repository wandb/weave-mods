# Weave Mods

A way to customize and enhance your GenAI dashboards.

## Getting Started

### Prerequisites

- [uv](https://docs.astral.sh/uv)
- [docker](https://docker.com/products/docker-desktop)

### Run a mod locally in dev mode

```bash
./mod.py dev mods/welcome
```

## Create your own mod!

```bash
./mod.py create my_mod
```

## What's in a mod?

A mod is a Python package that can be used to customize and enhance your GenAI dashboards.  It should have a `pyproject.toml` file with a `[tool.weave.mod]` section.  By default we use `app.py` as the entrypoint, but you can customize this in a `pyproject.toml` file.

### Configuration

```toml
[tool.weave.mod]
flavor = "streamlit"
secrets = ["OPENAI_API_KEY", "WANDB_API_KEY"]
# Optional, inferred from flavor
port = 6637
entrypoint = "app.py"

[tool.weave.mod.secrets.OPENAI_API_KEY]
description = "Your OpenAI API key"

[tool.weave.mod.env]
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
```

### Flavors

- `streamlit`: A Streamlit app.
- `fasthtml`: A FastHTML app.
- `marimo`: A Marimo app.
- `custom`: A custom entrypoint.

### Secrets

The secrets specified will automatically be exposed to the container.  When a mod is running in the cloud, we will ask the user to specify any secrets they haven't configured.

### Linked Mods

You can take existing repositories and turn them into a mod!  See `mods/openui` for an example.

## What about arbitrary Docker images?

We may support this in the future, but we're focusing on Python for now.  By offloading the packaging and runtime concerns to us, we're able to ensure the actual containers we run are secure and performant.
