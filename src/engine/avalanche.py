from dataclasses import dataclass, field
from typing import List


@dataclass
class Debt:
    name: str
    balance: float
    apr: float          # decimal, e.g. 0.2399 = 23.99%
    min_payment: float


@dataclass
class _MonthSnapshot:
    month: int
    balances: dict
    interest_charged: float
    paid_off_this_month: List[str] = field(default_factory=list)


def _validate(debts: List[Debt], monthly_budget: float) -> None:
    if not debts:
        raise ValueError("No debts provided")
    total_min = sum(d.min_payment for d in debts)
    if monthly_budget < total_min:
        raise ValueError(
            f"Budget ${monthly_budget:.2f} is below total minimums ${total_min:.2f}"
        )


def _run_simulation(priority_order: List[Debt], monthly_budget: float) -> dict:
    """
    Core payoff simulation. Debts must be pre-sorted in desired priority order.
    Each month: accrue interest → pay minimums → direct surplus at the first
    (highest-priority) debt that still carries a balance.
    """
    balances = {d.name: d.balance for d in priority_order}
    total_interest = 0.0
    schedule: List[_MonthSnapshot] = []
    paid_off_set: set = set()

    for month in range(1, 601):  # 50-year safety cap
        interest_this_month = 0.0

        for debt in priority_order:
            if balances[debt.name] <= 0:
                continue
            interest = balances[debt.name] * (debt.apr / 12)
            balances[debt.name] += interest
            interest_this_month += interest
            total_interest += interest

        remaining = monthly_budget

        for debt in priority_order:
            if balances[debt.name] <= 0:
                continue
            payment = min(debt.min_payment, balances[debt.name])
            balances[debt.name] = max(0.0, balances[debt.name] - payment)
            remaining -= payment

        # Avalanche/Snowball surplus: goes to the first live debt in priority order
        for debt in priority_order:
            if remaining <= 0:
                break
            if balances[debt.name] <= 0:
                continue
            payment = min(remaining, balances[debt.name])
            balances[debt.name] = max(0.0, balances[debt.name] - payment)
            remaining -= payment

        # Round sub-cent balances to zero to avoid infinite loops
        for name in balances:
            if balances[name] < 0.01:
                balances[name] = 0.0

        newly_paid = [
            name for name, bal in balances.items()
            if bal == 0 and name not in paid_off_set
        ]
        paid_off_set.update(newly_paid)

        schedule.append(
            _MonthSnapshot(
                month=month,
                balances={k: round(v, 2) for k, v in balances.items()},
                interest_charged=round(interest_this_month, 2),
                paid_off_this_month=newly_paid,
            )
        )

        if all(b == 0 for b in balances.values()):
            break

    payoff_order = [
        name
        for snap in schedule
        for name in snap.paid_off_this_month
    ]

    return {
        "months_to_payoff": len(schedule),
        "total_interest_paid": round(total_interest, 2),
        "payoff_order": payoff_order,
        "schedule": [
            {
                "month": s.month,
                "balances": s.balances,
                "interest_charged": s.interest_charged,
                "paid_off_this_month": s.paid_off_this_month,
            }
            for s in schedule
        ],
    }


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
