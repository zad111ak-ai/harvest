"""Tests for Docker configuration of Harvest Agent."""

from __future__ import annotations

from pathlib import Path

import yaml

# Resolve the project root (one level up from tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read(filename: str) -> str:
    """Read a file from the project root and return its content."""
    path = PROJECT_ROOT / filename
    assert path.exists(), f"{filename} not found at {path}"
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDockerfileExists:
    """Ensure the Dockerfile is present in the project root."""

    def test_dockerfile_exists(self) -> None:
        assert (PROJECT_ROOT / "Dockerfile").is_file()

    def test_dockerfile_not_empty(self) -> None:
        content = _read("Dockerfile")
        assert len(content.strip()) > 0, "Dockerfile is empty"


class TestDockerfileMultiStage:
    """Verify the Dockerfile uses a proper multi-stage build."""

    def test_has_multiple_from_statements(self) -> None:
        """A multi-stage build must contain at least two FROM instructions."""
        content = _read("Dockerfile")
        from_count = sum(1 for line in content.splitlines() if line.strip().upper().startswith("FROM "))
        assert from_count >= 2, f"Expected at least 2 FROM statements for multi-stage build, found {from_count}"

    def test_has_dev_stage(self) -> None:
        content = _read("Dockerfile")
        assert "AS dev" in content, "Missing 'AS dev' stage in Dockerfile"

    def test_has_production_stage(self) -> None:
        content = _read("Dockerfile")
        assert "AS production" in content, "Missing 'AS production' stage in Dockerfile"

    def test_uses_python_312_slim(self) -> None:
        content = _read("Dockerfile")
        assert "python:3.12-slim" in content, "Dockerfile should use python:3.12-slim base"

    def test_has_healthcheck(self) -> None:
        content = _read("Dockerfile")
        assert "HEALTHCHECK" in content.upper(), "Dockerfile should contain a HEALTHCHECK instruction"


class TestDockerComposeExists:
    """Ensure docker-compose.yml is present and valid."""

    def test_compose_file_exists(self) -> None:
        assert (PROJECT_ROOT / "docker-compose.yml").is_file()

    def test_compose_valid_yaml(self) -> None:
        """The compose file must parse as valid YAML."""
        content = _read("docker-compose.yml")
        data = yaml.safe_load(content)
        assert isinstance(data, dict), "docker-compose.yml should parse to a dict"

    def test_compose_has_services(self) -> None:
        data = yaml.safe_load(_read("docker-compose.yml"))
        assert "services" in data, "docker-compose.yml must define 'services'"
        assert isinstance(data["services"], dict), "'services' must be a mapping"

    def test_compose_has_harvest_service(self) -> None:
        data = yaml.safe_load(_read("docker-compose.yml"))
        assert "harvest" in data["services"], "'harvest' service must be defined"

    def test_compose_has_redis_service(self) -> None:
        data = yaml.safe_load(_read("docker-compose.yml"))
        assert "redis" in data["services"], "'redis' service must be defined"

    def test_compose_has_volumes(self) -> None:
        data = yaml.safe_load(_read("docker-compose.yml"))
        assert "volumes" in data, "docker-compose.yml should define 'volumes'"

    def test_compose_harvest_service_has_healthcheck(self) -> None:
        data = yaml.safe_load(_read("docker-compose.yml"))
        harvest = data["services"]["harvest"]
        assert "healthcheck" in harvest, "harvest service should have a healthcheck"

    def test_compose_harvest_service_has_volumes(self) -> None:
        data = yaml.safe_load(_read("docker-compose.yml"))
        harvest = data["services"]["harvest"]
        assert "volumes" in harvest, "harvest service should mount volumes"

    def test_compose_harvest_uses_production_target(self) -> None:
        data = yaml.safe_load(_read("docker-compose.yml"))
        harvest = data["services"]["harvest"]
        build = harvest.get("build", {})
        assert build.get("target") == "production", "harvest service should build the 'production' stage"


class TestDockerignoreExists:
    """Ensure .dockerignore is present and excludes expected patterns."""

    def test_dockerignore_exists(self) -> None:
        assert (PROJECT_ROOT / ".dockerignore").is_file()

    def test_dockerignore_not_empty(self) -> None:
        content = _read(".dockerignore")
        assert len(content.strip()) > 0, ".dockerignore is empty"

    def test_excludes_git(self) -> None:
        content = _read(".dockerignore")
        assert ".git" in content, ".dockerignore should exclude .git"

    def test_excludes_tests(self) -> None:
        content = _read(".dockerignore")
        assert "tests/" in content, ".dockerignore should exclude tests/"

    def test_excludes_venv(self) -> None:
        content = _read(".dockerignore")
        assert "venv/" in content, ".dockerignore should exclude venv/"

    def test_excludes_pycache(self) -> None:
        content = _read(".dockerignore")
        assert "__pycache__" in content, ".dockerignore should exclude __pycache__"

    def test_excludes_pyc_files(self) -> None:
        content = _read(".dockerignore")
        assert "*.pyc" in content, ".dockerignore should exclude *.pyc"

    def test_excludes_hermes(self) -> None:
        content = _read(".dockerignore")
        assert ".hermes/" in content, ".dockerignore should exclude .hermes/"
