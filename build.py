#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "typer",
#     "toml",
#     "pydantic",
# ]
# ///

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, List

import toml
import typer
from pydantic import BaseModel

env = os.getenv("ENVIRONMENT")
if env == "production" or env == "prod":
    REGISTRY = "gcr.io/wandb-production"
elif env == "qa":
    REGISTRY = "gcr.io/wandb-qa"
else:
    REGISTRY = "localhost:5001"

app = typer.Typer()

FLAVORS = {
    "streamlit": [
        "streamlit",
        "run",
        "/app/src/app.py",
        "--server.port=6637",
        "--server.address=0.0.0.0",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
    ],
    "marimo": ["marimo", "run", "--port=6637", "--host=0.0.0.0", "/app/src/app.py"],
}


class ModConfig(BaseModel):
    name: str
    classifiers: List[str]
    entrypoint: List[str]
    description: str
    version: str
    secrets: List[str]


def details_from_config(pyproject_path: Path) -> dict:
    with open(pyproject_path, "r") as f:
        pyproject = toml.load(f)
    config = pyproject.get("tool", {}).get("weave", {}).get("mod", {})
    flavor = config.get("flavor", "streamlit")
    entrypoint = config.get(
        "entrypoint", FLAVORS.get(flavor, ["python", "/app/src/app.py"])
    )
    secrets = config.get("secrets", [])
    project = pyproject.get("project", {})
    description = project.get("description", "A Weave Mod")
    version = project.get("project", {}).get("version", "0.1.0")
    name = project.get("project", {}).get("name", pyproject_path.parent.name)
    classifiers = project.get("project", {}).get("classifiers", [])
    return ModConfig(
        name=name,
        classifiers=classifiers,
        entrypoint=entrypoint,
        description=description,
        version=version,
        secrets=secrets,
    )


def exec_read(cmd: str) -> str:
    try:
        proc = subprocess.run(cmd, shell=True, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(e.stdout)
        print(e.stderr)
        raise e

    return proc.stdout.decode("utf-8").rstrip()


@app.command()
def build(
    root: Annotated[str, typer.Argument()] = "mods",
    upgrade: bool = typer.Option(
        False, "--upgrade", help="Upgrade dependencies before building"
    ),
):
    template_path = Path(__file__).parent / "Dockerfile.template"
    git_sha = exec_read("git rev-parse HEAD")
    mod_configs: List[ModConfig] = []
    # Loop over all directories containing 'pyproject.toml' under 'mods/'
    for pyproject in Path(root).rglob("pyproject.toml"):
        # Skip if '.venv' is in any part of the path
        if ".venv" in pyproject.parts:
            continue
        dir_path = pyproject.parent
        typer.secho(f"Processing directory: {dir_path}", fg=typer.colors.GREEN)
        dockerfile_path = dir_path / "Dockerfile"
        dockerignore_path = dir_path / ".dockerignore"
        try:
            if upgrade:
                typer.secho("Upgrading dependencies...", fg=typer.colors.YELLOW)
                subprocess.run(["uv", "lock", "--upgrade"], cwd=dir_path, check=True)

            # Create '.dockerignore' with '.venv' content
            with dockerignore_path.open("w") as f:
                f.write(".venv\n")

            with template_path.open("r") as f:
                template_content = f.read()

            # Replace '$$MOD_ENTRYPOINT$$' with '["python", "app.py"]'
            mod_config = details_from_config(pyproject)
            typer.secho(
                f"Entrypoint: {" ".join(mod_config.entrypoint)}", fg=typer.colors.YELLOW
            )
            new_content = template_content.replace(
                "$$MOD_ENTRYPOINT", json.dumps(mod_config.entrypoint)
            )

            # Write the new Dockerfile
            with dockerfile_path.open("w") as f:
                f.write(new_content)

            # Build the Docker image
            docker_tags = [
                "-t",
                f"{REGISTRY}/mods/{mod_config.name}:{mod_config.version}",
                "-t",
                f"{REGISTRY}/mods/{mod_config.name}:latest",
            ]

            labels = {
                "org.opencontainers.image.created": datetime.now().isoformat(),
                "org.opencontainers.image.description": mod_config.description,
                "org.opencontainers.image.licenses": "Apache-2.0",
                "org.opencontainers.image.revision": git_sha,
                "org.opencontainers.image.source": f"https://github.com/wandb/weave-mods/tree/{git_sha[0:7]}/{dir_path}",
                "org.opencontainers.image.title": mod_config.name,
                "org.opencontainers.image.url": "https://wandb.ai/site/docs/guides/weave/mods",
                "org.opencontainers.image.version": mod_config.version,
            }

            # Construct label arguments for the docker build command
            label_args = []
            for key, value in labels.items():
                label_args.extend(["--label", f"{key}={value}"])

            subprocess.run(
                ["docker", "build", ".", *docker_tags, *label_args, "--load"],
                cwd=dir_path,
                check=True,
            )
            mod_configs.append(mod_config)
            typer.secho(f"Built image: {docker_tags[1]}", fg=typer.colors.GREEN)
        finally:
            # Clean up: remove '.dockerignore' and 'Dockerfile'
            dockerignore_path.unlink(missing_ok=True)
            dockerfile_path.unlink(missing_ok=True)
    json.dump([item.dict() for item in mod_configs], sys.stdout, indent=4)


if __name__ == "__main__":
    app()
