<div align="center">

<img src="https://img.shields.io/badge/FinOps_Engine-v1.0.0-0a0a0a?style=for-the-badge&logo=lightning&logoColor=00ff88" alt="version"/>

# FinOps Engine
### *Debt Payoff Optimizer with Agentic AI Advisor*

> **Stop paying the interest tax.**  
> FinOps Engine turns your debt portfolio into a mathematically optimal payoff plan — then lets an AI advisor reason over it in plain English.

<br/>

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Anthropic](https://img.shields.io/badge/Anthropic-Claude_Sonnet-D97706?style=flat-square)](https://anthropic.com)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Store-FF6B35?style=flat-square)](https://trychroma.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![Prometheus](https://img.shields.io/badge/Prometheus-Metrics-E6522C?style=flat-square&logo=prometheus&logoColor=white)](https://prometheus.io)
[![Security](https://img.shields.io/badge/SAST-Bandit_+_pip--audit-red?style=flat-square&logo=shield&logoColor=white)]()
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

<br/>

[Features](#-key-features) · [Architecture](#-architecture) · [Quick Start](#-quick-start) · [API Docs](#-api-reference) · [DevSecOps](#-devsecops) · [Roadmap](#-roadmap)

</div>

---

## What Is FinOps Engine?

**FinOps Engine** is a personal finance tool built at the intersection of software engineering, AI, and DevSecOps. It combines a deterministic debt math engine with an agentic AI advisor that reasons across your actual portfolio.

| Layer | What It Does | Why It Matters |
|-------|-------------|----------------|
| **Math Engine** | Full amortization — daily compounding, promo APRs, prepayment penalties | 100% deterministic, no approximation |
| **Agentic AI** | Claude Sonnet calls tools autonomously before answering | Grounded answers, not hallucinations |
| **RAG Pipeline** | Semantic search over bank Terms & Conditions PDFs | Cites the actual clause, not the internet |
| **DevSecOps** | Bandit + pip-audit + Docker + Prometheus on every build | Production-grade from day one |

---

## Key Features

### Debt Avalanche & Snowball Optimizer

Two mathematically sound repayment strategies, run side-by-side with a full month-by-month schedule:

| Strategy | Attack Order | Best For |
|----------|-------------|----------|
| **Debt Avalanche** | Highest APR first | Minimising total interest paid |
| **Debt Snowball** | Smallest balance first | Psychological momentum |

The engine supports the full range of real-world loan terms:

- **Daily or monthly compounding** — matches how credit cards actually accrue interest
- **Percent-of-balance minimums** — minimum shrinks as the balance falls (credit-card style)
- **Promotional / intro APRs** — 0% balance-transfer offers with a countdown
- **Variable-rate schedules** — ARM-style rate jumps at a specified month
- **Prepayment penalties** — flat or percent-of-balance, with an optional window

### Agentic AI Advisor

The "Ask AI" tab connects to Claude claude-sonnet-4-6 via Anthropic's native tool-use API. The agent drives a multi-turn reasoning loop — it decides autonomously which tools to call and chains results before answering.

```
User  → "Which of my debts should I pay first, and what will I save?"

Agent → [calls get_user_debts]          ← loads your portfolio
      → [calls run_avalanche_scenario]  ← runs exact payoff math
      → [calls lookup_fee_clause]       ← checks T&C for penalty clauses
      → Final answer with cited numbers and source page references
```

**Three tools available to the agent:**

| Tool | What It Does |
|------|-------------|
| `get_user_debts` | Returns the user's loaded portfolio as structured data |
| `run_avalanche_scenario` | Runs Avalanche / Snowball / compare against the Python engine |
| `lookup_fee_clause` | Semantic search over indexed bank T&C PDFs |

Prompt caching is applied to the system prompt and tool definitions — repeated questions within the 5-minute TTL window cost significantly fewer tokens.

### Multi-Currency Support

The Streamlit UI supports 9 currencies out of the box: USD, EUR, GBP, AUD, CAD, JPY, INR, SGD, and LKR. All balances, interest totals, and chart labels update automatically.

### RAG Knowledge Base

Upload any bank Terms & Conditions PDF via `POST /index-pdf`. The document is chunked, embedded with `sentence-transformers`, and stored in ChromaDB. The agent's `lookup_fee_clause` tool then retrieves relevant clauses at query time — so answers about fees, penalty APRs, and grace periods are grounded in the actual document.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│               Streamlit UI  (app.py)                    │
│   Manual Input │ Upload CSV │ Ask AI                    │
└──────────────────────┬──────────────────────────────────┘
                       │  Python imports
┌──────────────────────▼──────────────────────────────────┐
│              FastAPI Backend  :8000                      │
│                                                         │
│   /analyze   /analyze/csv   /ask   /index-pdf           │
│       │            │          │         │               │
│   ┌───▼────┐  ┌────▼───┐  ┌──▼──────┐  │               │
│   │ Debt   │  │ CSV    │  │Agentic  │  │               │
│   │ Engine │  │ Parser │  │Advisor  │  │               │
│   └───┬────┘  └────────┘  └──┬──────┘  │               │
└───────┼─────────────────────┼──────────┼───────────────┘
        │                     │          │
        │              ┌──────▼──────┐   │
        │              │ Anthropic   │   │
        │              │ Claude API  │   │
        │              └─────────────┘   │
        │                               │
        │              ┌────────────────▼──────────┐
        │              │  ChromaDB  (local persist) │
        │              │  Bank PDF embeddings        │
        │              └───────────────────────────-┘
        │
 Pure Python math
 (no external dep)
```

### Data Flow

```
Manual input / CSV upload
        │
        ▼
src/ingestor/parser.py  ──►  list[Debt]
        │
        ▼
src/engine/avalanche.py ──►  Avalanche plan  ──►  JSON / Streamlit UI
                        └──►  Snowball plan   ──►  JSON / Streamlit UI

User question (Ask AI tab)
        │
        ▼
src/rag/agent.py  ──►  multi-turn tool loop  ──►  grounded answer + trace
```

---

## Project Structure

```
AI-powered-Personal-Finance-Optimization-Engine/
│
├── app.py                     # Streamlit UI entry point
│
├── src/
│   ├── api/
│   │   └── main.py            # FastAPI app (5 endpoints + Prometheus)
│   ├── engine/
│   │   └── avalanche.py       # Full amortization math engine
│   ├── ingestor/
│   │   └── parser.py          # CSV bank statement parser
│   └── rag/
│       ├── agent.py           # Anthropic tool-use agentic loop
│       └── knowledge_base.py  # ChromaDB PDF indexing & search
│
├── tests/
│   ├── test_avalanche.py      # Financial math unit tests
│   ├── test_api.py            # FastAPI endpoint tests
│   ├── test_agent.py          # Agent tool dispatch tests
│   └── test_ingestor.py       # CSV parser tests
│
├── .github/
│   └── workflows/
│       └── ci.yml             # Lint → Security → Test → Docker build
│
├── Dockerfile                 # Non-root, multi-stage container
├── docker-compose.yml         # App + Prometheus
├── prometheus.yml             # Prometheus scrape config
├── requirements.txt           # All dependencies pinned
├── pyproject.toml             # pytest + bandit config
├── .env.example               # Template — never commit .env
└── LICENSE                    # MIT
```

---

## Quick Start

### Prerequisites

- **Python 3.11+**
- An **Anthropic API key** (for the Ask AI tab and `/ask` endpoint)
- **Docker** & Docker Compose (optional — for containerised deployment)

### 1. Clone the Repository

```bash
git clone https://github.com/Nethmini-Rathnayake/AI-powered-Personal-Finance-Optimization-Engine.git
cd AI-powered-Personal-Finance-Optimization-Engine
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your key:
# ANTHROPIC_API_KEY=sk-ant-...
```

### 3a. Run Locally (Streamlit UI)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# Start the Streamlit UI
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) — the UI loads immediately. The Ask AI tab activates once `ANTHROPIC_API_KEY` is set.

### 3b. Run the FastAPI Backend

```bash
uvicorn src.api.main:app --reload --port 8000
```

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Prometheus metrics | http://localhost:8000/metrics |

### 3c. Run with Docker

```bash
docker compose up --build
```

This starts the FastAPI backend on `:8000` and Prometheus on `:9090`.

---

## API Reference

### `POST /analyze`

Run Avalanche (and optionally Snowball) on a JSON debt list.

```json
// Request
{
  "debts": [
    {
      "name": "Chase Sapphire",
      "balance": 5400,
      "apr": 0.2399,
      "min_payment": 50,
      "compounding": "daily",
      "promo_apr": 0.0,
      "promo_months": 6
    },
    {
      "name": "Student Loan",
      "balance": 15000,
      "apr": 0.0675,
      "min_payment": 150
    }
  ],
  "monthly_budget": 600,
  "compare_with_snowball": true
}

// Response (compare_with_snowball=true)
{
  "avalanche": {
    "months_to_payoff": 38,
    "total_interest_paid": 1842.17,
    "total_penalties_paid": 0.0,
    "payoff_order": ["Chase Sapphire", "Student Loan"],
    "schedule": [...]
  },
  "snowball": { ... },
  "interest_saved_by_avalanche": 63.44,
  "months_saved_by_avalanche": 1
}
```

### `POST /analyze/csv`

Upload a CSV file and receive an Avalanche payoff plan.

Required CSV columns: `name`, `balance`, `apr` (decimal, e.g. `0.2399`), `min_payment`

```bash
curl -X POST http://localhost:8000/analyze/csv \
  -F "file=@my_debts.csv" \
  -F "monthly_budget=600"
```

### `POST /ask`

Ask the agentic AI advisor a natural-language question.

```json
// Request
{
  "question": "Which of my debts should I prioritise, and what will I save?",
  "debts": [
    { "name": "Chase Sapphire", "balance": 5400, "apr": 0.2399, "min_payment": 50 },
    { "name": "Student Loan",   "balance": 15000, "apr": 0.0675, "min_payment": 150 }
  ]
}

// Response
{
  "answer": "Based on the Avalanche strategy with a $600 budget, you should prioritise Chase Sapphire (23.99% APR)...",
  "tool_trace": [
    { "tool": "get_user_debts",         "input": {}, "result": {...} },
    { "tool": "run_avalanche_scenario", "input": {...}, "result": {...} }
  ]
}
```

### `POST /index-pdf`

Index a bank Terms & Conditions PDF into ChromaDB.

```bash
curl -X POST http://localhost:8000/index-pdf \
  -F "file=@Chase_CC_Terms_2024.pdf"

# Response
{ "status": "indexed", "chunks": 142, "file": "Chase_CC_Terms_2024.pdf" }
```

### `GET /health`

Liveness probe — returns `{"status": "ok"}`.

---

## DevSecOps

Every push to `main` triggers the full CI pipeline:

```
Push / Pull Request
       │
       ▼
 ┌─────────────────────────────┐
 │  Security Scan              │
 │  ├── bandit  (SAST)         │
 │  └── pip-audit (CVE check)  │
 └──────────┬──────────────────┘
            │ PASS
            ▼
 ┌─────────────────────────────┐
 │  Test Suite                 │
 │  └── pytest -v              │
 └──────────┬──────────────────┘
            │ PASS
            ▼
 ┌─────────────────────────────┐
 │  Docker Build               │
 │  └── Build & tag image      │
 └─────────────────────────────┘
```

**Security principles:**

- **No hardcoded secrets** — API key loaded from `.env`, never committed
- **Non-root Docker container** — runs as `appuser` (principle of least privilege)
- **Pinned dependencies** — all versions locked in `requirements.txt`
- **SAST on every push** — Bandit scans for Python security issues
- **CVE auditing** — pip-audit checks packages against known vulnerabilities
- **Prometheus observability** — request latency and error rates tracked at `/metrics`

---

## Running Tests

```bash
# Full test suite
pytest tests/ -v

# Financial math only
pytest tests/test_avalanche.py -v

# API endpoint tests
pytest tests/test_api.py -v

# Run security scan locally
bandit -r src/
pip-audit -r requirements.txt
```

---

## Tech Stack

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Language** | Python 3.11 | Core runtime |
| **UI** | Streamlit + Plotly | Interactive dashboard with charts |
| **API Framework** | FastAPI + Uvicorn + Pydantic | REST endpoints + auto Swagger docs |
| **AI Agent** | Anthropic SDK (Claude claude-sonnet-4-6) | Multi-turn tool use with prompt caching |
| **Debt Math** | Pure Python | Deterministic full amortization engine |
| **Vector Store** | ChromaDB + sentence-transformers | Embedding storage & semantic search |
| **PDF Parsing** | pypdf + pymupdf | Bank T&C document ingestion |
| **Observability** | Prometheus | Request metrics via FastAPI instrumentator |
| **Containerization** | Docker + Compose | Reproducible environments |
| **CI/CD** | GitHub Actions | Automated security → test → build pipeline |
| **SAST** | Bandit | Python static security analysis |
| **Dependency Audit** | pip-audit | CVE checks on all packages |

---

## Roadmap

- [x] Avalanche & Snowball optimizer with full amortization
- [x] Daily/monthly compounding, promo APRs, prepayment penalties
- [x] Agentic AI advisor (Anthropic tool use, multi-turn reasoning)
- [x] RAG knowledge base (ChromaDB + bank T&C PDFs)
- [x] Streamlit UI with interactive Plotly charts
- [x] Multi-currency support (USD, EUR, GBP, AUD, CAD, JPY, INR, SGD, LKR)
- [x] FastAPI backend with CSV upload
- [x] Dockerized with Prometheus observability
- [x] CI/CD with SAST and CVE scanning
- [ ] **Plaid API integration** — live bank account syncing
- [ ] **React dashboard** — replace Streamlit for production deployments
- [ ] **Scheduler** — monthly automated payoff progress reports

---

## Contributing

```bash
# 1. Fork the repo and clone your fork
git clone https://github.com/Nethmini-Rathnayake/AI-powered-Personal-Finance-Optimization-Engine.git

# 2. Create a feature branch
git checkout -b feat/your-feature-name

# 3. Install dependencies and run tests
pip install -r requirements.txt
pytest tests/ -v

# 4. Commit using Conventional Commits
git commit -m "feat: add your feature"

# 5. Push and open a Pull Request
git push origin feat/your-feature-name
```

---

## License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

---

<div align="center">

**Built by [Nethmini Rathnayake](https://github.com/Nethmini-Rathnayake)**

*Demonstrating Software Engineering + AI + DevSecOps skills in the Fintech domain*

Star this repo if it helped you — it means a lot!

</div>
