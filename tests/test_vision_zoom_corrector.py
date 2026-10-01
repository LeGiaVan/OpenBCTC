"""
test_vision_zoom_corrector.py — Kiểm thử tự động cho module Agentic Vision-LLM Zoom Corrector.
Kiểm tra:
  1. Cơ chế Suy luận Loại trừ (Deductive Elimination) khoanh vùng đúng Fact nghi vấn.
  2. Vòng lặp Tự sửa sai Cục bộ (Self-Correction Loop) với Mock Vision API.
  3. Bỏ qua khi BCTC đã cân đối (No-op when already balanced).
  4. Cơ chế Revert an toàn khi giá trị đọc lại không giúp cân đối BCTC.
"""

from unittest.mock import MagicMock, patch
from PIL import Image

from src.models import FinancialFact, VerificationReport, VerificationStatus
from src.verifier.accounting_verifier import AccountingVerifier
from src.verifier.vision_zoom_corrector import VisionZoomCorrector


def _create_sample_fact(
    concept: str,
    value: float,
    code: str = "",
    label: str = "",
    page: int = 1,
) -> FinancialFact:
    return FinancialFact(
        id=f"TEST_{concept}",
        prov_id=f"TEST_p{page}_{concept}",
        concept=concept,
        standard_code=code,
        raw_label=label or concept,
        value=value,
        period_type="current",
        period="2024",
        company="TEST_CO",
        year=2024,
        page=page,
        table_id="t1",
        row_label=label or concept,
        confidence=1.0,
    )


def test_identify_suspect_facts_deductive():
    """Kiểm tra Deductive Elimination: Giảm điểm nghi ngờ của Tài sản khi Ngắn + Dài đã cân."""
    corrector = VisionZoomCorrector()

    facts = [
        _create_sample_fact("TOTAL_ASSETS", 1000.0, "270", "Tổng tài sản"),
        _create_sample_fact("CURRENT_ASSETS", 600.0, "100", "Tài sản ngắn hạn"),
        _create_sample_fact("NON_CURRENT_ASSETS", 400.0, "200", "Tài sản dài hạn"),
        _create_sample_fact("TOTAL_RESOURCES", 1200.0, "440", "Tổng nguồn vốn"),
        _create_sample_fact("LIABILITIES", 700.0, "300", "Nợ phải trả"),
        _create_sample_fact("EQUITY", 400.0, "400", "Vốn chủ sở hữu"),
    ]

    # Giả lập:
    # - Check 1 (270 == 440) THẤT BẠI (1000 != 1200)
    # - Check 2 (270 == 100 + 200) ĐẠT (1000 == 600 + 400)
    # - Check 4 (440 == 300 + 400) THẤT BẠI (1200 != 700 + 400)
    report = VerificationReport(
        company="TEST_CO",
        year=2024,
        is_balanced=False,
        total_checks=3,
        passed_checks=["CỘNG_TỔNG_TÀI_SẢN: Tài sản (270) == Ngắn hạn (100) + Dài hạn (200)"],
        failed_checks=[
            "LỆCH_CÂN_ĐỐI: Tổng tài sản (1,000) != Tổng nguồn vốn (1,200)",
            "LỆCH_NGUỒN_VỐN: Báo cáo (1,200) != Tính toán (1,100)",
        ],
        discrepancies=[
            {"check": "TOTAL_ASSETS == TOTAL_RESOURCES", "delta": 200},
            {"check": "TOTAL_RESOURCES == LIABILITIES + EQUITY", "delta": 100},
        ],
    )

    suspects = corrector.identify_suspect_facts(report, facts)
    suspect_concepts = [f.concept for f in suspects]

    # Vì Check 2 ĐẠT, nhóm Tài sản được giảm điểm.
    # Nhóm Nguồn vốn (TOTAL_RESOURCES, LIABILITIES, EQUITY) phải đứng đầu danh sách nghi vấn!
    assert "TOTAL_RESOURCES" in suspect_concepts
    assert suspect_concepts[0] == "TOTAL_RESOURCES"


def test_identify_suspect_facts_gross_profit():
    """Kiểm tra nhận diện đúng nhóm Kết quả Kinh doanh khi Lợi nhuận gộp lệch."""
    corrector = VisionZoomCorrector()

    facts = [
        _create_sample_fact("NET_REVENUE", 1000.0, "10", "Doanh thu thuần"),
        _create_sample_fact("COGS", 700.0, "11", "Giá vốn hàng bán"),
        _create_sample_fact("GROSS_PROFIT", 500.0, "20", "Lợi nhuận gộp"),  # Đáng lẽ phải là 300
    ]

    report = VerificationReport(
        company="TEST_CO",
        year=2024,
        is_balanced=False,
        total_checks=1,
        passed_checks=[],
        failed_checks=["LỆCH_LN_GỘP: Báo cáo (500) != Tính toán (300)"],
        discrepancies=[{"check": "GROSS_PROFIT == NET_REVENUE - COGS", "delta": 200}],
    )

    suspects = corrector.identify_suspect_facts(report, facts)
    suspect_concepts = [f.concept for f in suspects]
    assert set(suspect_concepts) == {"GROSS_PROFIT", "NET_REVENUE", "COGS"}


def test_identify_suspect_facts_cash_flow_deductive():
    """Kiểm tra nhận diện đúng nhóm LCTT khi Dòng tiền tài chính bị lệch."""
    corrector = VisionZoomCorrector()
    facts = [
        _create_sample_fact("CF_NET_FINANCING", 500.0, "40", "Lưu chuyển tiền từ hoạt động tài chính"),
        _create_sample_fact("CF_BORROWINGS", 1000.0, "33", "Tiền thu từ đi vay"),
        _create_sample_fact("CF_REPAYMENTS", -600.0, "34", "Tiền chi trả nợ gốc vay"),
    ]

    report = VerificationReport(
        company="TEST_CO",
        year=2024,
        is_balanced=False,
        total_checks=1,
        passed_checks=[],
        failed_checks=["LỆCH_LCTT_HĐTC: Báo cáo (500) != Tính toán (400)"],
        discrepancies=[{"check": "CF_NET_FINANCING == 31 - 32 + 33 - 34 - 35 - 36", "delta": 100}],
    )

    suspects = corrector.identify_suspect_facts(report, facts)
    suspect_concepts = [f.concept for f in suspects]

    assert "CF_NET_FINANCING" in suspect_concepts
    assert "CF_BORROWINGS" in suspect_concepts
    assert "CF_REPAYMENTS" in suspect_concepts


def test_identify_suspect_facts_cross_check_cash_deductive():
    """Kiểm tra Deductive Localization chéo liên bảng:
    Khi tiền cuối kỳ LCTT (70) != Tiền CĐKT (110), nhưng CĐKT đã chứng minh cân đối dọc ngắn hạn,
    bộ suy luận loại trừ xác định dòng Tiền LCTT (70) là kẻ tình nghi số 1!
    """
    corrector = VisionZoomCorrector()
    facts = [
        _create_sample_fact("CASH_AND_EQUIVALENTS", 1000.0, "110", "Tiền và tương đương tiền"),
        _create_sample_fact("CF_ENDING_CASH", 1200.0, "70", "Tiền và tương đương tiền cuối kỳ"),
    ]

    report = VerificationReport(
        company="TEST_CO",
        year=2024,
        is_balanced=False,
        total_checks=2,
        passed_checks=["CỘNG_DỌC_NGẮN_HẠN: TS Ngắn hạn (100) == ∑(khoản mục con)"],
        failed_checks=["LỆCH_ĐỐI_CHIẾU_CHÉO_TIỀN: LCTT (1,200) != CĐKT (1,000)"],
        discrepancies=[{"check": "CROSS_CHECK_CASH == CF_ENDING vs BS_CASH", "delta": 200}],
    )

    suspects = corrector.identify_suspect_facts(report, facts)
    suspect_concepts = [f.concept for f in suspects]

    assert len(suspect_concepts) == 1
    assert suspect_concepts[0] == "CF_ENDING_CASH"


def test_run_self_correction_when_already_balanced():
    """Nếu BCTC đã cân đối từ trước, corrector trả về ngay không gọi crop hay LLM."""
    corrector = VisionZoomCorrector()
    facts = [_create_sample_fact("TOTAL_ASSETS", 1000.0)]
    report = VerificationReport(company="TEST_CO", year=2024, is_balanced=True)

    res_facts, res_report, is_corrected = corrector.run_self_correction(
        pdf_path="dummy.pdf",
        facts=facts,
        report=report,
    )

    assert is_corrected is False
    assert res_report.is_balanced is True


@patch.object(VisionZoomCorrector, "locate_and_crop_row")
@patch.object(VisionZoomCorrector, "inspect_row_image")
def test_run_self_correction_success(mock_inspect, mock_crop):
    """Giả lập Vision LLM đọc lại đúng số và BCTC trở nên cân đối hoàn toàn."""
    # Bảng CĐKT ban đầu:
    # Tài sản 1000 == 600 + 400 (Cân đối)
    # Nguồn vốn: Nợ 600 + Vốn 400 = 1000, NHƯNG dòng TOTAL_RESOURCES bị OCR nhầm thành 1200
    facts = [
        _create_sample_fact("TOTAL_ASSETS", 1000.0, "270", "Tổng tài sản"),
        _create_sample_fact("CURRENT_ASSETS", 600.0, "100", "Tài sản ngắn hạn"),
        _create_sample_fact("NON_CURRENT_ASSETS", 400.0, "200", "Tài sản dài hạn"),
        _create_sample_fact("TOTAL_RESOURCES", 1200.0, "440", "Tổng nguồn vốn"),  # Sai! Đúng là 1000
        _create_sample_fact("LIABILITIES", 600.0, "300", "Nợ phải trả"),
        _create_sample_fact("EQUITY", 400.0, "400", "Vốn chủ sở hữu"),
    ]

    verifier = AccountingVerifier()
    initial_report = verifier.verify_facts(facts, company="TEST_CO", year=2024)
    assert initial_report.is_balanced is False

    # Mock crop ảnh thành công
    dummy_img = Image.new("RGB", (100, 30), color="white")
    mock_crop.return_value = (dummy_img, "dummy_b64", "Năm nay (2025)")

    # Mock Vision LLM đọc lại: TOTAL_RESOURCES thực ra là 1000.0
    mock_inspect.return_value = {
        "raw_text": "1.000.000.000",
        "value_current": 1000.0,
        "is_negative": False,
        "confidence": 0.98,
    }

    corrector = VisionZoomCorrector(verifier=verifier)
    corrected_facts, final_report, is_corrected = corrector.run_self_correction(
        pdf_path="dummy.pdf",
        facts=facts,
        report=initial_report,
        company="TEST_CO",
        year=2024,
    )

    # Kiểm tra kết quả tự sửa sai
    assert is_corrected is True
    assert final_report.is_balanced is True
    assert len(final_report.failed_checks) == 0
    assert len(final_report.correction_history) == 1

    entry = final_report.correction_history[0]
    assert entry["concept"] == "TOTAL_RESOURCES"
    assert entry["old_value"] == 1200.0
    assert entry["new_value"] == 1000.0

    target_fact = next(f for f in corrected_facts if f.concept == "TOTAL_RESOURCES")
    assert target_fact.value == 1000.0
    assert target_fact.verification_status == VerificationStatus.VERIFIED_AFTER_ZOOM_CORRECTION


@patch.object(VisionZoomCorrector, "locate_and_crop_row")
@patch.object(VisionZoomCorrector, "inspect_row_image")
def test_run_self_correction_revert_when_unhelpful(mock_inspect, mock_crop):
    """Nếu con số đọc lại không giúp cân đối BCTC, corrector tự động revert về giá trị ban đầu."""
    facts = [
        _create_sample_fact("TOTAL_ASSETS", 1000.0, "270", "Tổng tài sản"),
        _create_sample_fact("CURRENT_ASSETS", 600.0, "100", "Tài sản ngắn hạn"),
        _create_sample_fact("NON_CURRENT_ASSETS", 400.0, "200", "Tài sản dài hạn"),
        _create_sample_fact("TOTAL_RESOURCES", 1200.0, "440", "Tổng nguồn vốn"),
        _create_sample_fact("LIABILITIES", 600.0, "300", "Nợ phải trả"),
        _create_sample_fact("EQUITY", 400.0, "400", "Vốn chủ sở hữu"),
    ]

    verifier = AccountingVerifier()
    initial_report = verifier.verify_facts(facts, company="TEST_CO", year=2024)

    dummy_img = Image.new("RGB", (100, 30), color="white")
    mock_crop.return_value = (dummy_img, "dummy_b64", "Năm nay (2025)")

    # Giả lập Vision LLM đọc ra một số khác nhưng vẫn sai lệch (ví dụ 1500)
    mock_inspect.return_value = {
        "raw_text": "1.500.000.000",
        "value_current": 1500.0,
        "is_negative": False,
        "confidence": 0.85,
    }

    corrector = VisionZoomCorrector(verifier=verifier)
    corrected_facts, final_report, is_corrected = corrector.run_self_correction(
        pdf_path="dummy.pdf",
        facts=facts,
        report=initial_report,
        company="TEST_CO",
        year=2024,
    )

    assert is_corrected is False
    assert final_report.is_balanced is False
    # Fact phải được revert về 1200 ban đầu
    target_fact = next(f for f in corrected_facts if f.concept == "TOTAL_RESOURCES")
    assert target_fact.value == 1200.0
