"""
test_notes_ocr.py — Tests nghiệm thu OCR Post-Processing pipeline cho Thuyết minh BCTC.
Bao gồm:
  - Ontology chuẩn TT200 đủ 9 phần (I→IX)
  - Breadcrumb phân cấp đúng Roman → Numbered Note → Sub-item
  - Regex H4 không bắt nhầm số liệu bảng
  - MAX_NOTES_MAP_TT200 reject đúng mục vượt giới hạn
  - postprocess_mineru_table() pipeline 4 bước
  - Dấu gạch đầu dòng là body content, không tạo heading H5
"""

import pytest

from src.models import BlockType, ClassifiedBlock, ParsedBlock, StorageTarget
from src.parser.section_detector import (
    ROMAN_CANONICAL,
    SectionDetector,
    TT200_VI_BALANCE_SHEET_NOTES,
    TT200_VII_INCOME_STATEMENT_NOTES,
)
from src.parser.table_utils import (
    align_markdown_table_columns,
    clean_numeric_cells,
    extract_embedded_heading_from_table,
    postprocess_mineru_table,
    stitch_multiline_headers,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_text_block(block_id: str, page: int, content: str) -> ClassifiedBlock:
    """Tạo ClassifiedBlock text nhanh cho test."""
    return ClassifiedBlock(
        block=ParsedBlock(
            block_id=block_id,
            block_type="text",
            page=page,
            content=content,
        ),
        block_type=BlockType.NARRATIVE,
        target=[StorageTarget.VECTOR],
        confidence=0.9,
        classification_method="rule_based",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: Ontology & Canonical Taxonomy
# ══════════════════════════════════════════════════════════════════════════════

class TestOntologyTT200:
    """Kiểm tra Ontology chuẩn TT200 có đủ 9 phần La Mã."""

    def test_roman_canonical_has_9_sections(self):
        """ROMAN_CANONICAL phải có đúng 9 phần I→IX."""
        assert len(ROMAN_CANONICAL) == 9
        expected_keys = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"]
        assert list(ROMAN_CANONICAL.keys()) == expected_keys

    def test_roman_canonical_section_v_going_concern(self):
        """Phần V phải là 'Hoạt động liên tục' với canonical code đúng."""
        code, title, num = ROMAN_CANONICAL["V"]
        assert code == "NOTE_SEC_GOING_CONCERN"
        assert "HOẠT ĐỘNG LIÊN TỤC" in title
        assert num == 5

    def test_roman_canonical_section_ix_other_info(self):
        """Phần IX phải là 'Thông tin khác'."""
        code, title, num = ROMAN_CANONICAL["IX"]
        assert code == "NOTE_SEC_OTHER_INFO"
        assert "THÔNG TIN KHÁC" in title
        assert num == 9

    def test_roman_canonical_ordering(self):
        """Thứ tự các phần phải đúng từ 1 đến 9."""
        for i, (key, val) in enumerate(ROMAN_CANONICAL.items(), start=1):
            assert val[2] == i, f"Phần {key} phải có thứ tự {i}, nhưng là {val[2]}"

    def test_vi_balance_sheet_notes_has_30_items(self):
        """Phần VI (Bảng CĐKT) phải có đúng 30 mục."""
        assert len(TT200_VI_BALANCE_SHEET_NOTES) == 30
        assert TT200_VI_BALANCE_SHEET_NOTES[1] == "Tiền"
        assert TT200_VI_BALANCE_SHEET_NOTES[30] == "Các thông tin khác do doanh nghiệp tự thuyết minh"

    def test_vii_income_statement_notes_has_11_items(self):
        """Phần VII (KQKD) phải có đúng 11 mục."""
        assert len(TT200_VII_INCOME_STATEMENT_NOTES) == 11
        assert TT200_VII_INCOME_STATEMENT_NOTES[1] == "Tổng doanh thu bán hàng và cung cấp dịch vụ"
        assert TT200_VII_INCOME_STATEMENT_NOTES[11] == "Chi phí thuế thu nhập doanh nghiệp hoãn lại"


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: Breadcrumb phân cấp đúng (I→IX)
# ══════════════════════════════════════════════════════════════════════════════

class TestBreadcrumbHierarchy:
    """Kiểm tra breadcrumb phân cấp 9 phần La Mã + mục số + tiểu mục chữ."""

    def test_full_hierarchy_breadcrumb(self):
        """Breadcrumb phải đúng: Roman → Numbered Note → Sub-item."""
        detector = SectionDetector()
        blocks = [
            _make_text_block("b1", 15, "VI. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BẢNG CÂN ĐỐI KẾ TOÁN"),
            _make_text_block("b2", 15, "1. Tiền\nChi tiết các khoản tiền"),
            _make_text_block("b3", 16, "(a) Tiền mặt tại quỹ\nSố dư cuối kỳ"),
        ]
        sections = detector.detect_sections(blocks, company="TEST", year=2024)

        # Phải có ít nhất 3 sections: Roman VI, Note 1, Sub-item (a)
        assert len(sections) >= 3

        # Section Roman VI
        roman_sec = [s for s in sections if s.canonical_code == "NOTE_SEC_BALANCE_SHEET"]
        assert len(roman_sec) == 1
        assert roman_sec[0].level == 3

        # Section mục số 1
        note_secs = [s for s in sections if s.level == 4]
        assert len(note_secs) >= 1
        assert "1. Tiền" in note_secs[0].title
        # Breadcrumb phải chứa tên phần La Mã cha
        assert "BẢNG CÂN ĐỐI" in note_secs[0].breadcrumb or "VI." in note_secs[0].breadcrumb

        # Section tiểu mục (a)
        sub_secs = [s for s in sections if s.level == 5]
        assert len(sub_secs) >= 1
        assert "(a)" in sub_secs[0].title

    def test_section_ix_detected(self):
        """Phần IX (Thông tin khác) phải được nhận diện đúng."""
        detector = SectionDetector()
        blocks = [
            _make_text_block("b1", 50, "IX. NHỮNG THÔNG TIN KHÁC\nThông tin về các sự kiện sau ngày kết thúc kỳ kế toán"),
        ]
        sections = detector.detect_sections(blocks, company="TEST", year=2024)
        note_sections = [s for s in sections if s.canonical_code == "NOTE_SEC_OTHER_INFO"]
        assert len(note_sections) == 1
        assert note_sections[0].level == 3

    def test_roman_section_v_going_concern(self):
        """Phần V (hoạt động liên tục) phải được nhận diện."""
        detector = SectionDetector()
        blocks = [
            _make_text_block(
                "b1", 30,
                "V. CÁC CHÍNH SÁCH KẾ TOÁN ÁP DỤNG TRONG TRƯỜNG HỢP KHÔNG ĐÁP ỨNG GIẢ ĐỊNH HOẠT ĐỘNG LIÊN TỤC",
            ),
        ]
        sections = detector.detect_sections(blocks, company="TEST", year=2024)
        gc_sections = [s for s in sections if s.canonical_code == "NOTE_SEC_GOING_CONCERN"]
        assert len(gc_sections) == 1

    def test_sequential_roman_sections(self):
        """Các phần La Mã tuần tự phải được nhận diện và không bị bỏ sót."""
        detector = SectionDetector()
        blocks = [
            _make_text_block("b1", 13, "I. ĐẶC ĐIỂM HOẠT ĐỘNG CỦA DOANH NGHIỆP"),
            _make_text_block("b2", 15, "II. KỲ KẾ TOÁN VÀ ĐƠN VỊ TIỀN TỆ SỬ DỤNG TRONG KẾ TOÁN"),
            _make_text_block("b3", 16, "III. CHUẨN MỰC VÀ CHẾ ĐỘ KẾ TOÁN ÁP DỤNG"),
            _make_text_block("b4", 17, "IV. CÁC CHÍNH SÁCH KẾ TOÁN ÁP DỤNG"),
        ]
        sections = detector.detect_sections(blocks, company="TEST", year=2024)
        roman_sections = [s for s in sections if s.level == 3 and s.canonical_code]
        assert len(roman_sections) >= 4


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: Regex H4 — Không False Positive
# ══════════════════════════════════════════════════════════════════════════════

class TestRegexH4NoFalsePositive:
    """Kiểm tra regex H4 không bắt nhầm số liệu bảng."""

    def test_reject_numeric_data_as_heading(self):
        """Số liệu '20.899.554.450 triệu đồng' KHÔNG được nhận diện là H4."""
        detector = SectionDetector()
        blocks = [
            _make_text_block("b1", 20, "VI. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BẢNG CÂN ĐỐI KẾ TOÁN"),
            _make_text_block("b2", 20, "1. Tiền\nSố dư tiền mặt"),
            _make_text_block("b3", 21, "20.899.554.450 triệu đồng là tổng tài sản"),
        ]
        sections = detector.detect_sections(blocks, company="TEST", year=2024)
        # Block b3 chứa số liệu, KHÔNG được tạo section H4 mới
        h4_titles = [s.title for s in sections if s.level == 4]
        assert not any("20" in t and "899" in t for t in h4_titles)

    def test_accept_valid_numbered_note(self):
        """Mục '25. Vốn chủ sở hữu' PHẢI được nhận diện là H4."""
        detector = SectionDetector()
        blocks = [
            _make_text_block("b1", 20, "VI. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BẢNG CÂN ĐỐI KẾ TOÁN"),
            _make_text_block("b2", 20, "1. Tiền\nSố dư tiền mặt"),
            _make_text_block("b3", 25, "25. Vốn chủ sở hữu"),
        ]
        sections = detector.detect_sections(blocks, company="TEST", year=2024)
        h4_titles = [s.title for s in sections if s.level == 4]
        assert any("Vốn chủ sở hữu" in t for t in h4_titles)

    def test_reject_date_as_heading(self):
        """Dòng có ngày tháng KHÔNG được nhận diện là H4."""
        detector = SectionDetector()
        blocks = [
            _make_text_block("b1", 20, "VI. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BẢNG CÂN ĐỐI KẾ TOÁN"),
            _make_text_block("b2", 20, "15. ngày 31/12/2024 tổng cộng"),
        ]
        sections = detector.detect_sections(blocks, company="TEST", year=2024)
        h4_secs = [s for s in sections if s.level == 4]
        assert len(h4_secs) == 0

    def test_reject_currency_unit_as_heading(self):
        """Dòng có đơn vị tiền tệ KHÔNG được nhận diện là H4."""
        detector = SectionDetector()
        blocks = [
            _make_text_block("b1", 20, "VI. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BẢNG CÂN ĐỐI KẾ TOÁN"),
            _make_text_block("b2", 20, "5. Tổng số tiền là 500 triệu đồng"),
        ]
        sections = detector.detect_sections(blocks, company="TEST", year=2024)
        h4_secs = [s for s in sections if s.level == 4]
        assert len(h4_secs) == 0

    def test_title_must_start_with_letter(self):
        """Regex H4: phần title PHẢI bắt đầu bằng chữ cái, không phải số."""
        detector = SectionDetector()
        blocks = [
            _make_text_block("b1", 20, "VI. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BẢNG CÂN ĐỐI KẾ TOÁN"),
            # "20.5" — title "5..." bắt đầu bằng số → reject
            _make_text_block("b2", 20, "20.500.000 Doanh thu"),
        ]
        sections = detector.detect_sections(blocks, company="TEST", year=2024)
        h4_secs = [s for s in sections if s.level == 4]
        assert len(h4_secs) == 0


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: MAX_NOTES_MAP_TT200 — Reject mục vượt giới hạn
# ══════════════════════════════════════════════════════════════════════════════

class TestMaxNotesMap:
    """Kiểm tra MAX_NOTES_MAP_TT200 reject đúng mục vượt giới hạn."""

    def test_reject_note_31_in_section_vi(self):
        """Phần VI chỉ có 30 mục, mục 31 phải bị reject."""
        detector = SectionDetector()
        blocks = [
            _make_text_block("b1", 20, "VI. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BẢNG CÂN ĐỐI KẾ TOÁN"),
            _make_text_block("b2", 20, "30. Các thông tin khác do doanh nghiệp tự thuyết minh"),
            _make_text_block("b3", 21, "31. Mục không tồn tại trong TT200"),
        ]
        sections = detector.detect_sections(blocks, company="TEST", year=2024)
        h4_titles = [s.title for s in sections if s.level == 4]
        assert not any("31" in t and "không tồn tại" in t for t in h4_titles)

    def test_accept_note_30_in_section_vi(self):
        """Phần VI mục 30 (mục cuối cùng) phải được chấp nhận."""
        detector = SectionDetector()
        blocks = [
            _make_text_block("b1", 20, "VI. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BẢNG CÂN ĐỐI KẾ TOÁN"),
            _make_text_block("b2", 45, "30. Các thông tin khác do doanh nghiệp tự thuyết minh"),
        ]
        sections = detector.detect_sections(blocks, company="TEST", year=2024)
        h4_titles = [s.title for s in sections if s.level == 4]
        assert any("30" in t for t in h4_titles)

    def test_reject_note_12_in_section_vii(self):
        """Phần VII chỉ có 11 mục, mục 12 phải bị reject."""
        detector = SectionDetector()
        blocks = [
            _make_text_block("b1", 50, "VII. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH"),
            _make_text_block("b2", 51, "12. Mục vượt giới hạn KQKD"),
        ]
        sections = detector.detect_sections(blocks, company="TEST", year=2024)
        h4_titles = [s.title for s in sections if s.level == 4]
        assert not any("12" in t and "vượt giới hạn" in t for t in h4_titles)

    def test_reject_note_5_in_section_viii(self):
        """Phần VIII chỉ có 4 mục, mục 5 phải bị reject."""
        detector = SectionDetector()
        blocks = [
            _make_text_block("b1", 55, "VIII. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BÁO CÁO LƯU CHUYỂN TIỀN TỆ"),
            _make_text_block("b2", 55, "5. Mục không hợp lệ trong LCTT"),
        ]
        sections = detector.detect_sections(blocks, company="TEST", year=2024)
        h4_titles = [s.title for s in sections if s.level == 4]
        assert not any("5" in t and "LCTT" in t for t in h4_titles)

    def test_accept_note_4_in_section_viii(self):
        """Phần VIII mục 4 (mục cuối cùng) phải được chấp nhận."""
        detector = SectionDetector()
        blocks = [
            _make_text_block("b1", 55, "VIII. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BÁO CÁO LƯU CHUYỂN TIỀN TỆ"),
            _make_text_block("b2", 55, "4. Giao dịch không bằng tiền"),
        ]
        sections = detector.detect_sections(blocks, company="TEST", year=2024)
        h4_titles = [s.title for s in sections if s.level == 4]
        assert any("Giao dịch" in t for t in h4_titles)


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: postprocess_mineru_table() Pipeline 4 bước
# ══════════════════════════════════════════════════════════════════════════════

class TestPostprocessMineruTable:
    """Kiểm tra pipeline postprocess bảng MinerU TSR."""

    def test_extract_embedded_heading(self):
        """Tách tiêu đề dính vào hàng đầu bảng."""
        table_md = (
            "| 13. Chi phí trả trước | | |\n"
            "| --- | --- | --- |\n"
            "| Khoản mục | Số cuối kỳ | Số đầu kỳ |\n"
            "| Chi phí trả trước ngắn hạn | 1.234.567 | 2.345.678 |"
        )
        heading, remaining = extract_embedded_heading_from_table(table_md)
        assert heading == "13. Chi phí trả trước"
        assert "13." not in remaining.split("\n")[0]

    def test_align_ragged_columns(self):
        """Gióng hàng bảng ragged (số cột không đều)."""
        table_md = (
            "| A | B | C |\n"
            "| --- | --- |\n"
            "| x | y |"
        )
        aligned = align_markdown_table_columns(table_md)
        lines = aligned.strip().splitlines()
        # Tất cả các dòng phải có cùng số pipe
        pipe_counts = [line.count("|") for line in lines]
        assert len(set(pipe_counts)) == 1

    def test_stitch_multiline_headers(self):
        """Nối 2 dòng header không chứa số liệu thành 1 header."""
        table_md = (
            "| Khoản mục | Số cuối năm |  | Số đầu năm |  |\n"
            "| | Giá gốc | Khấu hao | Giá gốc | Khấu hao |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| TSCĐ | 1.000 | 200 | 900 | 150 |"
        )
        stitched = stitch_multiline_headers(table_md)
        first_line = stitched.strip().splitlines()[0]
        assert "Số cuối năm - Giá gốc" in first_line
        assert "Số đầu năm - Khấu hao" in first_line

    def test_clean_numeric_cells_parentheses(self):
        """Chuẩn hóa ngoặc đơn số âm: '( 15.420.000 )' → '(15.420.000)'."""
        table_md = (
            "| Khoản mục | Số tiền |\n"
            "| --- | --- |\n"
            "| Tiền mặt | ( 15.420.000 ) |\n"
            "| Vay | — |"
        )
        cleaned = clean_numeric_cells(table_md)
        assert "(15.420.000)" in cleaned
        assert "—" not in cleaned  # Đã được thay bằng "-"

    def test_clean_numeric_cells_space_in_numbers(self):
        """Xóa khoảng trắng chen vào giữa số: '1 234 567' → '1234567'."""
        table_md = (
            "| Khoản mục | Số tiền |\n"
            "| --- | --- |\n"
            "| Tiền | 1 234 567 |"
        )
        cleaned = clean_numeric_cells(table_md)
        assert "1234567" in cleaned

    def test_full_pipeline_postprocess(self):
        """Kiểm tra pipeline tổng hợp 4 bước hoạt động đúng."""
        table_md = (
            "| 7. Hàng tồn kho | | |\n"
            "| --- | --- | --- |\n"
            "| Khoản mục | Số cuối kỳ | Số đầu kỳ |\n"
            "| Nguyên vật liệu | 1 234 567 | ( 2.345.678 ) |"
        )
        heading, cleaned = postprocess_mineru_table(table_md)
        assert heading == "7. Hàng tồn kho"
        assert "1234567" in cleaned  # Khoảng trắng trong số đã bị xóa
        assert "(2.345.678)" in cleaned  # Ngoặc âm đã chuẩn hóa

    def test_no_heading_extraction_for_normal_table(self):
        """Bảng bình thường (không có heading dính) trả về heading=None."""
        table_md = (
            "| Khoản mục | Số tiền |\n"
            "| --- | --- |\n"
            "| Tiền mặt | 1.000.000 |"
        )
        heading, remaining = extract_embedded_heading_from_table(table_md)
        assert heading is None


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: Dash-bullet body content — KHÔNG tạo H5
# ══════════════════════════════════════════════════════════════════════════════

class TestDashBulletAsBody:
    """Dấu gạch đầu dòng '- Tiền mặt' là body, không phải heading H5."""

    def test_dash_bullet_not_creates_section(self):
        """'- Tiền mặt' KHÔNG được tạo section riêng (gom vào body H4)."""
        detector = SectionDetector()
        blocks = [
            _make_text_block("b1", 20, "VI. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BẢNG CÂN ĐỐI KẾ TOÁN"),
            _make_text_block("b2", 20, "1. Tiền"),
            _make_text_block("b3", 20, "- Tiền mặt\n- Tiền gửi ngân hàng"),
        ]
        sections = detector.detect_sections(blocks, company="TEST", year=2024)
        # Không có section level 5 cho dấu gạch đầu dòng
        dash_sections = [s for s in sections if "Tiền mặt" in s.title and s.level == 5]
        assert len(dash_sections) == 0

    def test_dash_bullet_appended_to_parent(self):
        """'- Tiền gửi ngân hàng' phải được gom vào section cha '1. Tiền'."""
        detector = SectionDetector()
        blocks = [
            _make_text_block("b1", 20, "VI. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BẢNG CÂN ĐỐI KẾ TOÁN"),
            _make_text_block("b2", 20, "1. Tiền"),
            _make_text_block("b3", 20, "- Tiền mặt\n- Tiền gửi ngân hàng"),
        ]
        sections = detector.detect_sections(blocks, company="TEST", year=2024)
        # Block b3 phải nằm trong section "1. Tiền"
        note_section = [s for s in sections if s.level == 4 and "1. Tiền" in s.title]
        assert len(note_section) == 1
        assert len(note_section[0].blocks) >= 2  # block b2 (heading) + block b3 (body)
