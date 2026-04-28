import pytest
from src.engine.avalanche import Debt, calculate_avalanche, calculate_snowball, compare_strategies


def _sample_debts():
    return [
        Debt("Chase Sapphire",   balance=5000.0,  apr=0.2399, min_payment=100.0),
        Debt("Capital One",      balance=2500.0,  apr=0.1999, min_payment=50.0),
        Debt("Student Loan",     balance=15000.0, apr=0.0675, min_payment=150.0),
    ]


def test_all_debts_reach_zero():
    result = calculate_avalanche(_sample_debts(), monthly_budget=600.0)
    for bal in result["schedule"][-1]["balances"].values():
        assert bal == 0.0


def test_avalanche_payoff_order_is_highest_apr_first():
    result = calculate_avalanche(_sample_debts(), monthly_budget=600.0)
    order = result["payoff_order"]
    # Chase (23.99%) must be retired before Capital One (19.99%)
    assert order.index("Chase Sapphire") < order.index("Capital One")


def test_total_interest_is_positive():
    result = calculate_avalanche(_sample_debts(), monthly_budget=600.0)
    assert result["total_interest_paid"] > 0


def test_budget_below_minimums_raises():
    with pytest.raises(ValueError, match="minimums"):
        calculate_avalanche(_sample_debts(), monthly_budget=100.0)


def test_empty_debts_raises():
    with pytest.raises(ValueError, match="No debts"):
        calculate_avalanche([], monthly_budget=500.0)


def test_single_debt_payoff():
    debts = [Debt("Card", balance=1000.0, apr=0.12, min_payment=50.0)]
    result = calculate_avalanche(debts, monthly_budget=200.0)
    assert result["months_to_payoff"] > 0
    assert result["total_interest_paid"] > 0
    assert result["payoff_order"] == ["Card"]


def test_exact_minimum_budget_still_converges():
    debts = [Debt("Card", balance=1000.0, apr=0.12, min_payment=100.0)]
    result = calculate_avalanche(debts, monthly_budget=100.0)
    assert result["months_to_payoff"] > 0


def test_avalanche_beats_snowball_on_interest():
    # High APR on the large-balance debt means avalanche saves real money here.
    debts = [
        Debt("Big High APR",   balance=5000.0, apr=0.25, min_payment=100.0),
        Debt("Small Low APR",  balance=1000.0, apr=0.05, min_payment=50.0),
    ]
    result = compare_strategies(debts, monthly_budget=500.0)
    # Avalanche targets the 25% debt first; snowball pays the small balance first.
    assert result["interest_saved_by_avalanche"] > 0


def test_snowball_payoff_order_is_lowest_balance_first():
    debts = [
        Debt("Big Debt",   balance=8000.0, apr=0.10, min_payment=80.0),
        Debt("Small Debt", balance=500.0,  apr=0.05, min_payment=25.0),
    ]
    result = calculate_snowball(debts, monthly_budget=400.0)
    assert result["payoff_order"][0] == "Small Debt"


def test_compare_returns_all_keys():
    result = compare_strategies(_sample_debts(), monthly_budget=600.0)
    assert "avalanche" in result
    assert "snowball" in result
    assert "interest_saved_by_avalanche" in result
    assert "months_saved_by_avalanche" in result
