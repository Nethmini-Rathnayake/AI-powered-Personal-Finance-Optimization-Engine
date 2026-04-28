import csv
import io
import re
from pathlib import Path
from typing import List, Optional

from src.engine.avalanche import Debt

# --- CSV parsing ---

def parse_csv_file(file_path: str) -> List[Debt]:
    """Parse a structured CSV bank statement file into Debt objects."""
    with open(file_path, newline="") as f:
        return _parse_csv_reader(csv.DictReader(f))


def parse_csv_text(text: str) -> List[Debt]:
    """Parse CSV text directly (useful for file uploads)."""
    return _parse_csv_reader(csv.DictReader(io.StringIO(text)))


def _parse_csv_reader(reader) -> List[Debt]:
    debts = []
    for row in reader:
        debts.append(
            Debt(
                name=row["name"].strip(),
                balance=float(row["balance"]),
                apr=float(row["apr"]),
                min_payment=float(row["min_payment"]),
            )
        )
    return debts


# --- Unstructured text extraction via regex ---

_BALANCE_RE = re.compile(
    r"(?:current\s+)?balance(?:\s+due)?[:\s]+\$?([\d,]+\.?\d*)",
    re.IGNORECASE,
)
_APR_RE = re.compile(
    r"(?:apr|annual\s+percentage\s+rate|interest\s+rate)[:\s]+([\d.]+)\s*%",
    re.IGNORECASE,
)
_MIN_PAYMENT_RE = re.compile(
    r"(?:minimum\s+payment|min\.?\s+(?:payment|due))[:\s]+\$?([\d,]+\.?\d*)",
    re.IGNORECASE,
)


def extract_debt_from_text(text: str, account_name: str = "Unknown") -> Optional[Debt]:
    """
    Pull balance, APR, and minimum payment from unstructured bank statement text.
    Returns None when any required field is missing.
    """
    balance_m = _BALANCE_RE.search(text)
    apr_m = _APR_RE.search(text)
    min_m = _MIN_PAYMENT_RE.search(text)

    if not (balance_m and apr_m and min_m):
        return None

    balance = float(balance_m.group(1).replace(",", ""))
    apr = float(apr_m.group(1)) / 100          # percent → decimal
    min_payment = float(min_m.group(1).replace(",", ""))

    return Debt(name=account_name, balance=balance, apr=apr, min_payment=min_payment)


# --- PDF parsing (requires pymupdf) ---

def parse_pdf_statement(file_path: str) -> List[Debt]:
    """
    Extract debt data from a PDF bank statement using PyMuPDF.
    Tries each page independently; skips pages with incomplete data.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise ImportError("Install PyMuPDF: pip install pymupdf") from exc

    debts: List[Debt] = []
    doc = fitz.open(file_path)
    for i, page in enumerate(doc):
        text = page.get_text()
        debt = extract_debt_from_text(text, account_name=f"Account (page {i + 1})")
        if debt:
            debts.append(debt)
    doc.close()
    return debts
