"""
Bank statement ingestor.

Parses structured CSV files and extracts debt fields (balance, APR, minimum
payment) from unstructured plain-text or PDF bank statements using compiled
regular expressions.  PDF extraction requires the optional ``pymupdf`` package.
"""

import csv
import io
import re

from src.engine.avalanche import Debt


# ── CSV parsing ────────────────────────────────────────────────────────────────

def parse_csv_file(file_path: str) -> list[Debt]:
    """
    Parse a structured CSV bank statement file into Debt objects.

    Args:
        file_path: Absolute or relative path to a CSV file with columns:
            ``name``, ``balance``, ``apr`` (decimal), ``min_payment``.

    Returns:
        List of Debt instances, one per data row.
    """
    with open(file_path, newline="") as f:
        return _parse_csv_reader(csv.DictReader(f))


def parse_csv_text(text: str) -> list[Debt]:
    """
    Parse CSV text directly into Debt objects.

    Useful for in-memory processing of uploaded file content without writing
    to disk first.

    Args:
        text: Raw CSV string with columns: ``name``, ``balance``,
            ``apr`` (decimal), ``min_payment``.

    Returns:
        List of Debt instances, one per data row.
    """
    return _parse_csv_reader(csv.DictReader(io.StringIO(text)))


def _parse_csv_reader(reader: csv.DictReader) -> list[Debt]:
    """
    Convert an open DictReader into a list of Debt objects.

    Args:
        reader: A ``csv.DictReader`` positioned at the start of the data rows.
            Expected columns: ``name``, ``balance``, ``apr``, ``min_payment``.

    Returns:
        List of Debt instances, one per row.
    """
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


# ── Unstructured text extraction via regex ─────────────────────────────────────

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


def extract_debt_from_text(text: str, account_name: str = "Unknown") -> Debt | None:
    """
    Pull balance, APR, and minimum payment from unstructured bank statement text.

    Uses compiled regular expressions to locate labelled values anywhere in the
    text block.  All three fields must be present; if any is missing the
    function returns ``None`` rather than raising.

    Args:
        text: Raw text content of a single bank statement page or section.
        account_name: Label to assign to the returned Debt object.

    Returns:
        A populated Debt instance if all three fields were found, otherwise None.
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


# ── PDF parsing (requires pymupdf) ────────────────────────────────────────────

def parse_pdf_statement(file_path: str) -> list[Debt]:
    """
    Extract debt data from a PDF bank statement using PyMuPDF.

    Each page is treated as an independent text block and passed to
    ``extract_debt_from_text``.  Pages that do not contain all three required
    fields are silently skipped.

    Args:
        file_path: Path to the PDF file to parse.

    Returns:
        List of Debt instances extracted from the PDF, one per qualifying page.

    Raises:
        ImportError: If ``pymupdf`` is not installed.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise ImportError("Install PyMuPDF: pip install pymupdf") from exc

    debts: list[Debt] = []
    doc = fitz.open(file_path)
    for i, page in enumerate(doc):
        text = page.get_text()
        debt = extract_debt_from_text(text, account_name=f"Account (page {i + 1})")
        if debt:
            debts.append(debt)
    doc.close()
    return debts
