"""
test_local_ocr.py — Unit tests cho Local Fast OCR Engine.
"""

from unittest.mock import MagicMock, patch

from src.models import ParsedBlock
from src.parser.local_ocr import LocalOCREngine


def test_group_lines_into_paragraphs():
    """Kiểm tra logic gom các dòng chữ thành đoạn văn dựa trên khoảng cách y."""
    ocr_items = [
        # Paragraph 1
        [[[10, 10], [100, 10], [100, 25], [10, 25]], "CÔNG TY CỔ PHẦN SỮA", 0.95],
        [[[10, 28], [100, 28], [100, 43], [10, 43]], "VIỆT NAM", 0.98],
        # Paragraph 2 (gap = 100 - 43 = 57 > 30)
        [[[10, 100], [100, 100], [100, 115], [10, 115]], "Thuyết minh số 1: Chính sách kế toán.", 0.92],
    ]

    paragraphs = LocalOCREngine._group_lines_into_paragraphs(ocr_items, line_gap_threshold=30.0)
    assert len(paragraphs) == 2
    assert paragraphs[0] == "CÔNG TY CỔ PHẦN SỮA VIỆT NAM"
    assert "Chính sách kế toán" in paragraphs[1]


def test_local_ocr_process_page_mocked(tmp_path):
    """Kiểm tra luồng xử lý trang bằng Mock RapidOCR."""
    engine = LocalOCREngine(engine="rapidocr")

    mock_ocr = MagicMock()
    mock_ocr.return_value = (
        [
            [[[10, 10], [200, 10], [200, 30], [10, 30]], "Thuyết minh báo cáo tài chính riêng năm 2024", 0.99],
            [[[10, 35], [200, 35], [200, 55], [10, 55]], "Đơn vị tính: Đồng Việt Nam (VND).", 0.95],
        ],
        0.15,
    )
    engine._rapid_ocr = mock_ocr

    mock_page = MagicMock()
    mock_img = MagicMock()
    mock_img.original = MagicMock()
    mock_page.to_image.return_value = mock_img

    with patch("numpy.array", return_value=MagicMock()):
        with patch("pathlib.Path.exists", return_value=False):
            with patch("pathlib.Path.mkdir"):
                with patch("builtins.open", MagicMock()):
                    blocks = engine.process_scanned_page(
                        page=mock_page,
                        page_number=15,
                        company="VNM",
                        year=2024,
                    )

    assert len(blocks) == 1
    assert isinstance(blocks[0], ParsedBlock)
    assert blocks[0].source == "local_ocr"
    assert blocks[0].page == 15
    assert "Thuyết minh báo cáo tài chính" in blocks[0].content


def test_local_ocr_vietocr_mocked(tmp_path):
    """Kiểm tra luồng xử lý trang bằng Mock VietOCR + DBNet detector."""
    engine = LocalOCREngine(engine="vietocr")

    mock_rapid = MagicMock()
    mock_rapid.return_value = (
        [
            [[[10, 10], [200, 10], [200, 30], [10, 30]], "Cong ty Co phan Sira Viet Nam", 0.99],
            [[[10, 35], [200, 35], [200, 55], [10, 55]], "Thuyet minh so 1: Chinh sach ke toan", 0.95],
        ],
        0.15,
    )
    engine._rapid_ocr = mock_rapid

    mock_viet = MagicMock()
    mock_viet.predict.side_effect = [
        "Công ty Cổ phần Sữa Việt Nam",
        "Thuyết minh số 1: Chính sách kế toán",
    ]
    engine._viet_predictor = mock_viet

    mock_page = MagicMock()
    mock_img = MagicMock()
    mock_img.size = (1000, 1500)
    mock_img.crop.return_value = MagicMock()
    mock_img.original = mock_img
    mock_page.to_image.return_value = mock_img

    with patch("numpy.array", return_value=MagicMock()):
        with patch("pathlib.Path.exists", return_value=False):
            with patch("pathlib.Path.mkdir"):
                with patch("builtins.open", MagicMock()):
                    blocks = engine.process_scanned_page(
                        page=mock_page,
                        page_number=13,
                        company="VNM",
                        year=2024,
                    )

    assert len(blocks) == 1
    assert isinstance(blocks[0], ParsedBlock)
    assert blocks[0].source == "local_ocr"
    assert "vietocr" in blocks[0].metadata["ocr_engine"]
    assert "Công ty Cổ phần Sữa Việt Nam" in blocks[0].content
    assert "Chính sách kế toán" in blocks[0].content


def test_local_ocr_predict_batch_invoked():
    """Kiểm tra luồng tối ưu hóa predict_batch được ưu tiên khi mô hình hỗ trợ batch inference."""
    engine = LocalOCREngine(engine="vietocr")

    mock_rapid = MagicMock()
    mock_rapid.return_value = (
        [
            [[[10, 10], [200, 10], [200, 30], [10, 30]], "Cong ty Co phan", 0.99],
            [[[10, 35], [200, 35], [200, 55], [10, 55]], "Thuyet minh so 1", 0.95],
        ],
        0.15,
    )
    engine._rapid_ocr = mock_rapid

    mock_viet = MagicMock()
    mock_viet.predict_batch.return_value = [
        "Công ty Cổ phần",
        "Thuyết minh số 1",
    ]
    engine._viet_predictor = mock_viet

    mock_page = MagicMock()
    mock_img = MagicMock()
    mock_img.size = (1000, 1500)
    mock_img.crop.return_value = MagicMock()
    mock_img.original = mock_img
    mock_page.to_image.return_value = mock_img

    with patch("numpy.array", return_value=MagicMock()), \
         patch("pathlib.Path.exists", return_value=False), \
         patch("pathlib.Path.mkdir"), \
         patch("builtins.open", MagicMock()):
        blocks = engine.process_scanned_page(
            page=mock_page,
            page_number=13,
            company="VNM",
            year=2024,
        )

    assert len(blocks) == 1
    assert "Công ty Cổ phần" in blocks[0].content
    assert "Thuyết minh số 1" in blocks[0].content
    assert mock_viet.predict_batch.called


def test_local_ocr_release_memory():
    """Kiểm tra hàm _release_memory dọn dẹp RAM và VRAM không phát sinh lỗi."""
    LocalOCREngine._release_memory()


def test_local_ocr_mineru_vietocr_mocked():
    """Kiểm tra luồng Hướng A (MinerU Layout + VietOCR Text) được ưu tiên khi MinerU có sẵn."""
    engine = LocalOCREngine(engine="auto")

    mock_table_block = ParsedBlock(
        block_id="p13_mineru_tbl_1",
        block_type="table",
        page=13,
        content="| Mục | Giá trị |\n| --- | --- |\n| Vốn điều lệ | 20.000 tỷ |",
        source="local_ocr",
        metadata={"engine": "mineru_table"},
    )
    mock_text_block = ParsedBlock(
        block_id="p13_mineru_vocr_2",
        block_type="text",
        page=13,
        content="Thuyết minh số 1: Đặc điểm hoạt động của doanh nghiệp",
        source="local_ocr",
        metadata={"engine": "mineru_vietocr"},
    )

    mock_page = MagicMock()

    with patch.object(engine, "_find_mineru_binary", return_value="magic-pdf"), \
         patch.object(engine, "_extract_with_mineru_and_vietocr", return_value=[mock_table_block, mock_text_block]) as mock_mineru, \
         patch("pathlib.Path.exists", return_value=False), \
         patch("pathlib.Path.mkdir"), \
         patch("builtins.open", MagicMock()):

        blocks = engine.process_scanned_page(
            page=mock_page,
            page_number=13,
            company="VNM",
            year=2024,
        )

    assert mock_mineru.called
    assert len(blocks) == 2
    assert blocks[0].block_type == "table"
    assert blocks[0].metadata["engine"] == "mineru_table"
    assert blocks[1].block_type == "text"
    assert blocks[1].metadata["engine"] == "mineru_vietocr"
    assert "20.000 tỷ" in blocks[0].content
    assert "Đặc điểm hoạt động" in blocks[1].content


def test_reconstruct_blocks_table_and_text():
    """Kiểm tra logic tái cấu trúc bảng và văn bản 2D từ bounding box OCR."""
    engine = LocalOCREngine(engine="auto")

    ocr_items = [
        # Text Header (y=10)
        [[[50, 10], [300, 10], [300, 30], [50, 30]], "19. Thay đổi vốn chủ sở hữu", 0.99],
        # Table Row 1: Header (y=60)
        [[[50, 60], [200, 60], [200, 80], [50, 80]], "Vốn cổ phần", 0.95],
        [[[300, 60], [450, 60], [450, 80], [300, 80]], "Tổng cộng VND", 0.95],
        # Table Row 2: Data (y=100)
        [[[50, 100], [200, 100], [200, 120], [50, 120]], "20.899.554.450.000", 0.95],
        [[[300, 100], [450, 100], [450, 120], [300, 120]], "30.687.957.547.001", 0.95],
        # Table Row 3: Data (y=140)
        [[[50, 140], [200, 140], [200, 160], [50, 160]], "Lợi nhuận thuần trong năm", 0.95],
        [[[300, 140], [450, 140], [450, 160], [300, 160]], "9.262.413.822.949", 0.95],
    ]

    blocks = engine._reconstruct_blocks_from_ocr_items(
        ocr_items=ocr_items,
        page_number=42,
        company="VNM",
        year=2024,
        engine_name="vietocr_test",
    )

    assert len(blocks) == 2
    # Block 1: Text Header
    assert blocks[0].block_type == "text"
    assert "Thay đổi vốn chủ sở hữu" in blocks[0].content

    # Block 2: Table
    assert blocks[1].block_type == "table"
    assert blocks[1].is_table is True
    assert "| " in blocks[1].content
    assert "20.899.554.450.000" in blocks[1].content
    assert blocks[1].metadata["num_rows"] == 2
    assert blocks[1].metadata["num_cols"] >= 2


def test_anti_pseudo_table_demotes_to_text():
    """Kiểm tra cơ chế Anti-Pseudo-Table: Văn bản chia nhiều box nhưng không có cột số thì xuất ra text, không tạo bảng 1 cột."""
    from src.parser.local_ocr import LocalOCREngine

    engine = LocalOCREngine(engine="auto")

    # Đoạn văn bản narrative bị cắt thành nhiều box trên cùng dòng nhưng KHÔNG CÓ SỐ
    ocr_items = [
        [[[50, 10], [200, 10], [200, 30], [50, 30]], "1. THÔNG TIN DOANH NGHIỆP", 0.98],
        [[[210, 10], [400, 10], [400, 30], [210, 30]], "Hình thức sở hữu vốn", 0.98],
        [[[50, 50], [300, 50], [300, 70], [50, 70]], "Công ty Cổ phần Sữa Việt Nam là công ty", 0.98],
        [[[310, 50], [500, 50], [500, 70], [310, 70]], "được thành lập tại Việt Nam", 0.98],
    ]

    blocks = engine._reconstruct_blocks_from_ocr_items(
        ocr_items=ocr_items,
        page_number=11,
        company="VNM",
        year=2024,
        engine_name="test_anti_pseudo",
    )

    # Tuyệt đối KHÔNG được tạo bảng giả 1 cột
    assert len(blocks) == 1
    assert blocks[0].block_type == "text"
    assert "| Khoản mục / Chỉ tiêu |" not in blocks[0].content
    assert "1. THÔNG TIN DOANH NGHIỆP" in blocks[0].content


def test_strip_boilerplate_lines():
    """Kiểm tra hàm strip_boilerplate_lines lọc bỏ đúng các mẫu câu hành chính lặp lại."""
    from src.parser.ocr_postprocess import strip_boilerplate_lines

    dirty_text = (
        "Công ty Cổ phần Sữa Việt Nam\n"
        "Thuyết minh báo cáo tài chính riêng cho năm kết thúc ngày 31 tháng 12 năm 2025 (tiếp theo)\n"
        "Mẫu B 09 - DN\n"
        "Ban hành theo Thông tư số 200/2014/TT-BTC\n"
        "ngày 22 tháng 12 năm 2014 của Bộ Tài chính)\n"
        "1. THÔNG TIN DOANH NGHIỆP\n"
        "Công ty hoạt động trong lĩnh vực chế biến sữa.\n"
        "Các thuyết minh này là bộ phận hợp thành và cần được đọc đồng thời...\n"
        "12\n"
    )

    cleaned = strip_boilerplate_lines(dirty_text)

    assert "Mẫu B 09 - DN" not in cleaned
    assert "Thông tư số 200" not in cleaned
    assert "Các thuyết minh này là bộ phận hợp thành" not in cleaned
    assert "12" not in cleaned
    assert "1. THÔNG TIN DOANH NGHIỆP" in cleaned
    assert "Công ty hoạt động trong lĩnh vực chế biến sữa." in cleaned


def test_polish_table_headers():
    """Kiểm tra logic làm sạch và gán tiêu đề ngày tháng ngữ nghĩa cho cột bảng."""
    from src.parser.local_ocr import _polish_table_headers

    # Case 1: 3 cột với 'Cột 1', 'Cột 2'
    h1 = ["Khoản mục / Chỉ tiêu", "Cột 1", "Cột 2"]
    res1 = _polish_table_headers(h1, year=2024)
    assert res1 == ["Khoản mục / Chỉ tiêu", "31/12/2024 VND", "1/1/2024 VND"]

    # Case 2: 3 cột với trùng 'VND', 'VND'
    h2 = ["Khoản mục / Chỉ tiêu", "VND", "VND"]
    res2 = _polish_table_headers(h2, year=2024)
    assert res2 == ["Khoản mục / Chỉ tiêu", "31/12/2024 VND", "1/1/2024 VND"]

    # Case 3: 5 cột với 'Cột 1' .. 'Cột 4'
    h3 = ["Khoản mục / Chỉ tiêu", "Cột 1", "Cột 2", "Cột 3", "Cột 4"]
    res3 = _polish_table_headers(h3, year=2024)
    assert "31/12/2024 Giá gốc" in res3[1]
    assert "1/1/2024 Giá gốc" in res3[3]

    # Case 4: Cột bị dính câu văn tường thuật dài (> 40 ký tự)
    h4 = [
        "Khoản mục / Chỉ tiêu",
        "Cột 1",
        "Vao ngay 19 thang 2 nam 2025 va ngay 9 thang 6 nam 2025, Cong ty da lan luqt gop them",
    ]
    res4 = _polish_table_headers(h4, year=2024)
    assert "31/12/2024 VND" in res4[1]
    assert "1/1/2024 VND" in res4[2]
    assert "Vao ngay 19" not in res4[2]


def test_sanitize_and_polish_blocks():
    """Kiểm tra cơ chế thanh lọc demote pseudo-tables thành text và chuẩn hóa headers."""
    from src.parser.local_ocr import _sanitize_and_polish_blocks

    # Block 1: Pseudo-table chỉ có 1 dòng dữ liệu và header chứa câu tường thuật dài
    pseudo_tbl = ParsedBlock(
        block_id="p15_tbl_1",
        block_type="table",
        page=15,
        content=(
            "| Khoản mục / Chỉ tiêu | Cột 1 | Vào ngày 19 tháng 2 năm 2024 Công ty đã góp vốn |\n"
            "| --- | --- | --- |\n"
            "| | 7.000.000.178.296 | 6.800.000 |"
        ),
        metadata={
            "num_rows": 1,
            "numeric_density": 0.0,
            "headers": ["Khoản mục / Chỉ tiêu", "Cột 1", "Vào ngày 19 tháng 2 năm 2024 Công ty đã góp vốn"],
        },
    )

    # Block 2: Bảng thật với headers 'VND', 'VND'
    real_tbl = ParsedBlock(
        block_id="p27_tbl_1",
        block_type="table",
        page=27,
        content=(
            "| Khoản mục / Chỉ tiêu | VND | VND |\n"
            "| --- | --- | --- |\n"
            "| Tiền mặt | 51.123.592 | 234.534.487 |\n"
            "| Tiền gửi ngân hàng | 1.047.577.721.603 | 1.408.333.166.834 |"
        ),
        metadata={
            "num_rows": 2,
            "numeric_density": 0.8,
            "headers": ["Khoản mục / Chỉ tiêu", "VND", "VND"],
        },
    )

    sanitized = _sanitize_and_polish_blocks([pseudo_tbl, real_tbl], year=2024)
    assert len(sanitized) == 2

    # Block 1 phải được demote thành text
    assert sanitized[0].block_type == "text"
    assert "Vào ngày 19 tháng 2 năm 2024" in sanitized[0].content

    # Block 2 giữ nguyên là table nhưng header được nâng cấp
    assert sanitized[1].block_type == "table"
    assert "31/12/2024 VND" in sanitized[1].content
    assert "1/1/2024 VND" in sanitized[1].content
    assert sanitized[1].metadata["headers"] == ["Khoản mục / Chỉ tiêu", "31/12/2024 VND", "1/1/2024 VND"]


def test_trailing_footnote_separation():
    """Kiểm tra dòng ghi chú cuối bảng không bị gộp vào ma trận bảng mà chuyển thành chú thích đuôi."""
    engine = LocalOCREngine(engine="auto")

    ocr_items = [
        # Table Header
        [[[50, 60], [200, 60], [200, 80], [50, 80]], "Khoản mục", 0.95],
        [[[250, 60], [400, 60], [400, 80], [250, 80]], "31/12/2024 VND", 0.95],
        [[[450, 60], [600, 60], [600, 80], [450, 80]], "1/1/2024 VND", 0.95],
        # Table Data Row 1
        [[[50, 100], [200, 100], [200, 120], [50, 120]], "Phải thu ngắn hạn", 0.95],
        [[[250, 100], [400, 100], [400, 120], [250, 120]], "5.123.456.789", 0.95],
        [[[450, 100], [600, 100], [600, 120], [450, 120]], "4.000.111.222", 0.95],
        # Table Data Row 2
        [[[50, 140], [200, 140], [200, 160], [50, 160]], "Tổng cộng", 0.95],
        [[[250, 140], [400, 140], [400, 160], [250, 160]], "5.123.456.789", 0.95],
        [[[450, 140], [600, 140], [600, 160], [450, 160]], "4.000.111.222", 0.95],
        # Footnote at bottom of table
        [[[50, 180], [500, 180], [500, 200], [50, 200]], "(1) Số dư này bao gồm tiền gửi có kỳ hạn tại ngân hàng.", 0.95],
    ]

    blocks = engine._reconstruct_blocks_from_ocr_items(
        ocr_items=ocr_items,
        page_number=28,
        company="VNM",
        year=2024,
        engine_name="test_footnote",
    )

    assert len(blocks) == 2
    table_block = blocks[0]
    footnote_block = blocks[1]
    assert table_block.block_type == "table"
    assert footnote_block.block_type == "text"
    # Tổng cộng không bị dính câu chú thích vào cột tên
    assert "| Tổng cộng | 5.123.456.789 | 4.000.111.222 |" in table_block.content
    # Footnote được tách sạch thành text block riêng biệt
    assert "(1) Số dư này bao gồm tiền gửi có kỳ hạn" in footnote_block.content



