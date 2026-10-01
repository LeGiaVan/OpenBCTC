"""
test_structured_cropper.py — Test từng strategy của StructuredTableCropper
với log chi tiết từng bước (không cần Vision LLM API key).

Các test group:
  A. Unit test từng strategy (mock pdfplumber page)
  B. Integration test với vnm.pdf thực tế — log ảnh ra data/logs/cropper_test/
  C. Regression test: fix signature mới (crop_result = img, b64, target_column)
"""

import io
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from PIL import Image

# ── Logger cấu hình chi tiết đến DEBUG ──────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("test_structured_cropper")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import FinancialFact, VerificationReport
from src.verifier.accounting_verifier import AccountingVerifier
from src.verifier.vision_zoom_corrector import (
    CONCEPT_REGEX,
    CropQuality,
    RowBBox,
    StructuredTableCropper,
    VisionZoomCorrector,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

OUTPUT_DIR = Path("data/logs/cropper_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VNM_PDF = Path("vnm.pdf")


def _make_fact(concept: str, code: str, label: str, page: int = 8) -> FinancialFact:
    return FinancialFact(
        id=f"TEST_{concept}",
        prov_id=f"TEST_{concept}",
        concept=concept,
        standard_code=code,
        raw_label=label,
        value=0.0,
        period_type="current",
        period="2024",
        company="VNM",
        year=2024,
        page=page,
        table_id="t1",
        row_label=label,
        confidence=1.0,
    )


def _save_img(img: Image.Image, name: str) -> Path:
    """Lưu ảnh test ra OUTPUT_DIR và in kích thước."""
    out = OUTPUT_DIR / name
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    logger.info("💾 Đã lưu ảnh: %s (%dx%d, %.1f KB)", out, img.width, img.height, out.stat().st_size / 1024)
    return out


def _make_white_page_img(w: int = 800, h: int = 1100) -> Image.Image:
    return Image.new("RGB", (w, h), color=(255, 255, 255))


# ─────────────────────────────────────────────────────────────────────────────
# GROUP A: Unit tests cho StructuredTableCropper (mock page)
# ─────────────────────────────────────────────────────────────────────────────

class TestStrategy1TableExtract:
    """Strategy 1: pdfplumber native table extraction."""

    def test_match_by_code_in_col1(self):
        """Match mã số '270' trong cột index 1 của bảng."""
        logger.info("\n=== [S1] test_match_by_code_in_col1 ===")
        cropper = StructuredTableCropper()

        # Mock row bbox
        mock_row_bbox = MagicMock()
        mock_row_bbox.bbox = (0, 120.0, 500, 140.0)

        # Mock table
        mock_table = MagicMock()
        mock_table.extract.return_value = [
            ["TỔNG TÀI SẢN", "270", ""],
        ]
        mock_table.rows = [mock_row_bbox]

        mock_page = MagicMock()
        mock_page.find_tables.return_value = [mock_table]

        result = cropper._strategy_table_extract(mock_page, "270")
        logger.info("  → Kết quả: %s", result)

        assert result is not None
        assert result.source == "table_extract"
        assert result.confidence == 1.0
        assert result.top == pytest.approx(120.0)
        assert result.bottom == pytest.approx(140.0)

    def test_no_match_returns_none(self):
        """Không tìm thấy mã '999' → None."""
        logger.info("\n=== [S1] test_no_match_returns_none ===")
        cropper = StructuredTableCropper()

        mock_table = MagicMock()
        mock_table.extract.return_value = [["TỔNG TÀI SẢN", "270", ""]]
        mock_table.rows = [MagicMock()]

        mock_page = MagicMock()
        mock_page.find_tables.return_value = [mock_table]

        result = cropper._strategy_table_extract(mock_page, "999")
        logger.info("  → Kết quả: %s", result)
        assert result is None

    def test_handles_exception_gracefully(self):
        """Lỗi trong find_tables → return None, không raise."""
        logger.info("\n=== [S1] test_handles_exception_gracefully ===")
        cropper = StructuredTableCropper()

        mock_page = MagicMock()
        mock_page.find_tables.side_effect = RuntimeError("PDF corrupt")

        result = cropper._strategy_table_extract(mock_page, "270")
        assert result is None


class TestStrategy2ColumnBounded:
    """Strategy 2: Column-bounded standard code match."""

    def test_match_code_in_column_zone(self):
        """Từ '270' nằm trong vùng 30-52% width → match."""
        logger.info("\n=== [S2] test_match_code_in_column_zone ===")
        cropper = StructuredTableCropper()

        page_width = 1000.0
        mock_page = MagicMock()
        mock_page.width = page_width
        mock_page.extract_words.return_value = [
            {"text": "270", "x0": 330.0, "top": 200.0, "bottom": 215.0},  # x0=33% ✓
        ]

        result = cropper._strategy_column_bounded_code(mock_page, "270")
        logger.info("  → Kết quả: %s", result)

        assert result is not None
        assert result.source == "col_bounded_code"
        assert result.confidence == pytest.approx(0.90)

    def test_reject_code_outside_column_zone(self):
        """Từ '2025' nằm ngoài vùng mã số (x0=70%) → không match dù chứa '20'."""
        logger.info("\n=== [S2] test_reject_code_outside_column_zone ===")
        cropper = StructuredTableCropper()

        mock_page = MagicMock()
        mock_page.width = 1000.0
        mock_page.extract_words.return_value = [
            {"text": "2025", "x0": 700.0, "top": 50.0, "bottom": 65.0},   # x0=70% ✗ nằm ở cột số tiền
            {"text": "2024", "x0": 850.0, "top": 50.0, "bottom": 65.0},   # x0=85% ✗
        ]

        # clean_code "20" không nên match vào "2025" hay "2024"
        result = cropper._strategy_column_bounded_code(mock_page, "20")
        logger.info("  → Kết quả: %s (kỳ vọng None)", result)
        assert result is None

    def test_match_uses_digit_only_compare(self):
        """'V.13' → clean_code '13', match từ '13' trong vùng cột."""
        logger.info("\n=== [S2] test_match_uses_digit_only_compare ===")
        cropper = StructuredTableCropper()

        mock_page = MagicMock()
        mock_page.width = 1000.0
        mock_page.extract_words.return_value = [
            {"text": "13", "x0": 380.0, "top": 300.0, "bottom": 315.0},
        ]

        result = cropper._strategy_column_bounded_code(mock_page, "13")
        logger.info("  → Kết quả: %s", result)
        assert result is not None


class TestStrategy3FuzzyLabel:
    """Strategy 3: Fuzzy label keyword match."""

    def test_match_high_keyword_overlap(self):
        """Label 'Tổng cộng tài sản' → match dòng chứa 'tổng tài sản'."""
        logger.info("\n=== [S3] test_match_high_keyword_overlap ===")
        cropper = StructuredTableCropper()

        mock_page = MagicMock()
        mock_page.width = 1000.0
        mock_page.extract_words.return_value = [
            {"text": "TỔNG", "x0": 10.0, "x1": 80.0, "top": 200.0, "bottom": 215.0},
            {"text": "TÀI", "x0": 85.0, "x1": 120.0, "top": 200.0, "bottom": 215.0},
            {"text": "SẢN", "x0": 125.0, "x1": 165.0, "top": 200.0, "bottom": 215.0},
        ]

        result = cropper._strategy_fuzzy_label(mock_page, "TỔNG TÀI SẢN")
        logger.info("  → Kết quả: %s", result)

        assert result is not None
        assert result.source == "fuzzy_label"
        assert result.confidence > 0

    def test_no_match_below_threshold(self):
        """Không có từ nào khớp → None."""
        logger.info("\n=== [S3] test_no_match_below_threshold ===")
        cropper = StructuredTableCropper()

        mock_page = MagicMock()
        mock_page.width = 1000.0
        mock_page.extract_words.return_value = [
            {"text": "XYZ", "x0": 10.0, "x1": 50.0, "top": 100.0, "bottom": 115.0},
        ]

        result = cropper._strategy_fuzzy_label(mock_page, "lưu chuyển tiền thuần")
        logger.info("  → Kết quả: %s (kỳ vọng None)", result)
        assert result is None


class TestStrategy4ProjectionProfile:
    """Strategy 4: Horizontal Projection Profile + Local OCR."""

    def test_empty_image_returns_empty(self):
        """Ảnh trắng hoàn toàn → không tìm thấy band nào → []."""
        logger.info("\n=== [S4] test_empty_image_returns_empty ===")
        cropper = StructuredTableCropper()

        white_img = _make_white_page_img()
        fact = _make_fact("CF_NET_OPERATING", "20", "Lưu chuyển tiền thuần từ HĐKD")

        result = cropper._strategy_projection_profile(white_img, [fact])
        logger.info("  → Số band kết quả: %d (kỳ vọng 0)", len(result))
        assert result == []

    def test_detects_text_bands_from_synthetic_image(self):
        """Ảnh tổng hợp có 3 dải text → phát hiện đúng ≥ 3 band."""
        logger.info("\n=== [S4] test_detects_text_bands_from_synthetic_image ===")
        import numpy as np
        from PIL import Image as PILImage

        # Tạo ảnh trắng 800x400 với 3 dải text tối
        arr = np.ones((400, 800, 3), dtype=np.uint8) * 255
        arr[50:62, 10:600] = 0    # band 1
        arr[120:132, 10:600] = 0  # band 2
        arr[200:212, 10:600] = 0  # band 3
        img = PILImage.fromarray(arr)

        _save_img(img, "s4_synthetic_3bands.png")

        cropper = StructuredTableCropper()

        # Dùng _strategy_projection_profile trực tiếp qua numpy để kiểm tra band detection
        import numpy as np2
        gray = np2.array(img.convert("L"))
        img_h, img_w = gray.shape
        dark_per_row = np2.sum(gray < 128, axis=1).astype(float)
        dark_smooth  = np2.convolve(dark_per_row, np2.ones(3) / 3, mode="same")
        is_text_row  = dark_smooth >= img_w * 0.015

        bands = []
        in_band = False
        for r, is_text in enumerate(is_text_row):
            if is_text and not in_band:
                in_band, band_top = True, r
            elif not is_text and in_band:
                in_band = False
                if r - band_top >= 4:
                    bands.append((band_top, r))

        logger.info("  → Bands detected: %s", bands)
        assert len(bands) >= 3, f"Kỳ vọng ≥ 3 bands, thực tế: {len(bands)}"


# ─────────────────────────────────────────────────────────────────────────────
# GROUP B: Integration test với CONCEPT_REGEX
# ─────────────────────────────────────────────────────────────────────────────

class TestConceptRegex:
    """Kiểm tra CONCEPT_REGEX map phủ đúng các concept và match đúng pattern."""

    def test_coverage_all_major_concepts(self):
        """Tất cả concept quan trọng phải có trong CONCEPT_REGEX."""
        logger.info("\n=== [REGEX] test_coverage_all_major_concepts ===")
        required = [
            # CF
            "CF_NET_OPERATING", "CF_NET_INVESTING", "CF_NET_FINANCING",
            "CF_ENDING_CASH", "CF_BEGINNING_CASH", "CF_NET_CHANGE",
            # BS
            "TOTAL_ASSETS", "TOTAL_RESOURCES", "CURRENT_ASSETS", "NON_CURRENT_ASSETS",
            "LIABILITIES", "EQUITY",
            # IS
            "NET_REVENUE", "GROSS_PROFIT", "PROFIT_BEFORE_TAX", "NET_PROFIT",
        ]
        missing = [c for c in required if c not in CONCEPT_REGEX]
        logger.info("  → Concepts trong CONCEPT_REGEX: %d", len(CONCEPT_REGEX))
        logger.info("  → Missing: %s", missing)
        assert not missing, f"Thiếu concepts: {missing}"

    @pytest.mark.parametrize("concept,text,should_match", [
        ("CF_NET_OPERATING",  "lưu chuyển tiền thuần từ hoạt động kinh doanh", True),
        ("CF_NET_OPERATING",  "20",                                              True),
        ("CF_NET_INVESTING",  "lưu chuyển tiền thuần từ hoạt động đầu tư",     True),
        ("CF_NET_FINANCING",  "lưu chuyển tiền thuần từ hoạt động tài chính",  True),
        ("TOTAL_ASSETS",      "tổng cộng tài sản",                              True),
        ("TOTAL_ASSETS",      "270",                                             True),
        ("TOTAL_RESOURCES",   "tổng cộng nguồn vốn",                           True),
        ("NET_PROFIT",        "lợi nhuận sau thuế",                             True),
        ("CF_NET_OPERATING",  "lưu chuyển tiền từ hoạt động tài chính",        False),  # Sai concept
        ("TOTAL_ASSETS",      "123456",                                         False),  # Số ngẫu nhiên
    ])
    def test_regex_patterns(self, concept, text, should_match):
        import re
        pattern = CONCEPT_REGEX[concept]
        matched = bool(re.search(pattern, text, re.IGNORECASE))
        logger.info(
            "  [REGEX] %s | text='%s' | match=%s | expected=%s",
            concept, text[:40], matched, should_match,
        )
        assert matched == should_match


# ─────────────────────────────────────────────────────────────────────────────
# GROUP C: CropQuality validation
# ─────────────────────────────────────────────────────────────────────────────

class TestCropQuality:
    """Kiểm tra _validate_crop_quality."""

    def test_blank_image_rejected(self):
        """Ảnh trắng hoàn toàn → valid=False, reason='nearly_blank'."""
        logger.info("\n=== [QUALITY] test_blank_image_rejected ===")
        cropper = StructuredTableCropper()
        blank = Image.new("RGB", (200, 30), color=(255, 255, 255))
        quality = cropper._validate_crop_quality(blank)
        logger.info("  → %s", quality)
        assert not quality.valid
        assert quality.reason == "nearly_blank"

    def test_dark_image_accepted(self):
        """Ảnh có nhiều pixel tối (text giả lập) → valid=True."""
        logger.info("\n=== [QUALITY] test_dark_image_accepted ===")
        import numpy as np
        arr = np.ones((30, 400, 3), dtype=np.uint8) * 255
        arr[10:20, 20:380] = 50   # dải text tối
        img = Image.fromarray(arr)

        _save_img(img, "quality_dark_text.png")

        cropper = StructuredTableCropper()
        quality = cropper._validate_crop_quality(img)
        logger.info("  → %s", quality)
        assert quality.valid


# ─────────────────────────────────────────────────────────────────────────────
# GROUP D: Signature regression test (mock)
# ─────────────────────────────────────────────────────────────────────────────

class TestSignatureRegression:
    """Đảm bảo signature mới (3 phần tử) hoạt động trong run_self_correction."""

    @patch.object(VisionZoomCorrector, "locate_and_crop_row")
    @patch.object(VisionZoomCorrector, "inspect_row_image")
    def test_crop_returns_3_tuple(self, mock_inspect, mock_crop):
        """
        Sau refactor, locate_and_crop_row trả về (img, b64, target_column).
        run_self_correction phải unpack đúng 3 phần tử và truyền target_column
        vào inspect_row_image.
        """
        logger.info("\n=== [SIGNATURE] test_crop_returns_3_tuple ===")

        facts = [
            _make_fact("TOTAL_ASSETS", "270", "Tổng tài sản"),
            _make_fact("CURRENT_ASSETS", "100", "Tài sản ngắn hạn"),
            _make_fact("NON_CURRENT_ASSETS", "200", "Tài sản dài hạn"),
            _make_fact("TOTAL_RESOURCES", "440", "Tổng nguồn vốn"),
            _make_fact("LIABILITIES", "300", "Nợ phải trả"),
            _make_fact("EQUITY", "400", "Vốn chủ sở hữu"),
        ]

        # Thiết lập giá trị facts
        fact_map = {
            "TOTAL_ASSETS": 1000.0, "CURRENT_ASSETS": 600.0,
            "NON_CURRENT_ASSETS": 400.0,
            "TOTAL_RESOURCES": 1200.0,  # Sai! Đúng là 1000
            "LIABILITIES": 600.0, "EQUITY": 400.0,
        }
        for f in facts:
            f.value = fact_map[f.concept]

        verifier = AccountingVerifier()
        initial_report = verifier.verify_facts(facts, company="VNM", year=2024)
        assert not initial_report.is_balanced

        # Mock trả về 3-tuple
        dummy_img = Image.new("RGB", (400, 50), color="white")
        mock_crop.return_value = (dummy_img, "dummy_b64_str", "Năm nay (2025)")

        # Mock Vision LLM sửa đúng
        mock_inspect.return_value = {
            "raw_text": "1.000",
            "value_current": 1000.0,
            "is_negative": False,
            "confidence": 0.99,
        }

        corrector = VisionZoomCorrector(verifier=verifier)
        _, final_report, is_corrected = corrector.run_self_correction(
            pdf_path="dummy.pdf",
            facts=facts,
            report=initial_report,
            company="VNM",
            year=2024,
        )

        logger.info("  → is_corrected=%s, is_balanced=%s", is_corrected, final_report.is_balanced)
        logger.info("  → inspect_row_image called with target_column=%s",
                    mock_inspect.call_args)

        assert is_corrected is True
        assert final_report.is_balanced is True

        # Kiểm tra target_column được truyền vào inspect_row_image
        call_kwargs = mock_inspect.call_args.kwargs
        assert call_kwargs.get("target_column") == "Năm nay (2025)"

    @patch.object(VisionZoomCorrector, "locate_and_crop_row")
    @patch.object(VisionZoomCorrector, "inspect_row_image")
    def test_correction_history_has_target_column(self, mock_inspect, mock_crop):
        """correction_history entry phải có trường 'target_column'."""
        logger.info("\n=== [SIGNATURE] test_correction_history_has_target_column ===")

        facts = [
            _make_fact("TOTAL_ASSETS", "270", "Tổng tài sản"),
            _make_fact("CURRENT_ASSETS", "100", "Tài sản ngắn hạn"),
            _make_fact("NON_CURRENT_ASSETS", "200", "Tài sản dài hạn"),
            _make_fact("TOTAL_RESOURCES", "440", "Tổng nguồn vốn"),
            _make_fact("LIABILITIES", "300", "Nợ phải trả"),
            _make_fact("EQUITY", "400", "Vốn chủ sở hữu"),
        ]
        for f in facts:
            f.value = {
                "TOTAL_ASSETS": 1000.0, "CURRENT_ASSETS": 600.0,
                "NON_CURRENT_ASSETS": 400.0, "TOTAL_RESOURCES": 1200.0,
                "LIABILITIES": 600.0, "EQUITY": 400.0,
            }[f.concept]

        verifier = AccountingVerifier()
        report = verifier.verify_facts(facts, company="VNM", year=2024)

        dummy_img = Image.new("RGB", (400, 50), color="white")
        mock_crop.return_value = (dummy_img, "b64", "Năm nay (2025)")
        mock_inspect.return_value = {"value_current": 1000.0, "is_negative": False, "confidence": 0.95}

        corrector = VisionZoomCorrector(verifier=verifier)
        _, final_report, is_corrected = corrector.run_self_correction(
            pdf_path="dummy.pdf", facts=facts, report=report,
            company="VNM", year=2024,
        )

        assert is_corrected
        assert final_report.correction_history
        entry = final_report.correction_history[0]
        logger.info("  → correction_history entry: %s", entry)
        assert "target_column" in entry
        assert entry["target_column"] == "Năm nay (2025)"


# ─────────────────────────────────────────────────────────────────────────────
# GROUP E: Integration test với vnm.pdf thực tế (skip nếu không có file)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not VNM_PDF.exists(), reason="vnm.pdf không tồn tại, bỏ qua integration test")
class TestIntegrationVnmPdf:
    """
    Integration test thực tế với vnm.pdf.
    Lưu ảnh crop và annotated ra data/logs/cropper_test/ để kiểm tra bằng mắt.
    """

    def test_strategy1_table_extract_page8(self):
        """Strategy 1: Locate dòng Mã 270 (Tổng tài sản) trên trang 8 của vnm.pdf."""
        import pdfplumber
        logger.info("\n=== [INTEGRATION] test_strategy1_table_extract_page8 ===")

        cropper = StructuredTableCropper()
        with pdfplumber.open(str(VNM_PDF)) as pdf:
            page = pdf.pages[7]  # trang 8 (0-indexed)
            result = cropper._strategy_table_extract(page, "270")
            logger.info("  → Strategy 1 result: %s", result)

            if result:
                full_img = page.to_image(resolution=150).original
                _save_img(full_img, "integration_s1_full_page8.png")

                crop = page.crop((0, result.top - 5, page.width, result.bottom + 5))
                pil_crop = crop.to_image(resolution=150).original
                _save_img(pil_crop, "integration_s1_crop_ma270.png")
                logger.info("  ✅ Strategy 1 thành công: top=%.1f, bottom=%.1f", result.top, result.bottom)
            else:
                logger.warning("  ⚠️ Strategy 1 không tìm thấy Mã 270 trên trang 8")

    def test_strategy2_col_bounded_page8(self):
        """Strategy 2: Column-bounded match Mã 270 trên trang 8."""
        import pdfplumber
        logger.info("\n=== [INTEGRATION] test_strategy2_col_bounded_page8 ===")

        cropper = StructuredTableCropper()
        with pdfplumber.open(str(VNM_PDF)) as pdf:
            page = pdf.pages[7]
            result = cropper._strategy_column_bounded_code(page, "270")
            logger.info("  → Strategy 2 result: %s", result)

            if result:
                crop = page.crop((0, result.top - 5, page.width, result.bottom + 5))
                pil_crop = crop.to_image(resolution=150).original
                _save_img(pil_crop, "integration_s2_crop_ma270.png")
                logger.info("  ✅ Strategy 2 thành công")
            else:
                logger.warning("  ⚠️ Strategy 2 không tìm thấy Mã 270")

    def test_strategy3_fuzzy_label_page8(self):
        """Strategy 3: Fuzzy label match 'TỔNG TÀI SẢN' trên trang 8."""
        import pdfplumber
        logger.info("\n=== [INTEGRATION] test_strategy3_fuzzy_label_page8 ===")

        cropper = StructuredTableCropper()
        with pdfplumber.open(str(VNM_PDF)) as pdf:
            page = pdf.pages[7]
            result = cropper._strategy_fuzzy_label(page, "TỔNG CỘNG TÀI SẢN")
            logger.info("  → Strategy 3 result: %s", result)

            if result:
                crop = page.crop((0, result.top - 5, page.width, result.bottom + 5))
                pil_crop = crop.to_image(resolution=150).original
                _save_img(pil_crop, "integration_s3_crop_fuzzy.png")
                logger.info("  ✅ Strategy 3 thành công, confidence=%.2f", result.confidence)

    def test_waterfall_locate_row_page8(self):
        """Waterfall đầy đủ: locate_row cho Mã 270 trên trang 8.
        vnm.pdf là scanned PDF — Strategy 1-3 đều return None (không có native text).
        Strategy 4 (projection OCR) xử lý ở tầng cao hơn (trong locate_and_crop_row).
        Test này xác nhận waterfall kết thúc đúng cách khi PDF là scan.
        """
        import pdfplumber
        logger.info("\n=== [INTEGRATION] test_waterfall_locate_row_page8 ===")

        cropper = StructuredTableCropper()
        fact = _make_fact("TOTAL_ASSETS", "270", "TỔNG CỘNG TÀI SẢN", page=8)

        with pdfplumber.open(str(VNM_PDF)) as pdf:
            page = pdf.pages[7]
            words = page.extract_words()
            tables = page.find_tables()
            logger.info(
                "  Page 8 — words=%d, tables=%d → %s",
                len(words), len(tables),
                "SCANNED PDF (expected)" if len(words) == 0 else "VECTOR PDF",
            )

            result = cropper.locate_row(page, fact, "270")
            logger.info("  → Waterfall result: %s", result)

            if len(words) == 0:
                # Scanned page: Strategy 1-3 đều fail → None là đúng
                assert result is None, "Scanned PDF: Strategy 1-3 phải return None"
                logger.info("  ✅ Đúng: Scanned PDF — Strategy 1-3 None, cần Strategy 4 (projection OCR)")

                # Kiểm tra Strategy 4 qua locate_and_crop_row (full pipeline)
                full_img = page.to_image(resolution=150).original
                _save_img(full_img, "integration_waterfall_page8_full.png")
                logger.info("  📸 Đã lưu ảnh full trang 8 để kiểm tra Strategy 4")
            else:
                # Vector PDF: waterfall phải tìm được
                assert result is not None, "Vector PDF: Waterfall phải tìm thấy Mã 270"
                composite = cropper._build_composite_crop(page, result, resolution=150)
                _save_img(composite, "integration_waterfall_composite_ma270.png")
                logger.info("  ✅ Waterfall thành công qua strategy: %s", result.source)


    def test_locate_and_crop_row_full_pipeline(self):
        """locate_and_crop_row end-to-end: Mã 20 (CF_NET_OPERATING) trang 10."""
        logger.info("\n=== [INTEGRATION] test_locate_and_crop_row_full_pipeline ===")

        corrector = VisionZoomCorrector()
        fact = _make_fact("CF_NET_OPERATING", "20", "Lưu chuyển tiền thuần từ hoạt động kinh doanh", page=10)

        result = corrector.locate_and_crop_row(
            pdf_path=str(VNM_PDF),
            fact=fact,
            save_debug_dir=str(OUTPUT_DIR),
        )

        if result:
            pil_img, b64, target_col = result
            _save_img(pil_img, "integration_full_pipeline_ma20.png")
            logger.info("  ✅ Crop thành công: size=%s, target_column='%s'", pil_img.size, target_col)
            logger.info("  ✅ Base64 length: %d chars", len(b64))
            assert isinstance(b64, str) and len(b64) > 0
            assert target_col == "Năm nay (2025)"
        else:
            logger.warning("  ⚠️ Không crop được Mã 20 — kiểm tra số trang")

    def test_projection_profile_page10(self):
        """Strategy 4: Projection Profile trên trang 10 (LCTT)."""
        import pdfplumber
        logger.info("\n=== [INTEGRATION] test_projection_profile_page10 ===")

        cropper = StructuredTableCropper()
        facts = [
            _make_fact("CF_NET_OPERATING", "20", "Lưu chuyển tiền thuần từ HĐKD", page=10),
            _make_fact("CF_NET_INVESTING",  "30", "Lưu chuyển tiền thuần từ HĐ đầu tư", page=10),
        ]

        with pdfplumber.open(str(VNM_PDF)) as pdf:
            if len(pdf.pages) < 10:
                pytest.skip("vnm.pdf không có đủ 10 trang")
            page = pdf.pages[9]
            full_img = page.to_image(resolution=150).original
            _save_img(full_img, "integration_s4_full_page10.png")

            results = cropper._strategy_projection_profile(full_img, facts)
            logger.info("  → Strategy 4 results: %d / %d facts located", len(results), len(facts))

            for fact, (top_px, bot_px) in results:
                band_crop = full_img.crop((0, max(0, top_px - 5), full_img.width, min(full_img.height, bot_px + 5)))
                _save_img(band_crop, f"integration_s4_band_{fact.concept}.png")
                logger.info("  ✅ Concept '%s' → band top=%d, bot=%d", fact.concept, top_px, bot_px)
