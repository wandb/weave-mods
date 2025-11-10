#!/usr/bin/env python3
"""
Helper script to create a W&B artifact from /app/src directory.

Creates an artifact only if:
- User is logged into wandb
- WANDB_PROJECT environment variable is set
- /app/src/pyproject.toml exists (to derive artifact name)

Artifact naming: {entity}/{project}/{artifact_name}:latest
Artifact type: app
"""

import os
import sys
import tomllib
from pathlib import Path

import wandb
from wandb.apis import InternalApi, PublicApi

# ANSI color codes for output
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

# Files and directories to exclude from artifact
EXCLUDE_PATTERNS = [
    # Mod infrastructure files
    "healthcheck.py",
    "marimo-entrypoint.py",
    "dev-entrypoint.py",
    # Build artifacts
    "__marimo__",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".Python",
    # Dependencies
    ".venv",
    "venv",
    "env",
    "ENV",
    "sdk",  # Symlinked SDK directory
    "requirements.in",
    # W&B
    "wandb",
    # Version control
    ".git",
    ".gitignore",
    # IDEs
    ".vscode",
    ".idea",
    "*.swp",
    "*.swo",
    # OS
    ".DS_Store",
    "Thumbs.db",
    # Docker
    "Dockerfile",
    ".dockerignore",
    # Caches
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    # Distribution / packaging
    "build",
    "dist",
    "*.egg-info",
]


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
    """Check if user is logged into wandb using api_key."""
    try:
        return wandb.api.api_key is not None
    except Exception as e:
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


def should_exclude(path: Path, base_path: Path) -> bool:
    """
    Check if a file or directory should be excluded based on EXCLUDE_PATTERNS.

    Args:
        path: The path to check
        base_path: The base directory being uploaded

    Returns:
        True if the path should be excluded, False otherwise
    """
    relative_path = path.relative_to(base_path)
    path_str = str(relative_path)
    name = path.name

    for pattern in EXCLUDE_PATTERNS:
        # Direct name match
        if name == pattern:
            return True
        # Wildcard pattern match
        if "*" in pattern:
            import fnmatch

            if fnmatch.fnmatch(name, pattern):
                return True
            if fnmatch.fnmatch(path_str, pattern):
                return True
        # Path component match
        if pattern in path_str.split("/"):
            return True

    return False


def create_artifact(project: str, artifact_name: str) -> int:
    """
    Create artifact using wandb Python API.

    Args:
        project: The wandb project name
        artifact_name: The artifact name from pyproject.toml

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Parse the artifact path to get entity, project, artifact_name
        # Similar to CLI implementation
        public_api = PublicApi()
        full_name = f"{project}/{artifact_name}"
        entity, parsed_project, parsed_artifact_name = public_api._parse_artifact_path(
            full_name
        )

        # Use parsed project if available, otherwise use provided project
        if parsed_project is None:
            parsed_project = project

        # Set up internal API with entity and project
        api = InternalApi()
        if entity:
            api.set_setting("entity", entity)
        api.set_setting("project", parsed_project)

        # Create the artifact
        artifact = wandb.Artifact(
            name=parsed_artifact_name, type="app", description="Mod snapshot"
        )

        # Build the full artifact path for display
        artifact_path = f"{entity}/{parsed_project}/{parsed_artifact_name}:latest"
        log_info(f'Uploading directory /app/src to: "{artifact_path}" (app)')

        # Add directory with exclusions
        src_path = Path("/app/src")

        # Walk the directory and add files that aren't excluded
        for item in src_path.rglob("*"):
            if item.is_file() and not should_exclude(item, src_path):
                relative_path = item.relative_to(src_path)
                artifact.add_file(str(item), name=str(relative_path))
                log_info(f"  Adding: {relative_path}")

        # Initialize a run and log the artifact
        with wandb.init(
            entity=entity,
            project=parsed_project,
            config={"path": "/app/src"},
            job_type="snapshot",
        ) as run:
            run.log_artifact(artifact, aliases=["latest"])

        # Wait for artifact to finish uploading
        artifact.wait()

        log_info(f"Artifact uploaded successfully: {artifact.source_qualified_name}")
        log_info(
            f'Use this artifact in a run by adding:\n    artifact = run.use_artifact("{artifact.source_qualified_name}")'
        )

        return 0

    except Exception as e:
        log_error(f"Failed to create artifact: {e}")
        import traceback

        traceback.print_exc()
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
