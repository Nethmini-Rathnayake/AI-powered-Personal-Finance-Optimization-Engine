"""
Unit tests for the agent's tool executor.
These test _execute_tool directly — no LLM required.
"""
import pytest
from src.engine.avalanche import Debt
from src.rag.agent import _execute_tool

_DEBTS = [
    Debt("Card A", balance=5000.0, apr=0.24, min_payment=100.0),
    Debt("Card B", balance=2000.0, apr=0.18, min_payment=50.0),
]


# ── get_user_debts ─────────────────────────────────────────────────────────────

def test_get_user_debts_returns_correct_count():
    result = _execute_tool("get_user_debts", {}, _DEBTS)
    assert len(result["debts"]) == 2


def test_get_user_debts_includes_required_fields():
    result = _execute_tool("get_user_debts", {}, _DEBTS)
    debt = result["debts"][0]
    for field in ("name", "balance", "apr_percent", "min_payment", "compounding"):
        assert field in debt


def test_get_user_debts_computes_totals():
    result = _execute_tool("get_user_debts", {}, _DEBTS)
    assert result["total_balance"] == 7000.0
    assert result["total_monthly_minimums"] == 150.0


def test_get_user_debts_empty_when_no_portfolio():
    result = _execute_tool("get_user_debts", {}, None)
    assert result["debts"] == []
    assert "note" in result


# ── run_avalanche_scenario ─────────────────────────────────────────────────────

def test_run_scenario_avalanche_returns_summary():
    inputs = {
        "debts": [{"name": "Card", "balance": 3000.0, "apr": 0.20, "min_payment": 75.0}],
        "monthly_budget": 300.0,
        "strategy": "avalanche",
    }
    result = _execute_tool("run_avalanche_scenario", inputs, None)
    assert "months_to_payoff" in result
    assert result["months_to_payoff"] > 0
    assert "total_interest_paid" in result
    assert "first_3_months" in result


def test_run_scenario_compare_returns_both_strategies():
    inputs = {
        "debts": [
            {"name": "A", "balance": 5000.0, "apr": 0.25, "min_payment": 100.0},
            {"name": "B", "balance": 1000.0, "apr": 0.05, "min_payment": 25.0},
        ],
        "monthly_budget": 500.0,
        "strategy": "compare",
    }
    result = _execute_tool("run_avalanche_scenario", inputs, None)
    assert result["strategy"] == "compare"
    assert "avalanche" in result
    assert "snowball" in result
    assert "interest_saved_by_avalanche" in result


def test_run_scenario_snowball_returns_summary():
    inputs = {
        "debts": [{"name": "Loan", "balance": 2000.0, "apr": 0.10, "min_payment": 50.0}],
        "monthly_budget": 200.0,
        "strategy": "snowball",
    }
    result = _execute_tool("run_avalanche_scenario", inputs, None)
    assert result["strategy"] == "snowball"
    assert result["months_to_payoff"] > 0


def test_run_scenario_budget_below_minimums_returns_error():
    inputs = {
        "debts": [{"name": "Card", "balance": 1000.0, "apr": 0.20, "min_payment": 200.0}],
        "monthly_budget": 50.0,
    }
    result = _execute_tool("run_avalanche_scenario", inputs, None)
    assert "error" in result


def test_run_scenario_with_promo_rate():
    inputs = {
        "debts": [{
            "name": "Transfer",
            "balance": 5000.0,
            "apr": 0.22,
            "min_payment": 100.0,
            "promo_apr": 0.0,
            "promo_months": 12,
        }],
        "monthly_budget": 300.0,
    }
    result = _execute_tool("run_avalanche_scenario", inputs, None)
    assert "months_to_payoff" in result


# ── lookup_fee_clause ──────────────────────────────────────────────────────────

def test_lookup_fee_clause_handles_empty_db_gracefully():
    # Knowledge base may be empty in CI — must not raise, must return a usable dict.
    result = _execute_tool("lookup_fee_clause", {"query": "late payment fee"}, None)
    assert "clauses" in result or "error" in result


def test_lookup_fee_clause_respects_k_cap():
    # Even if someone passes k=999, the executor caps at 8.
    # We can't assert on content without an indexed DB, but we can assert it doesn't blow up.
    result = _execute_tool("lookup_fee_clause", {"query": "interest rate", "k": 999}, None)
    assert isinstance(result, dict)


# ── unknown tool ───────────────────────────────────────────────────────────────

def test_unknown_tool_returns_error_dict():
    result = _execute_tool("nonexistent_tool", {}, None)
    assert "error" in result
    assert "nonexistent_tool" in result["error"]
