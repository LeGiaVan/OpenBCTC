"""
demo_real_zoom_correction.py — Demo Test Case Thực tế: Phát hiện Sai Lệch Số Liệu OCR và Tự Động Sửa Bằng Vision-LLM Zoom.

Kịch bản thực tế trên BCTC Vinamilk (vnm.pdf):
  1. Ban đầu OCR bị lem số: Đọc nhầm Mã 270 (Tổng tài sản) thành 40.952.496.972.636 (lệch đúng 5.000 tỷ VND).
  2. AccountingVerifier kiểm toán số học: Phát hiện lệch phương trình Mã 270 != 100 + 200.
  3. VisionZoomCorrector kích hoạt:
     - Tự động khoanh vùng Mã 270 trên Trang 8 của vnm.pdf.
     - Cắt ảnh dải ngang dòng độ phân giải cao và vẽ bounding box đỏ trên toàn trang.
     - Lưu các hình ảnh vào thư mục 'data/logs/zoom_demo/'.
     - Gọi Vision API đọc lại con số thực trên ảnh phóng to: 45.952.496.972.636 VND.
     - Hot-patch giá trị và re-verify tự động -> BCTC đạt trạng thái HOÀN TOÀN CÂN ĐỐI!
"""

import json
import logging
import sys
from pathlib import Path

# Thêm thư mục gốc dự án vào PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thiết lập logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ZoomCorrectionDemo")

from src.models import FinancialFact, VerificationStatus
from src.verifier.accounting_verifier import AccountingVerifier
from src.verifier.vision_zoom_corrector import VisionZoomCorrector


def run_demo():
    print("\n" + "=" * 80)
    print("🎯 DEMO TEST CASE: PHÁT HIỆN SAI LỆCH SỐ LIỆU OCR & TỰ SỬA QUA VISION-LLM ZOOM")
    print("=" * 80)

    pdf_path = "vnm.pdf"
    if not Path(pdf_path).exists():
        print(f"❌ Không tìm thấy file {pdf_path}")
        sys.exit(1)

    output_dir = Path("data/logs/zoom_demo")
    output_dir.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────────────────────────────────
    # BƯỚC 1: Khởi tạo dữ liệu Fact thực tế từ BCTC Vinamilk với lỗi OCR giả lập
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[BƯỚC 1] Khởi tạo các Fact tài chính từ Bảng CĐKT Vinamilk (Trang 7 & 8)...")

    # Trang 7: Tài sản ngắn hạn (Mã 100) = 27.309.234.148.199 VND
    fact_cur_assets = FinancialFact(
        id="VNM_2024_p7_tbl1_r1",
        prov_id="VNM_2024_p7_tbl1_r1",
        concept="CURRENT_ASSETS",
        standard_code="100",
        raw_label="TÀI SẢN NGẮN HẠN",
        value=27309234148199.0,
        page=7,
        company="VNM",
        year=2024,
        period_type="current",
        period="2024",
    )

    # Trang 8: Tài sản dài hạn (Mã 200) = 18.643.262.824.437 VND
    fact_non_cur_assets = FinancialFact(
        id="VNM_2024_p8_tbl1_r1",
        prov_id="VNM_2024_p8_tbl1_r1",
        concept="NON_CURRENT_ASSETS",
        standard_code="200",
        raw_label="TÀI SẢN DÀI HẠN",
        value=18643262824437.0,
        page=8,
        company="VNM",
        year=2024,
        period_type="current",
        period="2024",
    )

    # Trang 8: TỔNG TÀI SẢN (Mã 270)
    # Giá trị đúng trên ảnh in: 45.952.496.972.636 VND
    # Giả lập lỗi OCR: Bị lem số 5 thành số 0 -> Đọc nhầm thành 40.952.496.972.636 VND
    ocr_erroneous_value = 40952496972636.0
    fact_total_assets = FinancialFact(
        id="VNM_2024_p8_tbl1_r25",
        prov_id="VNM_2024_p8_tbl1_r25",
        concept="TOTAL_ASSETS",
        standard_code="270",
        raw_label="TỔNG TÀI SẢN (270 = 100 + 200)",
        value=ocr_erroneous_value,
        page=8,
        company="VNM",
        year=2024,
        period_type="current",
        period="2024",
    )

    facts = [fact_cur_assets, fact_non_cur_assets, fact_total_assets]

    print(f"  • Mã 100 (Tài sản ngắn hạn): {fact_cur_assets.value:>22,.0f} VND (Trang 7)")
    print(f"  • Mã 200 (Tài sản dài hạn):  {fact_non_cur_assets.value:>22,.0f} VND (Trang 8)")
    print(f"  • Mã 270 (Tổng tài sản - OCR): {fact_total_assets.value:>20,.0f} VND (Trang 8) ⚠️ [LỖI LEM SỐ]")

    # ──────────────────────────────────────────────────────────────────────────
    # BƯỚC 2: Chạy kiểm toán số học ban đầu (AccountingVerifier)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[BƯỚC 2] Kích hoạt Bộ Tự Kiểm Toán Số Học (AccountingVerifier)...")
    verifier = AccountingVerifier()
    initial_report = verifier.verify_facts(facts, company="VNM", year=2024)

    expected_sum = fact_cur_assets.value + fact_non_cur_assets.value
    delta = abs(fact_total_assets.value - expected_sum)

    print(f"  • Trạng thái cân đối: {'✅ CÂN ĐỐI' if initial_report.is_balanced else '❌ PHÁT HIỆN SAI LỆCH SỐ HỌC'}")
    print(f"  • Tổng tài sản tính toán (100 + 200): {expected_sum:>15,.0f} VND")
    print(f"  • Tổng tài sản báo cáo (Mã 270):      {fact_total_assets.value:>15,.0f} VND")
    print(f"  • Chênh lệch phát hiện:                {delta:>15,.0f} VND (LỆCH 5 NGHÌN TỶ)")
    print(f"  • Chi tiết cảnh báo: {initial_report.failed_checks[0] if initial_report.failed_checks else 'None'}")

    assert not initial_report.is_balanced, "Kiểm toán ban đầu bắt buộc phải phát hiện sai lệch!"

    # ──────────────────────────────────────────────────────────────────────────
    # BƯỚC 3: Kích hoạt Agentic Vision-LLM Zoom Corrector
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[BƯỚC 3] Kích hoạt Agentic Vision-LLM Zoom Corrector để tự động cứu nguy...")
    corrector = VisionZoomCorrector(verifier=verifier)

    # Tự động khoanh vùng, crop ảnh dòng và thẩm định lại qua Vision API
    corrected_facts, final_report, is_corrected = corrector.run_self_correction(
        pdf_path=pdf_path,
        facts=facts,
        report=initial_report,
        company="VNM",
        year=2024,
        save_debug_dir=str(output_dir),
    )

    # ──────────────────────────────────────────────────────────────────────────
    # BƯỚC 4: Đánh giá kết quả tự sửa sai
    # ──────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("📊 KẾT QUẢ TỰ SỬA SAI CỦA AGENTIC VISION ZOOM")
    print("=" * 80)

    print(f"  • Tự sửa sai thành công: {'✅ CÓ (TRUE)' if is_corrected else '❌ THẤT BẠI'}")
    print(f"  • Trạng thái BCTC sau khi sửa: {'✅ HOÀN TOÀN CÂN ĐỐI' if final_report.is_balanced else '❌ VẪN CÒN LỆCH'}")

    target_fact = next(f for f in corrected_facts if f.concept == "TOTAL_ASSETS")
    print(f"  • Giá trị cũ (OCR ban đầu): {ocr_erroneous_value:>20,.0f} VND")
    print(f"  • Giá trị mới (Vision Zoom): {target_fact.value:>19,.0f} VND")
    print(f"  • Trạng thái Fact: {target_fact.verification_status}")
    print(f"  • Ghi chú kiểm toán: {target_fact.verification_detail}")

    if final_report.correction_history:
        print("\n📜 Lịch sử can thiệp (Correction History):")
        for h in final_report.correction_history:
            print(f"    - Dòng {h['concept']} (Mã {h['standard_code']}, Trang {h['page']}): {h['old_value']:,.0f} -> {h['new_value']:,.0f}")

    # ──────────────────────────────────────────────────────────────────────────
    # BƯỚC 5: Kiểm tra và liệt kê các hình ảnh đã lưu
    # ──────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("🖼️ CÁC HÌNH ẢNH ĐÃ ĐƯỢC TỰ ĐỘNG LƯU ĐỂ PHỤC VỤ AUDIT TRAIL:")
    print("=" * 80)

    saved_images = list(output_dir.glob("*.png"))
    for img_path in saved_images:
        size_kb = img_path.stat().st_size / 1024
        print(f"  📸 [{size_kb:6.1f} KB] {img_path.resolve()}")

    # Lưu log chi tiết JSON
    audit_log_path = output_dir / "zoom_correction_audit_log.json"
    audit_data = {
        "company": "VNM",
        "year": 2024,
        "is_corrected": is_corrected,
        "is_balanced_before": initial_report.is_balanced,
        "is_balanced_after": final_report.is_balanced,
        "discrepancy_delta": delta,
        "old_value": ocr_erroneous_value,
        "new_value": target_fact.value,
        "correction_history": final_report.correction_history,
        "saved_images": [str(p.resolve()) for p in saved_images],
    }
    with open(audit_log_path, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, ensure_ascii=False, indent=2)

    print(f"\n📝 Đã lưu nhật ký kiểm toán JSON tại: {audit_log_path.resolve()}\n")
    return is_corrected and final_report.is_balanced


if __name__ == "__main__":
    success = run_demo()
    sys.exit(0 if success else 1)
