import os
import tempfile
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from prometheus_fastapi_instrumentator import Instrumentator

from src.engine.avalanche import Debt, calculate_avalanche, compare_strategies
from src.ingestor.parser import parse_csv_text, parse_pdf_statement
from src.rag.knowledge_base import answer_question, index_pdf

app = FastAPI(title="FinOps Engine", version="1.0.0")
Instrumentator().instrument(app).expose(app)


# --- Request / Response models ---

class DebtInput(BaseModel):
    name: str
    balance: float = Field(gt=0)
    apr: float = Field(gt=0, lt=1, description="Decimal rate, e.g. 0.2399 = 23.99%")
    min_payment: float = Field(gt=0)


class AnalyzeRequest(BaseModel):
    debts: List[DebtInput]
    monthly_budget: float = Field(gt=0)
    compare_with_snowball: bool = False


class AskRequest(BaseModel):
    question: str
    debt_context: Optional[str] = None


# --- Endpoints ---

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
def analyze_debts(req: AnalyzeRequest):
    """Run Debt Avalanche (and optionally compare with Snowball) on supplied debts."""
    debts = [Debt(d.name, d.balance, d.apr, d.min_payment) for d in req.debts]
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
    """RAG-powered Q&A grounded in indexed bank Terms & Conditions."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured")
    try:
        answer = answer_question(req.question, req.debt_context or "")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"answer": answer}


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
