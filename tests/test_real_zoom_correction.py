"""
test_real_zoom_correction.py — Kiểm thử tự động kịch bản thực tế phát hiện sai số và tự sửa bằng Vision-LLM Zoom.
Sử dụng trực tiếp file BCTC Vinamilk scan thực tế (vnm.pdf):
  1. Cắt ảnh thật từ trang scan (Trang 8).
  2. Tạo sai lệch giả lập (Mã 270 bị lệch 5 nghìn tỷ do OCR đọc sai).
  3. Kích hoạt VisionZoomCorrector crop thật ảnh dòng và tự sửa sai.
"""

from pathlib import Path
from unittest.mock import patch
import pytest

from src.models import FinancialFact, VerificationStatus
from src.verifier.accounting_verifier import AccountingVerifier
from src.verifier.vision_zoom_corrector import VisionZoomCorrector


def test_real_pdf_zoom_correction_end_to_end(tmp_path):
    """Kiểm thử toàn trình trên file vnm.pdf thực tế."""
    pdf_path = "vnm.pdf"
    if not Path(pdf_path).exists():
        pytest.skip("vnm.pdf không tồn tại trong môi trường kiểm thử.")

    verifier = AccountingVerifier()
    corrector = VisionZoomCorrector(verifier=verifier)

    # 1. Khởi tạo Facts với lỗi OCR giả lập tại dòng Tổng tài sản (Mã 270)
    fact_cur = FinancialFact(
        id="VNM_2024_p7_tbl1_r1",
        prov_id="VNM_2024_p7_tbl1_r1",
        concept="CURRENT_ASSETS",
        standard_code="100",
        raw_label="TÀI SẢN NGẮN HẠN",
        value=27309234148199.0,
        page=7,
        company="VNM",
        year=2024,
    )
    fact_non_cur = FinancialFact(
        id="VNM_2024_p8_tbl1_r1",
        prov_id="VNM_2024_p8_tbl1_r1",
        concept="NON_CURRENT_ASSETS",
        standard_code="200",
        raw_label="TÀI SẢN DÀI HẠN",
        value=18643262824437.0,
        page=8,
        company="VNM",
        year=2024,
    )
    # Lỗi: 40.952 tỷ thay vì 45.952 tỷ
    fact_total = FinancialFact(
        id="VNM_2024_p8_tbl1_r25",
        prov_id="VNM_2024_p8_tbl1_r25",
        concept="TOTAL_ASSETS",
        standard_code="270",
        raw_label="TỔNG TÀI SẢN (270 = 100 + 200)",
        value=40952496972636.0,
        page=8,
        company="VNM",
        year=2024,
    )

    facts = [fact_cur, fact_non_cur, fact_total]

    # Kiểm tra trước khi sửa: BCTC bị lệch
    initial_report = verifier.verify_facts(facts, company="VNM", year=2024)
    assert initial_report.is_balanced is False
    assert len(initial_report.discrepancies) == 1
    assert initial_report.discrepancies[0]["delta"] == 5000000000000.0

    # 2. Mock inspect_row_image để kiểm thử deterministic (tránh phụ thuộc mạng khi chạy pytest)
    mock_inspection_result = {
        "raw_text": "45.952.496.972.636",
        "value_current": 45952496972636.0,
        "is_negative": False,
        "confidence": 0.99,
    }

    with patch.object(corrector, "inspect_row_image", return_value=mock_inspection_result):
        corrected_facts, final_report, is_corrected = corrector.run_self_correction(
            pdf_path=pdf_path,
            facts=facts,
            report=initial_report,
            company="VNM",
            year=2024,
            save_debug_dir=str(tmp_path),
        )

    # 3. Khẳng định kết quả
    assert is_corrected is True
    assert final_report.is_balanced is True

    fixed_fact = next(f for f in corrected_facts if f.concept == "TOTAL_ASSETS")
    assert fixed_fact.value == 45952496972636.0
    assert fixed_fact.verification_status == VerificationStatus.VERIFIED_AFTER_ZOOM_CORRECTION

    # Kiểm tra ảnh debug đã được lưu thực tế trên đĩa
    saved_images = list(tmp_path.glob("*.png"))
    assert len(saved_images) >= 2
    assert any("zoomed_row_TOTAL_ASSETS" in p.name for p in saved_images)
    assert any("annotated_page_8_TOTAL_ASSETS" in p.name for p in saved_images)
