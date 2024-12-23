# Weave Mods

A way to customize and enhance your GenAI dashboards.

## Getting Started

### Prerequisites

- [uv](https://docs.astral.sh/uv)
- [docker](https://docker.com/products/docker-desktop)

Once installed, run the following to install pre-commit hooks and pull the latest dev image:

```bash
./dev.py setup
```

### Run a mod locally in dev mode

```bash
./dev.py mods/demo
```

> NOTE: ensure you're logged into wandb and you'll likely want to set the WANDB_PROJECT env var to a project with existing weave trace data.

### Create your own mod!

```bash
./dev.py create my_mod
```

### Add dependencies

```bash
cd mods/my_mod
uv add openai
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

## Mods SDK

This repo also includes a Python SDK with weave api helpers in `sdk`.  If you find yourself implementing custom logic for interacting with weave, consider adding it to the SDK.  Learn more at [sdk/README.md](sdk/README.md).

## What about arbitrary Docker images?

We may support this in the future, but we're focusing on Python for now.  By offloading the packaging and runtime concerns to us, we're able to ensure the actual containers we run are secure and performant.
