"""Fixture contracts, dependency integrity and validator failure cases."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_data import (  # noqa: E402
    validate_architecture,
    validate_data,
    validate_demo_sprint,
    validate_test_catalog,
)
from app.contracts import Architecture, CatalogTest, DemoSprint  # noqa: E402


def read_fixture(name: str):
    return json.loads((REPO_ROOT / "data" / name).read_text(encoding="utf-8"))


@pytest.fixture
def architecture() -> Architecture:
    return Architecture.model_validate(read_fixture("architecture.json"), strict=True)


@pytest.fixture
def catalog() -> list[CatalogTest]:
    return [CatalogTest.model_validate(test, strict=True) for test in read_fixture("test_catalog.json")]


@pytest.fixture
def sprint() -> DemoSprint:
    return DemoSprint.model_validate(read_fixture("demo_sprint.json"), strict=True)


def test_repository_fixtures_pass_all_checks():
    summary = validate_data()
    assert summary.components == 21
    assert summary.tests == 60
    assert summary.stories == 6
    assert summary.deployment_groups == 8
    assert summary.edges > 0


@pytest.mark.parametrize("working_dir", [REPO_ROOT, REPO_ROOT / "backend"])
def test_validator_cli_works_from_root_and_backend(working_dir):
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "validate_data.py")],
        cwd=working_dir,
        env={**os.environ, "LLM_DISABLED": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "21 components" in result.stdout
    assert "60 tests" in result.stdout
    assert "6 stories" in result.stdout


def test_cli_reports_invalid_fixture_and_exits_nonzero(tmp_path):
    for filename in ("architecture.json", "test_catalog.json", "demo_sprint.json"):
        payload = read_fixture(filename)
        if filename == "architecture.json":
            payload["components"][0]["criticality"] = 11
        (tmp_path / filename).write_text(json.dumps(payload), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "validate_data.py"), "--data-dir", str(tmp_path)],
        env={**os.environ, "LLM_DISABLED": "1"},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 1
    assert "Data validation failed" in result.stderr
    assert "criticality" in result.stderr


def test_components_validate_against_contracts():
    payload = read_fixture("architecture.json")
    payload["components"][0]["data_classes"] = ["confidential"]
    with pytest.raises(ValidationError, match="data_classes"):
        Architecture.model_validate(payload, strict=True)


def test_unknown_dependency_is_rejected(architecture):
    architecture.components[0].downstream.append("missing-service")
    with pytest.raises(ValueError, match="unknown downstream IDs"):
        validate_architecture(architecture)


def test_links_must_be_exact_inverses(architecture):
    component = next(c for c in architecture.components if c.id == "api-gateway")
    component.upstream.remove("mobile-banking")
    with pytest.raises(ValueError, match="exact inverse"):
        validate_architecture(architecture)


def test_consistent_links_that_form_a_cycle_are_rejected(architecture):
    by_id = {component.id: component for component in architecture.components}
    by_id["customer-db"].downstream.append("authentication-service")
    by_id["authentication-service"].upstream.append("customer-db")
    with pytest.raises(ValueError, match="contains a cycle"):
        validate_architecture(architecture)


def test_duplicate_component_ids_are_rejected(architecture):
    architecture.components.append(architecture.components[0].model_copy(deep=True))
    with pytest.raises(ValueError, match="Duplicate component IDs"):
        validate_architecture(architecture)


def test_duplicate_api_ids_are_rejected(architecture):
    architecture.components[1].apis[0].id = architecture.components[0].apis[0].id
    with pytest.raises(ValueError, match="Duplicate API IDs"):
        validate_architecture(architecture)


def test_duplicate_links_are_rejected(architecture):
    architecture.components[0].downstream.append(architecture.components[0].downstream[0])
    with pytest.raises(ValueError, match="downstream links"):
        validate_architecture(architecture)


def test_gateway_apis_must_be_external(architecture):
    gateway = next(c for c in architecture.components if c.id == "api-gateway")
    gateway.apis[0].external = False
    with pytest.raises(ValueError, match="must be external"):
        validate_architecture(architecture)


def test_catalog_rejects_unknown_service(architecture, catalog):
    catalog[0].services.append("missing-service")
    with pytest.raises(ValueError, match="unknown service reference"):
        validate_test_catalog(catalog, architecture)


def test_catalog_rejects_unknown_api(architecture, catalog):
    catalog[0].apis.append("unknown.endpoint")
    with pytest.raises(ValueError, match="unknown API reference"):
        validate_test_catalog(catalog, architecture)


def test_catalog_api_owner_must_be_a_covered_service(architecture, catalog):
    catalog[0].apis = ["payment-service.create"]
    with pytest.raises(ValueError, match="outside services"):
        validate_test_catalog(catalog, architecture)


def test_every_component_needs_two_tests(architecture, catalog):
    catalog = [test for test in catalog if "notification-service" not in test.services]
    with pytest.raises(ValueError, match="at least two tests.*notification-service"):
        validate_test_catalog(catalog, architecture)


def test_catalog_must_cover_every_type(architecture, catalog):
    for test in catalog:
        if test.type == "security":
            test.type = "regression"
    with pytest.raises(ValueError, match="all five test types"):
        validate_test_catalog(catalog, architecture)


def test_duplicate_test_ids_are_rejected(architecture, catalog):
    catalog[1].id = catalog[0].id
    with pytest.raises(ValueError, match="Duplicate test IDs"):
        validate_test_catalog(catalog, architecture)


def test_catalog_duration_must_be_positive(architecture, catalog):
    catalog[0].duration_min = 0
    with pytest.raises(ValueError, match="duration must be positive"):
        validate_test_catalog(catalog, architecture)


def test_story_description_length_is_checked(sprint):
    sprint.stories[0].description = "Change the payment limit."
    with pytest.raises(ValueError, match="60-120 words"):
        validate_demo_sprint(sprint)


def test_story_acceptance_criteria_are_checked(sprint):
    sprint.stories[0].acceptance_criteria = ["Limit is applied."]
    with pytest.raises(ValueError, match="3-5 acceptance criteria"):
        validate_demo_sprint(sprint)


def test_duplicate_story_ids_are_rejected(sprint):
    sprint.stories[1].id = sprint.stories[0].id
    with pytest.raises(ValueError, match="Duplicate story IDs"):
        validate_demo_sprint(sprint)


def test_explicit_unknown_story_component_is_rejected(sprint):
    sprint.stories[0].description += " Retire imaginary-service."
    with pytest.raises(ValueError, match="unknown component IDs"):
        validate_demo_sprint(sprint)


def test_story_must_retain_intended_component_wording(sprint):
    story = next(story for story in sprint.stories if story.id == "ST-110")
    story.description = story.description.replace("risk engine", "policy evaluator")
    story.acceptance_criteria = [
        criterion.replace("risk-engine", "policy evaluator")
        for criterion in story.acceptance_criteria
    ]
    with pytest.raises(ValueError, match="missing intended component wording.*risk-engine"):
        validate_demo_sprint(sprint)


def test_footer_story_avoids_sensitive_change_keywords(sprint):
    story = next(story for story in sprint.stories if story.id == "ST-115")
    prose = " ".join([story.description, *story.acceptance_criteria]).lower()
    for keyword in ("schema", "authentication", "card", "payment", "personal data", "financial"):
        assert keyword not in prose
