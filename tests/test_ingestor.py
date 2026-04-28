import textwrap
import pytest
from src.ingestor.parser import parse_csv_text, extract_debt_from_text


SAMPLE_CSV = textwrap.dedent("""\
    name,balance,apr,min_payment
    Chase Sapphire Reserve,5000.00,0.2399,100.00
    Capital One Venture,2500.00,0.1999,50.00
    Student Loan,15000.00,0.0675,150.00
""")


def test_csv_returns_correct_count():
    assert len(parse_csv_text(SAMPLE_CSV)) == 3


def test_csv_parses_values_correctly():
    debts = parse_csv_text(SAMPLE_CSV)
    chase = next(d for d in debts if d.name == "Chase Sapphire Reserve")
    assert chase.balance == 5000.00
    assert chase.apr == 0.2399
    assert chase.min_payment == 100.00


def test_csv_names_are_stripped():
    csv = "name,balance,apr,min_payment\n  My Card  ,1000,0.2,50\n"
    debts = parse_csv_text(csv)
    assert debts[0].name == "My Card"


def test_extract_from_text_success():
    statement = """
    Account: Visa Platinum
    Current Balance: $3,500.00
    APR: 21.99%
    Minimum Payment: $75.00
    """
    debt = extract_debt_from_text(statement, "Visa Platinum")
    assert debt is not None
    assert debt.balance == 3500.00
    assert abs(debt.apr - 0.2199) < 0.0001
    assert debt.min_payment == 75.00


def test_extract_from_text_missing_fields_returns_none():
    assert extract_debt_from_text("Balance: $1,000.00", "Incomplete") is None


def test_extract_from_text_no_comma_in_balance():
    statement = "Balance: $500.00\nAPR: 15.00%\nMinimum Payment: $25.00"
    debt = extract_debt_from_text(statement, "Simple Card")
    assert debt is not None
    assert debt.balance == 500.00
