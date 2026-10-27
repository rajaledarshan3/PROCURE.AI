
from app.services.dynamic_constraints import (
    evaluate_constraints,
    validate_constraints,
)


def test_mandatory_rule_rejects_vendor():
    rules = [
        {
            "field": "price",
            "operator": "<=",
            "value": 50000,
            "severity": "mandatory",
        }
    ]

    result = evaluate_constraints({"price": 55000}, rules)

    assert result["status"] == "not_eligible"
    assert len(result["mandatory_failures"]) == 1


def test_preferred_rule_does_not_disqualify_vendor():
    rules = [
        {
            "field": "material",
            "operator": "=",
            "value": "metal",
            "severity": "preferred",
        }
    ]

    result = evaluate_constraints({"material": "plastic"}, rules)

    assert result["status"] == "eligible"
    assert result["eligible"] is True
    assert len(result["preferred_misses"]) == 1


def test_missing_data_requires_review():
    rules = [
        {
            "field": "material",
            "operator": "=",
            "value": "metal",
            "severity": "mandatory",
        }
    ]

    result = evaluate_constraints({}, rules)

    assert result["status"] == "needs_review"
    assert result["eligible"] is False
    assert "material" in result["missing_fields"]


def test_in_operator():
    rules = [
        {
            "field": "material",
            "operator": "in",
            "value": ["metal", "wood"],
            "severity": "mandatory",
        }
    ]

    result = evaluate_constraints({"material": "metal"}, rules)

    assert result["status"] == "eligible"


def test_conflicting_mandatory_bounds_are_detected():
    rules = [
        {
            "field": "price",
            "operator": ">=",
            "value": 60000,
            "severity": "mandatory",
        },
        {
            "field": "price",
            "operator": "<=",
            "value": 40000,
            "severity": "mandatory",
        },
    ]

    errors = validate_constraints(rules)

    assert any("Conflicting mandatory rules" in error for error in errors)


def test_invalid_operator_is_rejected():
    rules = [
        {
            "field": "price",
            "operator": "~=",
            "value": 50000,
            "severity": "mandatory",
        }
    ]

    errors = validate_constraints(rules)

    assert any("unsupported operator" in error for error in errors)
def test_missing_field_is_not_automatically_rejected():
    rules = [
        {
            "field": "material",
            "operator": "=",
            "value": "steel",
            "severity": "mandatory",
        },
        {
            "field": "price",
            "operator": "<=",
            "value": 2500,
            "severity": "mandatory",
        },
    ]

    result = evaluate_constraints({"price": 2000}, rules)

    assert result["status"] == "needs_review"
    assert result["eligible"] is False
    assert "material" in result["missing_fields"]


def test_mandatory_failure_is_reported_when_data_is_complete():
    rules = [
        {
            "field": "price",
            "operator": "<=",
            "value": 2500,
            "severity": "mandatory",
        },
        {
            "field": "material",
            "operator": "=",
            "value": "steel",
            "severity": "mandatory",
        },
    ]

    result = evaluate_constraints(
        {"price": 3000, "material": "plastic"},
        rules,
    )

    assert result["status"] == "not_eligible"
    assert len(result["mandatory_failures"]) == 2