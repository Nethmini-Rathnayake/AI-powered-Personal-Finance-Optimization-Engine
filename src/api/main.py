import os
import tempfile
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from prometheus_fastapi_instrumentator import Instrumentator

from src.engine.avalanche import Debt, calculate_avalanche, compare_strategies
from src.ingestor.parser import parse_csv_text
from src.rag.agent import run_agent
from src.rag.knowledge_base import index_pdf

app = FastAPI(title="FinOps Engine", version="1.0.0")
Instrumentator().instrument(app).expose(app)


# --- Request / Response models ---

class DebtInput(BaseModel):
    name: str
    balance: float = Field(gt=0)
    apr: float = Field(gt=0, lt=1, description="Decimal rate, e.g. 0.2399 = 23.99%")
    min_payment: float = Field(gt=0)

    compounding: str = Field(default="monthly", pattern="^(monthly|daily)$")
    min_payment_type: str = Field(default="fixed", pattern="^(fixed|percent_of_balance)$")
    min_payment_percent: float = Field(default=0.02, ge=0.0, le=1.0)

    promo_apr: Optional[float] = Field(default=None, ge=0.0, lt=1.0)
    promo_months: int = Field(default=0, ge=0)

    rate_changes: List[List[float]] = Field(default_factory=list)

    prepayment_penalty_type: str = Field(default="none", pattern="^(none|flat|percent)$")
    prepayment_penalty_value: float = Field(default=0.0, ge=0.0)
    prepayment_penalty_months: int = Field(default=0, ge=0)


class AnalyzeRequest(BaseModel):
    debts: List[DebtInput]
    monthly_budget: float = Field(gt=0)
    compare_with_snowball: bool = False


class AskRequest(BaseModel):
    question: str
    debts: Optional[List[DebtInput]] = None   # portfolio for the agent's get_user_debts tool


def _to_debt(d: DebtInput) -> Debt:
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


# --- Endpoints ---

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
def analyze_debts(req: AnalyzeRequest):
    """Run Debt Avalanche (and optionally compare with Snowball) on supplied debts."""
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
):
    """Upload a CSV statement and receive a Debt Avalanche payoff plan."""
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
def ask(req: AskRequest):
    """
    Agentic debt advisor — Claude calls tools autonomously to answer the question.
    Returns the final answer and the full tool-call trace for auditability.
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
async def index_document(file: UploadFile = File(...)):
    """Upload a bank T&C PDF to index it into the RAG knowledge base."""
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
