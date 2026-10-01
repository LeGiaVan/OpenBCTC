"""
test_parser.py — Unit tests kiểm thử PDF Parser và Table Normalization của FinAudit AI.
"""

import pytest

from src.models import ParsedBlock, ParsedDocument
from src.parser.pdf_parser import PDFParser
from src.parser.table_utils import (
    compute_numeric_density,
    detect_currency_unit,
    format_table_to_markdown,
    merge_multi_level_headers,
    parse_financial_number,
)


class TestTableUtils:
    """Kiểm thử các hàm tiện ích chuẩn hóa bảng và số liệu tài chính."""

    def test_parse_financial_number_parentheses(self):
        """Kiểm thử số âm đặt trong dấu ngoặc đơn (1,234) -> -1234."""
        val, is_neg = parse_financial_number("(1,234)")
        assert val == -1234.0
        assert is_neg is True

        val, is_neg = parse_financial_number("( 1.234.567 )")
        assert val == -1234567.0
        assert is_neg is True

        val, is_neg = parse_financial_number("( 85.000.000.000 )")
        assert val == -85000000000.0
        assert is_neg is True

        val, is_neg = parse_financial_number("(50.5)")
        assert val == -50.5
        assert is_neg is True

    def test_parse_financial_number_standard_formats(self):
        """Kiểm thử định dạng số dương, số âm và dấu gạch ngang (VN & EN)."""
        # Định dạng VN
        val, is_neg = parse_financial_number("125.000.000.000")
        assert val == 125000000000.0
        assert is_neg is False

        # Định dạng EN
        val, is_neg = parse_financial_number("125,000,000,000")
        assert val == 125000000000.0
        assert is_neg is False

        # Số âm với dấu trừ
        val, is_neg = parse_financial_number("-15.400.000")
        assert val == -15400000.0
        assert is_neg is True

        # Gạch ngang biểu thị 0
        val, is_neg = parse_financial_number("-")
        assert val == 0.0
        assert is_neg is False

        # Văn bản không phải số
        val, is_neg = parse_financial_number("Tài sản ngắn hạn")
        assert val is None
        assert is_neg is False

    def test_detect_currency_unit(self):
        """Kiểm thử nhận diện đơn vị tiền tệ từ văn bản BCTC."""
        assert detect_currency_unit("Đơn vị tính: Đồng Việt Nam") == "VND"
        assert detect_currency_unit("Đơn vị tính: VND") == "VND"
        assert detect_currency_unit("Đơn vị tính: Triệu đồng") == "TRIEU_VND"
        assert detect_currency_unit("Đơn vị tính: Tỷ VND") == "TY_VND"
        assert detect_currency_unit("Đơn vị tính: USD") == "USD"
        assert detect_currency_unit("Nội dung không có đơn vị tính") is None

    def test_compute_numeric_density(self, sample_balance_sheet_table, sample_narrative_table_board):
        """Kiểm thử tính mật độ số (Numeric Density) trong bảng."""
        bctc_density = compute_numeric_density(sample_balance_sheet_table)
        assert bctc_density > 0.40  # Bảng BCTC có mật độ số cao

        board_density = compute_numeric_density(sample_narrative_table_board)
        assert board_density < 0.20  # Bảng danh sách HĐQT có mật độ số thấp

    def test_format_table_to_markdown(self, sample_income_statement_table_with_negatives):
        """Kiểm thử render bảng thành Markdown Table và chuẩn hóa số âm."""
        md = format_table_to_markdown(sample_income_statement_table_with_negatives)
        assert md.startswith("| Chỉ tiêu |")
        assert "| --- |" in md
        # Kiểm tra số âm ngoặc đơn đã được chuyển thành dấu trừ
        assert "-2.500.000.000" in md
        assert "-85.000.000.000" in md

    def test_merge_multi_level_headers(self):
        """Kiểm thử gộp header đa tầng (merged headers)."""
        header_rows = [
            ["", "Năm 2024", ""],
            ["Chỉ tiêu", "Kỳ này", "Kỳ trước"],
        ]
        merged = merge_multi_level_headers(header_rows)
        assert len(merged) == 3
        assert merged[0] == "Chỉ tiêu"
        assert "Năm 2024 - Kỳ này" in merged[1]
        assert "Năm 2024 - Kỳ trước" in merged[2]


class TestPDFParser:
    """Kiểm thử module PDFParser trích xuất block theo thứ tự đọc và metadata."""

    def test_parse_page_reading_order(self, mock_pdfplumber_page):
        """Kiểm thử trích xuất 1 trang theo thứ tự: Văn bản trên -> Bảng -> Văn bản dưới."""
        parser = PDFParser()
        blocks = parser._parse_page(
            page=mock_pdfplumber_page,
            page_number=1,
            company="VNM",
            year=2024,
        )

        assert len(blocks) == 3
        # Block 1: Text tiêu đề trên bảng
        assert blocks[0].block_type == "text"
        assert "BẢNG CÂN ĐỐI KẾ TOÁN" in blocks[0].content
        assert blocks[0].metadata.get("unit") == "VND"

        # Block 2: Bảng Cân đối kế toán dạng Markdown
        assert blocks[1].block_type == "table"
        assert "| CHỈ TIÊU |" in blocks[1].content
        assert blocks[1].metadata.get("numeric_density") > 0.40

        # Block 3: Text người ký dưới bảng
        assert blocks[2].block_type == "text"
        assert "Tổng Giám đốc" in blocks[2].content

    def test_merge_spanning_tables(self):
        """Kiểm thử phát hiện và gộp 2 bảng kéo dài qua 2 trang liên tiếp."""
        parser = PDFParser()
        b1 = ParsedBlock(
            block_id="p1_b1",
            block_type="table",
            page=1,
            content="| Chỉ tiêu | Số tiền |\n| --- | --- |\n| Mục A | 100 |",
            metadata={"num_cols": 2, "num_rows": 2},
        )
        b2 = ParsedBlock(
            block_id="p2_b1",
            block_type="table",
            page=2,
            content="| Chỉ tiêu | Số tiền |\n| --- | --- |\n| Mục B | 200 |",
            metadata={"num_cols": 2, "num_rows": 2},
        )

        merged = parser._merge_spanning_tables([b1, b2])
        assert len(merged) == 1
        assert "| Mục A | 100 |" in merged[0].content
        assert "| Mục B | 200 |" in merged[0].content
        assert merged[0].metadata.get("num_rows") == 4
        assert merged[0].metadata.get("spans_pages") == [1, 2]

    def test_parsed_document_to_markdown(self):
        """Kiểm thử xuất toàn bộ tài liệu ParsedDocument ra định dạng Markdown."""
        b1 = ParsedBlock(
            block_id="p1_b1",
            block_type="text",
            page=1,
            content="BÁO CÁO CỦA BAN TỔNG GIÁM ĐỐC\nNội dung diễn giải...",
        )
        b2 = ParsedBlock(
            block_id="p2_b1",
            block_type="table",
            page=2,
            content="| Chỉ tiêu | Số tiền |\n| --- | --- |\n| Doanh thu | 100 |",
        )
        doc = ParsedDocument(
            company="VNM",
            year=2024,
            total_pages=2,
            blocks=[b1, b2],
        )

        md = doc.to_markdown()
        assert "# BÁO CÁO TÀI CHÍNH — VNM (2024)" in md
        assert "BÁO CÁO CỦA BAN TỔNG GIÁM ĐỐC" in md
        assert "| Doanh thu | 100 |" in md

    def test_file_not_found_raises(self):
        """Kiểm thử ném ngoại lệ FileNotFoundError khi đường dẫn không tồn tại."""
        parser = PDFParser()
        with pytest.raises(FileNotFoundError):
            parser.parse_pdf("duong_dan_khong_ton_tai.pdf")
