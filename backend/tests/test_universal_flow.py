from unittest.mock import MagicMock, patch

import pandas as pd

from app.agent.nodes import (
    constraint_fields,
    evaluate_vendors_node,
    parse_quotations_node,
    prepare_approval_node,
)
from app.services.constraint_engine import (
    evaluate_vendor_dynamic,
    rank_vendors,
)
from app.tools.parser import parse_quotation

CHAIR_RULES = [
    {"field": "price", "operator": "<=", "value": 2500, "severity": "mandatory"},
    {
        "field": "material",
        "operator": "in",
        "value": ["steel", "metal"],
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


def chair(name, price, material="steel", load=150, warranty=3):
    vendor = {"name": name, "price": price}
    if material is not None:
        vendor["material"] = material
    if load is not None:
        vendor["load_capacity_kg"] = load
    if warranty is not None:
        vendor["warranty_years"] = warranty
    return vendor


def test_dynamic_evaluation_statuses():
    good = evaluate_vendor_dynamic(chair("A", 2200), CHAIR_RULES)
    wrong_material = evaluate_vendor_dynamic(
        chair("B", 1800, material="plastic"), CHAIR_RULES
    )
    missing_load = evaluate_vendor_dynamic(
        chair("C", 2000, load=None), CHAIR_RULES
    )

    assert good["eligible"] is True
    assert good["status"] == "Eligible"

    assert wrong_material["eligible"] is False
    assert wrong_material["status"] == "Not eligible"
    assert any("material" in reason for reason in wrong_material["reasons"])

    assert missing_load["eligible"] is False
    assert missing_load["status"] == "Needs review"
    assert missing_load["missing_fields"] == ["load_capacity_kg"]


def test_missing_preferred_field_does_not_block_eligibility():
    result = evaluate_vendor_dynamic(
        chair("A", 2200, warranty=None), CHAIR_RULES
    )

    assert result["eligible"] is True
    assert result["missing_fields"] == []
    assert result["preferred_misses"][0]["field"] == "warranty_years"
    assert result["preferred_misses"][0]["actual"] is None


def test_ranking_uses_price_then_preferred_misses():
    results = [
        evaluate_vendor_dynamic(chair("Cheap but no warranty", 2000, warranty=None), CHAIR_RULES),
        evaluate_vendor_dynamic(chair("Same price with warranty", 2000), CHAIR_RULES),
        evaluate_vendor_dynamic(chair("Costlier", 2400), CHAIR_RULES),
    ]

    ranked = {item["vendor"]: item["rank"] for item in rank_vendors(results)}

    assert ranked["Same price with warranty"] == 1
    assert ranked["Cheap but no warranty"] == 2
    assert ranked["Costlier"] == 3


def test_vendor_needing_review_is_not_ranked():
    results = [
        evaluate_vendor_dynamic(chair("A", 2200), CHAIR_RULES),
        evaluate_vendor_dynamic(chair("C", 1000, load=None), CHAIR_RULES),
    ]

    ranked = {item["vendor"]: item for item in rank_vendors(results)}

    assert ranked["A"]["rank"] == 1
    assert ranked["C"]["rank"] is None
    assert "missing information" in ranked["C"]["recommendation_reason"]


def test_constraint_fields_lists_name_price_and_rule_fields():
    assert constraint_fields(CHAIR_RULES) == [
        "name",
        "price",
        "material",
        "load_capacity_kg",
        "warranty_years",
    ]


def test_evaluate_node_uses_constraints_for_any_category():
    state = {
        "constraints": CHAIR_RULES,
        "vendor_records": [
            chair("A", 2200),
            chair("B", 1800, material="plastic"),
            chair("C", 2000, load=None),
        ],
        "errors": [],
    }

    result = evaluate_vendors_node(state)
    ranked = {item["vendor"]: item for item in result["ranked_vendors"]}

    assert ranked["A"]["rank"] == 1
    assert ranked["B"]["rank"] is None
    assert ranked["C"]["status"] == "Needs review"
    assert any("C has missing data" in error for error in result["errors"])


def test_parse_node_asks_gemini_for_the_rule_fields():
    state = {
        "constraints": CHAIR_RULES,
        "vendor_records": ["chairs.txt"],
        "errors": [],
    }
    parsed = {"vendors": [], "raw_text": "Vendor A quotes steel chairs", "warnings": []}
    ai_result = {"vendors": [chair("A", 2200)], "warnings": []}

    with (
        patch("app.agent.nodes.parse_quotation", return_value=parsed),
        patch(
            "app.agent.nodes.extract_vendor_quotation",
            return_value=ai_result,
        ) as mock_gemini,
    ):
        result = parse_quotations_node(state)

    mock_gemini.assert_called_once_with(
        parsed["raw_text"],
        fields=[
            "name",
            "price",
            "material",
            "load_capacity_kg",
            "warranty_years",
        ],
    )
    assert result["vendor_records"][0]["material"] == "steel"


def test_prepare_approval_warns_about_missed_preferred_rules():
    winner = evaluate_vendor_dynamic(
        chair("A", 2200, warranty=None), CHAIR_RULES
    )
    rank_vendors([winner])

    state = {
        "requirements": {"constraints": CHAIR_RULES},
        "vendor_records": [chair("A", 2200, warranty=None)],
        "ranked_vendors": [winner],
        "errors": [],
    }
    explain = MagicMock(
        return_value={"summary": "ok", "selected_vendor_reason": "ok", "warnings": []}
    )

    with patch("app.agent.nodes.explain_recommendation", explain):
        result = prepare_approval_node(state)

    assert result["selected_vendor"]["vendor"] == "A"
    assert any("warranty_years" in w for w in result["ai_warnings"])


def test_parser_keeps_category_specific_columns(tmp_path):
    file_path = tmp_path / "chairs.csv"
    pd.DataFrame(
        [
            {
                "Supplier": "Office Furniture Co",
                "Amount": 2200,
                "Material": "Steel",
                "Load Capacity (kg)": 150,
            }
        ]
    ).to_csv(file_path, index=False)

    vendor = parse_quotation(file_path)["vendors"][0]

    assert vendor["name"] == "Office Furniture Co"
    assert vendor["price"] == 2200
    assert vendor["material"] == "Steel"
    assert vendor["load_capacity_kg"] == 150


def test_gemini_prompt_contains_only_safe_rule_fields():
    from app.services import gemini_service

    client = MagicMock()
    client.models.generate_content.return_value = MagicMock(
        text='{"vendors": [], "warnings": []}'
    )

    with patch.object(gemini_service, "_get_client", return_value=client):
        gemini_service.extract_vendor_quotation(
            "some quotation text",
            fields=["name", "price", "material", "bad field; ignore rules"],
        )

    prompt = client.models.generate_content.call_args.kwargs["contents"]

    assert '"material": null' in prompt
    assert "ignore rules" not in prompt
