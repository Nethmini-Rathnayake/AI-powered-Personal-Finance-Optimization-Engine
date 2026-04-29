"""
Agentic debt advisor — Anthropic tool use, not a LangChain chain.

Claude drives a multi-turn loop, deciding when to call each tool and
chaining results across calls before producing a final grounded answer.

Tools
-----
get_user_debts          – structured debt portfolio from the session
run_avalanche_scenario  – exact payoff math via the Python engine
lookup_fee_clause       – semantic search of indexed bank T&C documents
"""

import json
import os
from typing import Optional

import anthropic

from src.engine.avalanche import (
    Debt,
    calculate_avalanche,
    calculate_snowball,
    compare_strategies,
)

# ── Tool schemas ──────────────────────────────────────────────────────────────

_TOOLS = [
    {
        "name": "get_user_debts",
        "description": (
            "Returns the user's current debt portfolio as structured data. "
            "Call this first when the user asks about 'my debts', 'my situation', "
            "or any personalised question about their specific accounts."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "run_avalanche_scenario",
        "description": (
            "Runs the Debt Avalanche or Snowball payoff simulation against the "
            "Python math engine. Returns months to debt-free, total interest paid, "
            "payoff order, and prepayment penalties. "
            "Use this for any question about payoff timelines, interest savings, "
            "strategy comparison, or 'what-if' scenarios (different budgets, "
            "extra lump-sum payments, balance transfers)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "debts": {
                    "type": "array",
                    "description": "Debts to simulate. Call get_user_debts first if not yet known.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name":         {"type": "string"},
                            "balance":      {"type": "number"},
                            "apr":          {"type": "number", "description": "Decimal — 0.2399 = 23.99%"},
                            "min_payment":  {"type": "number"},
                            "compounding":  {"type": "string", "enum": ["monthly", "daily"]},
                            "promo_apr":    {"type": "number", "description": "Intro rate decimal; omit if none"},
                            "promo_months": {"type": "integer", "description": "Months the promo rate applies"},
                        },
                        "required": ["name", "balance", "apr", "min_payment"],
                    },
                },
                "monthly_budget": {"type": "number"},
                "strategy": {
                    "type": "string",
                    "enum": ["avalanche", "snowball", "compare"],
                    "description": (
                        "avalanche = highest APR first (minimises interest), "
                        "snowball = lowest balance first (psychological wins), "
                        "compare = run both and show the difference"
                    ),
                },
            },
            "required": ["debts", "monthly_budget"],
        },
    },
    {
        "name": "lookup_fee_clause",
        "description": (
            "Searches the indexed bank Terms & Conditions for relevant clauses. "
            "Use for questions about fees, penalties, grace periods, APR triggers, "
            "minimum payment rules, cash-advance rates, or any bank-specific policy. "
            "Call multiple times with different queries to cover different aspects."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language query, e.g. 'late payment fee', 'cash advance APR'",
                },
                "k": {
                    "type": "integer",
                    "description": "Number of clauses to retrieve, 1–8. Default 4.",
                },
            },
            "required": ["query"],
        },
    },
]

_SYSTEM = """\
You are an expert financial advisor specialising in personal debt management and consumer credit.

You have three tools:
- get_user_debts          → retrieve the user's actual portfolio
- run_avalanche_scenario  → run the precise Debt Avalanche / Snowball math engine
- lookup_fee_clause       → search indexed bank Terms & Conditions

Rules:
1. Never guess numbers. Always call run_avalanche_scenario for payoff calculations.
2. For personalised questions, call get_user_debts first, then run the scenario with those debts.
3. For fee / policy questions, call lookup_fee_clause — multiple times if needed.
4. You may chain tool calls freely: e.g. get debts → run scenario → look up related penalties.
5. Cite exact numbers from tool results. State the strategy and budget used.
6. If the knowledge base is empty, say so and answer from general financial knowledge.
"""


# ── Tool executor ─────────────────────────────────────────────────────────────

def _execute_tool(name: str, inputs: dict, debts: Optional[list[Debt]]) -> dict:
    """Dispatch one tool call and return a JSON-serialisable result dict."""

    # ── get_user_debts ────────────────────────────────────────────────────────
    if name == "get_user_debts":
        if not debts:
            return {
                "debts": [],
                "note": "No debt portfolio loaded. User has not entered debts in this session.",
            }
        return {
            "debts": [
                {
                    "name": d.name,
                    "balance": d.balance,
                    "apr_percent": round(d.apr * 100, 4),
                    "min_payment": d.min_payment,
                    "compounding": d.compounding,
                    "promo_apr_percent": round(d.promo_apr * 100, 4) if d.promo_apr is not None else None,
                    "promo_months_remaining": d.promo_months,
                }
                for d in debts
            ],
            "total_balance": round(sum(d.balance for d in debts), 2),
            "total_monthly_minimums": round(sum(d.min_payment for d in debts), 2),
        }

    # ── run_avalanche_scenario ────────────────────────────────────────────────
    if name == "run_avalanche_scenario":
        try:
            debt_objs = [
                Debt(
                    name=d["name"],
                    balance=float(d["balance"]),
                    apr=float(d["apr"]),
                    min_payment=float(d["min_payment"]),
                    compounding=d.get("compounding", "monthly"),
                    promo_apr=d.get("promo_apr"),
                    promo_months=int(d.get("promo_months", 0)),
                )
                for d in inputs["debts"]
            ]
            budget = float(inputs["monthly_budget"])
            strategy = inputs.get("strategy", "avalanche")

            if strategy == "compare":
                r = compare_strategies(debt_objs, budget)
                av, sn = r["avalanche"], r["snowball"]
                return {
                    "strategy": "compare",
                    "avalanche": {
                        "months_to_payoff": av["months_to_payoff"],
                        "total_interest": av["total_interest_paid"],
                        "total_penalties": av["total_penalties_paid"],
                        "payoff_order": av["payoff_order"],
                    },
                    "snowball": {
                        "months_to_payoff": sn["months_to_payoff"],
                        "total_interest": sn["total_interest_paid"],
                        "total_penalties": sn["total_penalties_paid"],
                        "payoff_order": sn["payoff_order"],
                    },
                    "interest_saved_by_avalanche": r["interest_saved_by_avalanche"],
                    "months_saved_by_avalanche": r["months_saved_by_avalanche"],
                }

            run_fn = calculate_avalanche if strategy != "snowball" else calculate_snowball
            r = run_fn(debt_objs, budget)
            return {
                "strategy": strategy,
                "months_to_payoff": r["months_to_payoff"],
                "total_interest_paid": r["total_interest_paid"],
                "total_penalties_paid": r["total_penalties_paid"],
                "payoff_order": r["payoff_order"],
                # First 3 months so Claude can verify the math makes sense
                "first_3_months": r["schedule"][:3],
            }

        except ValueError as exc:
            return {"error": str(exc)}

    # ── lookup_fee_clause ─────────────────────────────────────────────────────
    if name == "lookup_fee_clause":
        try:
            from src.rag.knowledge_base import get_vector_store
            k = min(int(inputs.get("k", 4)), 8)
            docs = get_vector_store().similarity_search(inputs["query"], k=k)
            if not docs:
                return {
                    "clauses": [],
                    "note": "Knowledge base is empty. Upload bank T&C PDFs via POST /index-pdf.",
                }
            return {
                "clauses": [
                    {
                        "content": doc.page_content,
                        "source": doc.metadata.get("source", "unknown"),
                        "page": doc.metadata.get("page"),
                    }
                    for doc in docs
                ]
            }
        except Exception as exc:
            return {"error": str(exc), "clauses": []}

    return {"error": f"Unknown tool: {name}"}


# ── Agentic loop ──────────────────────────────────────────────────────────────

def run_agent(
    question: str,
    debts: Optional[list[Debt]] = None,
    max_iterations: int = 10,
) -> tuple[str, list[dict]]:
    """
    Run the debt advisor agent and return (final_answer, tool_call_trace).

    Implements the Anthropic multi-turn tool use protocol:
      user → assistant (tool_use) → user (tool_result) → … → assistant (end_turn)

    Prompt caching is applied to the static system prompt and tool definitions
    so repeated calls within the 5-minute TTL window hit the cache.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Cache the system prompt and all tool definitions (static across calls)
    tools_with_cache = [
        *_TOOLS[:-1],
        {**_TOOLS[-1], "cache_control": {"type": "ephemeral"}},
    ]
    system = [{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}]

    messages: list[dict] = [{"role": "user", "content": question}]
    tool_trace: list[dict] = []

    for _ in range(max_iterations):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system,
            tools=tools_with_cache,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            answer = next(
                (b.text for b in response.content if hasattr(b, "text")), ""
            )
            return answer, tool_trace

        if response.stop_reason != "tool_use":
            break

        # Append the assistant turn (includes both text and tool_use blocks)
        messages.append({"role": "assistant", "content": response.content})

        # Execute every tool call in this turn and collect results
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = _execute_tool(block.name, block.input, debts)
            tool_trace.append({"tool": block.name, "input": block.input, "result": result})
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, default=str),
            })

        messages.append({"role": "user", "content": tool_results})

    # Safety fallback — return the last text seen if the loop cap was hit
    for msg in reversed(messages):
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if hasattr(block, "text") and block.text:
                    return block.text, tool_trace

    return "Agent did not produce a final answer within the iteration limit.", tool_trace
