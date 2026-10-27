from app.services.dynamic_constraints import evaluate_constraints


def test_chair_quotation_uses_custom_requirements():
    requirements = [
        {
            "field": "price",
            "operator": "<=",
            "value": 2500,
            "severity": "mandatory",
        },
        {
            "field": "material",
            "operator": "in",
            "value": ["metal", "steel"],
            "severity": "mandatory",
        },
        {
            "field": "load_capacity_kg",
            "operator": ">=",
            "value": 120,
            "severity": "mandatory",
        },
        {
            "field": "warranty_years",
            "operator": ">=",
            "value": 2,
            "severity": "preferred",
        },
    ]

    quotation = {
        "name": "Vendor A",
        "price": 2200,
        "material": "steel",
        "load_capacity_kg": 150,
        "warranty_years": 1,
    }

    result = evaluate_constraints(quotation, requirements)

    assert result["status"] == "eligible"
    assert result["eligible"] is True
    assert len(result["preferred_misses"]) == 1