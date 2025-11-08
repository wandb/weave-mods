#!/usr/bin/env python3
"""
Helper script to create a W&B artifact from /app/src directory.

Creates an artifact only if:
- User is logged into wandb
- WANDB_PROJECT environment variable is set
- /app/src/pyproject.toml exists (to derive artifact name)

Artifact naming: {WANDB_PROJECT}/{project.name}:latest
Artifact type: app
"""

import os
import subprocess
import sys
import tomllib
from pathlib import Path

# ANSI color codes for output
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def log_error(msg: str) -> None:
    """Print error message to stderr."""
    print(f"{RED}ERROR: {msg}{RESET}", file=sys.stderr)


def log_info(msg: str) -> None:
    """Print info message to stdout."""
    print(f"{GREEN}INFO: {msg}{RESET}")


def log_warning(msg: str) -> None:
    """Print warning message to stdout."""
    print(f"{YELLOW}WARNING: {msg}{RESET}")


def check_wandb_login() -> bool:
    """Check if user is logged into wandb."""
    try:
        result = subprocess.run(
            ["wandb", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # wandb status returns 0 when logged in
        if result.returncode == 0 and "Logged in" in result.stdout:
            return True
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log_error(f"Failed to check wandb login status: {e}")
        return False


def get_wandb_project() -> str | None:
    """Get WANDB_PROJECT environment variable."""
    return os.environ.get("WANDB_PROJECT")


def get_artifact_name() -> str | None:
    """
    Parse /app/src/pyproject.toml to get project name.
    Falls back to directory name if project.name is not found.
    """
    pyproject_path = Path("/app/src/pyproject.toml")

    if not pyproject_path.exists():
        log_error(f"{pyproject_path} does not exist")
        return None

    try:
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)

        # Try to get project.name
        project_name = pyproject.get("project", {}).get("name")

        if project_name:
            return project_name
        else:
            # Fallback to directory name
            log_warning(
                "project.name not found in pyproject.toml, using directory name"
            )
            return Path("/app/src").name

    except Exception as e:
        log_error(f"Failed to parse {pyproject_path}: {e}")
        return None


def create_artifact(project: str, name: str) -> int:
    """
    Create artifact using wandb CLI.

    Returns:
        Exit code from wandb CLI (0 for success, non-zero for failure)
    """
    artifact_name = f"{project}/{name}:latest"

    log_info(f"Creating artifact: {artifact_name}")

    try:
        result = subprocess.run(
            [
                "wandb",
                "artifact",
                "put",
                "--name",
                artifact_name,
                "--type",
                "app",
                "/app/src",
            ],
            timeout=300,  # 5 minute timeout for large directories
        )

        if result.returncode == 0:
            log_info(f"Successfully created artifact: {artifact_name}")
        else:
            log_error(f"Failed to create artifact (exit code {result.returncode})")

        return result.returncode

    except subprocess.TimeoutExpired:
        log_error("Artifact creation timed out after 5 minutes")
        return 1
    except Exception as e:
        log_error(f"Unexpected error creating artifact: {e}")
        return 1


def main() -> int:
    """Main entry point."""
    log_info("Starting artifact creation process")

    # Check preconditions
    if not check_wandb_login():
        log_error("Not logged into wandb. Please run 'wandb login' first.")
        return 1

    wandb_project = get_wandb_project()
    if not wandb_project:
        log_error("WANDB_PROJECT environment variable is not set")
        return 1

    artifact_name = get_artifact_name()
    if not artifact_name:
        log_error("Could not determine artifact name from pyproject.toml")
        return 1

    # All preconditions met, create artifact
    return create_artifact(wandb_project, artifact_name)


if __name__ == "__main__":
    sys.exit(main())
