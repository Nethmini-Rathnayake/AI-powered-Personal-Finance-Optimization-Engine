import os
import sys

from dotenv import load_dotenv

load_dotenv()

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.engine.avalanche import Debt, calculate_avalanche, compare_strategies
from src.ingestor.parser import parse_csv_text

st.set_page_config(page_title="FinOps Engine", layout="wide")

# ── Currency selector ─────────────────────────────────────────────────────────

CURRENCIES: dict[str, str] = {
    "USD — US Dollar":         "$",
    "EUR — Euro":              "€",
    "GBP — British Pound":     "£",
    "AUD — Australian Dollar": "A$",
    "CAD — Canadian Dollar":   "C$",
    "JPY — Japanese Yen":      "¥",
    "INR — Indian Rupee":      "₹",
    "SGD — Singapore Dollar":  "S$",
    "LKR — Sri Lankan Rupee":  "Rs",
}

with st.sidebar:
    st.header("Settings")
    currency_label = st.selectbox("Currency", list(CURRENCIES.keys()))
    sym = CURRENCIES[currency_label]

st.title("FinOps Engine")
st.caption("Debt payoff optimizer — Avalanche method + RAG-powered advice")

tab_manual, tab_csv, tab_ask = st.tabs(["Manual Input", "Upload CSV", "Ask AI"])


# ── helpers ───────────────────────────────────────────────────────────────────

def fmt(amount: float, sym: str) -> str:
    return f"{sym}{amount:,.2f}"


def df_to_debts(df: pd.DataFrame) -> list[Debt]:
    debts = []
    for _, row in df.iterrows():
        name = str(row.get("Name", "")).strip()
        if not name or name == "nan":
            continue
        try:
            debts.append(
                Debt(
                    name=name,
                    balance=float(row["Balance"]),
                    apr=float(row["APR (%)"]) / 100,
                    min_payment=float(row["Min Payment"]),
                )
            )
        except (ValueError, TypeError):
            continue
    return debts


def balance_chart(result: dict, title: str, sym: str):
    rows = [
        {"Month": s["month"], "Debt": name, "Balance": bal}
        for s in result["schedule"]
        for name, bal in s["balances"].items()
    ]
    fig = px.line(
        pd.DataFrame(rows),
        x="Month",
        y="Balance",
        color="Debt",
        title=title,
        labels={"Balance": f"Balance ({sym})"},
    )
    fig.update_layout(hovermode="x unified", legend_title_text="")
    fig.update_traces(hovertemplate=f"{sym}%{{y:,.2f}}<extra>%{{fullData.name}}</extra>")
    return fig


def show_results(avalanche: dict, sym: str, comparison: dict | None = None) -> None:
    col1, col2, col3 = st.columns(3)
    col1.metric("Months to debt-free", avalanche["months_to_payoff"])
    col2.metric("Total interest (Avalanche)", fmt(avalanche["total_interest_paid"], sym))
    if comparison:
        saved = comparison["interest_saved_by_avalanche"]
        months_saved = comparison["months_saved_by_avalanche"]
        col3.metric(
            "Saved vs Snowball",
            fmt(saved, sym),
            delta=f"{abs(months_saved)} months faster" if months_saved > 0 else None,
        )

    st.plotly_chart(
        balance_chart(avalanche, "Balance Over Time — Avalanche", sym),
        use_container_width=True,
    )

    if avalanche["payoff_order"]:
        st.write("**Payoff order:** " + " → ".join(avalanche["payoff_order"]))

    if comparison:
        with st.expander("Avalanche vs Snowball side-by-side"):
            c1, c2 = st.columns(2)
            av, sn = comparison["avalanche"], comparison["snowball"]
            c1.metric("Avalanche — months", av["months_to_payoff"])
            c1.metric("Avalanche — interest", fmt(av["total_interest_paid"], sym))
            c1.plotly_chart(balance_chart(av, "Avalanche", sym), use_container_width=True)
            c2.metric("Snowball — months", sn["months_to_payoff"])
            c2.metric("Snowball — interest", fmt(sn["total_interest_paid"], sym))
            c2.plotly_chart(balance_chart(sn, "Snowball", sym), use_container_width=True)

    with st.expander("Full monthly schedule"):
        rows = [
            {"Month": s["month"], f"Interest ({sym})": s["interest_charged"], **s["balances"]}
            for s in avalanche["schedule"]
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True)


# ── Manual Input ──────────────────────────────────────────────────────────────

with tab_manual:
    st.subheader("Your debts")

    default_df = pd.DataFrame([
        {"Name": "Credit Card A", "Balance": 5000.0,  "APR (%)": 23.99, "Min Payment": 100.0},
        {"Name": "Credit Card B", "Balance": 2500.0,  "APR (%)": 19.99, "Min Payment": 50.0},
        {"Name": "Student Loan",  "Balance": 15000.0, "APR (%)": 6.75,  "Min Payment": 150.0},
    ])

    debt_df = st.data_editor(
        default_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Balance": st.column_config.NumberColumn(
                f"Balance ({sym})", min_value=0.01, format=f"{sym}%.2f"
            ),
            "APR (%)": st.column_config.NumberColumn(
                "APR (%)", min_value=0.01, max_value=99.99, format="%.2f%%"
            ),
            "Min Payment": st.column_config.NumberColumn(
                f"Min Payment ({sym})", min_value=0.01, format=f"{sym}%.2f"
            ),
        },
    )

    col_budget, col_compare = st.columns([2, 1])
    budget = col_budget.number_input(
        f"Monthly budget ({sym})", min_value=1.0, value=600.0, step=50.0
    )
    compare = col_compare.checkbox("Compare with Snowball", value=True)

    if st.button("Analyze", type="primary", key="analyze_manual"):
        debts = df_to_debts(debt_df)
        if not debts:
            st.error("Add at least one debt row.")
        else:
            try:
                with st.spinner("Calculating..."):
                    if compare:
                        result = compare_strategies(debts, budget)
                        show_results(result["avalanche"], sym, result)
                    else:
                        show_results(calculate_avalanche(debts, budget), sym)
            except ValueError as exc:
                st.error(str(exc))


# ── Upload CSV ────────────────────────────────────────────────────────────────

with tab_csv:
    st.subheader("Upload a bank statement CSV")
    st.caption(
        "Required columns: `name`, `balance`, `apr` (decimal e.g. 0.2399), `min_payment`  \n"
        "Try the sample file in `data/sample/sample_statement.csv`."
    )

    uploaded = st.file_uploader("Choose a CSV file", type=["csv"])
    budget_csv = st.number_input(
        f"Monthly budget ({sym})", min_value=1.0, value=600.0, step=50.0, key="csv_budget"
    )

    if uploaded and st.button("Analyze CSV", type="primary"):
        try:
            debts = parse_csv_text(uploaded.read().decode("utf-8"))
            with st.spinner("Calculating..."):
                result = compare_strategies(debts, budget_csv)
            show_results(result["avalanche"], sym, result)
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Could not parse CSV: {exc}")


# ── Ask AI ────────────────────────────────────────────────────────────────────

with tab_ask:
    st.subheader("Ask anything about your debts")
    st.caption(
        "Answers are grounded in bank Terms & Conditions indexed via `POST /index-pdf`.  \n"
        "Requires `ANTHROPIC_API_KEY` in your environment."
    )

    if not os.getenv("ANTHROPIC_API_KEY"):
        st.warning(
            "Set `ANTHROPIC_API_KEY` in your environment or `.env` file to enable this tab."
        )
    else:
        question = st.text_input(
            "Your question",
            placeholder="What fees apply if I miss a minimum payment?",
        )
        debt_context = st.text_area(
            "Optional: paste a plain-text summary of your debts",
            height=80,
        )

        if st.button("Ask", type="primary") and question:
            from src.rag.knowledge_base import answer_question

            with st.spinner("Retrieving relevant clauses and generating answer..."):
                try:
                    answer = answer_question(question, debt_context)
                    st.write(answer)
                except Exception as exc:
                    st.error(f"Error: {exc}")
