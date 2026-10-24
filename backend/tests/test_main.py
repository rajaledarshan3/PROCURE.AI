
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def sample_request():
    return {
        "requirements": {
            "quantity": 50,
            "min_ram_gb": 16,
            "min_ssd_gb": 512,
            "max_price": 60000,
            "max_delivery_days": 15,
            "min_warranty_years": 3,
        },
        "vendors": [
            {
                "name": "Vendor A",
                "price": 55000,
                "ram_gb": 16,
                "ssd_gb": 512,
                "delivery_days": 12,
                "warranty_years": 3,
            },
            {
                "name": "Vendor B",
                "price": 48000,
                "ram_gb": 8,
                "ssd_gb": 512,
                "delivery_days": 10,
                "warranty_years": 3,
            },
            {
                "name": "Vendor C",
                "price": 58000,
                "ram_gb": 16,
                "ssd_gb": 512,
                "delivery_days": 20,
                "warranty_years": 2,
            },
            {
                "name": "Vendor D",
                "price": 52000,
                "ram_gb": 16,
                "ssd_gb": 512,
                "delivery_days": 10,
                "warranty_years": 3,
            },
        ],
    }


def test_home_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_only_eligible_vendors_are_ranked():
    response = client.post("/analyze", json=sample_request())

    assert response.status_code == 200

    data = response.json()
    assert data["total_vendors"] == 4
    assert data["eligible_count"] == 2

    results = {item["vendor"]: item for item in data["results"]}

    assert results["Vendor D"]["eligible"] is True
    assert results["Vendor D"]["rank"] == 1

    assert results["Vendor A"]["eligible"] is True
    assert results["Vendor A"]["rank"] == 2

    assert results["Vendor B"]["eligible"] is False
    assert results["Vendor B"]["rank"] is None
    assert any("RAM" in reason for reason in results["Vendor B"]["reasons"])

    assert results["Vendor C"]["eligible"] is False
    assert results["Vendor C"]["rank"] is None
    assert len(results["Vendor C"]["reasons"]) == 2


def test_no_eligible_vendors():
    request_data = sample_request()
    request_data["vendors"] = [request_data["vendors"][1]]

    response = client.post("/analyze", json=request_data)

    assert response.status_code == 200
    assert response.json()["eligible_count"] == 0
    assert response.json()["results"][0]["rank"] is None


def test_empty_vendor_list():
    request_data = sample_request()
    request_data["vendors"] = []

    response = client.post("/analyze", json=request_data)

    assert response.status_code == 200
    assert response.json()["total_vendors"] == 0
    assert response.json()["eligible_count"] == 0
