from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_returns_payoff_plan():
    payload = {
        "debts": [
            {"name": "Card A", "balance": 5000.0, "apr": 0.2399, "min_payment": 100.0},
            {"name": "Card B", "balance": 2500.0, "apr": 0.1999, "min_payment": 50.0},
        ],
        "monthly_budget": 500.0,
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "months_to_payoff" in data
    assert "total_interest_paid" in data
    assert data["months_to_payoff"] > 0


def test_analyze_with_snowball_comparison():
    payload = {
        "debts": [
            {"name": "High APR", "balance": 5000.0, "apr": 0.25, "min_payment": 100.0},
            {"name": "Low APR",  "balance": 1000.0, "apr": 0.05, "min_payment": 50.0},
        ],
        "monthly_budget": 500.0,
        "compare_with_snowball": True,
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "avalanche" in data
    assert "snowball" in data


def test_analyze_budget_below_minimums_returns_400():
    payload = {
        "debts": [{"name": "Card", "balance": 1000.0, "apr": 0.20, "min_payment": 100.0}],
        "monthly_budget": 50.0,
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 400


def test_analyze_invalid_apr_returns_422():
    payload = {
        "debts": [{"name": "Card", "balance": 1000.0, "apr": 1.5, "min_payment": 50.0}],
        "monthly_budget": 200.0,
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 422


def test_analyze_csv_upload():
    csv_content = "name,balance,apr,min_payment\nCard A,1000.00,0.15,25.00\n"
    response = client.post(
        "/analyze/csv?monthly_budget=200",
        files={"file": ("statement.csv", csv_content.encode(), "text/csv")},
    )
    assert response.status_code == 200
    assert "months_to_payoff" in response.json()


def test_ask_without_api_key_returns_503(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    response = client.post("/ask", json={"question": "What is my APR?"})
    assert response.status_code == 503


def test_index_pdf_rejects_non_pdf():
    response = client.post(
        "/index-pdf",
        files={"file": ("terms.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 422
