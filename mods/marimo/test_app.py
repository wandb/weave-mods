"""Tests for marimo app and utilities.

Split into:
- Unit tests for utils.py functions
- Integration tests for marimo page rendering
"""

import os
from datetime import datetime
from unittest.mock import patch

import pytest

# ============================================================================
# Mock wandb API objects
# ============================================================================


class MockRun:
    """Mock wandb Run object."""

    def __init__(self, run_id, name="test-run", state="finished", tags=None):
        self.id = run_id
        self.name = name
        self.state = state
        self.tags = tags or []
        self.created_at = datetime.now()
        self.summary = {"loss": 0.5, "accuracy": 0.9}
        self.config = {"learning_rate": 0.001, "epochs": 10}

    def history(self, keys=None, pandas=False):
        import pandas as pd

        return pd.DataFrame({"step": [1, 2, 3], "loss": [0.6, 0.5, 0.4]})


class MockArtifact:
    """Mock wandb Artifact object."""

    def __init__(self, name, artifact_type="dataset", version="v0"):
        self.name = name
        self.type = artifact_type
        self.version = version
        self.aliases = []
        self.created_at = datetime.now()


class MockArtifactType:
    """Mock wandb ArtifactType object."""

    def __init__(self, type_name):
        self.type_name = type_name

    def collections(self):
        return [MockArtifactCollection()]


class MockArtifactCollection:
    """Mock wandb ArtifactCollection object."""

    def artifacts(self):
        return [
            MockArtifact("artifact-1", "dataset", "v0"),
            MockArtifact("artifact-2", "model", "v1"),
        ]


class MockWandbApi:
    """Mock wandb API object."""

    def __init__(self):
        self.runs_data = [
            MockRun("run-1", "test-run-1", "finished", ["tag1", "tag2"]),
            MockRun("run-2", "test-run-2", "running", ["tag2"]),
        ]
        self.artifacts_data = [
            MockArtifact("artifact-1", "dataset", "v0"),
            MockArtifact("artifact-2", "model", "v1"),
        ]

    def runs(self, path=None, **kwargs):
        return self.runs_data

    def run(self, path):
        # Extract run_id from path like "entity/project/run_id"
        run_id = path.split("/")[-1] if "/" in path else path
        for run in self.runs_data:
            if run.id == run_id:
                return run
        raise Exception(f"Run {run_id} not found")

    def artifacts(self, project=None, entity=None, type=None, per_page=200):
        return self.artifacts_data

    def artifact_types(self, project=None):
        return [MockArtifactType("dataset"), MockArtifactType("model")]

    def artifact_type(self, type_name=None, project=None):
        return MockArtifactType(type_name or "dataset")


@pytest.fixture
def mock_wandb_api():
    """Create a mock wandb API object."""
    return MockWandbApi()


@pytest.fixture
def mock_env_vars():
    """Set up mock environment variables."""
    with patch.dict(
        os.environ,
        {
            "WANDB_PROJECT": "test-entity/test-project",
            "WANDB_ENTITY": "test-entity",
        },
    ):
        yield


# ============================================================================
# Unit Tests for utils.py
# ============================================================================


def test_resolve_entity_project_with_slash():
    """Test that resolve_entity_project parses entity/project format."""
    from utils import resolve_entity_project

    with patch.dict(os.environ, {"WANDB_PROJECT": "my-entity/my-project"}):
        entity, project = resolve_entity_project()
        assert entity == "my-entity"
        assert project == "my-project"
