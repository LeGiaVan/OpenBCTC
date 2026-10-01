"""
db_manager.py — Quản lý kết nối và thao tác dữ liệu với SQLite Database.
Lưu trữ và truy xuất các facts tài chính, chỉ số tài chính, và báo cáo kiểm toán số học.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from src.database.schema import SCHEMA_SQL
from src.models import FinancialFact, FinancialRatio, VerificationReport, VerificationStatus

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Quản lý CSDL SQLite phục vụ FinAudit AI."""

    def __init__(self, db_path: str | Path = "data/finaudit.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        """Khởi tạo cấu trúc bảng nếu chưa tồn tại."""
        with self._get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        logger.debug("Database initialized at %s", self.db_path)

    def save_company(self, code: str, name: str = "", industry: str = "") -> None:
        """Thêm hoặc cập nhật thông tin doanh nghiệp."""
        sql = """
        INSERT INTO companies (code, name, industry)
        VALUES (?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            name = COALESCE(EXCLUDED.name, companies.name),
            industry = COALESCE(EXCLUDED.industry, companies.industry);
        """
        with self._get_connection() as conn:
            conn.execute(sql, (code.upper().strip(), name, industry))
            conn.commit()

    def clear_facts(self, company: str, year: int) -> int:
        """Xóa các facts cũ của doanh nghiệp trong năm tài chính trước khi nạp mới."""
        with self._get_connection() as conn:
            cur = conn.execute(
                "DELETE FROM financial_facts WHERE company = ? AND year = ?",
                (company.upper().strip(), year),
            )
            conn.commit()
            return cur.rowcount

    def save_facts(self, facts: list[FinancialFact]) -> int:
        """
        Lưu danh sách FinancialFact vào CSDL.
        Nếu fact đã tồn tại (trùng id), cập nhật giá trị và trạng thái kiểm toán.
        """
        if not facts:
            return 0

        # Đảm bảo công ty tồn tại trong bảng companies
        company_codes = {f.company.upper().strip() for f in facts}
        with self._get_connection() as conn:
            for code in company_codes:
                conn.execute(
                    "INSERT OR IGNORE INTO companies (code, name) VALUES (?, ?)",
                    (code, code),
                )

            sql = """
            INSERT INTO financial_facts (
                id, prov_id, company, year, period, period_type,
                concept, standard_code, raw_label, value, unit,
                page, table_id, source, confidence,
                verification_status, verification_detail
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                value = EXCLUDED.value,
                verification_status = EXCLUDED.verification_status,
                verification_detail = EXCLUDED.verification_detail,
                confidence = EXCLUDED.confidence;
            """
            rows = [
                (
                    f.id,
                    f.prov_id,
                    f.company.upper().strip(),
                    f.year,
                    f.period,
                    f.period_type,
                    f.concept,
                    f.standard_code,
                    f.raw_label,
                    f.value,
                    f.unit,
                    f.page,
                    f.table_id,
                    f.source,
                    f.confidence,
                    str(f.verification_status.value if hasattr(f.verification_status, "value") else f.verification_status),
                    f.verification_detail,
                )
                for f in facts
            ]
            conn.executemany(sql, rows)
            conn.commit()

        logger.info("Saved %d financial facts to %s", len(facts), self.db_path)
        return len(facts)

    def save_ratios(self, ratios: list[FinancialRatio]) -> int:
        """Lưu các chỉ số tài chính tính toán vào CSDL."""
        if not ratios:
            return 0

        with self._get_connection() as conn:
            company_codes = {r.company.upper().strip() for r in ratios}
            for code in company_codes:
                conn.execute(
                    "INSERT OR IGNORE INTO companies (code, name) VALUES (?, ?)",
                    (code, code),
                )

            sql = """
            INSERT INTO financial_ratios (
                id, company, year, ratio_name, ratio_category,
                value, formula, input_prov_ids, is_deterministic
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                value = EXCLUDED.value,
                formula = EXCLUDED.formula,
                input_prov_ids = EXCLUDED.input_prov_ids,
                is_deterministic = EXCLUDED.is_deterministic;
            """
            rows = [
                (
                    r.id,
                    r.company.upper().strip(),
                    r.year,
                    r.ratio_name,
                    r.ratio_category,
                    r.value,
                    r.formula,
                    json.dumps(r.input_prov_ids, ensure_ascii=False),
                    1 if r.is_deterministic else 0,
                )
                for r in ratios
            ]
            conn.executemany(sql, rows)
            conn.commit()

        logger.info("Saved %d financial ratios to %s", len(ratios), self.db_path)
        return len(ratios)

    def save_verification_report(
        self,
        report: VerificationReport,
        source_file: str = "",
        statement_type: str = "CONSOLIDATED",
    ) -> None:
        """Lưu báo cáo kiểm toán số học BCTC."""
        stmt_id = f"{report.company.upper()}_{report.year}_{statement_type}"
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO companies (code, name) VALUES (?, ?)",
                (report.company.upper(), report.company.upper()),
            )

            sql = """
            INSERT INTO financial_statements (
                id, company, year, period, statement_type,
                source_file, is_balanced, total_checks, passed_checks, failed_checks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                is_balanced = EXCLUDED.is_balanced,
                total_checks = EXCLUDED.total_checks,
                passed_checks = EXCLUDED.passed_checks,
                failed_checks = EXCLUDED.failed_checks;
            """
            conn.execute(
                sql,
                (
                    stmt_id,
                    report.company.upper(),
                    report.year,
                    str(report.year),
                    statement_type,
                    source_file,
                    1 if report.is_balanced else 0,
                    report.total_checks,
                    json.dumps(report.passed_checks, ensure_ascii=False),
                    json.dumps(report.failed_checks, ensure_ascii=False),
                ),
            )
            conn.commit()

    def get_facts_by_company_and_year(
        self,
        company: str,
        year: int,
        period_type: str = "current",
    ) -> list[FinancialFact]:
        """Lấy danh sách Facts tài chính của doanh nghiệp theo năm."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM financial_facts
                WHERE company = ? AND year = ? AND period_type = ?
                ORDER BY page, id;
                """,
                (company.upper(), year, period_type),
            )
            rows = cursor.fetchall()

        facts = []
        for r in rows:
            status_val = r["verification_status"]
            try:
                status = VerificationStatus(status_val)
            except ValueError:
                status = VerificationStatus.UNCHECKED

            facts.append(
                FinancialFact(
                    id=r["id"],
                    prov_id=r["prov_id"],
                    company=r["company"],
                    year=r["year"],
                    period=r["period"],
                    period_type=r["period_type"],
                    concept=r["concept"],
                    standard_code=r["standard_code"] or "",
                    raw_label=r["raw_label"],
                    value=float(r["value"]),
                    unit=r["unit"] or "VND",
                    page=int(r["page"]) if r["page"] is not None else 1,
                    table_id=r["table_id"] or "t1",
                    source=r["source"] or "pdfplumber",
                    confidence=float(r["confidence"] or 1.0),
                    verification_status=status,
                    verification_detail=r["verification_detail"] or "",
                )
            )
        return facts

    def get_ratios(self, company: str, year: int) -> list[FinancialRatio]:
        """Lấy danh sách các chỉ số tài chính đã tính toán."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM financial_ratios
                WHERE company = ? AND year = ?
                ORDER BY ratio_category, ratio_name;
                """,
                (company.upper(), year),
            )
            rows = cursor.fetchall()

        ratios = []
        for r in rows:
            try:
                inputs = json.loads(r["input_prov_ids"])
            except Exception:
                inputs = []
            ratios.append(
                FinancialRatio(
                    id=r["id"],
                    company=r["company"],
                    year=r["year"],
                    ratio_name=r["ratio_name"],
                    ratio_category=r["ratio_category"],
                    value=float(r["value"]),
                    formula=r["formula"],
                    input_prov_ids=inputs,
                    is_deterministic=bool(r["is_deterministic"]),
                )
            )
        return ratios

    def get_summary(self, company: str, year: int) -> dict[str, Any]:
        """Tổng hợp thông tin kiểm toán và số lượng facts/ratios."""
        with self._get_connection() as conn:
            fact_count = conn.execute(
                "SELECT COUNT(*) FROM financial_facts WHERE company = ? AND year = ?",
                (company.upper(), year),
            ).fetchone()[0]

            verified_count = conn.execute(
                "SELECT COUNT(*) FROM financial_facts WHERE company = ? AND year = ? AND verification_status = 'VERIFIED'",
                (company.upper(), year),
            ).fetchone()[0]

            discrepancy_count = conn.execute(
                "SELECT COUNT(*) FROM financial_facts WHERE company = ? AND year = ? AND verification_status = 'DISCREPANCY'",
                (company.upper(), year),
            ).fetchone()[0]

            ratio_count = conn.execute(
                "SELECT COUNT(*) FROM financial_ratios WHERE company = ? AND year = ?",
                (company.upper(), year),
            ).fetchone()[0]

        return {
            "company": company.upper(),
            "year": year,
            "total_facts": fact_count,
            "verified_facts": verified_count,
            "discrepancy_facts": discrepancy_count,
            "total_ratios": ratio_count,
        }
