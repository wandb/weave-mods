#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "typer",
#     "toml",
# ]
# ///

import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import toml
import typer

app = typer.Typer()


@app.command()
def dev(directory: Annotated[str, typer.Argument()] = "."):
    """Start mod using docker in dev mode."""
    if directory.startswith("pkg:"):
        purl = directory
        # TODO: Parse PURL and load config
        weave_config = {}
    else:
        # Find pyproject.toml in the specified directory
        pyproject_path = os.path.join(directory, "pyproject.toml")
        if not os.path.exists(pyproject_path):
            typer.secho(
                f"Warning: pyproject.toml not found in {directory}",
                fg=typer.colors.YELLOW,
            )
            sys.exit(1)
        # Parse pyproject.toml
        try:
            with open(pyproject_path, "r") as f:
                pyproject = toml.load(f)
        except Exception as e:
            typer.secho(f"Error parsing pyproject.toml: {e}", fg=typer.colors.RED)
            sys.exit(1)
        # Get [tool.weave] section
        weave_config = pyproject.get("tool", {}).get("weave", {}).get("mod", {})
        if not weave_config:
            typer.secho(
                "Warning: [tool.weave.mod] section not found in pyproject.toml",
                fg=typer.colors.YELLOW,
            )
            sys.exit(1)
        # Check flavor
        flavor = weave_config.get("flavor", "")
        if flavor not in ["streamlit", "fasthtml", "uvicorn", "custom"]:
            typer.secho(
                "Flavor not one of streamlit, fasthtml, uvicorn, custom; nothing to do.",
                fg=typer.colors.YELLOW,
            )
            sys.exit(1)
        purl = "pkg:mod/" + directory.replace("mods/", "").replace("/", "%2F")
    port = weave_config.get("port", 6637)
    # Get secrets
    secrets = weave_config.get("secrets", ["OPENAI_API_KEY"])
    if os.getenv("WANDB_BASE_URL") is None:
        os.environ["WANDB_BASE_URL"] = "http://app.k8s.wandb.dev"
    if os.getenv("WANDB_API_KEY") is None:
        if os.path.exists(os.path.expanduser("~/.netrc")):
            found_machine = False
            with open(os.path.expanduser("~/.netrc"), "r") as f:
                for line in f.readlines():
                    if "machine api.k8s.wandb.dev" in line:
                        found_machine = True
                    if found_machine and "password" in line:
                        os.environ["WANDB_API_KEY"] = line.split(" ")[-1].strip()
                        break
    if os.getenv("WANDB_API_KEY") is None:
        typer.secho(
            "Warning: WANDB_API_KEY not found; you probably want to set this.",
            fg=typer.colors.RED,
        )
    typer.secho(
        f"Setting WANDB_BASE_URL={os.getenv('WANDB_BASE_URL')}", fg=typer.colors.BLUE
    )
    # Build docker command
    docker_command = [
        "docker",
        "run",
        "--rm",
        "--name",
        os.path.basename(Path(directory).resolve()),
        "--add-host=app.k8s.wandb.dev:host-gateway",
        "-e",
        f"PURL={purl}",
        "-e",
        "WANDB_BASE_URL",
        "-e",
        "WANDB_API_KEY",
        "-e",
        f"WANDB_PROJECT={os.getenv('WANDB_PROJECT', 'mods')}",
        "-p",
        f"{port}:{port}",
        "-v",
        f"{os.path.abspath(os.path.dirname(__file__))}/mods:/mods",
        "-v",
        "weave-mods-cache:/app/.cache",
    ]
    # "--tmpfs", "/app/src/.venv:mode=0777",
    # Add -e secrets
    for secret in secrets:
        docker_command.extend(["-e", secret])
    for env in weave_config.get("env", {}).items():
        docker_command.extend(["-e", f"{env[0]}={env[1]}"])
    docker_command.append("localhost:5001/spiderweb-mods")
    # Display command
    typer.secho("Running docker command:", fg=typer.colors.GREEN)
    typer.secho(" ".join(docker_command), fg=typer.colors.BLUE)
    # Run the command
    try:
        subprocess.run(docker_command, check=True)
    except subprocess.CalledProcessError as e:
        typer.secho(f"Docker command failed: {e}", fg=typer.colors.RED)
        sys.exit(1)


@app.command()
def create(directory: str):
    """Create a new mod."""
    # Check if directory exists, if not, create it
    if not os.path.exists(directory):
        os.makedirs(directory)
        typer.secho(f"Created directory: {directory}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"Directory already exists: {directory}", fg=typer.colors.YELLOW)
    # Run 'uv init' in the directory
    try:
        subprocess.run(["uv", "init"], cwd=directory, check=True)
        typer.secho(f"Ran 'uv init' in {directory}", fg=typer.colors.GREEN)
    except subprocess.CalledProcessError as e:
        typer.secho(f"Failed to run 'uv init' in {directory}: {e}", fg=typer.colors.RED)
        sys.exit(1)
    try:
        subprocess.run(["uv", "add", "streamlit"], cwd=directory, check=True)
    except subprocess.CalledProcessError as e:
        typer.secho(
            f"Failed to run 'uv add streamlit' in {directory}: {e}", fg=typer.colors.RED
        )
        sys.exit(1)
    os.unlink(os.path.join(directory, "hello.py"))
    with open(os.path.join(directory, "app.py"), "w") as f:
        f.write("""import streamlit as st

st.title("Welcome to Weave Mods!")
""")
    with open(os.path.join(directory, ".gitignore"), "w") as f:
        f.write("__pycache__\n.venv\n")
    with open(os.path.join(directory, "README.md"), "w") as f:
        f.write(
            f"# {os.path.basename(directory).upper()} mod\n\nAdd more description here..."
        )
    # Modify pyproject.toml to add [tool.weave] section with flavor = "streamlit"
    pyproject_path = os.path.join(directory, "pyproject.toml")
    if not os.path.exists(pyproject_path):
        typer.secho(
            f"Error: pyproject.toml not found in {directory} after 'uv init'",
            fg=typer.colors.RED,
        )
        sys.exit(1)
    try:
        with open(pyproject_path, "r") as f:
            pyproject = toml.load(f)
    except Exception as e:
        typer.secho(f"Error reading pyproject.toml: {e}", fg=typer.colors.RED)
        sys.exit(1)
    # Add [tool.weave.mod] section
    tool = pyproject.get("tool", {})
    weave_config = tool.get("weave", {"mod": {}})
    weave_config["mod"]["flavor"] = "streamlit"
    # Update the nested dictionaries
    tool["weave"] = weave_config
    pyproject["tool"] = tool
    # Write back to pyproject.toml
    try:
        with open(pyproject_path, "w") as f:
            toml.dump(pyproject, f)
        typer.secho(
            "Updated pyproject.toml with [tool.weave.mod] section",
            fg=typer.colors.GREEN,
        )
    except Exception as e:
        typer.secho(f"Error writing to pyproject.toml: {e}", fg=typer.colors.RED)
        sys.exit(1)


if __name__ == "__main__":
    app()
