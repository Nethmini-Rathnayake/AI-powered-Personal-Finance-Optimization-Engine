<div align="center">

<img src="https://img.shields.io/badge/FinOps_Engine-v1.0.0-0a0a0a?style=for-the-badge&logo=lightning&logoColor=00ff88" alt="version"/>

# 💳 FinOps Engine
### *Cloud-Native Financial Operations & Intelligent Debt Orchestration*

> **Stop paying the Interest Tax.**
> FinOps Engine bridges the gap between messy real-world transactions and mathematically optimal debt repayment — powered by deterministic algorithms and RAG-grounded AI.

<br/>

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-0.2-1C3C3C?style=flat-square&logo=chainlink&logoColor=white)](https://langchain.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Store-FF6B35?style=flat-square)](https://trychroma.com)
[![CI/CD](https://img.shields.io/badge/CI/CD-GitHub_Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![Security](https://img.shields.io/badge/SAST-Bandit_+_Safety-red?style=flat-square&logo=shield&logoColor=white)]()
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

<br/>

[Features](#-key-features) · [Architecture](#-architecture) · [Quick Start](#-quick-start) · [API Docs](#-api-reference) · [DevSecOps](#️-devsecops-fortress) · [Roadmap](#-roadmap)

</div>

---

## 🧠 What Is FinOps Engine?

**FinOps Engine** is a cloud-native financial operations tool built for the intersection of **software engineering**, **NLP**, and **DevSecOps**.

Unlike generic chatbots that hallucinate financial advice, FinOps Engine uses a hybrid approach:

| Layer | What It Does | Why It Matters |
|-------|-------------|----------------|
| 🔤 **NLP Engine** | Maps `"AMZN Mktp US*2B3K9"` → `"Shopping"` | Turns noise into structured data |
| 📚 **RAG Pipeline** | Answers *"Why did my APR change?"* from actual bank PDFs | Grounded, not hallucinated |
| 📐 **Optimizer** | Runs Avalanche & Snowball algorithms in pure Python | 100% deterministic math |
| 🔐 **DevSecOps** | Bandit + Safety + GitHub Actions on every push | Production-grade security |

---

## 🚀 Key Features

### 🔤 Intelligent Transaction Mapping
Uses an LLM to categorize unstructured bank transaction descriptions into clean financial clusters — turning raw statement noise into actionable spending intelligence.

```
"AMZN Mktp US*2B3K9"     →  🛒 Shopping
"UBER *TRIP 4F9D"         →  🚗 Travel & Transport
"NETFLIX.COM"             →  📺 Subscriptions
"ATM CASH ADVANCE 0041"   →  💸 Cash Advance  [⚠ HIGH RISK]
```

### 📚 Grounded RAG (Retrieval-Augmented Generation)
When a user asks *"Why did my interest go up?"*, the RAG engine searches the bank's actual Terms & Conditions PDF — not the open internet — and returns an answer with source citations.

```
User  →  "What triggers a penalty APR on my Chase card?"
RAG   →  [Searches: Chase_CC_Terms_2024.pdf]
      →  "Per Section 4.2, a penalty APR of 29.99% may apply if
          you make a late payment..." [Source: Page 11]
```

### 📐 Deterministic Debt Optimizer
Two mathematically sound repayment strategies, implemented in pure Python with zero approximation:

| Strategy | Attack Order | Best For |
|----------|-------------|----------|
| **Debt Avalanche** ⚡ | Highest APR first | Minimizing total interest paid |
| **Debt Snowball** ❄️ | Smallest balance first | Psychological momentum & quick wins |

The API returns both side-by-side with projected payoff dates, total interest, and month-by-month schedules.

### 🔐 DevSecOps Ready
Built with a **security-first** mindset required in Fintech:
- **Zero hardcoded secrets** — all API keys managed via HashiCorp Vault
- **SAST on every push** — Bandit scans for Python CVEs automatically
- **Dependency auditing** — Safety checks all packages against CVE databases
- **Non-root Docker containers** — principle of least privilege enforced

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client / Browser                         │
│                    React / Streamlit UI :3000                   │
└──────────────────────────────┬──────────────────────────────────┘
                               │  REST / JSON
┌──────────────────────────────▼──────────────────────────────────┐
│                    FastAPI Backend :8000                         │
│                                                                  │
│   ┌──────────────┐   ┌───────────────┐   ┌──────────────────┐  │
│   │  NLP Service │   │  RAG Pipeline │   │  Debt Optimizer  │  │
│   │ (Categorizer)│   │ (LangChain)   │   │ Avalanche/Snowbal│  │
│   └──────┬───────┘   └──────┬────────┘   └──────────────────┘  │
└──────────┼─────────────────┼─────────────────────────────────── ┘
           │                 │
  ┌────────▼───────┐  ┌──────▼────────────────────┐
  │  LLM API       │  │  ChromaDB Vector DB :8001  │
  │  (via Vault)   │  │  Bank PDF embeddings       │
  └────────────────┘  └───────────────────────────-┘
```

### Data Flow

```
Raw CSV Statement
       │
       ▼
data_processor.py  ──►  Cleaned DataFrame  ──►  Risk Segments
       │
       ▼
nlp_categorizer.py ──►  "AMZN" → "Shopping"
       │
       ▼
optimizer.py       ──►  Avalanche Plan  ──►  JSON Response
                   └──►  Snowball Plan  ──►  JSON Response
```

---

## 📂 Project Structure

```
FinOps-Engine/
│
├── 📁 data/
│   ├── raw/                    # Kaggle CC dataset (not committed)
│   ├── processed/              # Cleaned CSVs (not committed)
│   └── bank_pdfs/             # T&C source documents for RAG
│
├── 📁 src/
│   ├── data_processor.py      # Data cleaning & feature engineering
│   ├── rag_engine.py          # ChromaDB + LangChain RAG pipeline
│   ├── optimizer.py           # Avalanche & Snowball algorithms
│   └── main.py                # FastAPI app entry point
│
├── 📁 tests/
│   ├── test_optimizer.py      # Unit tests for financial math
│   ├── test_rag.py            # RAG retrieval accuracy tests
│   └── conftest.py            # Pytest fixtures
│
├── 📁 .github/
│   └── workflows/
│       └── ci.yml             # Lint → Security scan → Docker build
│
├── 🐳 Dockerfile              # Non-root, multi-stage container
├── 🐳 docker-compose.yml      # Backend + ChromaDB orchestration
├── 📋 requirements.txt        # All dependencies pinned
├── 🔒 .env.example            # Template — never commit .env
├── 📖 README.md               # You are here
└── 📄 LICENSE                 # MIT
```

---

## ⚡ Quick Start

### Prerequisites
- **Docker** & Docker Compose
- **Python 3.11+** (for local dev)
- An **OpenAI** or **Gemini Pro** API key

### 1. Clone the Repository

```bash
git clone https://github.com/Nethmini-Rathnayake/FinOps-Engine.git
cd FinOps-Engine
```

### 2. Configure Environment

```bash
cp .env.example .env
# Open .env and add your API key:
# API_KEY=your_api_key_here
```

### 3. Launch with Docker

```bash
# Build and start all services
docker compose up --build

# Or run just the API
docker build -t finops-engine .
docker run -p 8000:8000 --env-file .env finops-engine
```

### 4. Access the Services

| Service | URL | Description |
|---------|-----|-------------|
| 📡 API | http://localhost:8000 | FastAPI backend |
| 📖 Docs | http://localhost:8000/docs | Interactive Swagger UI |
| 🗄️ ChromaDB | http://localhost:8001 | Vector store |

### 5. Local Development (no Docker)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the API
uvicorn src.main:app --reload --port 8000
```

---

## 📡 API Reference

### `POST /api/optimizer/compare`
Run both Avalanche and Snowball strategies side-by-side.

```json
// Request
{
  "debts": [
    { "name": "Chase Sapphire", "balance": 5400, "apr": 0.24, "min_payment": 50 },
    { "name": "HSBC Personal",  "balance": 2100, "apr": 0.18, "min_payment": 25 }
  ],
  "monthly_budget": 500
}

// Response
{
  "avalanche": { "months_to_payoff": 14, "total_interest_paid": 487.32 },
  "snowball":  { "months_to_payoff": 15, "total_interest_paid": 531.90 },
  "recommendation": {
    "interest_saved_by_avalanche": 44.58,
    "best_financial": "avalanche",
    "best_psychological": "snowball"
  }
}
```

### `POST /api/transactions/categorize`
NLP-categorize raw bank transaction descriptions.

```json
// Request
{ "descriptions": ["AMZN Mktp US*2B", "UBER *TRIP", "ATM CASH ADV"] }

// Response
{
  "results": [
    { "description": "AMZN Mktp US*2B", "category": "Shopping" },
    { "description": "UBER *TRIP",      "category": "Travel & Transport" },
    { "description": "ATM CASH ADV",    "category": "Cash Advance" }
  ]
}
```

### `POST /api/rag/ask`
Ask a question grounded in your bank's Terms & Conditions.

```json
// Request
{ "question": "What triggers a penalty APR?", "bank_name": "Chase" }

// Response
{
  "answer": "Per Section 4.2, a penalty APR of 29.99% applies when...",
  "sources": [{ "page": 11, "bank": "Chase", "excerpt": "..." }]
}
```

---

## 🛡️ DevSecOps Fortress

Every push to `main` or `develop` triggers the full CI/CD pipeline:

```
Push / Pull Request
       │
       ▼
 ┌─────────────────────────────┐
 │  Job 1: Lint & Security     │
 │  ├── flake8  (style)        │
 │  ├── bandit  (SAST)         │
 │  └── safety  (CVE check)    │
 └──────────┬──────────────────┘
            │ PASS
            ▼
 ┌─────────────────────────────┐
 │  Job 2: Test Suite          │
 │  └── pytest --cov           │
 └──────────┬──────────────────┘
            │ PASS
            ▼
 ┌─────────────────────────────┐
 │  Job 3: Docker Build        │
 │  └── Build & tag image      │
 └─────────────────────────────┘
```

### Security Principles
- 🔑 **Zero hardcoded secrets** — Use `.env` locally, Vault in production
- 🐳 **Non-root containers** — All Docker images run as `appuser`
- 🔍 **Dependency pinning** — All versions locked in `requirements.txt`
- 📊 **Audit artifacts** — Bandit & Safety reports uploaded on every run

---

## 🧪 Running Tests

```bash
# Run full test suite with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Run only financial math tests
pytest tests/test_optimizer.py -v

# Run security scan locally
bandit -r src/ -ll
safety check -r requirements.txt
```

---

## 🛠️ Tech Stack

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Language** | Python 3.11 | Core runtime |
| **API Framework** | FastAPI | REST endpoints + auto Swagger docs |
| **AI / NLP** | LangChain + OpenAI/Gemini | RAG pipeline & transaction NLP |
| **Vector Store** | ChromaDB | Embedding storage for bank PDFs |
| **Data Processing** | Pandas, NumPy, SciPy | Cleaning, feature engineering |
| **PDF Parsing** | pdfplumber, PyPDF2 | T&C document ingestion |
| **Containerization** | Docker + Compose | Reproducible environments |
| **CI/CD** | GitHub Actions | Automated pipeline |
| **SAST** | Bandit | Python security vulnerability scanning |
| **Dependency Audit** | Safety | CVE checks on pip packages |
| **Secret Management** | HashiCorp Vault | Zero hardcoded API keys |

---

## 📈 Roadmap

- [x] Core Avalanche & Snowball optimizer
- [x] NLP transaction categorizer
- [x] RAG pipeline with ChromaDB
- [x] CI/CD with security scanning
- [x] Dockerized microservices
- [ ] **Plaid API integration** — live bank syncing
- [ ] **Multi-currency support** — international debt optimization
- [ ] **React dashboard** — interactive repayment visualizer
- [ ] **Scheduler** — monthly automated reports via email

---

## 🤝 Contributing

Contributions are welcome! Please read the guidelines before opening a PR.

```bash
# 1. Fork the repo and clone your fork
git clone https://github.com/Nethmini-Rathnayake/FinOps-Engine.git

# 2. Create a feature branch
git checkout -b feat/your-feature-name

# 3. Make changes, then lint and test
flake8 src/ && pytest tests/ -v

# 4. Commit using Conventional Commits
git commit -m "feat: add multi-currency support"

# 5. Push and open a Pull Request
git push origin feat/your-feature-name
```

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

---

<div align="center">

**Built by [Nethmini Rathnayake](https://github.com/Nethmini-Rathnayake)**

*Showcasing Software Engineering + DevSecOps expertise in the Fintech sector*

⭐ **Star this repo** if it helped you — it means a lot!

</div>