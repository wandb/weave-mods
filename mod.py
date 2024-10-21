#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "typer",
#     "toml",
# ]
# ///

import os
import sys
import typer
import toml
import subprocess
from pathlib import Path
app = typer.Typer()

@app.command()
def dev(directory: str = "."):
    """Start mod using docker in dev mode."""
    # Find pyproject.toml in the specified directory
    pyproject_path = os.path.join(directory, "pyproject.toml")
    if not os.path.exists(pyproject_path):
        typer.secho(f"Warning: pyproject.toml not found in {directory}", fg=typer.colors.YELLOW)
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
        typer.secho("Warning: [tool.weave.mod] section not found in pyproject.toml", fg=typer.colors.YELLOW)
        sys.exit(1)
    # Check flavor
    flavor = weave_config.get("flavor", "")
    if flavor not in ["streamlit", "fasthtml", "uvicorn", "custom"]:
        typer.secho("Flavor not one ofstreamlit, fasthtml, uvicorn, custom; nothing to do.", fg=typer.colors.YELLOW)
        sys.exit(1)
    port = weave_config.get("port", 8501)
    # Get secrets
    secrets = weave_config.get("secrets", [])
    # Build docker command
    docker_command = [
        "docker",
        "run",
        "--rm",
        "-t",
        "--name",
        os.path.basename(Path(directory).resolve()),
        "-p", f"{port}:{port}",
        "-v", f"{os.path.abspath(directory)}:/app/src",
        "--tmpfs", "/app/src/.venv:mode=0777",
    ]
    # Add -e secrets
    for secret in secrets:
        docker_command.extend(["-e", secret])
    docker_command.append("localhost:5001/spiderweb-streamlit")
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
        typer.secho(f"Failed to run 'uv add streamlit' in {directory}: {e}", fg=typer.colors.RED)
        sys.exit(1)
    os.unlink(os.path.join(directory, "hello.py"))
    with open(os.path.join(directory, "app.py"), "w") as f:
        f.write("""import streamlit as st

st.title("Welcome to Weave Mods!")
""")
    with open(os.path.join(directory, ".gitignore"), "w") as f:
        f.write("__pycache__\n.venv\n")
    with open(os.path.join(directory, "README.md"), "w") as f:
        f.write(f"# {os.path.basename(directory).upper()} mod\n\nAdd more description here...")
    # Modify pyproject.toml to add [tool.weave] section with flavor = "streamlit"
    pyproject_path = os.path.join(directory, "pyproject.toml")
    if not os.path.exists(pyproject_path):
        typer.secho(f"Error: pyproject.toml not found in {directory} after 'uv init'", fg=typer.colors.RED)
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
        typer.secho("Updated pyproject.toml with [tool.weave.mod] section", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Error writing to pyproject.toml: {e}", fg=typer.colors.RED)
        sys.exit(1)

if __name__ == "__main__":
    app()