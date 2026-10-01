# -*- coding: utf-8 -*-
"""
test_child_chunk_extractor.py — Bộ kiểm thử tự động cho module Child Chunk Extractor.

Kiểm tra thuật toán trích xuất Child Chunks từ tệp Markdown BCTC phân cấp,
đảm bảo tính toàn vẹn của cây phả hệ (breadcrumb, parent_id), mã tham chiếu TT200,
phân lập đoạn văn xuôi (text_snippet), và siêu dữ liệu bảng biểu.
"""

import json
from pathlib import Path

import pytest

from tests.child_chunk_extractor import (
    ChildChunk,
    ChildChunkExtractor,
    clean_vietnamese_text,
    slugify_vietnamese,
)


class TestChildChunkExtractor:
    """Bộ kiểm thử unit test cho ChildChunkExtractor."""

    @pytest.fixture
    def sample_markdown(self) -> str:
        """Tạo đoạn markdown giả lập có cấu trúc 3 tầng H3, H4, H5 và bảng biểu."""
        return """# BÁO CÁO TÀI CHÍNH — DEMO (2024)

> **Doanh nghiệp:** DEMO | **Năm tài chính:** 2024

---

### BẢNG CÂN ĐỐI KẾ TOÁN
*(Trang 5–6)*

Báo cáo tình hình tài chính tại ngày 31 tháng 12 năm 2024.

| Chỉ tiêu | Mã số | Thuyết minh | Số cuối năm | Số đầu năm |
| --- | --- | --- | --- | --- |
| Tài sản ngắn hạn | 100 | | 10,000 | 8,000 |
| Tiền | 110 | V.1 | 5,000 | 4,000 |

### V. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BẢNG CÂN ĐỐI KẾ TOÁN
*(Trang 15)*

#### 1. Tiền và các khoản tương đương tiền

Tiền mặt tại quỹ và tiền gửi ngân hàng không kỳ hạn.

| Khoản mục | Cuối năm | Đầu năm |
| --- | --- | --- |
| Tiền mặt | 1,000 | 800 |
| Tiền gửi ngân hàng | 4,000 | 3,200 |

#### 19. Thay đổi vốn chủ sở hữu

Nội dung thuyết minh chi tiết về biến động nguồn vốn.

##### (a) Cổ phiếu phổ thông

Số lượng cổ phiếu đang lưu hành trên thị trường.

##### (b) Bảng đối chiếu biến động vốn

| Chỉ tiêu | Vốn góp | Thặng dư | LNST chưa PP |
| --- | --- | --- | --- |
| Số dư đầu năm | 20,000 | 500 | 3,000 |
"""

    def test_text_helpers(self):
        """Kiểm thử các hàm tiện ích làm sạch text và slugify."""
        assert clean_vietnamese_text("**BẢNG CÂN ĐỐI**  KẾ TOÁN") == "BẢNG CÂN ĐỐI KẾ TOÁN"
        assert slugify_vietnamese("Báo cáo kết quả hoạt động kinh doanh") == "bao_cao_ket_qua_hoat_dong_kinh_doanh"
        assert slugify_vietnamese("V.19 Thay đổi vốn CSH") == "v19_thay_doi_von_csh"

    def test_clean_heading_title_h5_table_header(self):
        """Kiểm thử tách bỏ header bảng vô tình dính vào heading H5 do lỗi OCR."""
        extractor = ChildChunkExtractor()
        raw = "(a) Các công ty con Tên Tru số Hoạt động chính Lợi ích kinh tế 31/12/2025"
        cleaned = extractor._clean_heading_title(raw, level=5)
        assert cleaned == "(a) Các công ty con"

        # Nếu không dính header thì giữ nguyên
        normal_h5 = "(b) Chi phí trả trước dài hạn"
        assert extractor._clean_heading_title(normal_h5, level=5) == "(b) Chi phí trả trước dài hạn"

    def test_extract_from_mock_markdown(self, sample_markdown: str):
        """Kiểm thử trích xuất trên cấu trúc mock 3 tầng."""
        extractor = ChildChunkExtractor(doc_id="demo_2024")
        chunks = extractor.extract_from_markdown(sample_markdown)

        # Kỳ vọng có 6 chunks:
        # 1. BẢNG CÂN ĐỐI KẾ TOÁN (H3)
        # 2. V. THÔNG TIN BỔ SUNG... (H3)
        # 3. 1. Tiền và các khoản... (H4)
        # 4. 19. Thay đổi vốn chủ sở hữu (H4)
        # 5. (a) Cổ phiếu phổ thông (H5)
        # 6. (b) Bảng đối chiếu biến động vốn (H5)
        assert len(chunks) == 6

        # Kiểm tra H3 Core Statement
        bs_chunk = chunks[0]
        assert bs_chunk.level == 3
        assert bs_chunk.reference_code == "CORE_BALANCE_SHEET"
        assert bs_chunk.parent_id == "demo_2024_root"
        assert bs_chunk.page_hint == "Trang 5–6"
        assert bs_chunk.has_table is True
        assert bs_chunk.table_count == 1
        assert "Chỉ tiêu" in bs_chunk.table_headers

        # Kiểm tra H4 mục 19
        v19_chunk = [c for c in chunks if "19. Thay đổi vốn" in c.title][0]
        assert v19_chunk.level == 4
        assert v19_chunk.reference_code == "V.19"
        assert "V. THÔNG TIN BỔ SUNG" in v19_chunk.breadcrumb
        assert v19_chunk.parent_id == chunks[1].chunk_id  # Trỏ đúng H3 cha
        assert "Nội dung thuyết minh chi tiết" in v19_chunk.text_snippet

        # Kiểm tra H5 mục (b)
        h5_b_chunk = [c for c in chunks if "(b) Bảng đối chiếu" in c.title][0]
        assert h5_b_chunk.level == 5
        assert h5_b_chunk.reference_code == "V.19(b)"
        assert h5_b_chunk.parent_id == v19_chunk.chunk_id  # Trỏ đúng H4 cha
        assert len(h5_b_chunk.breadcrumb_path) == 4  # Root > H3 > H4 > H5
        assert h5_b_chunk.has_table is True
        assert "LNST chưa PP" in h5_b_chunk.table_headers

    def test_extract_real_vnm_2024_file(self):
        """Kiểm thử trích xuất toàn diện trực tiếp trên file outputs/vnm_2024_triaged.md."""
        md_file = Path("outputs/vnm_2024_triaged.md")
        if not md_file.exists():
            pytest.skip("File outputs/vnm_2024_triaged.md không tồn tại trong môi trường test.")

        extractor = ChildChunkExtractor(doc_id="vnm_2024")
        chunks = extractor.extract_from_file(md_file)

        # 1. Kiểm tra tổng số đề mục (chính xác 63 đề mục phân cấp)
        assert len(chunks) == 63

        stats = extractor.get_summary_stats(chunks)
        assert stats["h3_count"] == 9
        assert stats["h4_count"] > 0
        assert stats["h5_count"] > 0
        assert stats["chunks_with_tables"] > 0

        # 2. Kiểm tra các BCTC cốt lõi
        h3_chunks = [c for c in chunks if c.level == 3]
        h3_codes = [c.reference_code for c in h3_chunks]
        assert "CORE_BALANCE_SHEET" in h3_codes
        assert "CORE_INCOME_STATEMENT" in h3_codes
        assert "CORE_CASH_FLOW" in h3_codes
        assert "I" in h3_codes
        assert "V" in h3_codes
        assert "VI" in h3_codes

        # 3. Kiểm tra mục Thuyết minh 19 (Thay đổi vốn chủ sở hữu)
        v19 = next((c for c in chunks if "19. Thay đổi vốn chủ sở hữu" in c.clean_title), None)
        assert v19 is not None
        assert v19.reference_code == "V.19"
        assert v19.has_table is True
        assert any("Vốn cổ phần" in h for h in v19.table_headers)
        assert "V. THÔNG TIN BỔ SUNG" in v19.breadcrumb

        # 4. Kiểm tra mục Thuyết minh Doanh thu (VI.1)
        vi1 = next((c for c in chunks if "1. Doanh thu bán hàng" in c.clean_title), None)
        assert vi1 is not None
        assert vi1.reference_code == "VI.1"
        assert vi1.has_table is True

        # 5. Kiểm tra tính độc lập của text snippet (không được dính ký tự bảng markdown '|' ở đầu dòng)
        for c in chunks:
            if c.text_snippet:
                # Snippet không được bắt đầu bằng ký tự bảng markdown
                assert not c.text_snippet.startswith("|")
                # Payload tìm kiếm phải chứa thông tin tối thiểu
                assert len(c.search_payload) > 0

        # 6. Kiểm tra các H5 có parent_id trỏ về đúng H4 hoặc H3
        h5_chunks = [c for c in chunks if c.level == 5]
        for h5 in h5_chunks:
            assert h5.parent_id != ""
            assert not h5.parent_id.endswith("_root")  # H5 phải có cha là H4 hoặc H3

    def test_json_export_and_readback(self, tmp_path: Path):
        """Kiểm thử việc xuất file JSON và đọc lại đảm bảo toàn vẹn dữ liệu UTF-8."""
        extractor = ChildChunkExtractor(doc_id="test_doc")
        mock_text = """### BẢNG CÂN ĐỐI KẾ TOÁN\n\nThuyết minh tài chính.\n\n| Cột 1 | Cột 2 |\n| --- | --- |\n| A | 100 |\n"""
        chunks = extractor.extract_from_markdown(mock_text)

        json_file = tmp_path / "test_chunks.json"
        extractor.export_json(chunks, json_file)

        assert json_file.exists()
        data = json.loads(json_file.read_text(encoding="utf-8"))

        assert data["document_id"] == "test_doc"
        assert data["total_child_chunks"] == 1
        assert len(data["chunks"]) == 1
        first_chunk = data["chunks"][0]
        assert first_chunk["reference_code"] == "CORE_BALANCE_SHEET"
        assert first_chunk["has_table"] is True
        assert first_chunk["table_headers"] == ["Cột 1", "Cột 2"]
