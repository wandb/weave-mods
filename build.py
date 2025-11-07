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
from typing import Annotated, Dict, List, Optional, Set

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
elif env == "dev":
    REGISTRY = "localhost:5001/mods"
else:
    REGISTRY = "ghcr.io/wandb/weave-mods"

REGISTRY = os.getenv("REGISTRY", REGISTRY)

app = typer.Typer()

# Default package manager for JavaScript mods. Can be overridden with the
# JS_PACKAGE_MANAGER environment variable.
JS_PACKAGE_MANAGER = os.getenv("JS_PACKAGE_MANAGER", "deno")

FLAVORS = {
    "streamlit": [
        "streamlit",
        "run",
        "/app/src/app.py",
        "--server.port=6637",
        "--server.address=0.0.0.0",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
        "--client.toolbarMode=minimal",
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


def details_from_package(package_path: Path) -> ModConfig:
    with open(package_path, "r") as f:
        package = json.load(f)
    config = package.get("weave", {}).get("mod", {})
    secrets = config.get("secrets", [])
    description = package.get("description", "A Weave Mod")
    version = package.get("version", "0.1.0")
    name = package.get("name", package_path.parent.name)
    return ModConfig(
        name=name,
        classifiers=[],
        entrypoint=[],
        description=description,
        version=version,
        secrets=secrets,
    )


def details_from_config(pyproject_path: Path) -> dict:
    with open(pyproject_path, "r") as f:
        pyproject = toml.load(f)
    config = pyproject.get("tool", {}).get("weave", {}).get("mod", {})
    flavor = config.get("flavor", "streamlit")
    entrypoint = config.get(
        "entrypoint", FLAVORS.get(flavor, ["python", "/app/src/app.py"])
    )
    if isinstance(entrypoint, str):
        entrypoint = [entrypoint]
    # TODO: this is sketchy and likely to be confusing for some poor future dev
    # Detect a user overriding the entrypoint filename for a streamlit mod
    if entrypoint[0].endswith(".py") and flavor == "streamlit":
        file = entrypoint[0]
        path = os.path.join("/app/src", file)
        FLAVORS["streamlit"][2] = path
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
        "--build/--no-build",
        help="Actually build the images, defaults to true when REGISTRY is localhost",
    ),
    manifest: Optional[bool] = typer.Option(
        False,
        "--manifest",
        help="Generate a manifest of the built images",
    ),
    upgrade: bool = typer.Option(
        False, "--upgrade", help="Upgrade dependencies before building"
    ),
):
    template_path = Path(__file__).parent / "Dockerfile.template"
    js_template_path = Path(__file__).parent / "Dockerfile.spa.template"
    deno_server = Path(__file__).parent / "mods" / "deno_server.ts"
    git_sha = exec_read("git rev-parse HEAD")
    mod_configs: List[ModConfig] = []
    if build is None:
        build = "localhost:" in REGISTRY
    # If no directories specified, build all pyproject or package.json dirs
    if not directories:
        dirs: Set[str] = set(
            str(p.parent)
            for p in Path(root).rglob("pyproject.toml")
            if ".venv" not in p.parts
        )
        dirs.update(
            str(p.parent)
            for p in Path(root).rglob("package.json")
            if "node_modules" not in p.parts
        )
        directories = sorted(list(dirs))

    mod_configs = []
    build_configs = []
    healthcheck = Path(__file__).parent / "mods" / "healthcheck.py"
    # Loop over all directories containing configuration
    for dir_str in directories:
        dir_path = Path(dir_str)
        pyproject = dir_path / "pyproject.toml"
        package_json = dir_path / "package.json"
        is_python = pyproject.exists()
        is_js = package_json.exists()
        if not is_python and not is_js:
            log.print(
                f"Skipping directory: {dir_path} (no config)",
                style="yellow",
            )
            continue
        if not manifest:
            log.print(f"Processing directory: {dir_path}", style="green")
        dockerfile_path = dir_path / "Dockerfile"
        dockerignore_path = dir_path / ".dockerignore"
        healthcheck_path = dir_path / "healthcheck.py"
        try:
            if upgrade:
                if is_python:
                    log.print("Upgrading dependencies...", style="yellow")
                    subprocess.run(
                        ["uv", "lock", "--upgrade"], cwd=dir_path, check=True
                    )

            if is_python:
                with dockerignore_path.open("w") as f:
                    f.write(".venv\n")

                with template_path.open("r") as f:
                    template_content = f.read()

                mod_config = details_from_config(pyproject)
                new_content = template_content.replace(
                    "$$MOD_ENTRYPOINT",
                    " ".join(
                        ["python", "/app/src/healthcheck.py", "&"]
                        + mod_config.entrypoint
                    ),
                )

                with dockerfile_path.open("w") as f:
                    f.write(new_content)

                shutil.copy(healthcheck, dir_path)
            else:
                with dockerignore_path.open("w") as f:
                    f.write("node_modules\n")

                with js_template_path.open("r") as f:
                    template_content = f.read()

                mod_config = details_from_package(package_json)

                shutil.copy(deno_server, dir_path)

                with dockerfile_path.open("w") as f:
                    f.write(template_content)

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

            # Construct label arguments for the docker build command when not localhost
            label_args = []
            for key, value in labels.items():
                label_args.extend(["--label", f"{key}={value}"])

            # No multi-arch for dev
            if env == "dev":
                platform = "linux/arm64"

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
                tags = [t for t in docker_tags if t != "-t"]
                # Add our default registry to the tags if it's set
                if os.getenv("DEFAULT_REGISTRY"):
                    for tag in tags.copy():
                        tag = tag.replace(REGISTRY, os.getenv("DEFAULT_REGISTRY"))
                        tags.append(tag)
                build_configs.append(
                    DockerConfig(
                        directory=str(dir_path),
                        dockerfile=dockerfile_path.name,
                        tags=tags,
                        labels=labels,
                    )
                )
            mod_configs.append(mod_config)
        finally:
            # Clean up '.dockerignore' and 'Dockerfile' only if we built locally
            if build:
                if is_python:
                    healthcheck_path.unlink(missing_ok=True)
                dockerignore_path.unlink(missing_ok=True)
                dockerfile_path.unlink(missing_ok=True)
                if is_js:
                    (dir_path / deno_server.name).unlink(missing_ok=True)
    log.print(
        f"{'Built' if build else 'Wrote'} {len(mod_configs)} mods {'to the manifest' if manifest else ''}",
        style="green",
    )
    if manifest:
        if len(mod_configs) == 1:
            typer.secho(
                "Manifest can not be updated for a single mod.", fg=typer.colors.RED
            )
            raise typer.Exit(code=1)

        mod_lookup = {mc.name: mc.model_dump() for mc in mod_configs}

        with open("featured.toml", "r") as f:
            featured_config = toml.load(f)

        featured_manifest = {}
        featured_count = 0
        for section, content in featured_config.items():
            if "mods" in content:
                for mod_id in content["mods"]:
                    if mod_id not in mod_lookup:
                        typer.secho(
                            f"Mod {mod_id} not found in manifest.json",
                            fg=typer.colors.RED,
                        )
                        raise typer.Exit(code=1)
                featured_manifest[section] = [
                    mod_lookup[mod_id]
                    for mod_id in content["mods"]
                    if mod_id in mod_lookup
                ]
                featured_count += len(featured_manifest[section])

        if featured_count == 0:
            typer.secho(
                "No featured mods found, check the format of featured.toml",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

        with open("featured-mods.json", "w") as f:
            json.dump(featured_manifest, f, indent=4, sort_keys=True)
            f.write("\n")

        log.print(f"Wrote {featured_count} mods to featured-mods.json", style="green")

        with open("manifest.json", "w") as f:
            json.dump(
                mod_lookup,
                f,
                indent=4,
                sort_keys=True,
            )
            f.write("\n")
    else:
        if len(build_configs) == 1:
            json.dump(build_configs[0].model_dump(), sys.stdout)
        else:
            json.dump([item.model_dump() for item in build_configs], sys.stdout)


if __name__ == "__main__":
    app()
