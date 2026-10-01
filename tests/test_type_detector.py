"""
test_type_detector.py — Unit tests kiểm thử module PDFTypeDetector.
Kiểm tra logic phân loại trang:
  - char_count >= 50: Digital Text
  - char_count < 50: Scanned Image
"""

from unittest.mock import MagicMock, patch

import pytest

from src.parser.pdf_type_detector import (
    DocumentClassification,
    PageClassification,
    PDFTypeDetector,
)


class TestPDFTypeDetector:
    """Bộ test cho PDFTypeDetector."""

    def test_page_classification_properties(self):
        """Kiểm tra thuộc tính tiện ích is_text và is_scanned."""
        text_page = PageClassification(
            page=1,
            page_type="text",
            char_count=1200,
            images_count=0,
            has_tables=True,
        )
        assert text_page.is_text is True
        assert text_page.is_scanned is False

        scanned_page = PageClassification(
            page=2,
            page_type="scanned",
            char_count=12,
            images_count=1,
            has_tables=False,
        )
        assert scanned_page.is_text is False
        assert scanned_page.is_scanned is True

    def test_detect_pages_threshold(self, tmp_path):
        """Kiểm tra ngưỡng phân loại 50 ký tự với mock pdfplumber."""
        dummy_pdf_path = tmp_path / "dummy.pdf"
        dummy_pdf_path.write_bytes(b"%PDF-1.4 dummy")

        # Mock page 1: Digital text (150 chars)
        mock_page_text = MagicMock()
        mock_page_text.extract_text.return_value = "A" * 150
        mock_page_text.images = []
        mock_page_text.find_tables.return_value = [MagicMock()]

        # Mock page 2: Scanned image (20 chars)
        mock_page_scan = MagicMock()
        mock_page_scan.extract_text.return_value = "A" * 20
        mock_page_scan.images = [MagicMock()]
        mock_page_scan.find_tables.return_value = []

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page_text, mock_page_scan]

        detector = PDFTypeDetector(min_char_threshold=50)

        with patch("pdfplumber.open") as mock_open:
            mock_open.return_value.__enter__.return_value = mock_pdf
            results = detector.detect_pages(dummy_pdf_path)

        assert len(results) == 2
        assert results[0].page == 1
        assert results[0].page_type == "text"
        assert results[0].char_count == 150
        assert results[0].has_tables is True

        assert results[1].page == 2
        assert results[1].page_type == "scanned"
        assert results[1].char_count == 20
        assert results[1].images_count == 1

    def test_classify_document_predominantly_scanned(self, tmp_path):
        """Kiểm tra tổng quan tài liệu có phần lớn trang là scan."""
        dummy_pdf_path = tmp_path / "scanned_doc.pdf"
        dummy_pdf_path.write_bytes(b"%PDF-1.4 dummy")

        pages = []
        for _ in range(5):
            p = MagicMock()
            p.extract_text.return_value = ""
            p.images = [MagicMock()]
            p.find_tables.return_value = []
            pages.append(p)

        mock_pdf = MagicMock()
        mock_pdf.pages = pages

        detector = PDFTypeDetector()
        with patch("pdfplumber.open") as mock_open:
            mock_open.return_value.__enter__.return_value = mock_pdf
            doc_class = detector.classify_document(dummy_pdf_path)

        assert isinstance(doc_class, DocumentClassification)
        assert doc_class.total_pages == 5
        assert doc_class.scanned_pages_count == 5
        assert doc_class.text_pages_count == 0
        assert doc_class.is_predominantly_scanned is True

    def test_file_not_found(self):
        """Kiểm tra báo lỗi khi không tìm thấy file PDF."""
        detector = PDFTypeDetector()
        with pytest.raises(FileNotFoundError):
            detector.detect_pages("non_existent_file.pdf")
