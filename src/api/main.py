"""
FinOps Engine — FastAPI application.

Exposes five endpoints:
  GET  /health          liveness probe
  POST /analyze         Debt Avalanche payoff plan (JSON debt list)
  POST /analyze/csv     Debt Avalanche payoff plan (CSV file upload)
  POST /ask             Agentic debt advisor (Anthropic tool use)
  POST /index-pdf       Index a bank T&C PDF into the RAG knowledge base

Prometheus metrics are auto-exposed at /metrics via
prometheus-fastapi-instrumentator.
"""

import os
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from prometheus_fastapi_instrumentator import Instrumentator

from src.engine.avalanche import Debt, calculate_avalanche, compare_strategies
from src.ingestor.parser import parse_csv_text
from src.rag.agent import run_agent
from src.rag.knowledge_base import index_pdf

app = FastAPI(title="FinOps Engine", version="1.0.0")
Instrumentator().instrument(app).expose(app)


# ── Request / Response models ─────────────────────────────────────────────────

class DebtInput(BaseModel):
    """
    Input model for a single debt account.

    Attributes:
        name: Human-readable label, e.g. "Chase Sapphire Reserve".
        balance: Outstanding principal (must be > 0).
        apr: Annual percentage rate as a decimal (0.2399 = 23.99 %).
            Must be in the range (0, 1).
        min_payment: Minimum monthly payment or floor for percent-of-balance mode.
        compounding: "monthly" or "daily"; controls interest accrual formula.
        min_payment_type: "fixed" keeps payment constant; "percent_of_balance"
            shrinks the minimum as the balance falls.
        min_payment_percent: Fraction used when type is "percent_of_balance".
        promo_apr: Introductory rate as a decimal; None means no promo.
        promo_months: Number of months the promo rate applies.
        rate_changes: Scheduled APR adjustments as [[start_month, new_apr], …].
        prepayment_penalty_type: "none", "flat", or "percent".
        prepayment_penalty_value: Flat dollar amount or decimal fraction.
        prepayment_penalty_months: Penalty window; 0 = entire loan life.
    """

    name: str
    balance: float = Field(gt=0)
    apr: float = Field(gt=0, lt=1, description="Decimal rate, e.g. 0.2399 = 23.99%")
    min_payment: float = Field(gt=0)

    compounding: str = Field(default="monthly", pattern="^(monthly|daily)$")
    min_payment_type: str = Field(default="fixed", pattern="^(fixed|percent_of_balance)$")
    min_payment_percent: float = Field(default=0.02, ge=0.0, le=1.0)

    promo_apr: float | None = Field(default=None, ge=0.0, lt=1.0)
    promo_months: int = Field(default=0, ge=0)

    rate_changes: list[list[float]] = Field(default_factory=list)

    prepayment_penalty_type: str = Field(default="none", pattern="^(none|flat|percent)$")
    prepayment_penalty_value: float = Field(default=0.0, ge=0.0)
    prepayment_penalty_months: int = Field(default=0, ge=0)


class AnalyzeRequest(BaseModel):
    """
    Request body for the /analyze endpoint.

    Attributes:
        debts: One or more debt accounts to include in the simulation.
        monthly_budget: Total monthly payment available across all debts.
        compare_with_snowball: When True, the response includes both Avalanche
            and Snowball results with a side-by-side comparison.
    """

    debts: list[DebtInput]
    monthly_budget: float = Field(gt=0)
    compare_with_snowball: bool = False


class AskRequest(BaseModel):
    """
    Request body for the /ask endpoint.

    Attributes:
        question: Natural-language question for the debt advisor agent.
        debts: Optional debt portfolio made available to the agent via the
            ``get_user_debts`` tool.  Omit if no portfolio context is needed.
    """

    question: str
    debts: list[DebtInput] | None = None


def _to_debt(d: DebtInput) -> Debt:
    """Map a validated Pydantic DebtInput onto the engine's Debt dataclass."""
    return Debt(
        name=d.name,
        balance=d.balance,
        apr=d.apr,
        min_payment=d.min_payment,
        compounding=d.compounding,
        min_payment_type=d.min_payment_type,
        min_payment_percent=d.min_payment_percent,
        promo_apr=d.promo_apr,
        promo_months=d.promo_months,
        rate_changes=d.rate_changes,
        prepayment_penalty_type=d.prepayment_penalty_type,
        prepayment_penalty_value=d.prepayment_penalty_value,
        prepayment_penalty_months=d.prepayment_penalty_months,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe — returns ``{"status": "ok"}`` when the service is up."""
    return {"status": "ok"}


@app.post("/analyze")
def analyze_debts(req: AnalyzeRequest) -> dict[str, object]:
    """
    Run the Debt Avalanche payoff simulation on the supplied debt portfolio.

    Optionally compares Avalanche against the Snowball strategy when
    ``compare_with_snowball`` is True.

    Args:
        req: Debt portfolio, monthly budget, and comparison flag.

    Returns:
        Simulation result dict including months to payoff, total interest,
        payoff order, and full monthly schedule.  When ``compare_with_snowball``
        is True, both strategies are returned side-by-side.

    Raises:
        HTTPException 400: If the monthly budget is below total minimums.
    """
    debts = [_to_debt(d) for d in req.debts]
    try:
        if req.compare_with_snowball:
            return compare_strategies(debts, req.monthly_budget)
        return calculate_avalanche(debts, req.monthly_budget)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/analyze/csv")
async def analyze_from_csv(
    file: UploadFile = File(...),
    monthly_budget: float = 500.0,
) -> dict[str, object]:
    """
    Upload a CSV bank statement and receive a Debt Avalanche payoff plan.

    The CSV must contain columns: ``name``, ``balance``, ``apr`` (decimal),
    ``min_payment``.

    Args:
        file: Uploaded CSV file.
        monthly_budget: Total monthly payment available across all debts.

    Returns:
        Avalanche simulation result dict.

    Raises:
        HTTPException 422: If the CSV cannot be parsed.
        HTTPException 400: If the monthly budget is below total minimums.
    """
    content = (await file.read()).decode("utf-8")
    try:
        debts = parse_csv_text(content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"CSV parse error: {exc}")
    try:
        return calculate_avalanche(debts, monthly_budget)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/ask")
def ask(req: AskRequest) -> dict[str, object]:
    """
    Agentic debt advisor powered by Anthropic tool use.

    The model drives a multi-turn loop, calling tools autonomously before
    producing a final grounded answer.  The full tool-call trace is returned
    for auditability.

    Args:
        req: User question and optional debt portfolio.

    Returns:
        A dict with keys ``answer`` (str) and ``tool_trace`` (list of tool
        call records including name, inputs, and result).

    Raises:
        HTTPException 503: If ``ANTHROPIC_API_KEY`` is not set.
        HTTPException 500: If the agent encounters an unexpected error.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured")
    debts = [_to_debt(d) for d in req.debts] if req.debts else None
    try:
        answer, tool_trace = run_agent(req.question, debts)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"answer": answer, "tool_trace": tool_trace}


@app.post("/index-pdf")
async def index_document(file: UploadFile = File(...)) -> dict[str, object]:
    """
    Upload a bank Terms & Conditions PDF to index it into the RAG knowledge base.

    The PDF is chunked, embedded, and stored in ChromaDB so the agent's
    ``lookup_fee_clause`` tool can retrieve relevant clauses at query time.

    Args:
        file: Uploaded PDF file.

    Returns:
        A dict with keys ``status`` ("indexed"), ``chunks`` (int), and
        ``file`` (original filename).

    Raises:
        HTTPException 422: If the uploaded file is not a PDF.
        HTTPException 500: If indexing fails.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        chunks = index_pdf(tmp_path)
        return {"status": "indexed", "chunks": chunks, "file": file.filename}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        os.unlink(tmp_path)
