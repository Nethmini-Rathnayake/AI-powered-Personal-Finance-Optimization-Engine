import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.engine.avalanche import Debt, calculate_avalanche, compare_strategies
from src.ingestor.parser import parse_csv_text

st.set_page_config(page_title="FinOps Engine", layout="wide")

# ── Sidebar settings ──────────────────────────────────────────────────────────

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
st.caption("Debt payoff optimizer — Avalanche method + agentic AI advisor")

tab_manual, tab_csv, tab_ask = st.tabs(["Manual Input", "Upload CSV", "Ask AI"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def fmt(amount: float, sym: str) -> str:
    return f"{sym}{amount:,.2f}"


def df_to_debts(df: pd.DataFrame) -> list[Debt]:
    debts = []
    for _, row in df.iterrows():
        name = str(row.get("Name", "")).strip()
        if not name or name == "nan":
            continue
        try:
            promo_months_val = int(row.get("Promo Months", 0) or 0)
            promo_apr_raw = row.get("Promo APR (%)", None)
            promo_apr_val = None
            if promo_months_val > 0 and promo_apr_raw is not None and not pd.isna(promo_apr_raw):
                promo_apr_val = float(promo_apr_raw) / 100

            penalty_pct = float(row.get("Prepay Penalty (%)", 0.0) or 0.0)

            debts.append(Debt(
                name=name,
                balance=float(row["Balance"]),
                apr=float(row["APR (%)"]) / 100,
                min_payment=float(row["Min Payment"]),
                compounding=str(row.get("Compounding", "monthly") or "monthly"),
                min_payment_type=str(row.get("Min Pay Type", "fixed") or "fixed"),
                promo_apr=promo_apr_val,
                promo_months=promo_months_val,
                prepayment_penalty_type="percent" if penalty_pct > 0 else "none",
                prepayment_penalty_value=penalty_pct / 100,
                prepayment_penalty_months=int(row.get("Penalty Window (mo)", 0) or 0),
            ))
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
        pd.DataFrame(rows), x="Month", y="Balance", color="Debt", title=title,
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
            "Saved vs Snowball", fmt(saved, sym),
            delta=f"{abs(months_saved)} months faster" if months_saved > 0 else None,
        )

    penalties = avalanche.get("total_penalties_paid", 0)
    if penalties > 0:
        st.caption(f"Includes {fmt(penalties, sym)} in prepayment penalties.")

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


def render_tool_trace(trace: list[dict], sym: str) -> None:
    """Render the agent's tool call trace as structured UI components."""
    if not trace:
        return
    with st.expander(f"Agent reasoning — {len(trace)} tool call(s)"):
        for i, call in enumerate(trace, 1):
            tool = call["tool"]
            st.markdown(f"**{i}. `{tool}`**")

            if tool == "get_user_debts":
                debts_list = call["result"].get("debts", [])
                if debts_list:
                    display_cols = [c for c in ("name", "balance", "apr_percent", "min_payment") if c in debts_list[0]]
                    st.dataframe(
                        pd.DataFrame(debts_list)[display_cols],
                        use_container_width=True, hide_index=True,
                    )
                    st.caption(
                        f"Total balance: {fmt(call['result']['total_balance'], sym)}  |  "
                        f"Monthly minimums: {fmt(call['result']['total_monthly_minimums'], sym)}"
                    )
                else:
                    st.caption(call["result"].get("note", "No debts found."))

            elif tool == "run_avalanche_scenario":
                res = call["result"]
                if "error" in res:
                    st.error(res["error"])
                elif res.get("strategy") == "compare":
                    av, sn = res["avalanche"], res["snowball"]
                    c1, c2 = st.columns(2)
                    c1.metric("Avalanche months", av["months_to_payoff"])
                    c1.metric("Avalanche interest", fmt(av["total_interest"], sym))
                    c2.metric("Snowball months", sn["months_to_payoff"])
                    c2.metric("Snowball interest", fmt(sn["total_interest"], sym))
                    if res["interest_saved_by_avalanche"] > 0:
                        st.caption(
                            f"Avalanche saves {fmt(res['interest_saved_by_avalanche'], sym)} "
                            f"and {res['months_saved_by_avalanche']} month(s)."
                        )
                else:
                    c1, c2 = st.columns(2)
                    c1.metric("Months to payoff", res.get("months_to_payoff"))
                    c2.metric("Total interest", fmt(res.get("total_interest_paid", 0), sym))

            elif tool == "lookup_fee_clause":
                clauses = call["result"].get("clauses", [])
                if clauses:
                    for clause in clauses[:2]:
                        src = clause.get("source", "T&C")
                        pg = clause.get("page")
                        label = f"{src} p.{pg}" if pg is not None else src
                        st.caption(f"[{label}] {clause['content'][:280]}…")
                else:
                    st.caption(call["result"].get("note") or call["result"].get("error", "No clauses found."))

            if i < len(trace):
                st.divider()


# ── Manual Input ──────────────────────────────────────────────────────────────

with tab_manual:
    st.subheader("Your debts")

    default_df = pd.DataFrame([
        {"Name": "Credit Card A", "Balance": 5000.0,  "APR (%)": 23.99, "Min Payment": 100.0,
         "Compounding": "monthly", "Min Pay Type": "fixed",
         "Promo APR (%)": 0.0, "Promo Months": 0, "Prepay Penalty (%)": 0.0, "Penalty Window (mo)": 0},
        {"Name": "Credit Card B", "Balance": 2500.0,  "APR (%)": 19.99, "Min Payment": 50.0,
         "Compounding": "monthly", "Min Pay Type": "fixed",
         "Promo APR (%)": 0.0, "Promo Months": 0, "Prepay Penalty (%)": 0.0, "Penalty Window (mo)": 0},
        {"Name": "Student Loan",  "Balance": 15000.0, "APR (%)": 6.75,  "Min Payment": 150.0,
         "Compounding": "monthly", "Min Pay Type": "fixed",
         "Promo APR (%)": 0.0, "Promo Months": 0, "Prepay Penalty (%)": 0.0, "Penalty Window (mo)": 0},
    ])

    show_advanced = st.toggle("Show advanced loan terms", value=False)
    basic_cols = ["Name", "Balance", "APR (%)", "Min Payment"]
    advanced_cols = ["Compounding", "Min Pay Type", "Promo APR (%)", "Promo Months",
                     "Prepay Penalty (%)", "Penalty Window (mo)"]
    column_order = basic_cols + (advanced_cols if show_advanced else [])

    if show_advanced:
        st.caption(
            "**Compounding**: daily = (1 + r/365)^(365/12) − 1 per month.  \n"
            "**Min Pay Type**: *% of balance* — minimum shrinks as balance falls (credit-card style).  \n"
            "**Promo APR / Promo Months**: 0% for N months on a balance transfer.  \n"
            "**Prepay Penalty**: % of remaining balance charged when closing the debt early.  \n"
            "**Penalty Window**: 0 = always; N = first N months only."
        )

    debt_df = st.data_editor(
        default_df, num_rows="dynamic", use_container_width=True, column_order=column_order,
        column_config={
            "Balance": st.column_config.NumberColumn(f"Balance ({sym})", min_value=0.01, format=f"{sym}%.2f"),
            "APR (%)": st.column_config.NumberColumn("APR (%)", min_value=0.01, max_value=99.99, format="%.2f%%"),
            "Min Payment": st.column_config.NumberColumn(f"Min Payment ({sym})", min_value=0.01, format=f"{sym}%.2f"),
            "Compounding": st.column_config.SelectboxColumn("Compounding", options=["monthly", "daily"]),
            "Min Pay Type": st.column_config.SelectboxColumn("Min Pay Type", options=["fixed", "percent_of_balance"]),
            "Promo APR (%)": st.column_config.NumberColumn("Promo APR (%)", min_value=0.0, max_value=99.99, format="%.2f%%"),
            "Promo Months": st.column_config.NumberColumn("Promo Months", min_value=0),
            "Prepay Penalty (%)": st.column_config.NumberColumn("Prepay Penalty (%)", min_value=0.0, max_value=50.0, format="%.2f%%"),
            "Penalty Window (mo)": st.column_config.NumberColumn("Penalty Window (mo)", min_value=0),
        },
    )

    col_budget, col_compare = st.columns([2, 1])
    budget = col_budget.number_input(f"Monthly budget ({sym})", min_value=1.0, value=600.0, step=50.0)
    compare = col_compare.checkbox("Compare with Snowball", value=True)

    if st.button("Analyze", type="primary", key="analyze_manual"):
        debts = df_to_debts(debt_df)
        if not debts:
            st.error("Add at least one debt row.")
        else:
            st.session_state.current_debts = debts  # share with Ask AI tab
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
    budget_csv = st.number_input(f"Monthly budget ({sym})", min_value=1.0, value=600.0, step=50.0, key="csv_budget")

    if uploaded and st.button("Analyze CSV", type="primary"):
        try:
            debts = parse_csv_text(uploaded.read().decode("utf-8"))
            st.session_state.current_debts = debts  # share with Ask AI tab
            with st.spinner("Calculating..."):
                result = compare_strategies(debts, budget_csv)
            show_results(result["avalanche"], sym, result)
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Could not parse CSV: {exc}")


# ── Ask AI ────────────────────────────────────────────────────────────────────

with tab_ask:
    st.subheader("Ask your debt advisor")
    st.caption(
        "The agent calls tools autonomously: it fetches your portfolio, runs exact "
        "payoff math, and searches bank Terms & Conditions — then reasons across all "
        "three before answering."
    )

    if not os.getenv("ANTHROPIC_API_KEY"):
        st.warning("Set `ANTHROPIC_API_KEY` in your `.env` file to enable this tab.")
    else:
        current_debts: list[Debt] | None = st.session_state.get("current_debts")

        if current_debts:
            st.info(
                f"{len(current_debts)} debt(s) loaded from the input tab — "
                "the agent can access them via `get_user_debts()`."
            )
        else:
            st.caption("No debts loaded yet. Go to Manual Input or Upload CSV first, or ask a general question.")

        question = st.text_input(
            "Your question",
            placeholder="Which of my debts should I prioritise, and what will I save?",
        )

        if st.button("Ask", type="primary") and question:
            from src.rag.agent import run_agent

            with st.spinner("Agent is reasoning..."):
                try:
                    answer, trace = run_agent(question, current_debts)
                except Exception as exc:
                    st.error(f"Error: {exc}")
                    st.stop()

            st.write(answer)
            render_tool_trace(trace, sym)
