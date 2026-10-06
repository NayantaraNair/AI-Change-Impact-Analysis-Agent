"""Compliance rules and prose isolation; all graphs use the dependency engine."""

import json

import pytest
from pydantic import ValidationError

from app import llm
from app.agents import compliance
from app.architecture import get_architecture
from app.contracts import Architecture, Component, RequirementFacts
from app.engine.dependency import build_impact_graph


def facts(**overrides):
    values = dict(
        business_summary="Update a banking capability",
        technical_summary="Update the affected services",
        business_domain="banking",
        affected_capabilities=[],
        affected_services=[],
        change_type="enhancement",
        touches_customer_data=False,
        touches_card_data=False,
        touches_financial_data=False,
        changes_auth_flow=False,
        changes_external_api_contract=False,
        changes_db_schema=False,
        ambiguity="low",
        engineering_scope="Service implementation",
        source="test-fixture",
    )
    values.update(overrides)
    return RequirementFacts(**values)


def component(node_id, *, criticality=5, data_classes=(), kind="core", downstream=()):
    return Component(
        id=node_id,
        name=node_id,
        type=kind,
        description="Test component",
        owner_team="Test team",
        owner_contact="test@bank.example",
        criticality=criticality,
        data_classes=list(data_classes),
        downstream=list(downstream),
        deployment_group=f"deploy-{node_id}",
        sla_tier="tier2",
    )


async def assess(requirement, arch, *, max_hops=3):
    graph = build_impact_graph(requirement.affected_services, arch, max_hops=max_hops)
    return await compliance.assess_compliance(requirement, graph, arch)


def frameworks(report):
    return {assessment.framework: assessment for assessment in report.frameworks}


@pytest.fixture(autouse=True)
def no_provider_calls(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise llm.NoLLM("Test fallback")

    monkeypatch.setattr(llm, "complete_structured", unavailable)


@pytest.mark.parametrize("card_node,card_fact", [(True, False), (False, True), (True, True)])
async def test_card_data_always_makes_pci_applicable(card_node, card_fact):
    arch = Architecture(
        components=[component("changed", data_classes=["card"] if card_node else [])]
    )
    report, provider = await assess(
        facts(affected_services=["changed"], touches_card_data=card_fact), arch
    )
    pci = frameworks(report)["PCI DSS"]
    assert pci.applicable
    assert pci.score == (65 if card_node else 75)
    assert pci.risk_level == "medium"
    assert provider == "template-fallback"
    assert all(finding.node_ids == ["changed"] for finding in pci.findings)


async def test_repository_architecture_with_real_dependency_graph():
    arch = get_architecture()
    assert any(component.id == "payment-service" for component in arch.components)
    requirement = facts(affected_services=["payment-service"], touches_financial_data=True)
    report, _ = await assess(requirement, arch)
    sox = frameworks(report)["SOX"]
    assert sox.applicable
    assert sox.score is not None and sox.score <= 85
    impacted = set(build_impact_graph(requirement.affected_services, arch).impacted_services)
    assert all(set(finding.node_ids) <= impacted for finding in sox.findings)


async def test_st115_has_no_high_risk_framework():
    # Mirrors the ST-115 document/report change in test_scoring. The worktree
    # currently lacks data/demo_sprint.json and its full architecture catalog.
    arch = Architecture(
        components=[
            component("document-service", criticality=4, downstream=["reporting-service"]),
            component("reporting-service", criticality=5, downstream=["reporting-db", "audit-db"]),
            component("reporting-db", criticality=6, data_classes=["financial"], kind="database"),
            component("audit-db", criticality=7, data_classes=["audit"], kind="database"),
        ]
    )
    report, _ = await assess(
        facts(affected_services=["document-service", "reporting-service"]), arch
    )
    assert all(assessment.risk_level != "high" for assessment in report.frameworks)
    sox = frameworks(report)["SOX"]
    assert sox.score == 85  # 100 - 5 (nearby financial) - 10 (audit database)
    assert sox.risk_level == "low"
    assert sox.findings[1].text == (
        "Deterministic control exposure: financial data impacted through dependencies (-5); "
        "audit database impacted (-10)."
    )
    assert report.overall_score == 85


async def test_no_applicable_framework_has_fixed_order_and_empty_details(monkeypatch):
    async def unexpected_call(*args, **kwargs):
        pytest.fail("No LLM call is needed when no framework applies")

    monkeypatch.setattr(llm, "complete_structured", unexpected_call)
    arch = Architecture(
        components=[
            component("changed"),
            component(
                "unrelated", criticality=10, data_classes=["pii", "card", "financial", "audit"]
            ),
        ]
    )
    report, provider = await assess(
        facts(
            affected_services=["changed"],
            changes_external_api_contract=True,
            changes_db_schema=True,
        ),
        arch,
    )
    assert [assessment.framework for assessment in report.frameworks] == list(
        compliance.FRAMEWORK_ORDER
    )
    assert report.overall_score == 100
    assert "No compliance framework applies" in report.summary
    assert provider == "template-fallback"
    for assessment in report.frameworks:
        assert not assessment.applicable
        assert assessment.reason
        assert assessment.risk_level is None
        assert assessment.score is None
        assert assessment.findings == []
        assert assessment.recommendations == []


@pytest.mark.parametrize(
    "flag,name,score",
    [
        ("touches_customer_data", "GDPR", 85),
        ("touches_card_data", "PCI DSS", 75),
        ("touches_financial_data", "SOX", 85),
        ("changes_auth_flow", "Internal Governance", 85),
    ],
)
async def test_fact_triggers_apply_even_without_sensitive_catalog_metadata(flag, name, score):
    arch = Architecture(components=[component("changed")])
    report, _ = await assess(facts(affected_services=["changed"], **{flag: True}), arch)
    assessment = frameworks(report)[name]
    assert assessment.applicable and assessment.score == score
    assert all(finding.node_ids == ["changed"] for finding in assessment.findings)


async def test_fact_only_change_with_no_known_services_still_applies():
    report, _ = await assess(
        facts(touches_card_data=True, affected_services=["unknown"]), Architecture(components=[])
    )
    pci = frameworks(report)["PCI DSS"]
    assert pci.applicable and pci.score == 75
    assert all(finding.node_ids == [] for finding in pci.findings)


@pytest.mark.parametrize("direct_pii,score", [(True, 45), (False, 55)])
async def test_gdpr_direct_and_indirect_conditions_are_charged_once(direct_pii, score):
    arch = Architecture(
        components=[
            component("customer", data_classes=["pii"] if direct_pii else [],
                      downstream=["customer-db", "profile-db"]),
            component("customer-db", data_classes=["pii"], kind="database"),
            component("profile-db", data_classes=["pii"], kind="database"),
        ]
    )
    report, _ = await assess(
        facts(
            affected_services=["customer"],
            touches_customer_data=True,
            changes_db_schema=True,
            changes_external_api_contract=True,
        ),
        arch,
    )
    gdpr = frameworks(report)["GDPR"]
    # Charge either direct PII (20) or indirect PII (10), plus 15 + 10 + 10.
    assert gdpr.score == score
    assert gdpr.risk_level == "high"
    assert report.overall_score == score
    pii_deduction = (
        "PII impacted directly (-20)" if direct_pii
        else "PII impacted through dependencies (-10)"
    )
    assert gdpr.findings[1].text == (
        f"Deterministic control exposure: {pii_deduction}; customer data touched (-15); "
        "database schema changes (-10); external API contract changes (-10)."
    )
    assert set(gdpr.findings[1].node_ids) == {"customer", "customer-db", "profile-db"}


async def test_pci_all_deductions_and_no_double_charge_for_card_flag():
    arch = Architecture(
        components=[
            component("card-service", data_classes=["card"], downstream=["card-db"]),
            component("card-db", data_classes=["card"], kind="database"),
        ]
    )
    report, _ = await assess(
        facts(
            affected_services=["card-service"],
            touches_card_data=True,
            changes_external_api_contract=True,
            changes_auth_flow=True,
        ),
        arch,
    )
    pci = frameworks(report)["PCI DSS"]
    assert pci.score == 40  # 100 - 25 - 15 - 10 - 10
    assert pci.risk_level == "high"
    assert report.overall_score == 40


async def test_sox_all_deductions_and_business_rule_on_payment_path():
    arch = Architecture(
        components=[
            component("payment-service", data_classes=["financial"], downstream=["audit-db"]),
            component("audit-db", data_classes=["audit"], kind="database"),
        ]
    )
    requirement = facts(
        affected_services=["payment-service"],
        touches_financial_data=True,
        changes_db_schema=True,
        change_type="business_rule_change",
    )
    report, _ = await assess(requirement, arch)
    sox = frameworks(report)["SOX"]
    assert sox.score == 55  # 100 - 15 - 10 - 10 - 10
    assert sox.risk_level == "high"
    assert "payment-service" in sox.findings[1].node_ids
    without_rule, _ = await assess(
        requirement.model_copy(update={"change_type": "enhancement"}), arch
    )
    assert frameworks(without_rule)["SOX"].score == 65


@pytest.mark.parametrize("kind,expected_score", [("core", 100), ("database", 90)])
async def test_audit_alone_applies_but_deduction_requires_database(kind, expected_score):
    arch = Architecture(components=[component("audit", data_classes=["audit"], kind=kind)])
    report, _ = await assess(facts(affected_services=["audit"]), arch)
    assert frameworks(report)["SOX"].applicable
    assert frameworks(report)["SOX"].score == expected_score


async def test_financial_business_rule_outside_payment_path_has_no_payment_deduction():
    arch = Architecture(components=[component("reporting", data_classes=["financial"])])
    report, _ = await assess(
        facts(affected_services=["reporting"], change_type="business_rule_change"), arch
    )
    assert frameworks(report)["SOX"].score == 85


@pytest.mark.parametrize(
    "criticality,applicable,score",
    [(7, False, None), (8, True, 100), (9, True, 85), (10, True, 85)],
)
async def test_governance_direct_criticality_thresholds(criticality, applicable, score):
    arch = Architecture(components=[component("changed", criticality=criticality)])
    report, _ = await assess(facts(affected_services=["changed"]), arch)
    governance = frameworks(report)["Internal Governance"]
    assert governance.applicable is applicable
    assert governance.score == score


async def test_governance_critical_deductions_are_capped_and_indirect_nodes_excluded():
    arch = Architecture(
        components=[
            component("one", criticality=9, downstream=["indirect"]),
            component("two", criticality=10),
            component("three", criticality=9),
            component("indirect", criticality=10),
        ]
    )
    report, _ = await assess(
        facts(
            affected_services=["one", "two", "three"],
            changes_auth_flow=True,
            changes_external_api_contract=True,
        ),
        arch,
    )
    governance = frameworks(report)["Internal Governance"]
    assert governance.score == 45  # 100 - cap(3 * 15, 30) - 15 - 10
    assert governance.risk_level == "high"
    assert "indirect" not in governance.findings[1].node_ids


async def test_indirect_critical_node_does_not_trigger_governance():
    arch = Architecture(
        components=[
            component("changed", downstream=["critical"]),
            component("critical", criticality=10),
        ]
    )
    report, _ = await assess(facts(affected_services=["changed"]), arch)
    assert not frameworks(report)["Internal Governance"].applicable


@pytest.mark.parametrize(
    "score,level",
    [(0, "high"), (59, "high"), (60, "medium"), (79, "medium"), (80, "low"), (100, "low")],
)
async def test_risk_level_boundaries(monkeypatch, score, level):
    monkeypatch.setitem(compliance.PCI_DEDUCTIONS, "card_data", 100 - score)
    report, _ = await assess(facts(touches_card_data=True), Architecture(components=[]))
    pci = frameworks(report)["PCI DSS"]
    assert pci.score == score
    assert pci.risk_level == level


@pytest.mark.parametrize("deduction,expected", [(150, 0), (-10, 100)])
async def test_score_is_clamped_when_constants_are_tuned(monkeypatch, deduction, expected):
    monkeypatch.setitem(compliance.PCI_DEDUCTIONS, "card_data", deduction)
    report, _ = await assess(facts(touches_card_data=True), Architecture(components=[]))
    assert frameworks(report)["PCI DSS"].score == expected
    assert report.overall_score == expected


async def test_catalog_is_authority_and_graph_summaries_do_not_add_impact():
    arch = Architecture(
        components=[
            component("changed"),
            component(
                "unrelated", criticality=10, data_classes=["pii", "card", "financial", "audit"]
            ),
        ]
    )
    requirement = facts(affected_services=["changed"])
    graph = build_impact_graph(requirement.affected_services, arch)
    graph.nodes[0].data_classes = ["pii", "card", "financial", "audit"]
    graph.nodes[0].criticality = 10
    graph.impacted_services.append("unrelated")
    report, _ = await compliance.assess_compliance(requirement, graph, arch)
    assert all(not assessment.applicable for assessment in report.frameworks)


async def test_no_llm_fallback_is_deterministic_and_provides_two_to_four_items():
    arch = Architecture(
        components=[
            component(
                "payment-service",
                criticality=10,
                data_classes=["pii", "card", "financial", "audit"],
            )
        ]
    )
    requirement = facts(affected_services=["payment-service"])
    result = await assess(requirement, arch)
    assert result == await assess(requirement, arch)
    report, provider = result
    assert provider == "template-fallback"
    for assessment in report.frameworks:
        assert assessment.applicable
        assert 2 <= len(assessment.findings) <= 4
        assert 2 <= len(assessment.recommendations) <= 4
        assert all(finding.node_ids == ["payment-service"] for finding in assessment.findings)
        assert all("payment-service" in text for text in assessment.recommendations)


async def test_one_fast_llm_call_for_all_frameworks_preserves_rules_and_filters_ids(monkeypatch):
    arch = Architecture(
        components=[
            component(
                "payment-service",
                criticality=10,
                data_classes=["pii", "card", "financial", "audit"],
            ),
            component("unrelated", data_classes=["pii"]),
        ]
    )
    requirement = facts(affected_services=["payment-service"])
    fallback, _ = await assess(requirement, arch)
    calls = []

    async def generated(system, user, schema, tier="fast", max_tokens=1500):
        calls.append((system, json.loads(user), tier, max_tokens))
        payload = {
            name: {
                "findings": [
                    {
                        "text": "Control exposure on payment-service",
                        "node_ids": ["payment-service", "unknown", "unrelated", "payment-service"],
                    },
                    {"text": "Review payment-service controls", "node_ids": ["payment-service"]},
                ],
                "recommendations": [
                    "Test payment-service controls",
                    "Review payment-service evidence",
                ],
            }
            for name in compliance.FRAMEWORK_ORDER
        }
        return schema.model_validate(payload), "mock:fast"

    monkeypatch.setattr(llm, "complete_structured", generated)
    report, provider = await assess(requirement, arch)
    assert provider == "mock:fast"
    assert len(calls) == 1
    assert calls[0][2] == "fast"
    assert {entry["framework"] for entry in calls[0][1]["frameworks"]} == set(
        compliance.FRAMEWORK_ORDER
    )
    assert [entry["id"] for entry in calls[0][1]["impacted_components"]] == ["payment-service"]
    assert report.overall_score == fallback.overall_score
    assert report.summary == fallback.summary
    for before, after in zip(fallback.frameworks, report.frameworks, strict=True):
        assert (before.applicable, before.reason, before.score, before.risk_level) == (
            after.applicable,
            after.reason,
            after.score,
            after.risk_level,
        )
        assert after.findings[0].text == "Control exposure on payment-service"
        assert after.findings[0].node_ids == ["payment-service"]


async def test_llm_schema_contains_only_applicable_frameworks(monkeypatch):
    arch = Architecture(components=[component("changed")])

    async def generated(system, user, schema, **kwargs):
        assert set(schema.model_json_schema()["properties"]) == {"GDPR"}
        return (
            schema.model_validate(
                {
                    "GDPR": {
                        "findings": [{"text": "Customer data on changed", "node_ids": ["changed"]}]
                        * 2,
                        "recommendations": [
                            "Review changed privacy controls",
                            "Test changed retention",
                        ],
                    }
                }
            ),
            "mock:fast",
        )

    monkeypatch.setattr(llm, "complete_structured", generated)
    report, provider = await assess(
        facts(affected_services=["changed"], touches_customer_data=True), arch
    )
    assert provider == "mock:fast"
    assert all(not entry.findings for entry in report.frameworks if not entry.applicable)


@pytest.mark.parametrize(
    "invalid",
    ["score", "missing_framework", "one_finding", "five_recommendations", "blank_recommendation"],
)
async def test_invalid_llm_prose_falls_back_without_changing_rules(monkeypatch, invalid):
    arch = Architecture(components=[component("changed")])
    requirement = facts(affected_services=["changed"], touches_card_data=True)
    fallback = await assess(requirement, arch)

    async def invalid_response(system, user, schema, **kwargs):
        entry = {
            "findings": [{"text": "Card data on changed", "node_ids": ["changed"]}] * 2,
            "recommendations": ["Review changed", "Test changed"],
        }
        payload = {"PCI DSS": entry}
        if invalid == "score":
            entry["score"] = 100
        elif invalid == "missing_framework":
            payload = {}
        elif invalid == "one_finding":
            entry["findings"] = entry["findings"][:1]
        elif invalid == "five_recommendations":
            entry["recommendations"] = ["Review changed"] * 5
        elif invalid == "blank_recommendation":
            entry["recommendations"] = [" ", "Review changed"]
        return schema.model_validate(payload), "mock:invalid"

    monkeypatch.setattr(llm, "complete_structured", invalid_response)
    assert await assess(requirement, arch) == fallback


async def test_schema_rejects_llm_risk_fields(monkeypatch):
    async def check_schema(system, user, schema, **kwargs):
        with pytest.raises(ValidationError):
            schema.model_validate(
                {
                    "PCI DSS": {
                        "findings": [{"text": "Card data", "node_ids": []}] * 2,
                        "recommendations": ["Review", "Test"],
                        "risk_level": "low",
                    }
                }
            )
        raise llm.NoLLM("Test complete")

    monkeypatch.setattr(llm, "complete_structured", check_schema)
    report, provider = await assess(facts(touches_card_data=True), Architecture(components=[]))
    assert provider == "template-fallback"
    assert frameworks(report)["PCI DSS"].score == 75
