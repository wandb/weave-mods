#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "typer",
#     "toml",
#     "requests",
# "pydantic",
# ]
# ///

import json
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from enum import Enum
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import toml
import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from build import JS_PACKAGE_MANAGER

app = typer.Typer(no_args_is_help=True)


def ensure_dev():
    if len(sys.argv) > 1:
        if os.path.exists(sys.argv[1]) or sys.argv[1].startswith("pkg:"):
            return sys.argv.insert(1, "dev")


class VersionPart(str, Enum):
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


def host_and_key() -> tuple[str, str | None]:
    """Get host and key from the .netrc file and settings file."""
    # Host from config
    settings_path = os.path.expanduser("~/.config/wandb/settings")
    host = "https://api.wandb.ai"
    if os.path.exists(settings_path):
        with open(settings_path, "r") as f:
            for line in f.readlines():
                if line.startswith("base_url"):
                    host = line.split("=")[-1].strip()

    # Key from config
    netrc_path = os.path.expanduser("~/.netrc")
    machine_name = urlparse(host).hostname
    key = None
    if os.path.exists(netrc_path):
        found_machine = False
        with open(netrc_path, "r") as f:
            for line in f.readlines():
                if f"machine {machine_name}" in line:
                    found_machine = True
                if found_machine and "password" in line:
                    key = line.split()[-1].strip()
                    break

    return host, key


def print_setup_info(console, host: str, key: str):
    # Build your auth status string with color markup
    auth_status = (
        "[green]✅ logged in[/green]"
        if key
        else "[red]❌ not logged in[/red] (run `wandb login` to fix)"
    )

    panel_content = f"""
[bold underline]System Configuration[/bold underline]
  Weave Server: [yellow]{host}[/yellow] - {auth_status}

[bold underline]Next Steps[/bold underline]
 1) [bold magenta]./dev.py mods/demo[/bold magenta]
    to start the dev server for an existing mod

 2) [bold magenta]./dev.py create mods/my-rad-mod[/bold magenta]
    to create your own rad mod 😎
"""
    body = Text.from_markup(panel_content)

    # Wrap everything in a Panel
    panel = Panel(
        body,
        title="⚡ Weave Mods Setup Complete ⚡",
        title_align="left",  # Align the panel title to the left
        border_style="green",
        expand=True,  # Let the panel grow to fit content
    )

    console.print(panel)


@app.command()
def setup():
    """Setup your system for developing mods."""
    console = Console(stderr=True)
    console.print("Syncing SDK...", style="blue")
    subprocess.run(
        ["uv", "sync", "--frozen", "--dev"],
        cwd=os.path.join(Path(__file__).parent, "sdk"),
        check=True,
    )
    repo_venv = os.path.join(Path(__file__).parent, ".venv")
    sdk_venv = os.path.join(Path(__file__).parent, "sdk", ".venv")
    if not os.path.exists(repo_venv):
        os.symlink(sdk_venv, repo_venv, target_is_directory=True)
    console.print("Installing pre-commit hooks", style="blue")
    subprocess.run(
        ["uv", "run", "pre-commit", "install"],
        check=True,
    )
    console.print("Pulling latest dev image", style="blue")
    subprocess.run(
        ["docker", "pull", "ghcr.io/wandb/weave-mods/dev"],
        check=True,
    )
    host, key = host_and_key()
    print_setup_info(console, host, key)


@app.command()
def bump(
    directory: Annotated[str, typer.Argument()] = ".",
    part: Annotated[
        VersionPart, typer.Option(help="Version part to bump")
    ] = VersionPart.MINOR,
    no_upgrade: Annotated[
        bool, typer.Option(help="Skip running uv lock --upgrade")
    ] = False,
):
    """Bump the version in pyproject.toml and optionally upgrade dependencies."""
    # Find and parse pyproject.toml
    pyproject_path = os.path.join(directory, "pyproject.toml")
    if not os.path.exists(pyproject_path):
        typer.secho(
            f"Error: pyproject.toml not found in {directory}",
            fg=typer.colors.RED,
        )
        sys.exit(1)

    try:
        with open(pyproject_path, "r") as f:
            pyproject = toml.load(f)
    except Exception as e:
        typer.secho(f"Error parsing pyproject.toml: {e}", fg=typer.colors.RED)
        sys.exit(1)

    # Get current version
    current_version = pyproject.get("project", {}).get("version")
    if not current_version:
        typer.secho(
            "Error: No version found in pyproject.toml [project] section",
            fg=typer.colors.RED,
        )
        sys.exit(1)

    # Parse version
    try:
        major, minor, patch = map(int, current_version.split("."))
    except ValueError:
        typer.secho(
            f"Error: Invalid version format {current_version}. Expected x.y.z",
            fg=typer.colors.RED,
        )
        sys.exit(1)

    # Bump version
    if part == VersionPart.MAJOR:
        major += 1
        minor = 0
        patch = 0
    elif part == VersionPart.MINOR:
        minor += 1
        patch = 0
    else:  # PATCH
        patch += 1

    new_version = f"{major}.{minor}.{patch}"
    pyproject["project"]["version"] = new_version

    # Write updated pyproject.toml
    try:
        with open(pyproject_path, "w") as f:
            toml.dump(pyproject, f)
        typer.secho(
            f"Bumped version from {current_version} to {new_version}",
            fg=typer.colors.GREEN,
        )
    except Exception as e:
        typer.secho(f"Error writing to pyproject.toml: {e}", fg=typer.colors.RED)
        sys.exit(1)

    # Run uv lock --upgrade if not disabled
    if not no_upgrade:
        try:
            subprocess.run(["uv", "lock", "--upgrade"], cwd=directory, check=True)
            typer.secho("Successfully ran 'uv lock --upgrade'", fg=typer.colors.GREEN)
        except subprocess.CalledProcessError as e:
            typer.secho(f"Error running 'uv lock --upgrade': {e}", fg=typer.colors.RED)
            sys.exit(1)


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
        js_path = os.path.join(directory, "package.json")
        if not os.path.exists(pyproject_path) and not os.path.exists(js_path):
            typer.secho(
                f"Warning: pyproject.toml or package.json not found in {directory}",
                fg=typer.colors.YELLOW,
            )
            sys.exit(1)
        try:
            if os.path.exists(pyproject_path):
                subprocess.run(["uv", "sync"], cwd=directory, check=True)
            else:
                deno_server = Path(__file__).parent / "mods" / "deno_server.ts"
                shutil.copy(deno_server, os.path.join(directory, "deno_server.ts"))
                subprocess.run(
                    [JS_PACKAGE_MANAGER, "install"], cwd=directory, check=True
                )
        except subprocess.CalledProcessError as e:
            typer.secho(f"Error installing dependencies: {e}", fg=typer.colors.RED)
            sys.exit(1)
        # Parse pyproject.toml
        try:
            if os.path.exists(pyproject_path):
                with open(pyproject_path, "r") as f:
                    pyproject = toml.load(f)
                weave_config = pyproject.get("tool", {}).get("weave", {}).get("mod", {})
            else:
                with open(js_path, "r") as f:
                    package = json.load(f)
                weave_config = package.get("weave", {}).get("mod", {})
        except Exception as e:
            typer.secho(f"Error parsing pyproject.toml: {e}", fg=typer.colors.RED)
            sys.exit(1)
        # Get [tool.weave] section
        if not weave_config:
            typer.secho(
                "Warning: [weave.mod] section not found in pyproject.toml or package.json",
                fg=typer.colors.YELLOW,
            )
            sys.exit(1)
        # Check flavor
        flavor = weave_config.get("flavor", "")
        if flavor not in ["streamlit", "fasthtml", "uvicorn", "spa", "custom"]:
            typer.secho(
                "Flavor not one of streamlit, fasthtml, uvicorn, spa, custom; nothing to do.",
                fg=typer.colors.YELLOW,
            )
            sys.exit(1)
        purl = "pkg:mod/" + directory.replace("mods/", "").replace("/", "%2F")
    port = weave_config.get("port", 6637)
    # Get secrets
    secrets = weave_config.get("secrets", ["OPENAI_API_KEY"])
    host, key = host_and_key()
    if os.getenv("WANDB_API_KEY") is None:
        if key is not None:
            os.environ["WANDB_API_KEY"] = key
        else:
            typer.secho(
                "Warning: WANDB_API_KEY not found; you probably want to set this.",
                fg=typer.colors.RED,
            )
    if os.getenv("WANDB_BASE_URL") is None:
        os.environ["WANDB_BASE_URL"] = host
    typer.secho(
        f"Using server: {os.environ['WANDB_BASE_URL']}",
        fg=typer.colors.BLUE,
    )
    if os.getenv("WANDB_PROJECT") is None:
        os.environ["WANDB_PROJECT"] = typer.prompt("WANDB_PROJECT")
    # Build docker command
    container_name = os.path.basename(Path(directory).resolve())
    docker_command = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "--add-host=app.k8s.wandb.dev:host-gateway",
        "-e",
        f"PURL={purl}",
        "-e",
        "WANDB_BASE_URL",
        "-e",
        "WANDB_API_KEY",
        "-e",
        "WANDB_PROJECT",
        "-p",
        f"{port}:{port}",
        "-v",
        f"{os.path.abspath(os.path.dirname(__file__))}/mods:/mods",
        "-v",
        f"{os.path.abspath(os.path.dirname(__file__))}/sdk:/sdk",
        "-v",
        "weave-mods-cache:/app/.cache",
    ]
    # "--tmpfs", "/app/src/.venv:mode=0777",
    # Add -e secrets
    for secret in secrets:
        docker_command.extend(["-e", secret])
    for env in weave_config.get("env", {}).items():
        docker_command.extend(["-e", f"{env[0]}={env[1]}"])
    docker_command.append("ghcr.io/wandb/weave-mods/dev")
    # Display command
    typer.secho("Running docker command:", fg=typer.colors.GREEN)
    typer.secho(" ".join(docker_command), fg=typer.colors.BLUE)
    # Run the command and open the browser on success
    process = subprocess.Popen(docker_command)
    try:
        typer.secho("Waiting for container to be healthy", fg=typer.colors.YELLOW)
        for _ in range(60):
            health_check = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.Health.Status}}",
                    container_name,
                ],
                capture_output=True,
                text=True,
            )
            if health_check.stdout.strip() == "healthy":
                typer.secho("Container is healthy", fg=typer.colors.GREEN)
                break
            if health_check.stdout.strip() == "unhealthy":
                typer.secho(
                    f"Container is unhealthy: {health_check.stdout.strip()}",
                    fg=typer.colors.RED,
                )
                sys.exit(1)
            else:
                print(".", end="", flush=True)
            time.sleep(1)
        if process.poll() is None:
            webbrowser.open(f"http://localhost:{port}")
    except subprocess.CalledProcessError as e:
        typer.secho(f"Docker command failed: {e}", fg=typer.colors.RED)
    finally:
        exit_code = 1
        try:
            exit_code = process.wait()
        except KeyboardInterrupt:
            typer.secho(
                "\nReceived interrupt signal, stopping container...",
                fg=typer.colors.YELLOW,
            )
            process.terminate()
            subprocess.run(["docker", "stop", container_name], check=False)
        if exit_code != 0:
            typer.secho(
                f"Docker process exited with code {exit_code}", fg=typer.colors.RED
            )
        sys.exit(exit_code)


@app.command()
def create(directory: Annotated[str, typer.Argument()] = "."):
    """Create a new mod."""
    # Let's normalize mod names on dashes
    directory = directory.replace("_", "-")
    if "mods/" not in directory:
        directory = os.path.join("mods", directory)
    # Check if directory exists, if not, create it
    if not os.path.exists(directory):
        os.makedirs(directory)
        typer.secho(f"Created directory: {directory}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"Directory already exists: {directory}", fg=typer.colors.YELLOW)
    # Setup a streamlit mod by default, TODO: extend this to other flavors
    try:
        subprocess.run(["uv", "init"], cwd=directory, check=True)
        typer.secho(f"Ran 'uv init' in {directory}", fg=typer.colors.GREEN)
    except subprocess.CalledProcessError as e:
        typer.secho(f"Failed to run 'uv init' in {directory}: {e}", fg=typer.colors.RED)
        sys.exit(1)
    try:
        subprocess.run(["uv", "add", "streamlit"], cwd=directory, check=True)
        # add sdk as a dev editable dependency to make dev easier for now
        subprocess.run(
            ["uv", "add", "--dev", "--editable", "../../sdk/"],
            cwd=directory,
            check=True,
        )
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
    # Configure vscode to know about our new virtual environment
    os.makedirs(os.path.join(directory, ".vscode"))
    with open(os.path.join(directory, ".vscode", "settings.json"), "w") as f:
        f.write('{"python.defaultInterpreterPath": ".venv/bin/python"}')
    workspace_path = os.path.join(
        Path(__file__).parent, ".vscode", "weave-mods.code-workspace"
    )
    with open(workspace_path, "r") as f:
        workspace = json.load(f)
    workspace["folders"].append({"path": os.path.join("..", directory)})
    with open(workspace_path, "w") as f:
        json.dump(workspace, f, indent=4)
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
    description = typer.prompt("Enter a brief description of the mod")
    pyproject["project"]["description"] = description
    with open(os.path.join(directory, "README.md"), "w") as f:
        f.write(f"# {os.path.basename(directory).capitalize()} mod\n\n{description}")
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
    ensure_dev()
    app()
