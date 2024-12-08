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
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Dict, List, Optional

import toml
import typer
from pydantic import BaseModel
from rich.console import Console

log = Console(stderr=True)

env = os.getenv("ENVIRONMENT")
if env == "production" or env == "prod":
    REGISTRY = "us-central1-docker.pkg.dev/wandb-production/mods"
elif env == "qa":
    REGISTRY = "us-central1-docker.pkg.dev/wandb-qa/mods"
else:
    REGISTRY = "localhost:5001/mods"

REGISTRY = os.getenv("REGISTRY", REGISTRY)

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


class DockerConfig(BaseModel):
    directory: str
    dockerfile: str
    tags: List[str]
    labels: Dict[str, str]


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
    directories: Annotated[
        Optional[List[str]],
        typer.Argument(
            ...,
            help="Directories to build. If not provided, all directories with pyproject.toml will be built.",
        ),
    ] = None,
    root: str = typer.Option(
        "mods", "--root", help="Root directory to search for pyproject.toml"
    ),
    platform: str = typer.Option(
        "linux/amd64,linux/arm64", "--platform", help="Docker platform arg"
    ),
    build: Optional[bool] = typer.Option(
        None,
        "--build",
        help="Actually build the images, defaults to true when REGISTRY is localhost",
    ),
    upgrade: bool = typer.Option(
        False, "--upgrade", help="Upgrade dependencies before building"
    ),
):
    template_path = Path(__file__).parent / "Dockerfile.template"
    git_sha = exec_read("git rev-parse HEAD")
    mod_configs: List[ModConfig] = []
    if build is None:
        build = "localhost:" in REGISTRY
    # If no directories specified, build all
    if not directories:
        directories = [
            str(p.parent)
            for p in Path(root).rglob("pyproject.toml")
            if ".venv" not in p.parts
        ]

    mod_configs = []
    build_configs = []
    healthcheck = Path(__file__).parent / "mods" / "healthcheck.py"
    # Loop over all directories containing 'pyproject.toml' under 'mods/'
    for dir_str in directories:
        dir_path = Path(dir_str)
        pyproject = dir_path / "pyproject.toml"
        if not pyproject.exists():
            log.print(
                f"Skipping directory: {dir_path} (no pyproject.toml)",
                style="yellow",
            )
            continue

        log.print(f"Processing directory: {dir_path}", style="green")
        dockerfile_path = dir_path / "Dockerfile"
        dockerignore_path = dir_path / ".dockerignore"
        healthcheck_path = dir_path / "healthcheck.py"
        try:
            if upgrade:
                log.print("Upgrading dependencies...", style="yellow")
                subprocess.run(["uv", "lock", "--upgrade"], cwd=dir_path, check=True)

            # Create '.dockerignore' with '.venv' content
            with dockerignore_path.open("w") as f:
                f.write(".venv\n")

            with template_path.open("r") as f:
                template_content = f.read()

            # Replace '$$MOD_ENTRYPOINT$$' with '["python", "app.py"]'
            mod_config = details_from_config(pyproject)
            new_content = template_content.replace(
                "$$MOD_ENTRYPOINT",
                " ".join(
                    ["python", "/app/src/healthcheck.py", "&"] + mod_config.entrypoint
                ),
            )

            # Write the new Dockerfile
            with dockerfile_path.open("w") as f:
                f.write(new_content)

            # Copy healthcheck.py to the mod directory
            shutil.copy(healthcheck, dir_path)

            # Build the Docker image
            docker_tags = [
                "-t",
                f"{REGISTRY}/{mod_config.name}:{mod_config.version}",
                "-t",
                f"{REGISTRY}/{mod_config.name}:latest",
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

            if build:
                subprocess.run(
                    [
                        "docker",
                        "buildx",
                        "build",
                        ".",
                        "--platform",
                        platform,
                        *docker_tags,
                        *label_args,
                        "--load",
                    ],
                    cwd=dir_path,
                    check=True,
                )
                log.print(f"Built image: {docker_tags[1]}", style="green")
            else:
                log.print(f"Discovered image: {docker_tags[1]}", style="green")
                build_configs.append(
                    DockerConfig(
                        directory=str(dir_path),
                        dockerfile=dockerfile_path.name,
                        tags=[t for t in docker_tags if t != "-t"],
                        labels=labels,
                    )
                )
            mod_configs.append(mod_config)
        finally:
            # Clean up '.dockerignore' and 'Dockerfile' only if we built locally
            if build:
                healthcheck_path.unlink(missing_ok=True)
                dockerignore_path.unlink(missing_ok=True)
                dockerfile_path.unlink(missing_ok=True)
    log.print(
        f"{'Built' if build else 'Discovered'} {len(mod_configs)} mods",
        style="green",
    )
    if build:
        json.dump([item.model_dump() for item in mod_configs], sys.stdout, indent=4)
    else:
        json.dump([item.model_dump() for item in build_configs], sys.stdout)


if __name__ == "__main__":
    app()
