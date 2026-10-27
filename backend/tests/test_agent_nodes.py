
from unittest.mock import patch

from app.agent.nodes import evaluate_vendors_node, parse_quotations_node


def test_gemini_fallback_used_when_local_parser_has_no_vendors():
    state = {
        "vendor_records": ["sample.txt"],
        "errors": [],
    }

    parsed_result = {
        "vendors": [],
        "raw_text": (
            "Vendor: Vendor A\n"
            "Price: 55000\n"
            "RAM: 16 GB\n"
            "SSD: 512 GB\n"
            "Delivery: 12 days\n"
            "Warranty: 3 years"
        ),
        "warnings": [],
    }

    ai_result = {
        "vendors": [
            {
                "name": "Vendor A",
                "price": 55000,
                "ram_gb": 16,
                "ssd_gb": 512,
                "delivery_days": 12,
                "warranty_years": 3,
                "missing_fields": [],
            }
        ],
        "warnings": [],
    }

    with (
        patch(
            "app.agent.nodes.parse_quotation",
            return_value=parsed_result,
        ),
        patch(
            "app.agent.nodes.extract_vendor_quotation",
            return_value=ai_result,
        ) as mock_gemini,
    ):
        result = parse_quotations_node(state)

    mock_gemini.assert_called_once_with(parsed_result["raw_text"])
    assert result["vendor_records"][0]["name"] == "Vendor A"
    assert result["vendor_records"][0]["price"] == 55000


def test_python_engine_remains_authoritative_for_eligibility():
    state = {
        "requirements": {
            "min_ram_gb": 16,
            "min_ssd_gb": 512,
            "max_price": 60000,
            "max_delivery_days": 15,
            "min_warranty_years": 3,
        },
        "vendor_records": [
            {
                "name": "Vendor B",
                "price": 48000,
                "ram_gb": 8,
                "ssd_gb": 512,
                "delivery_days": 10,
                "warranty_years": 3,
                "missing_fields": [],
            }
        ],
        "errors": [],
    }

    result = evaluate_vendors_node(state)

    vendor = result["ranked_vendors"][0]
    assert vendor["eligible"] is False
    assert vendor["rank"] is None
    assert any("RAM" in reason for reason in vendor["reasons"])
