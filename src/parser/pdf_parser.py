"""
pdf_parser.py — Facade / Orchestrator điều phối bóc tách Báo cáo tài chính cho FinAudit AI.
Thực hiện kiến trúc 2-Branch PDF Ingestion Architecture (Module 1, 2a, 2b, 3 trong proposal.md):
  1. PDFTypeDetector: Quét và phân loại từng trang thành "text" hoặc "scanned"
  2a. TextParser: Định tuyến các trang digital text sang pdfplumber
  2b. OCRPipeline: Định tuyến các trang scan ảnh sang Free Vision API (Gemini/Groq Vision) + Post-processing
  3. OutputNormalizer: Hợp nhất và chuẩn hóa đầu ra thành danh sách ParsedBlock thống nhất
"""

import logging
from pathlib import Path

import pdfplumber

from src.config import Settings, get_settings
from src.models import ParsedBlock, ParsedDocument
from src.parser.normalizer import OutputNormalizer
from src.parser.ocr_pipeline import OCRPipeline
from src.parser.pdf_type_detector import PDFTypeDetector
from src.parser.text_parser import TextParser

logger = logging.getLogger(__name__)


class PDFParser:
    """Bộ điều phối Ingestion PDF BCTC chuyên dụng theo kiến trúc 2 nhánh."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.type_detector = PDFTypeDetector(
            min_char_threshold=self.settings.ocr_min_char_threshold
        )
        self.text_parser = TextParser(self.settings)
        self.ocr_pipeline = OCRPipeline(self.settings)
        self.normalizer = OutputNormalizer()

    def parse_pdf(
        self,
        pdf_path: str | Path,
        company: str = "DOANH_NGHIEP",
        year: int = 2024,
        page_range: tuple[int, int] | None = None,
    ) -> list[ParsedBlock]:
        """
        Bóc tách file PDF BCTC qua 2 nhánh (Digital Text vs Scanned OCR).

        Args:
            pdf_path: Đường dẫn file PDF
            company: Mã công ty (VNM, HPG, FPT...)
            year: Năm tài chính
            page_range: Tuple (start_page, end_page) 1-indexed (ví dụ: (1, 10))

        Returns:
            list[ParsedBlock]: Danh sách các khối văn bản và bảng biểu đã chuẩn hóa
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy file PDF BCTC: {path.resolve()}")

        with pdfplumber.open(path) as pdf:
            total_pages = len(pdf.pages)
            start_p = 1
            end_p = total_pages

            if page_range:
                start_p = max(1, page_range[0])
                end_p = min(total_pages, page_range[1])

            logger.info(
                "PDFParser: Bắt đầu xử lý '%s' (%d trang, khoảng trang: %d -> %d)...",
                path.name,
                total_pages,
                start_p,
                end_p,
            )

            # 1. Module 1: Phân loại loại trang (PDF Type Detection)
            all_page_types = self.type_detector.detect_pages(path)
            target_pages = [p for p in all_page_types if start_p <= p.page <= end_p]

            text_page_nums = [p.page for p in target_pages if p.is_text]
            scanned_page_nums = [p.page for p in target_pages if p.is_scanned]

            logger.info(
                "PDFParser: Định tuyến trang '%s' -> %d trang Digital (TextParser), %d trang Scan (OCRPipeline).",
                path.name,
                len(text_page_nums),
                len(scanned_page_nums),
            )

            # 2a. Module 2a: Trích xuất Digital Text (pdfplumber)
            text_blocks: list[ParsedBlock] = []
            if text_page_nums:
                text_blocks = self.text_parser.parse_pages(
                    pdf=pdf,
                    page_numbers=text_page_nums,
                    company=company,
                    year=year,
                )

            # 2b. Module 2b: Trích xuất Scanned Pages (OCRPipeline)
            ocr_blocks: list[ParsedBlock] = []
            if scanned_page_nums:
                if self.settings.enable_ocr_fallback:
                    ocr_blocks = self.ocr_pipeline.process_pages(
                        pdf=pdf,
                        page_numbers=scanned_page_nums,
                        company=company,
                        year=year,
                    )
                else:
                    logger.warning(
                        "PDFParser: Phát hiện %d trang scan nhưng ENABLE_OCR_FALLBACK=False. Bỏ qua OCR.",
                        len(scanned_page_nums),
                    )

            # 3. Module 3: Output Normalization (Hợp nhất và chuẩn hóa kết quả)
            normalized_blocks = self.normalizer.normalize(
                text_blocks=text_blocks,
                ocr_blocks=ocr_blocks,
            )

            logger.info(
                "PDFParser: Hoàn tất xử lý '%s' -> Tổng cộng %d ParsedBlocks chuẩn hóa.",
                path.name,
                len(normalized_blocks),
            )
            return normalized_blocks

    def parse_pdf_to_document(
        self,
        pdf_path: str | Path,
        company: str = "DOANH_NGHIEP",
        year: int = 2024,
        page_range: tuple[int, int] | None = None,
    ) -> ParsedDocument:
        """Parse PDF và đóng gói thành ParsedDocument hoàn chỉnh."""
        blocks = self.parse_pdf(
            pdf_path=pdf_path,
            company=company,
            year=year,
            page_range=page_range,
        )
        total_pages = max((b.page for b in blocks), default=1)
        return ParsedDocument(
            company=company,
            year=year,
            total_pages=total_pages,
            blocks=blocks,
            metadata={"source_file": str(pdf_path)},
        )

    # Delegating helper methods để đảm bảo backward compatibility với tests và callers cũ
    def _parse_page(
        self,
        page: pdfplumber.page.Page,
        page_number: int,
        company: str,
        year: int,
    ) -> list[ParsedBlock]:
        """Ủy quyền sang TextParser (backward compatibility)."""
        return self.text_parser.parse_page(page, page_number=page_number, company=company, year=year)

    def _merge_spanning_tables(self, blocks: list[ParsedBlock]) -> list[ParsedBlock]:
        """Ủy quyền sang OutputNormalizer (backward compatibility)."""
        return self.normalizer._merge_spanning_tables(blocks)
