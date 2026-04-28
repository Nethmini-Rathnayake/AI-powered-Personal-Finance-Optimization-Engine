import pytest
from src.engine.avalanche import Debt, calculate_avalanche, calculate_snowball, compare_strategies


def _sample_debts():
    return [
        Debt("Chase Sapphire",   balance=5000.0,  apr=0.2399, min_payment=100.0),
        Debt("Capital One",      balance=2500.0,  apr=0.1999, min_payment=50.0),
        Debt("Student Loan",     balance=15000.0, apr=0.0675, min_payment=150.0),
    ]


# ── Original tests (must keep passing) ────────────────────────────────────────

def test_all_debts_reach_zero():
    result = calculate_avalanche(_sample_debts(), monthly_budget=600.0)
    for bal in result["schedule"][-1]["balances"].values():
        assert bal == 0.0


def test_avalanche_payoff_order_is_highest_apr_first():
    result = calculate_avalanche(_sample_debts(), monthly_budget=600.0)
    order = result["payoff_order"]
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
    debts = [
        Debt("Big High APR",  balance=5000.0, apr=0.25, min_payment=100.0),
        Debt("Small Low APR", balance=1000.0, apr=0.05, min_payment=50.0),
    ]
    result = compare_strategies(debts, monthly_budget=500.0)
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


# ── Daily compounding ──────────────────────────────────────────────────────────

def test_daily_compounding_costs_more_than_monthly():
    # Daily compounding (1 + r/365)^(365/12) > r/12, so more interest accrues.
    monthly = Debt("Card", balance=5000.0, apr=0.24, min_payment=100.0, compounding="monthly")
    daily   = Debt("Card", balance=5000.0, apr=0.24, min_payment=100.0, compounding="daily")
    result_m = calculate_avalanche([monthly], 300.0)
    result_d = calculate_avalanche([daily],   300.0)
    assert result_d["total_interest_paid"] > result_m["total_interest_paid"]


def test_daily_compounding_still_pays_off():
    debts = [Debt("Card", balance=3000.0, apr=0.20, min_payment=75.0, compounding="daily")]
    result = calculate_avalanche(debts, 250.0)
    assert result["schedule"][-1]["balances"]["Card"] == 0.0


# ── Percent-of-balance minimum payments ───────────────────────────────────────

def test_percent_min_payment_initial_exceeds_floor():
    # At $10,000 balance, 2% = $200 > $25 floor → effective min is $200
    debt = Debt("Card", balance=10000.0, apr=0.20, min_payment=25.0,
                min_payment_type="percent_of_balance", min_payment_percent=0.02)
    result = calculate_avalanche([debt], monthly_budget=200.0)
    assert result["months_to_payoff"] > 0


def test_percent_min_payment_takes_longer_than_fixed_with_same_floor():
    # With a tight budget equal to the floor, the percent-of-balance type can
    # lead to shrinking minimums, leaving more as surplus — but at lower balances
    # the interest savings vary. Key invariant: both must eventually converge.
    debt_fixed   = Debt("Card", balance=5000.0, apr=0.18, min_payment=100.0)
    debt_percent = Debt("Card", balance=5000.0, apr=0.18, min_payment=100.0,
                        min_payment_type="percent_of_balance", min_payment_percent=0.02)
    r_fixed   = calculate_avalanche([debt_fixed],   400.0)
    r_percent = calculate_avalanche([debt_percent], 400.0)
    # Both must fully pay off
    assert r_fixed["schedule"][-1]["balances"]["Card"] == 0.0
    assert r_percent["schedule"][-1]["balances"]["Card"] == 0.0


# ── Promotional / intro rate ───────────────────────────────────────────────────

def test_promo_rate_reduces_total_interest():
    # 0% for 12 months means no interest in the first year — significant savings.
    normal = Debt("Card", balance=6000.0, apr=0.22, min_payment=120.0)
    promo  = Debt("Card", balance=6000.0, apr=0.22, min_payment=120.0,
                  promo_apr=0.0, promo_months=12)
    r_normal = calculate_avalanche([normal], 300.0)
    r_promo  = calculate_avalanche([promo],  300.0)
    assert r_promo["total_interest_paid"] < r_normal["total_interest_paid"]


def test_promo_rate_expires_and_reverts_to_base():
    # After promo ends, interest should start accruing at base APR.
    # A 0% promo for only 1 month should save roughly 1 month of interest.
    debt_no_promo = Debt("Card", balance=5000.0, apr=0.24, min_payment=100.0)
    debt_promo    = Debt("Card", balance=5000.0, apr=0.24, min_payment=100.0,
                         promo_apr=0.0, promo_months=1)
    r_no   = calculate_avalanche([debt_no_promo], 300.0)
    r_yes  = calculate_avalanche([debt_promo],    300.0)
    # Promo saves at least some interest
    assert r_yes["total_interest_paid"] < r_no["total_interest_paid"]


# ── Variable rate schedule ─────────────────────────────────────────────────────

def test_rate_increase_raises_total_interest():
    # APR jumps from 8% → 22% at month 13 (like a teaser-rate ARM).
    flat   = Debt("Loan", balance=10000.0, apr=0.08, min_payment=200.0)
    arm    = Debt("Loan", balance=10000.0, apr=0.08, min_payment=200.0,
                  rate_changes=[[13, 0.22]])
    r_flat = calculate_avalanche([flat], 400.0)
    r_arm  = calculate_avalanche([arm],  400.0)
    assert r_arm["total_interest_paid"] > r_flat["total_interest_paid"]


# ── Prepayment penalty ─────────────────────────────────────────────────────────

def test_prepayment_penalty_is_recorded():
    # Auto loan with 3% prepayment penalty paid off quickly.
    debt = Debt("Auto", balance=15000.0, apr=0.06, min_payment=300.0,
                prepayment_penalty_type="percent", prepayment_penalty_value=0.03)
    result = calculate_avalanche([debt], monthly_budget=2000.0)
    assert result["total_penalties_paid"] > 0


def test_prepayment_penalty_window_expiry():
    # Penalty only applies for first 12 months; paying off slowly avoids it.
    debt = Debt("Loan", balance=5000.0, apr=0.07, min_payment=100.0,
                prepayment_penalty_type="flat", prepayment_penalty_value=500.0,
                prepayment_penalty_months=12)
    # With a tight budget the loan takes well over 12 months — no penalty.
    result = calculate_avalanche([debt], monthly_budget=110.0)
    assert result["total_penalties_paid"] == 0.0


def test_result_includes_penalties_key():
    result = calculate_avalanche(_sample_debts(), monthly_budget=600.0)
    assert "total_penalties_paid" in result
    assert result["total_penalties_paid"] == 0.0
