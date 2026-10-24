
import json

import pandas as pd
import pytest

from app.tools.parser import parse_quotation


def test_csv_parses_vendor_and_normalizes_fields(tmp_path):
    file_path = tmp_path / "quotation.csv"
    pd.DataFrame([{
        "Vendor Name": "Vendor D",
        "Unit Price": 52000,
        "RAM": "16 GB",
        "SSD": "512 GB",
        "Delivery Days": 10,
        "Warranty Years": 3,
    }]).to_csv(file_path, index=False)

    result = parse_quotation(file_path)

    assert result["vendors"][0]["name"] == "Vendor D"
    assert result["vendors"][0]["price"] == 52000
    assert result["vendors"][0]["ram_gb"] == 16
    assert result["vendors"][0]["complete"] is True


def test_json_reports_missing_fields(tmp_path):
    file_path = tmp_path / "quotation.json"
    file_path.write_text(
        json.dumps([{"vendor": "Vendor A", "price": 55000}]),
        encoding="utf-8",
    )

    result = parse_quotation(file_path)

    vendor = result["vendors"][0]
    assert vendor["name"] == "Vendor A"
    assert vendor["price"] == 55000
    assert "ram_gb" in vendor["missing_fields"]
    assert vendor["complete"] is False


def test_txt_extracts_explicit_fields(tmp_path):
    file_path = tmp_path / "quotation.txt"
    file_path.write_text(
        "Vendor: Vendor A\n"
        "Price: 55000\n"
        "RAM: 16 GB\n"
        "SSD: 512 GB\n"
        "Delivery: 12 days\n"
        "Warranty: 3 years\n",
        encoding="utf-8",
    )

    result = parse_quotation(file_path)

    vendor = result["vendors"][0]
    assert vendor["name"] == "Vendor A"
    assert vendor["price"] == 55000
    assert vendor["ram_gb"] == 16
    assert vendor["ssd_gb"] == 512
    assert vendor["delivery_days"] == 12
    assert vendor["warranty_years"] == 3
    assert vendor["complete"] is True


def test_unsupported_file_fails_clearly(tmp_path):
    file_path = tmp_path / "quotation.png"
    file_path.write_bytes(b"placeholder")

    with pytest.raises(ValueError, match="Unsupported format"):
        parse_quotation(file_path)


def test_missing_file_fails_clearly(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_quotation(tmp_path / "missing.csv")
