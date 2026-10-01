"""
test_normalizer.py — Unit tests kiểm thử Module 3: OutputNormalizer.
Kiểm tra:
  - Hợp nhất text_blocks và ocr_blocks
  - Gán nhãn source ("pdfplumber" vs "ocr")
  - Sắp xếp thứ tự đọc tự nhiên (page, y0, x0)
  - Đánh số lại block_id liên tục theo trang
  - Ghép bảng kéo dài qua 2 trang liên tiếp
  - Lan truyền đơn vị tiền tệ tài liệu
"""

from src.models import ParsedBlock
from src.parser.normalizer import OutputNormalizer, normalize_output


class TestOutputNormalizer:
    """Bộ kiểm thử cho OutputNormalizer."""

    def test_normalize_sources_and_ordering(self):
        """Kiểm tra gán nhãn source và sắp xếp theo thứ tự đọc tự nhiên."""
        normalizer = OutputNormalizer()

        # Block OCR ở trang 1, y0 = 200
        ocr_b = ParsedBlock(
            block_id="raw_ocr_1",
            block_type="text",
            page=1,
            content="Nội dung trang scan",
            bbox=(10.0, 200.0, 500.0, 250.0),
        )

        # Block Text ở trang 1, y0 = 50 (nằm trên block OCR)
        text_b = ParsedBlock(
            block_id="raw_text_1",
            block_type="text",
            page=1,
            content="Tiêu đề trên cùng",
            bbox=(10.0, 50.0, 500.0, 80.0),
            metadata={"unit": "VND"},
        )

        # Block ở trang 2
        page2_b = ParsedBlock(
            block_id="raw_p2",
            block_type="text",
            page=2,
            content="Nội dung trang 2",
        )

        results = normalizer.normalize(
            text_blocks=[text_b, page2_b],
            ocr_blocks=[ocr_b],
        )

        assert len(results) == 3

        # Thứ tự trang 1: text_b (y0=50) trước ocr_b (y0=200)
        assert results[0].block_id == "p1_b1"
        assert results[0].content == "Tiêu đề trên cùng"
        assert results[0].source == "pdfplumber"

        assert results[1].block_id == "p1_b2"
        assert results[1].content == "Nội dung trang scan"
        assert results[1].source == "ocr"

        # Trang 2
        assert results[2].block_id == "p2_b1"
        assert results[2].page == 2

        # Kiểm tra lan truyền đơn vị tính VND sang các block chưa có
        assert results[1].metadata.get("unit") == "VND"
        assert results[2].metadata.get("unit") == "VND"

    def test_merge_spanning_tables(self):
        """Kiểm tra ghép bảng nối trang."""
        b1 = ParsedBlock(
            block_id="p1_b1",
            block_type="table",
            page=1,
            content="| Chỉ tiêu | Số tiền |\n| --- | --- |\n| Hàng tồn kho | 500 |",
            metadata={"num_cols": 2, "num_rows": 2},
        )
        b2 = ParsedBlock(
            block_id="p2_b1",
            block_type="table",
            page=2,
            content="| Chỉ tiêu | Số tiền |\n| --- | --- |\n| Phải thu | 300 |",
            metadata={"num_cols": 2, "num_rows": 2},
        )

        merged = normalize_output(text_blocks=[b1, b2])
        assert len(merged) == 1
        assert "| Hàng tồn kho | 500 |" in merged[0].content
        assert "| Phải thu | 300 |" in merged[0].content
        assert merged[0].metadata.get("num_rows") == 4
        assert merged[0].metadata.get("spans_pages") == [1, 2]
