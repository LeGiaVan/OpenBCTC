"""
conftest.py — Pytest fixtures dùng chung cho bộ kiểm thử FinAudit AI.
"""

from unittest.mock import MagicMock

import pytest

from src.models import ParsedBlock


@pytest.fixture
def sample_balance_sheet_table() -> list[list[str]]:
    """Dữ liệu bảng Cân đối kế toán mẫu với cột chỉ tiêu, mã số, thuyết minh, số cuối năm, số đầu năm."""
    return [
        ["CHỈ TIÊU", "Mã số", "Thuyết minh", "Số cuối năm", "Số đầu năm"],
        ["TÀI SẢN NGẮN HẠN", "100", "", "35.200.500.000", "28.150.000.000"],
        ["1. Tiền và các khoản tương đương tiền", "110", "V.01", "5.400.000.000", "4.200.000.000"],
        ["2. Đầu tư tài chính ngắn hạn", "120", "V.02", "12.000.000.000", "9.500.000.000"],
        ["3. Các khoản phải thu ngắn hạn", "130", "V.03", "8.600.500.000", "7.100.000.000"],
        ["4. Hàng tồn kho", "140", "V.04", "9.200.000.000", "7.350.000.000"],
        ["TỔNG CỘNG TÀI SẢN", "270", "", "52.800.000.000", "45.000.000.000"],
    ]


@pytest.fixture
def sample_income_statement_table_with_negatives() -> list[list[str]]:
    """Bảng Kết quả kinh doanh mẫu có số âm dạng ngoặc đơn: (1,234,000,000)."""
    return [
        ["Chỉ tiêu", "Mã số", "Thuyết minh", "Năm nay", "Năm trước"],
        ["1. Doanh thu bán hàng và cung cấp dịch vụ", "01", "VI.25", "125.000.000.000", "110.000.000.000"],
        ["2. Các khoản giảm trừ doanh thu", "02", "VI.26", "(2.500.000.000)", "(1.800.000.000)"],
        ["3. Doanh thu thuần (10 = 01 - 02)", "10", "VI.25", "122.500.000.000", "108.200.000.000"],
        ["4. Giá vốn hàng bán", "11", "VI.27", "(85.000.000.000)", "(76.000.000.000)"],
        ["5. Lợi nhuận gộp về bán hàng", "20", "", "37.500.000.000", "32.200.000.000"],
        ["6. Chi phí tài chính", "22", "VI.28", "(3.200.000.000)", "(2.900.000.000)"],
        ["7. Lợi nhuận sau thuế thu nhập doanh nghiệp", "60", "", "18.400.000.000", "15.100.000.000"],
    ]


@pytest.fixture
def sample_numeric_note_inventory() -> list[list[str]]:
    """Bảng Thuyết minh chi tiết Hàng tồn kho."""
    return [
        ["Đối tượng hàng hóa", "Giá gốc", "Dự phòng giảm giá", "Giá trị thuần"],
        ["Nguyên vật liệu", "4.500.000.000", "(200.000.000)", "4.300.000.000"],
        ["Công cụ, dụng cụ", "800.000.000", "-", "800.000.000"],
        ["Chi phí sản xuất kinh doanh dở dang", "1.200.000.000", "-", "1.200.000.000"],
        ["Thành phẩm tồn kho", "2.700.000.000", "(150.000.000)", "2.550.000.000"],
        ["Tổng số", "9.200.000.000", "(350.000.000)", "8.850.000.000"],
    ]


@pytest.fixture
def sample_narrative_table_board() -> list[list[str]]:
    """Bảng phi số liệu (Danh sách thành viên HĐQT)."""
    return [
        ["Họ và tên", "Chức vụ", "Ngày bổ nhiệm"],
        ["Nguyễn Văn A", "Chủ tịch HĐQT", "15/04/2021"],
        ["Trần Thị B", "Thành viên HĐQT", "15/04/2021"],
    ]


@pytest.fixture
def sample_policy_text_block() -> ParsedBlock:
    """Block văn bản Chính sách kế toán."""
    content = (
        "IV. CÁC CHÍNH SÁCH KẾ TOÁN ÁP DỤNG\n\n"
        "1. Nguyên tắc ghi nhận doanh thu: Doanh thu bán hàng được ghi nhận khi đồng thời "
        "thỏa mãn các điều kiện chuyển giao phần lớn rủi ro và lợi ích gắn liền với quyền sở hữu. "
        "Doanh thu cung cấp dịch vụ được ghi nhận khi kết quả của giao dịch đó được xác định một cách đáng tin cậy. "
        "Phương pháp khấu hao tài sản cố định áp dụng phương pháp đường thẳng theo chuẩn mực kế toán Việt Nam."
    )
    return ParsedBlock(
        block_id="p12_b1",
        block_type="text",
        page=12,
        content=content,
        bbox=(50.0, 50.0, 550.0, 250.0),
        metadata={"unit": "VND"},
    )


@pytest.fixture
def sample_mda_text_block() -> ParsedBlock:
    """Block văn bản Báo cáo Ban Giám Đốc."""
    content = (
        "BÁO CÁO CỦA BAN TỔNG GIÁM ĐỐC\n\n"
        "Trong năm tài chính 2024, tình hình kinh tế vĩ mô có nhiều biến động nhưng công ty vẫn giữ vững "
        "tăng trưởng thị phần. Đánh giá của ban giám đốc cho thấy chuỗi cung ứng đã phục hồi ổn định, "
        "kế hoạch sản xuất kinh doanh năm 2025 sẽ tiếp tục tập trung vào thị trường xuất khẩu."
    )
    return ParsedBlock(
        block_id="p3_b1",
        block_type="text",
        page=3,
        content=content,
        bbox=(50.0, 50.0, 550.0, 300.0),
        metadata={},
    )


@pytest.fixture
def sample_mixed_text_block() -> ParsedBlock:
    """Block văn bản hỗn hợp chứa nhiều số liệu định lượng."""
    content = (
        "Trong năm 2024, công ty đã tiến hành chi trả cổ tức bằng tiền mặt với tổng giá trị 2.500 tỷ đồng, "
        "tương ứng tỷ lệ 25% trên vốn điều lệ. Tổng chi phí đầu tư tài sản cố định đạt 1.850 tỷ VND, "
        "trong khi dư nợ vay ngân hàng giảm 450 tỷ đồng so với đầu năm."
    )
    return ParsedBlock(
        block_id="p18_b2",
        block_type="text",
        page=18,
        content=content,
        bbox=(50.0, 300.0, 550.0, 450.0),
        metadata={},
    )


@pytest.fixture
def mock_pdfplumber_page(sample_balance_sheet_table):
    """Tạo mock pdfplumber Page với 1 bảng và 2 đoạn văn bản trên/dưới bảng."""
    page = MagicMock()
    page.width = 600.0
    page.height = 800.0

    # Mock table object
    mock_table = MagicMock()
    mock_table.bbox = (50.0, 200.0, 550.0, 500.0)
    mock_table.extract.return_value = sample_balance_sheet_table
    page.find_tables.return_value = [mock_table]

    # Mock crop cho các vùng text
    top_crop = MagicMock()
    top_crop.extract_text.return_value = "BẢNG CÂN ĐỐI KẾ TOÁN\nTại ngày 31 tháng 12 năm 2024\nĐơn vị tính: Đồng Việt Nam"

    tail_crop = MagicMock()
    tail_crop.extract_text.return_value = "Người lập biểu                Kế toán trưởng                Tổng Giám đốc"

    def crop_side_effect(bbox):
        top_y = bbox[1]
        if top_y < 100:
            return top_crop
        return tail_crop

    page.crop.side_effect = crop_side_effect
    page.extract_text.return_value = "BẢNG CÂN ĐỐI KẾ TOÁN..."

    return page
