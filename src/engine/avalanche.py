"""
Debt payoff simulation engine.

Implements the Debt Avalanche and Snowball strategies with full support for
daily/monthly compounding, percent-of-balance minimum payments, promotional
intro rates, variable-rate schedules (ARM-style), and prepayment penalties.
"""

from dataclasses import dataclass, field


@dataclass
class Debt:
    """
    Represents a single debt account with all terms needed for amortization.

    Attributes:
        name: Human-readable label, e.g. "Chase Sapphire Reserve".
        balance: Outstanding principal in the chosen currency.
        apr: Annual percentage rate as a decimal (0.2399 = 23.99 %).
        min_payment: Fixed payment amount, or floor for percent-of-balance mode.
        compounding: "monthly" applies APR/12 per month; "daily" applies
            (1 + APR/365)^(365/12) − 1, matching how credit cards accrue interest.
        min_payment_type: "fixed" keeps the payment constant every month;
            "percent_of_balance" shrinks the minimum as the balance falls
            (credit-card style — typically 2 % of balance, floored at a minimum).
        min_payment_percent: Fraction used when type is "percent_of_balance"
            (default 0.02 = 2 %).
        promo_apr: Introductory rate applied during the first `promo_months`
            billing cycles, e.g. 0.0 for a 0 % balance-transfer offer.
            None means no promotional rate.
        promo_months: Number of months the promo rate applies before reverting
            to the base APR.
        rate_changes: Scheduled APR adjustments as a list of
            [start_month, new_apr] pairs, e.g. [[13, 0.2499]] means the rate
            jumps to 24.99 % at month 13 (ARM-style adjustment).
        prepayment_penalty_type: "none" — no penalty; "flat" — a fixed dollar
            charge; "percent" — a percentage of the remaining balance.
        prepayment_penalty_value: The flat dollar amount or decimal fraction
            (0.03 = 3 %) charged when the debt is paid off early.
        prepayment_penalty_months: Penalty window in months; 0 means the
            penalty applies for the entire life of the loan, otherwise it
            expires after this many months.
    """

    name: str
    balance: float
    apr: float
    min_payment: float

    # ── Compounding ────────────────────────────────────────────────────────────
    compounding: str = "monthly"        # "monthly" | "daily"

    # ── Minimum payment ────────────────────────────────────────────────────────
    min_payment_type: str = "fixed"     # "fixed" | "percent_of_balance"
    min_payment_percent: float = 0.02

    # ── Promotional / intro rate ───────────────────────────────────────────────
    promo_apr: float | None = None
    promo_months: int = 0

    # ── Variable rate schedule: [[start_month, new_apr], ...] ─────────────────
    rate_changes: list[list[float]] = field(default_factory=list)

    # ── Prepayment penalty ─────────────────────────────────────────────────────
    prepayment_penalty_type: str = "none"   # "none" | "flat" | "percent"
    prepayment_penalty_value: float = 0.0
    prepayment_penalty_months: int = 0


# ── Internal helpers ───────────────────────────────────────────────────────────

def _resolve_apr(debt: Debt, month: int) -> float:
    """
    Return the APR in effect for the given billing month (1-indexed).

    Precedence (highest to lowest):
      1. Promotional rate — applies for months 1 … promo_months.
      2. Rate-change schedule — later entries override earlier ones.
      3. Base APR.

    Args:
        debt: The debt whose rate schedule is being evaluated.
        month: The billing cycle number, starting at 1.

    Returns:
        Effective annual rate as a decimal for this month.
    """
    apr = debt.apr
    # Rate changes stack; a later entry overrides an earlier one for that range
    for change_month, new_apr in sorted(debt.rate_changes, key=lambda x: x[0]):
        if month >= change_month:
            apr = new_apr
    # Promo rate wins over everything during the intro window
    if debt.promo_apr is not None and month <= debt.promo_months:
        apr = debt.promo_apr
    return apr


def _effective_monthly_rate(apr: float, compounding: str) -> float:
    """
    Convert an annual rate to an effective monthly rate.

    Args:
        apr: Annual percentage rate as a decimal.
        compounding: "daily" uses (1 + apr/365)^(365/12) − 1, which costs
            slightly more than simple APR/12 due to intra-month compounding.
            Any other value falls back to APR/12.

    Returns:
        Effective monthly rate as a decimal.
    """
    if compounding == "daily":
        return (1 + apr / 365) ** (365 / 12) - 1
    return apr / 12


def _calc_min_payment(debt: Debt, balance: float) -> float:
    """
    Return the minimum required payment for this billing cycle.

    For "percent_of_balance" debts the minimum shrinks as the balance falls,
    but never drops below the floor stored in ``debt.min_payment``.

    Args:
        debt: The debt being evaluated.
        balance: Current outstanding balance after interest has been accrued.

    Returns:
        Minimum payment amount in the same currency as the balance.
    """
    if debt.min_payment_type == "percent_of_balance":
        return max(debt.min_payment, balance * debt.min_payment_percent)
    return debt.min_payment


def _calc_penalty(debt: Debt, balance: float, month: int) -> float:
    """
    Return the prepayment penalty incurred if this debt is fully closed at ``month``.

    Args:
        debt: The debt being paid off.
        balance: Remaining balance at the point of payoff (post-interest).
        month: The billing cycle number in which the payoff occurs.

    Returns:
        Penalty amount in the same currency as the balance, or 0.0 if none applies.
    """
    if debt.prepayment_penalty_type == "none":
        return 0.0
    if debt.prepayment_penalty_months > 0 and month > debt.prepayment_penalty_months:
        return 0.0  # penalty window has expired
    if debt.prepayment_penalty_type == "flat":
        return debt.prepayment_penalty_value
    if debt.prepayment_penalty_type == "percent":
        return balance * debt.prepayment_penalty_value
    return 0.0


# ── Core simulation ────────────────────────────────────────────────────────────

def _validate(debts: list[Debt], monthly_budget: float) -> None:
    """
    Raise ValueError if the input is invalid before running a simulation.

    Args:
        debts: Portfolio to validate; must contain at least one debt.
        monthly_budget: Total monthly payment available across all debts.

    Raises:
        ValueError: If ``debts`` is empty, or if ``monthly_budget`` is less
            than the sum of all initial minimum payments.
    """
    if not debts:
        raise ValueError("No debts provided")
    total_min = sum(_calc_min_payment(d, d.balance) for d in debts)
    if monthly_budget < total_min:
        raise ValueError(
            f"Budget ${monthly_budget:.2f} is below total minimums ${total_min:.2f}"
        )


def _run_simulation(priority_order: list[Debt], monthly_budget: float) -> dict[str, object]:
    """
    Run the month-by-month payoff simulation with debts in the supplied priority order.

    Each billing cycle:
      1. Accrue interest — uses the effective monthly rate derived from the
         current APR (promo / rate-change aware) and compounding setting.
      2. Pay minimums — fixed or percent-of-balance, capped at remaining budget.
      3. Direct surplus — all remaining budget goes to the first live debt in
         priority order; if fully closing that debt triggers a prepayment
         penalty, the penalty cost is included in the payoff amount.

    Args:
        priority_order: Debts sorted in the desired payoff priority (highest
            APR first for Avalanche, lowest balance first for Snowball).
        monthly_budget: Total amount available every month across all debts.

    Returns:
        A dict containing:
            months_to_payoff (int): Number of billing cycles until all debts reach zero.
            total_interest_paid (float): Cumulative interest accrued across all debts.
            total_penalties_paid (float): Cumulative prepayment penalties paid.
            payoff_order (list[str]): Debt names in the order they reached zero.
            schedule (list[dict]): Month-by-month snapshot of balances and interest.
    """
    balances = {d.name: d.balance for d in priority_order}
    total_interest = 0.0
    total_penalties = 0.0
    schedule: list[dict] = []
    paid_off_set: set[str] = set()

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


# ── Public API ─────────────────────────────────────────────────────────────────

def calculate_avalanche(debts: list[Debt], monthly_budget: float) -> dict[str, object]:
    """
    Run the Debt Avalanche strategy — pay minimums on all debts, then direct
    every surplus dollar at the highest-APR debt first.

    This minimises total interest paid over the life of the portfolio.

    Args:
        debts: Portfolio of debts to pay off.
        monthly_budget: Total monthly payment available across all debts.

    Returns:
        Simulation result dict (see ``_run_simulation`` for key definitions).

    Raises:
        ValueError: If ``debts`` is empty or budget is below total minimums.
    """
    _validate(debts, monthly_budget)
    priority = sorted(debts, key=lambda d: d.apr, reverse=True)
    return _run_simulation(priority, monthly_budget)


def calculate_snowball(debts: list[Debt], monthly_budget: float) -> dict[str, object]:
    """
    Run the Debt Snowball strategy — pay minimums on all debts, then direct
    every surplus dollar at the lowest-balance debt first.

    This maximises the number of quick wins (fully paid-off accounts),
    which can improve motivation even though it costs more in interest.

    Args:
        debts: Portfolio of debts to pay off.
        monthly_budget: Total monthly payment available across all debts.

    Returns:
        Simulation result dict (see ``_run_simulation`` for key definitions).

    Raises:
        ValueError: If ``debts`` is empty or budget is below total minimums.
    """
    _validate(debts, monthly_budget)
    priority = sorted(debts, key=lambda d: d.balance)
    return _run_simulation(priority, monthly_budget)


def compare_strategies(debts: list[Debt], monthly_budget: float) -> dict[str, object]:
    """
    Run both Avalanche and Snowball and return their results side-by-side.

    Args:
        debts: Portfolio of debts to pay off.
        monthly_budget: Total monthly payment available across all debts.

    Returns:
        A dict containing:
            avalanche (dict): Full Avalanche simulation result.
            snowball (dict): Full Snowball simulation result.
            interest_saved_by_avalanche (float): How much less interest the
                Avalanche strategy pays compared to Snowball.
            months_saved_by_avalanche (int): How many fewer months Avalanche
                takes compared to Snowball (negative means Snowball is faster).

    Raises:
        ValueError: If ``debts`` is empty or budget is below total minimums.
    """
    avalanche = calculate_avalanche(debts, monthly_budget)
    snowball = calculate_snowball(debts, monthly_budget)
    return {
        "avalanche": avalanche,
        "snowball": snowball,
        "interest_saved_by_avalanche": round(
            snowball["total_interest_paid"] - avalanche["total_interest_paid"], 2  # type: ignore[operator]
        ),
        "months_saved_by_avalanche": (
            snowball["months_to_payoff"] - avalanche["months_to_payoff"]  # type: ignore[operator]
        ),
    }
