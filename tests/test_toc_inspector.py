"""
test_toc_inspector.py — Unit tests cho TOC Inspector Agent.
"""

from src.agents.toc_inspector import TOCInspector


def test_parse_page_number_raw():
    """Kiểm tra xử lý các dạng số trang in mục lục (kể cả số dính do scan)."""
    parse_fn = TOCInspector._parse_page_number_raw

    # Dạng chuẩn
    assert parse_fn("2") == (2, 2)
    assert parse_fn("6-8") == (6, 8)
    assert parse_fn("6 - 8") == (6, 8)

    # Dạng OCR dính 2 số: '45' -> 4, 5; '68' -> 6, 8
    assert parse_fn("45") == (4, 5)
    assert parse_fn("68") == (6, 8)

    # Dạng OCR dính 4 số: '1011' -> 10, 11; '1253' -> 12, 53
    assert parse_fn("1,011") == (10, 11)
    assert parse_fn("1,253") == (12, 53)


def test_parse_toc_markdown():
    """Kiểm tra bóc tách bảng Markdown mục lục."""
    inspector = TOCInspector()
    sample_md = """
| NỘI DUNG | TRANG |
| --- | --- |
| THÔNG TIN VỀ CÔNG TY | 2 |
| BÁO CÁO CỦA BAN ĐIỀU HÀNH | 3 |
| BÁO CÁO KIỂM TOÁN ĐỘC LẬP | 45 |
| BÁO CÁO TÌNH HÌNH TÀI CHÍNH RIÊNG | 68 |
| BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH RIÊNG | 9 |
| BÁO CÁO LƯU CHUYỂN TIỀN TỆ RIÊNG | 1,011 |
| THUYẾT MINH BÁO CÁO TÀI CHÍNH RIÊNG | 1,253 |
"""
    entries = inspector._parse_toc_markdown(sample_md)
    assert len(entries) >= 5

    struct = inspector._build_structure_from_toc(
        toc_entries=entries,
        toc_pdf_page=2,
        total_pages=54,
    )

    assert struct.toc_found is True
    assert struct.toc_page == 2
    assert struct.page_offset == 1
    # 6-8 + offset 1 => 7, 8, 9
    assert 7 in struct.core_statement_pages
    assert 8 in struct.core_statement_pages
    # Thuyết minh 12-53 + offset 1 => 13 -> 54
    assert 13 in struct.notes_pages
    assert 54 in struct.notes_pages
    assert struct.intro_pages == [1, 2, 3, 4, 5, 6]


def test_fallback_structure():
    """Kiểm tra cấu trúc dự phòng khi không tìm thấy mục lục."""
    struct = TOCInspector._build_fallback_structure(total_pages=50)
    assert struct.toc_found is False
    assert struct.core_statement_pages == [6, 7, 8, 9, 10, 11]
    assert 12 in struct.notes_pages
    assert struct.intro_pages == [1, 2, 3, 4, 5]


def test_parse_toc_plain_text():
    """Kiểm tra bóc tách mục lục dạng văn bản thuần có dấu chấm nối."""
    inspector = TOCInspector()
    sample_text = """
    MỤC LỤC BÁO CÁO TÀI CHÍNH
    Báo cáo của Ban Giám đốc ..................................... 2 - 3
    Báo cáo kiểm toán độc lập ................................... 4 - 5
    Báo cáo tình hình tài chính ................................. 6 - 8
    Báo cáo kết quả hoạt động kinh doanh ........................ 9
    Báo cáo lưu chuyển tiền tệ .................................. 10 - 11
    Thuyết minh báo cáo tài chính ............................... 12 - 53
    """
    entries = inspector._parse_toc_plain_text(sample_text)
    assert len(entries) >= 5
    titles = [e["title"] for e in entries]
    assert any("Báo cáo tình hình tài chính" in t for t in titles)
    assert any("Thuyết minh" in t for t in titles)


def test_toc_inspector_native_page_routing(tmp_path):
    """Kiểm tra TOCInspector tự động dùng TextParser khi trang có native text."""
    from unittest.mock import MagicMock, patch
    from src.models import ParsedBlock

    dummy_pdf = tmp_path / "toc_native.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "MỤC LỤC BÁO CÁO TÀI CHÍNH NỘI DUNG VÀ TRANG " * 3

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]

    mock_block = ParsedBlock(
        block_id="p1_b1",
        block_type="text",
        page=1,
        content="BÁO CÁO TÌNH HÌNH TÀI CHÍNH ....... 6 - 8\nTHUYẾT MINH ....... 12 - 53",
        source="pdfplumber",
    )

    inspector = TOCInspector()

    with patch("pdfplumber.open") as mock_open, \
         patch.object(inspector.text_parser, "parse_page", return_value=[mock_block]) as mock_parse_page, \
         patch.object(inspector.vision_pipeline, "process_scanned_page") as mock_vision_page:

        mock_open.return_value.__enter__.return_value = mock_pdf
        blocks = inspector._get_page_blocks(mock_page, page_num=1, company="VNM", year=2024)

    assert mock_parse_page.called
    assert not mock_vision_page.called
    assert len(blocks) == 1
    assert blocks[0].source == "pdfplumber"


def test_toc_offset_when_numbering_starts_after_toc():
    """Kiểm tra trường hợp Mục lục coi như trang 0, đánh số 1 từ trang Báo cáo cốt lõi kế tiếp."""
    inspector = TOCInspector()
    entries = [
        {"title": "Bảng cân đối kế toán riêng", "pages": (1, 3)},
        {"title": "Báo cáo kết quả hoạt động kinh doanh riêng", "pages": (4, 4)},
        {"title": "Báo cáo lưu chuyển tiền tệ riêng", "pages": (5, 6)},
        {"title": "Thuyết minh báo cáo tài chính riêng", "pages": (7, 45)},
    ]
    # Giả sử TOC nằm ở trang PDF thứ 2 (sau trang bìa)
    struct = inspector._build_structure_from_toc(
        toc_entries=entries,
        toc_pdf_page=2,
        total_pages=50,
    )
    assert struct.toc_found is True
    assert struct.toc_page == 2
    # Offset tự động = 2 vì trang in số 1 nằm ở trang PDF 3
    assert struct.page_offset == 2
    # Bảng CĐKT (1-3) + offset 2 => PDF [3, 4, 5]
    assert struct.core_statement_pages == [3, 4, 5, 6, 7, 8]
    # Thuyết minh (7-45) + offset 2 => PDF [9, ..., 47]
    assert 9 in struct.notes_pages
    assert 47 in struct.notes_pages
    # Intro pages: [1, 2] (Bìa + Mục lục)
    assert struct.intro_pages == [1, 2]


def test_detect_offset_by_anchor_with_blank_pages():
    """Kiểm tra Anchor Search phát hiện chính xác offset khi có các trang trắng (blank pages) kẹp giữa."""
    from unittest.mock import MagicMock

    inspector = TOCInspector()
    entries = [
        {"title": "Bảng cân đối kế toán riêng", "pages": (1, 3)},
        {"title": "Báo cáo kết quả hoạt động kinh doanh riêng", "pages": (4, 4)},
        {"title": "Thuyết minh báo cáo tài chính riêng", "pages": (7, 45)},
    ]

    # Mock PDF:
    # Page 1: Bìa
    # Page 2: Mục lục (toc_pdf_page = 2)
    # Page 3: Trang trắng (blank)
    # Page 4: Thư ngỏ / Thông điệp (không chứa tiêu đề BCTC)
    # Page 5: Bắt đầu Bảng cân đối kế toán riêng (Trang in 1)
    mock_p1 = MagicMock()
    mock_p1.extract_text.return_value = "BÁO CÁO THƯỜNG NIÊN VÀ TÀI CHÍNH"
    mock_p2 = MagicMock()
    mock_p2.extract_text.return_value = "MỤC LỤC TRANG 1-3 4 7-45"
    mock_p3 = MagicMock()
    mock_p3.extract_text.return_value = ""  # Trang trắng
    mock_p4 = MagicMock()
    mock_p4.extract_text.return_value = "THƯ NGỎ CỦA CHỦ TỊCH HỘI ĐỒNG QUẢN TRỊ GỬI CỔ ĐÔNG"
    mock_p5 = MagicMock()
    mock_p5.extract_text.return_value = "CÔNG TY ABC\nBẢNG CÂN ĐỐI KẾ TOÁN RIÊNG\nTại ngày 31 tháng 12 năm 2024"
    mock_p6 = MagicMock()
    mock_p6.extract_text.return_value = "BẢN THUYẾT MINH BÁO CÁO TÀI CHÍNH RIÊNG"

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_p1, mock_p2, mock_p3, mock_p4, mock_p5, mock_p6]

    struct = inspector._build_structure_from_toc(
        toc_entries=entries,
        toc_pdf_page=2,
        total_pages=50,
        pdf=mock_pdf,
    )

    assert struct.toc_found is True
    assert struct.toc_page == 2
    # Nhờ Anchor Search tìm thấy 'BẢNG CÂN ĐỐI KẾ TOÁN' ở Page 5 -> offset = 5 - 1 = 4 (bỏ qua 2 trang trắng/thư ngỏ)
    assert struct.page_offset == 4
    # Bảng CĐKT (1-3) + offset 4 => PDF [5, 6, 7]
    assert 5 in struct.core_statement_pages
    assert 6 in struct.core_statement_pages
    assert 7 in struct.core_statement_pages
    # Intro pages gồm từ 1 đến trước first_core (5) -> [1, 2, 3, 4]
    assert struct.intro_pages == [1, 2, 3, 4]
