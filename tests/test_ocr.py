"""
test_ocr.py — Unit tests kiểm thử Vision OCR Pipeline, Free Vision API extraction,
Làm sạch số tài chính (clean_ocr_number) và Validation Layer.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from src.config import Settings
from src.models import ParsedBlock
from src.parser.ocr_pipeline import (
    OCRPipeline,
    VisionOCRPipeline,
    preprocess_scanned_image,
)
from src.parser.ocr_postprocess import (
    clean_ocr_number,
    clean_ocr_text_line,
    validate_ocr_table,
)


class TestOCRPostProcess:
    """Kiểm thử tầng làm sạch số và kiểm định OCR tài chính."""

    def test_clean_ocr_number_character_confusion(self):
        """Kiểm thử sửa lỗi nhận diện nhầm O -> 0, l/I -> 1."""
        # Nhầm O -> 0
        assert clean_ocr_number("1O,OOO") == 10000.0
        assert clean_ocr_number("5O.OOO.OOO") == 50000000.0

        # Nhầm l / I -> 1
        assert clean_ocr_number("l,234") == 1234.0
        assert clean_ocr_number("I,500,000") == 1500000.0

    def test_clean_ocr_number_parentheses_negative(self):
        """Kiểm thử nhận diện số âm trong ngoặc đơn (1,234) -> -1234."""
        assert clean_ocr_number("(1,234)") == -1234.0
        assert clean_ocr_number("( 50.000.000 )") == -50000000.0
        assert clean_ocr_number("(1O,OOO)") == -10000.0

    def test_clean_ocr_number_edge_cases(self):
        """Kiểm thử các trường hợp biên: gạch ngang, rỗng, văn bản chữ."""
        assert clean_ocr_number("-") == 0.0
        assert clean_ocr_number("") is None
        assert clean_ocr_number("   ") is None
        assert clean_ocr_number("Doanh thu bán hàng") is None

    def test_clean_ocr_text_line(self):
        """Kiểm thử chuẩn hóa khoảng trắng dòng text OCR."""
        raw = "  BÁO   CÁO    TÀI CHÍNH   "
        assert clean_ocr_text_line(raw) == "BÁO CÁO TÀI CHÍNH"

    def test_validate_ocr_table_normal(self):
        """Kiểm thử bảng hợp lệ không có vấn đề cảnh báo."""
        table_rows = [
            ["Chỉ tiêu", "Năm 2024", "Năm 2023"],
            ["Doanh thu thuần", "50,000,000", "45,000,000"],
            ["Lợi nhuận gộp", "15,000,000", "12,000,000"],
        ]
        result = validate_ocr_table(table_rows)
        assert result["is_valid"] is True
        assert len(result["issues"]) == 0

    def test_validate_ocr_table_abnormal_negative(self):
        """Kiểm thử phát hiện doanh thu hoặc tài sản âm bất thường."""
        table_rows = [
            ["Chỉ tiêu", "Năm 2024"],
            ["Tổng cộng tài sản", "(50,000,000)"],  # Tài sản âm bất thường
        ]
        result = validate_ocr_table(table_rows)
        assert result["is_valid"] is False
        assert any("âm bất thường" in issue for issue in result["issues"])


class TestOpenCVPreprocessing:
    """Kiểm thử tiền xử lý ảnh OpenCV."""

    def test_preprocess_scanned_image_grayscale_blur(self):
        """Kiểm thử chuyển RGB sang Grayscale và khử nhiễu Median Blur."""
        rgb_img = np.zeros((100, 100, 3), dtype=np.uint8)
        rgb_img[10, 10] = [255, 255, 255]

        processed = preprocess_scanned_image(rgb_img, use_adaptive_thresh=False)
        assert len(processed.shape) == 2
        assert processed.shape == (100, 100)
        assert processed.dtype == np.uint8

    def test_preprocess_scanned_image_adaptive_threshold(self):
        """Kiểm thử phân ngưỡng nhị phân thích ứng."""
        rgb_img = np.full((100, 100, 3), 128, dtype=np.uint8)
        processed = preprocess_scanned_image(rgb_img, use_adaptive_thresh=True)
        assert len(processed.shape) == 2
        unique_vals = set(np.unique(processed))
        assert unique_vals.issubset({0, 255})


class TestVisionOCRPipeline:
    """Kiểm thử VisionOCRPipeline sử dụng Free Vision API."""

    def test_ocr_pipeline_alias(self):
        """Kiểm tra alias OCRPipeline trỏ đến VisionOCRPipeline để tương thích ngược."""
        assert OCRPipeline is VisionOCRPipeline

    @pytest.fixture
    def mock_settings(self):
        return Settings(
            gemini_api_key="mock_gemini_key",
            groq_api_key="mock_groq_key",
            ocr_provider="auto",
        )

    def test_parse_markdown_to_blocks_structure(self, mock_settings):
        """Kiểm thử bóc tách phản hồi Markdown thành table và text blocks."""
        pipeline = VisionOCRPipeline(settings=mock_settings)

        sample_markdown = (
            "# BÁO CÁO TÀI CHÍNH\n\n"
            "Đơn vị tính: VND\n\n"
            "| Chỉ tiêu | Năm 2024 | Năm 2023 |\n"
            "| --- | --- | --- |\n"
            "| Doanh thu thuần | 50.000.000 | 45.000.000 |\n"
            "| Lợi nhuận sau thuế | 10.000.000 | 8.500.000 |\n\n"
            "Thuyết minh giải trình: Doanh thu tăng trưởng mạnh mẽ."
        )

        blocks = pipeline._parse_markdown_to_blocks(
            markdown_content=sample_markdown,
            page_number=3,
            company="VNM",
            year=2024,
        )

        assert len(blocks) >= 2
        # Kiểm tra table block
        table_blocks = [b for b in blocks if b.is_table]
        assert len(table_blocks) == 1
        tbl = table_blocks[0]
        assert tbl.source == "ocr"
        assert tbl.page == 3
        assert tbl.metadata["num_rows"] == 3
        assert tbl.metadata["company"] == "VNM"
        assert tbl.metadata["unit"] == "VND"

        # Kiểm tra text blocks
        text_blocks = [b for b in blocks if not b.is_table]
        assert len(text_blocks) >= 1
        assert any("Thuyết minh" in b.content for b in text_blocks)

    def test_call_gemini_vision_mocked(self, mock_settings):
        """Kiểm thử gọi Google Gemini Vision API với HTTP mock."""
        pipeline = VisionOCRPipeline(settings=mock_settings)

        mock_gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "| Chỉ tiêu | Giá trị |\n| --- | --- |\n| Doanh thu | 100 |"
                            }
                        ]
                    }
                }
            ]
        }

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_gemini_response
            mock_resp.raise_for_status.return_value = None
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_client

            extracted = pipeline._call_gemini_vision("dummy_b64")
            assert "| Doanh thu | 100 |" in extracted

    def test_call_groq_vision_mocked(self, mock_settings):
        """Kiểm thử gọi Groq Vision API với SDK mock."""
        settings = Settings(ocr_provider="groq", groq_api_key="gsk_test")
        pipeline = VisionOCRPipeline(settings=settings)

        mock_choice = MagicMock()
        mock_choice.message.content = "| Cột 1 | Cột 2 |\n| --- | --- |\n| A | 500 |"
        mock_response = MagicMock(choices=[mock_choice])

        with patch("groq.Groq") as mock_groq_cls:
            mock_groq_instance = MagicMock()
            mock_groq_instance.chat.completions.create.return_value = mock_response
            mock_groq_cls.return_value = mock_groq_instance

            extracted = pipeline._call_groq_vision("dummy_b64")
            assert "| A | 500 |" in extracted

    def test_missing_api_keys_fallback(self):
        """Kiểm thử hành vi xử lý an toàn khi không cấu hình key."""
        empty_settings = Settings(gemini_api_key="", groq_api_key="", ocr_provider="auto")
        pipeline = VisionOCRPipeline(settings=empty_settings)

        extracted = pipeline._call_vision_api("dummy_b64")
        assert extracted == ""

    def test_process_scanned_page_end_to_end(self, mock_settings):
        """Kiểm thử toàn bộ luồng process_scanned_page với mock pdfplumber page."""
        pipeline = VisionOCRPipeline(settings=mock_settings)

        # Mock page to_image()
        mock_page = MagicMock()
        dummy_img = Image.new("RGB", (100, 100), color="white")
        mock_page.to_image.return_value.original = dummy_img

        with patch.object(
            pipeline,
            "_call_vision_api",
            return_value="| Chỉ tiêu | 2024 |\n| --- | --- |\n| Lợi nhuận | 250 |",
        ):
            blocks = pipeline.process_scanned_page(
                page=mock_page,
                page_number=5,
                company="HPG",
                year=2024,
            )

            assert len(blocks) == 1
            assert blocks[0].is_table is True
            assert blocks[0].source == "ocr"
            assert blocks[0].page == 5
            assert blocks[0].metadata["company"] == "HPG"

    def test_gemini_503_backoff_and_model_fallback(self, mock_settings):
        """Kiểm thử xử lý lỗi 503: Áp dụng backoff và tự động chuyển model tiếp theo thành công."""
        pipeline = VisionOCRPipeline(settings=mock_settings)

        resp_503 = MagicMock()
        resp_503.status_code = 503

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.raise_for_status.return_value = None
        resp_200.json.return_value = {
            "candidates": [
                {"content": {"parts": [{"text": "| Chỉ tiêu | 2024 |\n| --- | --- |\n| Doanh thu | 999 |"}]}}
            ]
        }

        with patch("httpx.Client") as mock_client_cls, patch("time.sleep") as mock_sleep:
            mock_client = MagicMock()
            # Lần 1 trả về 503 (quá tải), lần 2 model kế tiếp trả về 200 (thành công)
            mock_client.post.side_effect = [resp_503, resp_200]
            mock_client_cls.return_value.__enter__.return_value = mock_client

            extracted = pipeline._call_gemini_vision("dummy_b64")
            assert "| Doanh thu | 999 |" in extracted
            # Đảm bảo đã gọi sleep (backoff) khi gặp 503
            assert mock_sleep.called

    def test_process_scanned_page_local_ocr_fallback(self, mock_settings):
        """Kiểm thử khi Vision API trả về rỗng (503/quota), tự động kích hoạt Local OCR fallback cứu nguy."""
        pipeline = VisionOCRPipeline(settings=mock_settings)

        mock_page = MagicMock()
        dummy_img = Image.new("RGB", (100, 100), color="white")
        mock_page.to_image.return_value.original = dummy_img

        fallback_block = ParsedBlock(
            block_id="p99_b1",
            block_type="table",
            page=99,
            content="| Chỉ tiêu | Số tiền |\n| --- | --- |\n| Tài sản | 1000 |",
            source="local_ocr",
            metadata={"company": "FALLBACK_TEST"},
        )

        with patch.object(pipeline, "_call_vision_api", return_value=""), patch(
            "src.parser.local_ocr.LocalOCREngine.process_scanned_page", return_value=[fallback_block]
        ):
            blocks = pipeline.process_scanned_page(
                page=mock_page,
                page_number=99,
                company="FALLBACK_TEST",
                year=2099,
            )

            assert len(blocks) == 1
            assert blocks[0].metadata.get("is_fallback") is True
            assert blocks[0].metadata.get("fallback_reason") == "vision_api_503_overloaded"
            assert blocks[0].page == 99
