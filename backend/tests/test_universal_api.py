from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_runs_requires_a_rule_source():
    response = client.post(
        "/runs",
        json={"vendors": [{"name": "A", "price": 1000}]},
    )

    assert response.status_code == 422


def test_runs_rejects_conflicting_constraints():
    response = client.post(
        "/runs",
        json={
            "constraints": [
                {"field": "price", "operator": ">=", "value": 10, "severity": "mandatory"},
                {"field": "price", "operator": "<=", "value": 5, "severity": "mandatory"},
            ],
            "vendors": [{"name": "A", "price": 7}],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["errors"]
