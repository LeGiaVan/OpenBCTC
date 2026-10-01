"""
test_database.py — Unit tests cho DatabaseManager và schema SQLite.
"""

from pathlib import Path

import pytest

from src.database.db_manager import DatabaseManager
from src.models import FinancialFact, FinancialRatio, VerificationReport, VerificationStatus


@pytest.fixture
def temp_db(tmp_path: Path) -> DatabaseManager:
    db_file = tmp_path / "test_finaudit.db"
    return DatabaseManager(db_path=db_file)


def test_save_and_get_facts(temp_db: DatabaseManager):
    facts = [
        FinancialFact(
            id="VNM_2024_current_TOTAL_ASSETS",
            prov_id="p5_t1_r7",
            concept="TOTAL_ASSETS",
            standard_code="270",
            raw_label="TỔNG CỘNG TÀI SẢN",
            value=55300500.0,
            unit="VND",
            period="2024",
            period_type="current",
            company="VNM",
            year=2024,
            page=5,
            verification_status=VerificationStatus.VERIFIED,
        ),
        FinancialFact(
            id="VNM_2024_current_CURRENT_ASSETS",
            prov_id="p5_t1_r1",
            concept="CURRENT_ASSETS",
            standard_code="100",
            raw_label="TÀI SẢN NGẮN HẠN",
            value=35200500.0,
            unit="VND",
            period="2024",
            period_type="current",
            company="VNM",
            year=2024,
            page=5,
            verification_status=VerificationStatus.VERIFIED,
        ),
    ]

    count = temp_db.save_facts(facts)
    assert count == 2

    retrieved = temp_db.get_facts_by_company_and_year("VNM", 2024, "current")
    assert len(retrieved) == 2
    assert retrieved[0].concept in ("TOTAL_ASSETS", "CURRENT_ASSETS")
    assert retrieved[0].verification_status == VerificationStatus.VERIFIED


def test_save_and_get_ratios(temp_db: DatabaseManager):
    ratios = [
        FinancialRatio(
            id="VNM_2024_current_ratio",
            company="VNM",
            year=2024,
            ratio_name="current_ratio",
            ratio_category="liquidity",
            value=2.2,
            formula="CURRENT_ASSETS / CURRENT_LIABILITIES",
            input_prov_ids=["p5_t1_r1", "p5_t2_r2"],
        ),
    ]

    count = temp_db.save_ratios(ratios)
    assert count == 1

    retrieved = temp_db.get_ratios("VNM", 2024)
    assert len(retrieved) == 1
    assert retrieved[0].ratio_name == "current_ratio"
    assert retrieved[0].value == 2.2
    assert retrieved[0].input_prov_ids == ["p5_t1_r1", "p5_t2_r2"]


def test_save_verification_report_and_summary(temp_db: DatabaseManager):
    report = VerificationReport(
        company="VNM",
        year=2024,
        is_balanced=True,
        total_checks=5,
        passed_checks=["Check 1 passed", "Check 2 passed"],
        failed_checks=[],
    )
    temp_db.save_verification_report(report)

    summary = temp_db.get_summary("VNM", 2024)
    assert summary["company"] == "VNM"
    assert summary["year"] == 2024
