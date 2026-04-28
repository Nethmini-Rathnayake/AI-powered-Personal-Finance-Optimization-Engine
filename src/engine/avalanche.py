from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Debt:
    name: str
    balance: float
    apr: float          # annual rate, decimal (0.2399 = 23.99%)
    min_payment: float  # fixed amount, or floor when min_payment_type="percent_of_balance"

    # ── Compounding ────────────────────────────────────────────────────────────
    compounding: str = "monthly"        # "monthly" | "daily"

    # ── Minimum payment ────────────────────────────────────────────────────────
    min_payment_type: str = "fixed"     # "fixed" | "percent_of_balance"
    min_payment_percent: float = 0.02   # fraction of balance; used when type = percent

    # ── Promotional / intro rate ───────────────────────────────────────────────
    promo_apr: Optional[float] = None   # e.g. 0.0 for a 0% balance-transfer offer
    promo_months: int = 0               # number of months the promo rate applies

    # ── Variable rate schedule: [[start_month, new_apr], ...] ─────────────────
    # e.g. [[13, 0.2499]] means APR jumps to 24.99% at month 13 (ARM adjustment)
    rate_changes: List = field(default_factory=list)

    # ── Prepayment penalty ─────────────────────────────────────────────────────
    prepayment_penalty_type: str = "none"   # "none" | "flat" | "percent"
    prepayment_penalty_value: float = 0.0   # flat $ amount or fraction (0.03 = 3%)
    prepayment_penalty_months: int = 0      # 0 = applies entire loan; N = first N months


# ── Internal helpers ───────────────────────────────────────────────────────────

def _resolve_apr(debt: Debt, month: int) -> float:
    """Return the APR in effect for month (1-indexed), respecting promo and rate changes."""
    apr = debt.apr
    # Rate changes stack — a later entry overrides an earlier one for the same month range
    for change_month, new_apr in sorted(debt.rate_changes, key=lambda x: x[0]):
        if month >= change_month:
            apr = new_apr
    # Promo rate wins over everything for the intro window
    if debt.promo_apr is not None and month <= debt.promo_months:
        apr = debt.promo_apr
    return apr


def _effective_monthly_rate(apr: float, compounding: str) -> float:
    """Convert an annual rate to an effective monthly rate."""
    if compounding == "daily":
        # True daily compounding: (1 + r/365)^(365/12) - 1
        # Costs slightly more than simple APR/12 due to intra-month compounding.
        return (1 + apr / 365) ** (365 / 12) - 1
    return apr / 12


def _calc_min_payment(debt: Debt, balance: float) -> float:
    """Minimum required payment for this billing cycle."""
    if debt.min_payment_type == "percent_of_balance":
        # Credit-card style: max(floor, pct × balance). As balance falls, so does the min.
        return max(debt.min_payment, balance * debt.min_payment_percent)
    return debt.min_payment


def _calc_penalty(debt: Debt, balance: float, month: int) -> float:
    """Prepayment penalty incurred if this debt is fully closed at `month`."""
    if debt.prepayment_penalty_type == "none":
        return 0.0
    if debt.prepayment_penalty_months > 0 and month > debt.prepayment_penalty_months:
        return 0.0  # penalty window expired
    if debt.prepayment_penalty_type == "flat":
        return debt.prepayment_penalty_value
    if debt.prepayment_penalty_type == "percent":
        return balance * debt.prepayment_penalty_value
    return 0.0


# ── Core simulation ────────────────────────────────────────────────────────────

def _validate(debts: List[Debt], monthly_budget: float) -> None:
    if not debts:
        raise ValueError("No debts provided")
    total_min = sum(_calc_min_payment(d, d.balance) for d in debts)
    if monthly_budget < total_min:
        raise ValueError(
            f"Budget ${monthly_budget:.2f} is below total minimums ${total_min:.2f}"
        )


def _run_simulation(priority_order: List[Debt], monthly_budget: float) -> dict:
    """
    Run the payoff simulation with debts in the supplied priority order.

    Each month:
      1. Accrue interest using the effective monthly rate (daily or monthly compounding,
         current APR from promo / rate-change schedule).
      2. Pay the required minimum on every live debt (fixed or percent-of-balance).
      3. Direct all surplus at the first live debt in priority order; if fully paying
         it off triggers a prepayment penalty, that cost is included.
    """
    balances = {d.name: d.balance for d in priority_order}
    total_interest = 0.0
    total_penalties = 0.0
    schedule = []
    paid_off_set: set = set()

    for month in range(1, 601):  # 50-year safety cap

        # ── 1. Accrue interest ─────────────────────────────────────────────────
        interest_this_month = 0.0
        for debt in priority_order:
            bal = balances[debt.name]
            if bal <= 0:
                continue
            rate = _effective_monthly_rate(_resolve_apr(debt, month), debt.compounding)
            interest = bal * rate
            balances[debt.name] += interest
            interest_this_month += interest
            total_interest += interest

        # ── 2. Pay minimums ────────────────────────────────────────────────────
        remaining = monthly_budget
        for debt in priority_order:
            bal = balances[debt.name]
            if bal <= 0:
                continue
            min_pay = _calc_min_payment(debt, bal)
            payment = min(min_pay, bal, remaining)   # never overpay or overspend
            balances[debt.name] = max(0.0, bal - payment)
            remaining = max(0.0, remaining - payment)

        # ── 3. Avalanche / Snowball surplus ────────────────────────────────────
        for debt in priority_order:
            if remaining <= 0:
                break
            bal = balances[debt.name]
            if bal <= 0:
                continue
            penalty = _calc_penalty(debt, bal, month)
            full_cost = bal + penalty
            if remaining >= full_cost:
                # Full payoff — penalty is part of the closing cost
                balances[debt.name] = 0.0
                remaining -= full_cost
                total_penalties += penalty
            else:
                # Partial payment — paying less than full balance avoids triggering penalty
                payment = min(remaining, bal)
                balances[debt.name] = max(0.0, bal - payment)
                remaining -= payment

        # Clean sub-cent residuals to prevent infinite loops
        for name in balances:
            if 0 < balances[name] < 0.01:
                balances[name] = 0.0

        newly_paid = [
            name for name, bal in balances.items()
            if bal == 0 and name not in paid_off_set
        ]
        paid_off_set.update(newly_paid)

        schedule.append({
            "month": month,
            "balances": {k: round(v, 2) for k, v in balances.items()},
            "interest_charged": round(interest_this_month, 2),
            "paid_off_this_month": newly_paid,
        })

        if all(b == 0 for b in balances.values()):
            break

    payoff_order = [
        name
        for snap in schedule
        for name in snap["paid_off_this_month"]
    ]

    return {
        "months_to_payoff": len(schedule),
        "total_interest_paid": round(total_interest, 2),
        "total_penalties_paid": round(total_penalties, 2),
        "payoff_order": payoff_order,
        "schedule": schedule,
    }


# ── Public API (unchanged signatures) ─────────────────────────────────────────

def calculate_avalanche(debts: List[Debt], monthly_budget: float) -> dict:
    """Debt Avalanche: pay minimums on all, then attack the highest-APR debt."""
    _validate(debts, monthly_budget)
    priority = sorted(debts, key=lambda d: d.apr, reverse=True)
    return _run_simulation(priority, monthly_budget)


def calculate_snowball(debts: List[Debt], monthly_budget: float) -> dict:
    """Debt Snowball: pay minimums on all, then attack the lowest-balance debt."""
    _validate(debts, monthly_budget)
    priority = sorted(debts, key=lambda d: d.balance)
    return _run_simulation(priority, monthly_budget)


def compare_strategies(debts: List[Debt], monthly_budget: float) -> dict:
    """Return Avalanche vs Snowball side-by-side with interest and time savings."""
    avalanche = calculate_avalanche(debts, monthly_budget)
    snowball = calculate_snowball(debts, monthly_budget)
    return {
        "avalanche": avalanche,
        "snowball": snowball,
        "interest_saved_by_avalanche": round(
            snowball["total_interest_paid"] - avalanche["total_interest_paid"], 2
        ),
        "months_saved_by_avalanche": (
            snowball["months_to_payoff"] - avalanche["months_to_payoff"]
        ),
    }
