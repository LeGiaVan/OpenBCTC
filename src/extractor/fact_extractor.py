"""
fact_extractor.py — Bóc tách Fact tài chính nguyên tử từ các bảng BCTC.
Ánh xạ các dòng dữ liệu sang Chuẩn mực Kế toán (Thông tư 200) thông qua Financial Ontology,
gắn provenance_id truy vết nguồn gốc và kích hoạt AccountingVerifier để kiểm toán số học.
"""

import logging
import re

from typing import TYPE_CHECKING

from src.database.db_manager import DatabaseManager
from src.extractor.ontology import match_concept_from_label_and_code
from src.models import ClassifiedBlock, FinancialFact, VerificationReport, VerificationStatus
from src.parser.ocr_postprocess import clean_ocr_number

if TYPE_CHECKING:
    from src.verifier.accounting_verifier import AccountingVerifier

logger = logging.getLogger(__name__)


class FinancialFactExtractor:
    """Bộ bóc tách facts tài chính từ ClassifiedBlock dạng bảng."""

    def __init__(
        self,
        db_manager: DatabaseManager | None = None,
        verifier: "AccountingVerifier | None" = None,
    ) -> None:
        self.db_manager = db_manager
        if verifier is None:
            from src.verifier.accounting_verifier import AccountingVerifier
            self.verifier = AccountingVerifier()
        else:
            self.verifier = verifier

    def extract_from_blocks(
        self,
        blocks: list[ClassifiedBlock],
        company: str = "VNM",
        year: int = 2024,
    ) -> tuple[list[FinancialFact], VerificationReport]:
        """
        Trích xuất danh sách FinancialFact từ danh sách ClassifiedBlock.
        Chỉ xử lý các block bảng hoặc các block có target bao gồm "sql".
        """
        facts: list[FinancialFact] = []
        fact_id_counters: dict[str, int] = {}

        for block in blocks:
            # Ưu tiên các khối bảng hoặc khối nhắm tới SQL
            is_table = block.block.block_type == "table" or block.is_sql_target or "|" in block.content
            if not is_table:
                continue

            extracted_facts = self._extract_from_table_block(block, company=company, year=year)
            for f in extracted_facts:
                # Đảm bảo fact ID là duy nhất nếu trùng concept trong cùng kỳ
                key = f"{f.company}_{f.year}_{f.period_type}_{f.concept}"
                if key in fact_id_counters:
                    fact_id_counters[key] += 1
                    f.id = f"{key}_{fact_id_counters[key]}"
                else:
                    fact_id_counters[key] = 1
                    f.id = key
                facts.append(f)

        # Chạy kiểm toán số học tự động (Anti-GIGO Accounting Invariants Verifier)
        report = self.verifier.verify_facts(facts, company=company, year=year)

        # Lưu vào SQLite CSDL nếu có db_manager
        if self.db_manager:
            self.db_manager.save_company(code=company)
            self.db_manager.clear_facts(company=company, year=year)
            self.db_manager.save_facts(facts)
            self.db_manager.save_verification_report(report)

        return facts, report

    def _extract_from_table_block(
        self,
        block: ClassifiedBlock,
        company: str,
        year: int,
    ) -> list[FinancialFact]:
        """Phân tích nội dung Markdown table trong block và trích xuất các facts."""
        lines = [line.strip() for line in block.content.split("\n") if line.strip()]
        table_lines = [line for line in lines if line.startswith("|") and line.endswith("|")]

        if len(table_lines) < 3:
            return []

        header_line = table_lines[0]
        # Bỏ qua dòng phân cách: | --- | --- |
        data_lines = [line for line in table_lines[2:] if not re.match(r"^\|(\s*[-:]+\s*\|)+$", line)]

        # Phân tích các cột từ tiêu đề
        col_indices = self._detect_columns(header_line)
        if col_indices["label"] is None or col_indices["current"] is None:
            return []

        facts: list[FinancialFact] = []
        table_id = block.block_id or f"p{block.page}_tbl"
        statement_type = self._detect_statement_type(block)

        for row_idx, line in enumerate(data_lines, start=1):
            raw_cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(raw_cols) <= max(filter(lambda x: x is not None, col_indices.values())):
                continue

            raw_label_cell = raw_cols[col_indices["label"]]
            clean_label = self._clean_label(raw_label_cell)
            if not clean_label:
                continue

            raw_code = ""
            if col_indices["code"] is not None and col_indices["code"] < len(raw_cols):
                raw_code = raw_cols[col_indices["code"]].strip()

            # Nếu mã số không nằm ở cột riêng, tìm mã số dạng số trong ngoặc ở label
            if not raw_code:
                match_code = re.search(r"\((\d{2,3})\s*=", clean_label)
                if match_code:
                    raw_code = match_code.group(1)

            # Ánh xạ concept theo Financial Ontology Thông tư 200
            concept, standard_code = match_concept_from_label_and_code(
                raw_label=clean_label,
                raw_code=raw_code,
                statement_type_hint=statement_type if statement_type != "UNKNOWN" else None,
            )

            if not concept:
                continue

            prov_id = f"{company}_{year}_p{block.page}_{table_id}_r{row_idx}"

            # Trích xuất giá trị kỳ này (current period)
            current_cell = raw_cols[col_indices["current"]]
            current_val = clean_ocr_number(current_cell)

            if current_val is not None:
                fact_current = FinancialFact(
                    id=f"{company}_{year}_current_{concept}",
                    prov_id=prov_id,
                    concept=concept,
                    standard_code=standard_code or raw_code,
                    raw_label=clean_label,
                    value=current_val,
                    unit="VND",
                    period=str(year),
                    period_type="current",
                    company=company,
                    year=year,
                    page=block.page,
                    table_id=table_id,
                    row_label=clean_label,
                    confidence=block.confidence,
                    source="ocr" if block.block.source == "ocr" else "pdfplumber",
                    verification_status=VerificationStatus.UNCHECKED,
                )
                facts.append(fact_current)

            # Trích xuất giá trị kỳ trước (previous period) nếu có
            if col_indices["previous"] is not None and col_indices["previous"] < len(raw_cols):
                prev_cell = raw_cols[col_indices["previous"]]
                prev_val = clean_ocr_number(prev_cell)
                if prev_val is not None:
                    fact_prev = FinancialFact(
                        id=f"{company}_{year-1}_prev_{concept}",
                        prov_id=f"{prov_id}_prev",
                        concept=concept,
                        standard_code=standard_code or raw_code,
                        raw_label=clean_label,
                        value=prev_val,
                        unit="VND",
                        period=str(year - 1),
                        period_type="previous",
                        company=company,
                        year=year,
                        page=block.page,
                        table_id=table_id,
                        row_label=clean_label,
                        confidence=block.confidence,
                        source="ocr" if block.block.source == "ocr" else "pdfplumber",
                        verification_status=VerificationStatus.UNCHECKED,
                    )
                    facts.append(fact_prev)

        return facts

    def _clean_label(self, label: str) -> str:
        """Loại bỏ các định dạng Markdown như **, *, <br> trong tên khoản mục."""
        cleaned = re.sub(r"[*_`]", "", label)
        cleaned = re.sub(r"<br\s*/?>", " ", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def _detect_columns(self, header_line: str) -> dict[str, int | None]:
        """Xác định vị trí các cột: label, code, note, current, previous từ dòng tiêu đề."""
        cols = [c.strip().lower() for c in header_line.split("|")[1:-1]]
        result: dict[str, int | None] = {
            "label": None,
            "code": None,
            "note": None,
            "current": None,
            "previous": None,
        }

        # 1. Tìm cột tên khoản mục (Chỉ tiêu, Tài sản, Nguồn vốn...)
        for idx, col in enumerate(cols):
            if any(k in col for k in ["chỉ tiêu", "chi tieu", "tài sản", "nguồn vốn", "khoản mục", "nội dung"]):
                result["label"] = idx
                break
        if result["label"] is None and len(cols) > 0:
            result["label"] = 0

        # 2. Tìm cột mã số (Mã số, Mã, Code)
        for idx, col in enumerate(cols):
            if any(k in col for k in ["mã số", "ma so", "mã", "code"]):
                result["code"] = idx
                break

        # 3. Tìm cột thuyết minh
        for idx, col in enumerate(cols):
            if any(k in col for k in ["thuyết minh", "thuyet minh", "tm", "note"]):
                result["note"] = idx
                break

        # 4. Fallback cấu trúc chuẩn Thông tư 200 cho bảng thiếu header tường minh (headless tables)
        # Trong BCTC Việt Nam Mẫu B01/B02/B03-DN:
        # 5 cột: [Chỉ tiêu (0), Mã số (1), Thuyết minh (2), Năm nay (3), Năm trước (4)]
        # 4 cột: [Chỉ tiêu (0), Mã số (1), Năm nay (2), Năm trước (3)]
        # 3 cột: [Chỉ tiêu (0), Năm nay (1), Năm trước (2)]
        if result["code"] is None:
            if len(cols) == 5:
                result["label"] = 0
                result["code"] = 1
                result["note"] = 2
                result["current"] = 3
                result["previous"] = 4
                return result
            elif len(cols) == 4:
                result["label"] = 0
                result["code"] = 1
                result["current"] = 2
                result["previous"] = 3
                return result
            elif len(cols) == 3:
                result["label"] = 0
                result["current"] = 1
                result["previous"] = 2
                return result

        # 5. Tìm các cột số liệu (kỳ này, kỳ trước)
        numeric_cols: list[int] = []
        for idx, col in enumerate(cols):
            if idx in (result["label"], result["code"], result["note"]):
                continue
            numeric_cols.append(idx)

        if len(numeric_cols) >= 2:
            # Phân biệt kỳ này và kỳ trước dựa trên ngày tháng hoặc thứ tự
            # Thường cột đầu tiên trong các cột số liệu là số cuối kỳ (kỳ này), cột thứ hai là số đầu năm (kỳ trước)
            col0_text = cols[numeric_cols[0]]
            is_col0_prev = (
                any(k in col0_text for k in ["đầu năm", "dau nam", "năm trước", "nam truoc"])
                or re.search(r"(?<!\d)0?1/0?1(?!\d)", col0_text) is not None
            )
            if is_col0_prev:
                result["previous"] = numeric_cols[0]
                result["current"] = numeric_cols[1]
            else:
                result["current"] = numeric_cols[0]
                result["previous"] = numeric_cols[1]
        elif len(numeric_cols) == 1:
            result["current"] = numeric_cols[0]
        else:
            # Mặc định theo bố cục 4-5 cột phổ biến
            if len(cols) == 5:
                result["label"] = 0
                result["code"] = 1
                result["note"] = 2
                result["current"] = 3
                result["previous"] = 4
            elif len(cols) == 4:
                result["label"] = 0
                result["code"] = 1
                result["current"] = 2
                result["previous"] = 3
            elif len(cols) == 3:
                result["label"] = 0
                result["current"] = 1
                result["previous"] = 2

        return result

    def _detect_statement_type(self, block: ClassifiedBlock) -> str:
        """Nhận diện loại Báo cáo Tài chính của block: BALANCE_SHEET, INCOME_STATEMENT, CASH_FLOW."""
        content_lower = block.content.lower()
        if any(k in content_lower for k in [
            "lưu chuyển tiền tệ", "báo cáo lưu chuyển tiền", "lưu chuyển thuần",
            "mẫu b 03", "tiền và các khoản tương đương tiền cuối", "lưu chuyển tiền từ hoạt động"
        ]):
            return "CASH_FLOW"
        if any(k in content_lower for k in [
            "kết quả hoạt động kinh doanh", "kết quả kinh doanh", "mẫu b 02",
            "doanh thu thuần về bán hàng", "giá vốn hàng bán", "lợi nhuận gộp về bán hàng"
        ]):
            return "INCOME_STATEMENT"
        if any(k in content_lower for k in [
            "cân đối kế toán", "tình hình tài chính", "mẫu b 01",
            "tài sản ngắn hạn", "tổng cộng tài sản", "tổng cộng nguồn vốn"
        ]):
            return "BALANCE_SHEET"
        return "UNKNOWN"

