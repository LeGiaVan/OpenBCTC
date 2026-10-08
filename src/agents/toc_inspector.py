"""
toc_inspector.py — Trinh sát Mục lục và Phân ranh giới tài liệu Báo cáo Tài chính (Document Triage).
Nhiệm vụ:
  1. Quét nhanh 3-5 trang đầu tiên của file PDF BCTC để phát hiện Bảng Mục lục (Table of Contents - TOC).
  2. Phân tích các dòng mục lục để xác định:
     - Các trang chứa Báo cáo Tài chính cốt lõi (Bảng cân đối kế toán, KQKD, Lưu chuyển tiền tệ).
     - Các trang chứa Thuyết minh BCTC (Notes / Narrative text cho RAG).
     - Các trang mở đầu (Báo cáo Ban Giám đốc, Báo cáo kiểm toán độc lập).
  3. Tính toán Page Offset giữa số trang in trong mục lục và số thứ tự trang PDF thực tế.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from src.parser.local_ocr import LocalOCREngine
from src.parser.ocr_pipeline import VisionOCRPipeline
from src.parser.pdf_type_detector import PDFTypeDetector
from src.parser.text_parser import TextParser
import json

logger = logging.getLogger(__name__)


@dataclass
class DocumentStructure:
    """Cấu trúc phân vùng tài liệu BCTC sau khi trinh sát mục lục."""

    total_pages: int
    toc_found: bool
    toc_page: int | None
    core_statement_pages: list[int]
    notes_pages: list[int]
    intro_pages: list[int]
    page_offset: int = 1
    raw_toc_entries: list[dict] = field(default_factory=list)
    # field(default_factory=list) tạo vùng nhớ mới khi khởi tạo chung Class, nếu ko có thì các Class sẽ trỏ chung 1 ô nhớ trong RAM.

    def summary(self) -> str:
        toc_str = f"Trang {self.toc_page}" if self.toc_found else "Không có mục lục (Dùng Heuristics chuẩn)"
        core_range = f"{min(self.core_statement_pages)} -> {max(self.core_statement_pages)}" if self.core_statement_pages else "N/A"
        notes_range = f"{min(self.notes_pages)} -> {max(self.notes_pages)}" if self.notes_pages else "N/A"
        intro_range = f"{min(self.intro_pages)} -> {max(self.intro_pages)}" if self.intro_pages else "N/A"
        return (
            f"Tổng số trang: {self.total_pages} | Mục lục: {toc_str} | Offset: +{self.page_offset}\n"
            f"  - Trang mở đầu & Kiểm toán: {intro_range} ({len(self.intro_pages)} trang)\n"
            f"  - BCTC cốt lõi: {core_range} ({len(self.core_statement_pages)} trang)\n"
            f"  - Thuyết minh BCTC: {notes_range} ({len(self.notes_pages)} trang)"
        )


class TOCInspector:
    """Agent trinh sát mục lục phân luồng tài liệu BCTC."""

    def __init__(
        self,
        vision_pipeline: VisionOCRPipeline | None = None,
        local_ocr: LocalOCREngine | None = None,
        text_parser: TextParser | None = None,
        type_detector: PDFTypeDetector | None = None,
    ) -> None:
        self.vision_pipeline = vision_pipeline or VisionOCRPipeline()
        self.local_ocr = local_ocr or LocalOCREngine()
        self.text_parser = text_parser or TextParser()
        self.type_detector = type_detector or PDFTypeDetector()

    def inspect(
        self,
        pdf_path: str | Path,
        company: str = "DOANH_NGHIEP",
        year: int = 2024,
        max_scan_pages: int = 5,
        page_offset: int | None = None,
    ) -> DocumentStructure:
        """
        Trinh sát tài liệu: Quét nhanh tối đa 5 trang đầu để tìm Mục lục.
        Nếu tìm thấy -> parse các dải trang và tính offset.
        Nếu không -> dùng heuristic chuẩn BCTC Việt Nam (TT 200).
        """
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"Không tìm thấy file PDF: {pdf_file.resolve()}")

        with pdfplumber.open(pdf_file) as pdf:
            total_pages = len(pdf.pages)
            pages_to_check = min(max_scan_pages, total_pages)

            for p_num in range(1, pages_to_check + 1):
                page = pdf.pages[p_num - 1]

                # Thử nạp từ cache hoặc trích xuất nhanh
                blocks = self._get_page_blocks(page, p_num, company, year)
                toc_entries = self._find_toc_in_blocks(blocks)

                if toc_entries:
                    logger.info("TOCInspector: Đã phát hiện Bảng Mục lục tại trang PDF %d!", p_num)
                    doc_struct = self._build_structure_from_toc(
                        toc_entries=toc_entries,
                        toc_pdf_page=p_num,
                        total_pages=total_pages,
                        page_offset=page_offset,
                        pdf=pdf,
                        company=company,
                        year=year,
                    )
                    return doc_struct

        # Fallback Heuristics chuẩn nếu tài liệu không in bảng mục lục rõ ràng
        logger.info(
            "TOCInspector: Không phát hiện bảng mục lục ở %d trang đầu. Kích hoạt Heuristic TT 200.",
            pages_to_check,
        )
        return self._build_fallback_structure(total_pages)

    def _get_page_blocks(
        self,
        page: pdfplumber.page.Page,
        page_num: int,
        company: str,
        year: int,
    ) -> list:
        """
        Lấy blocks trang theo cơ chế định tuyến thông minh:
        - Nếu trang là Digital Native Text (char_count >= threshold): Sử dụng TextParser (pdfplumber)
          -> Cực nhanh, 0 token API, giữ nguyên cấu trúc bảng/văn bản.
        - Nếu trang là Scanned Image: Sử dụng Vision Pipeline (hoặc checkpoint cache nếu có).
        """
        raw_text = page.extract_text() or ""
        char_count = len(raw_text.strip())

        if char_count >= self.type_detector.min_char_threshold:
            logger.info(
                "TOCInspector: Trang %d là Native Text (%d ký tự) -> Sử dụng TextParser (pdfplumber, 0 API calls).",
                page_num,
                char_count,
            )
            return self.text_parser.parse_page(
                page=page,
                page_number=page_num,
                company=company,
                year=year,
            )

        logger.info(
            "TOCInspector: Trang %d là Scanned Image (%d ký tự) -> Chuyển sang VisionOCRPipeline.",
            page_num,
            char_count,
        )
        return self.vision_pipeline.process_scanned_page(
            page=page,
            page_number=page_num,
            company=company,
            year=year,
        )

    def _find_toc_in_blocks(self, blocks: list) -> list[dict]:
        """Tìm bảng hoặc đoạn text có chứa nội dung mục lục (hỗ trợ cả Markdown Table và Plain text)."""
        for b in blocks:
            content = b.content if hasattr(b, "content") else str(b.get("content", ""))
            content_upper = content.upper()

            # Kiểm tra từ khóa mục lục
            is_toc_candidate = (
                ("NỘI DUNG" in content_upper or "MỤC LỤC" in content_upper)
                and ("TRANG" in content_upper or "PAGE" in content_upper)
            ) or (
                "BÁO CÁO TÌNH HÌNH TÀI CHÍNH" in content_upper
                and "THUYẾT MINH" in content_upper
            )

            if is_toc_candidate:
                # 1. Thử parse dạng Markdown table
                entries = self._parse_toc_markdown(content)
                if len(entries) >= 3:
                    return entries

                # 2. Thử parse dạng Plain text (kết xuất từ TextParser/pdfplumber)
                plain_entries = self._parse_toc_plain_text(content)
                if len(plain_entries) >= 3:
                    return plain_entries
        return []

    def _parse_toc_plain_text(self, text_content: str) -> list[dict]:
        """
        Bóc tách mục lục từ văn bản thuần (plain text) nếu không phải bảng markdown:
        Ví dụ:
          Báo cáo tình hình tài chính .................... 6
          Báo cáo kết quả hoạt động kinh doanh .......... 9
          Thuyết minh báo cáo tài chính ................. 12 - 53
        """
        entries: list[dict] = []
        lines = text_content.split("\n")
        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue
            m = re.search(r"^(.*?)(?:[\.\-\s_]{2,}|\t+)\s*([\d\-\,\s]+)$", line_clean)
            if m:
                title = m.group(1).strip()
                page_raw = m.group(2).strip()
                parsed_pages = self._parse_page_number_raw(page_raw)
                if parsed_pages and len(title) > 3:
                    entries.append({"title": title, "pages": parsed_pages, "raw": page_raw})
        return entries

    def _parse_toc_markdown(self, markdown_content: str) -> list[dict]:
        """
        Bóc tách các dòng trong bảng Markdown Mục lục thành danh sách các mục:
        Hỗ trợ cả bảng có ký tự '|' ở đầu dòng lẫn bảng chỉ dùng '|' làm phân cách giữa các cột.
        Ví dụ:
          | BÁO CÁO TÌNH HÌNH TÀI CHÍNH RIÊNG | 6 - 8 |
          BÁO CÁO TÌNH HÌNH TÀI CHÍNH RIÊNG | 6 - 8
          | THUYẾT MINH BÁO CÁO TÀI CHÍNH RIÊNG | 12 - 53 |
        """
        entries: list[dict] = []
        lines = markdown_content.split("\n")

        for line in lines:
            line_clean = line.strip()
            if not line_clean or line_clean.startswith("---") or "| ---" in line_clean or "--- |" in line_clean:
                continue

            if "|" in line_clean:
                parts = [p.strip() for p in line_clean.split("|") if p.strip()]
                if len(parts) >= 2:
                    title = parts[0]
                    page_raw = parts[1]

                    # Bỏ qua dòng tiêu đề cột
                    if "NỘI DUNG" in title.upper() and "TRANG" in page_raw.upper():
                        continue

                    parsed_pages = self._parse_page_number_raw(page_raw)
                    if parsed_pages:
                        entries.append({"title": title, "pages": parsed_pages, "raw": page_raw})

        return entries

    @staticmethod
    def _parse_page_number_raw(page_str: str) -> tuple[int, int] | None:
        """
        Xử lý số trang có thể bị dính số do OCR scan:
          - '2' -> (2, 2)
          - '6 - 8' hoặc '6-8' -> (6, 8)
          - '68' (OCR dính 6-8) -> (6, 8)
          - '45' (OCR dính 4-5) -> (4, 5)
          - '1,011' hoặc '1011' (OCR dính 10-11) -> (10, 11)
          - '1,253' hoặc '1253' (OCR dính 12-53) -> (12, 53)
        """
        clean = re.sub(r"[^\d\-]", "", page_str)
        if not clean:
            return None

        # 1. Định dạng rõ ràng có dấu gạch ngang (6-8)
        if "-" in clean:
            parts = clean.split("-")
            try:
                return (int(parts[0]), int(parts[1]))
            except ValueError:
                pass

        # 2. Định dạng đơn số (2, 3, 9)
        if clean.isdigit():
            val = int(clean)
            if val < 20:
                return (val, val)

            # OCR dính 2 số: '45' -> 4, 5; '68' -> 6, 8
            if len(clean) == 2:
                d1, d2 = int(clean[0]), int(clean[1])
                if d1 < d2:
                    return (d1, d2)

            # OCR dính 4 số: '1011' -> 10, 11; '1253' -> 12, 53
            if len(clean) == 4:
                d1 = int(clean[:2])
                d2 = int(clean[2:])
                if d1 < d2:
                    return (d1, d2)

        return None

    @staticmethod
    def _is_anchor_match(candidate_title: str, page_text: str) -> bool:
        """Kiểm tra xem tiêu đề mục có xuất hiện trong phần đầu của trang PDF hay không."""
        title_upper = candidate_title.upper().strip()
        # Tiêu đề mục luôn nằm ở khu vực đầu trang (khoảng 800 ký tự đầu)
        header_area = page_text[:800].upper()

        if title_upper in header_area:
            return True

        # Tách các từ khoá chính (bỏ qua từ nối / phụ từ)
        ignore_words = {"VÀ", "CỦA", "CÁC", "CHO", "NĂM", "KỲ", "TẠI", "NGÀY"}
        words = [
            w for w in re.split(r"[\s,\.\-]+", title_upper)
            if len(w) >= 3 and w not in ignore_words
        ]
        if not words:
            return False

        # Các cụm từ đặc trưng nhận diện BCTC / Báo cáo
        core_terms = ["CÂN ĐỐI", "KẾT QUẢ", "LƯU CHUYỂN", "THUYẾT MINH", "BAN ĐIỀU HÀNH", "BAN GIÁM ĐỐC", "KIỂM TOÁN"]
        for term in core_terms:
            if term in title_upper and term in header_area:
                return True

        # Nếu không có core_term thì yêu cầu ít nhất 70% số từ khóa xuất hiện trong header_area
        matched_count = sum(1 for w in words if w in header_area)
        return (matched_count / len(words)) >= 0.7

    def _detect_offset_by_anchor(
        self,
        pdf: pdfplumber.PDF,
        toc_entries: list[dict],
        toc_pdf_page: int,
        total_pages: int,
        max_lookahead: int = 6,
        company: str = "DOANH_NGHIEP",
        year: int = 2024,
    ) -> int | None:
        """
        Tìm kiếm neo (Anchor Search): Quét nhanh các trang PDF kế tiếp sau Mục lục
        để phát hiện trang thực tế chứa tiêu đề của mục đầu tiên (hoặc các mục chính).
        Hỗ trợ cả Digital Native PDF lẫn Scanned/Non-native PDF (thông qua OCR cache/pipeline).
        """
        if not toc_entries:
            return None

        # Chọn ứng viên neo từ các mục đầu tiên có tiêu đề rõ nghĩa
        anchor_candidates = [
            e for e in toc_entries[:4]
            if len(e.get("title", "").strip()) >= 5 and e.get("pages")
        ]
        if not anchor_candidates:
            return None

        # Quét tối đa max_lookahead trang sau trang Mục lục
        scan_end = min(total_pages, toc_pdf_page + max_lookahead)
        for p_num in range(toc_pdf_page + 1, scan_end + 1):
            try:
                page = pdf.pages[p_num - 1]
                page_text = page.extract_text() or ""

                if not page_text.strip():
                    cand1 = Path(f"outputs/{company}_{year}/cache/ocr/page_{p_num}.json")
                    cand2 = Path("data/cache/ocr") / f"{company}_{year}" / f"page_{p_num}.json"
                    cache_file = cand1 if cand1.exists() else cand2
                    if cache_file.exists():
                        try:
                            with open(cache_file, encoding="utf-8") as f:
                                cached_data = json.load(f)
                            page_text = "\n".join(item.get("content", "") for item in cached_data)
                        except Exception:
                            pass

                if not page_text.strip():
                    continue

                for candidate in anchor_candidates:
                    if self._is_anchor_match(candidate["title"], page_text):
                        first_printed_page = candidate["pages"][0]
                        offset = p_num - first_printed_page
                        logger.info(
                            "TOCInspector: Anchor Search phát hiện mục '%s' (trang in %d) tại trang PDF %d -> page_offset = %d",
                            candidate["title"],
                            first_printed_page,
                            p_num,
                            offset,
                        )
                        return max(0, offset)
            except Exception as e:
                logger.debug("TOCInspector: Lỗi trích xuất trang %d khi tìm anchor: %s", p_num, e)

        return None

    def _build_structure_from_toc(
        self,
        toc_entries: list[dict],
        toc_pdf_page: int,
        total_pages: int,
        page_offset: int | None = None,
        pdf: pdfplumber.PDF | None = None,
        company: str = "DOANH_NGHIEP",
        year: int = 2024,
    ) -> DocumentStructure:
        """Ánh xạ mục lục sang các dải trang PDF vật lý với Page Offset."""
        # 1. Thử Anchor Search nếu có đối tượng PDF và chưa có page_offset
        if page_offset is None and pdf is not None:
            page_offset = self._detect_offset_by_anchor(
                pdf=pdf,
                toc_entries=toc_entries,
                toc_pdf_page=toc_pdf_page,
                total_pages=total_pages,
                company=company,
                year=year,
            )

        # 2. Tự động tính page_offset theo heuristic nếu anchor search không tìm thấy:
        # - min_printed_page == 1 => Trang in 1 nằm ở trang PDF (toc_pdf_page + 1) => page_offset = toc_pdf_page
        # - min_printed_page >= 2 => Trang in 1 chính là toc_pdf_page => page_offset = max(1, toc_pdf_page - 1)
        if page_offset is None:
            min_printed_page = (
                min(entry["pages"][0] for entry in toc_entries)
                if toc_entries
                else 1
            )
            if min_printed_page == 1:
                page_offset = toc_pdf_page
            else:
                page_offset = max(1, toc_pdf_page - 1)

        core_printed_pages: list[int] = []
        notes_printed_pages: list[int] = []

        for entry in toc_entries:
            title_upper = entry["title"].upper()
            p_start, p_end = entry["pages"]
            p_range = list(range(p_start, p_end + 1))

            # Báo cáo cốt lõi: Tình hình tài chính, KQKD, Lưu chuyển tiền tệ
            if any(k in title_upper for k in ["TÌNH HÌNH TÀI CHÍNH", "CÂN ĐỐI", "KẾT QUẢ", "LƯU CHUYỂN"]):
                core_printed_pages.extend(p_range)
            # Thuyết minh BCTC
            elif "THUYẾT MINH" in title_upper:
                notes_printed_pages.extend(p_range)

        # Chuyển đổi từ số trang in sang số trang PDF thực tế
        core_pdf_pages = sorted(list({p + page_offset for p in core_printed_pages if 1 <= p + page_offset <= total_pages}))
        notes_pdf_pages = sorted(list({p + page_offset for p in notes_printed_pages if 1 <= p + page_offset <= total_pages}))

        # Nếu không có notes_pages cụ thể từ mục lục, lấy từ sau core_pdf_pages đến hết
        if not notes_pdf_pages and core_pdf_pages:
            notes_pdf_pages = list(range(max(core_pdf_pages) + 1, total_pages + 1))

        # Intro pages: Các trang đứng trước BCTC cốt lõi
        first_core = min(core_pdf_pages) if core_pdf_pages else 6
        intro_pdf_pages = list(range(1, first_core))

        return DocumentStructure(
            total_pages=total_pages,
            toc_found=True,
            toc_page=toc_pdf_page,
            core_statement_pages=core_pdf_pages or [7, 8, 9, 10, 11],
            notes_pages=notes_pdf_pages or list(range(12, total_pages + 1)),
            intro_pages=intro_pdf_pages,
            page_offset=page_offset,
            raw_toc_entries=toc_entries,
        )

    @staticmethod
    def _build_fallback_structure(total_pages: int) -> DocumentStructure:
        """Cấu trúc mặc định dựa trên thông lệ Báo cáo tài chính Việt Nam (Thông tư 200)."""
        core_pages = [p for p in range(6, min(12, total_pages + 1))]
        notes_pages = [p for p in range(12, total_pages + 1)]
        intro_pages = [p for p in range(1, 6)]

        return DocumentStructure(
            total_pages=total_pages,
            toc_found=False,
            toc_page=None,
            core_statement_pages=core_pages,
            notes_pages=notes_pages,
            intro_pages=intro_pages,
            page_offset=1,
            raw_toc_entries=[],
        )
