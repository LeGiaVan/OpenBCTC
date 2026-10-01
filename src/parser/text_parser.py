"""
text_parser.py — Bóc tách dữ liệu từ các trang Digital PDF (văn bản số hóa) bằng pdfplumber.
- Trích xuất bảng biểu có cấu trúc và văn bản ngoài bảng
- Tách dải văn bản (bands) để duy trì thứ tự đọc tự nhiên từ trên xuống dưới
- Nhận diện đơn vị tiền tệ và header nhiều tầng
- Đặt thuộc tính source="pdfplumber" cho tất cả ParsedBlock
"""

import logging
from typing import Any

import pdfplumber

from src.config import Settings, get_settings
from src.models import ParsedBlock
from src.parser.table_utils import (
    clean_cell_value,
    compute_numeric_density,
    detect_currency_unit,
    format_table_to_markdown,
)

logger = logging.getLogger(__name__)


class TextParser:
    """Bộ trích xuất chuyên dụng cho các trang PDF dạng văn bản (Digital / Searchable PDF)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def parse_page(
        self,
        page: pdfplumber.page.Page,
        page_number: int,
        company: str = "DOANH_NGHIEP",
        year: int = 2024,
    ) -> list[ParsedBlock]:
        """
        Bóc tách 1 trang Digital PDF, phân tách bảng biểu và văn bản ngoài bảng.

        Args:
            page: Trang pdfplumber
            page_number: Số thứ tự trang (1-indexed)
            company: Mã công ty
            year: Năm tài chính

        Returns:
            list[ParsedBlock]: Danh sách các khối văn bản và bảng biểu theo thứ tự đọc
        """
        blocks: list[ParsedBlock] = []
        page_height = float(page.height)
        page_width = float(page.width)

        # 1. Tìm tất cả bảng biểu trên trang
        raw_tables = page.find_tables()
        if not raw_tables:
            # Trang không có bảng biểu -> trích xuất toàn bộ văn bản thuần
            text = (page.extract_text() or "").strip()
            if text:
                unit = detect_currency_unit(text)
                blocks.append(
                    ParsedBlock(
                        block_id=f"p{page_number}_b1",
                        block_type="text",
                        page=page_number,
                        content=text,
                        bbox=(0.0, 0.0, page_width, page_height),
                        source="pdfplumber",
                        metadata={"unit": unit, "company": company, "year": year},
                    )
                )
            return blocks

        # 2. Sắp xếp các bảng theo tọa độ y0 (từ trên xuống dưới)
        sorted_tables = sorted(raw_tables, key=lambda t: t.bbox[1])

        # 3. Cắt trang thành các dải (bands) xen kẽ: Text -> Table -> Text -> Table...
        current_y = 0.0
        block_counter = 1

        for table_obj in sorted_tables:
            t_x0, t_top, t_x1, t_bottom = table_obj.bbox

            # Dải văn bản nằm trên bảng này (nếu khoảng cách > 10 points)
            if t_top - current_y > 10.0:
                band_bbox = (0.0, max(0.0, current_y), page_width, min(page_height, t_top))
                try:
                    cropped_band = page.crop(band_bbox)
                    band_text = (cropped_band.extract_text() or "").strip()
                    if band_text:
                        unit = detect_currency_unit(band_text)
                        blocks.append(
                            ParsedBlock(
                                block_id=f"p{page_number}_b{block_counter}",
                                block_type="text",
                                page=page_number,
                                content=band_text,
                                bbox=band_bbox,
                                source="pdfplumber",
                                metadata={"unit": unit, "company": company, "year": year},
                            )
                        )
                        block_counter += 1
                except Exception as e:
                    logger.debug("Bỏ qua crop text band trang %d: %s", page_number, e)

            # Trích xuất dữ liệu bảng
            extracted_cells = table_obj.extract()
            if extracted_cells and any(extracted_cells):
                table_block = self._process_extracted_table(
                    extracted_cells=extracted_cells,
                    bbox=(float(t_x0), float(t_top), float(t_x1), float(t_bottom)),
                    page_number=page_number,
                    block_index=block_counter,
                    company=company,
                    year=year,
                )
                if table_block:
                    blocks.append(table_block)
                    block_counter += 1

            current_y = max(current_y, t_bottom)

        # Dải văn bản còn lại ở cuối trang (dưới bảng cuối cùng)
        if page_height - current_y > 15.0:
            tail_bbox = (0.0, current_y, page_width, page_height)
            try:
                cropped_tail = page.crop(tail_bbox)
                tail_text = (cropped_tail.extract_text() or "").strip()
                if tail_text:
                    unit = detect_currency_unit(tail_text)
                    blocks.append(
                        ParsedBlock(
                            block_id=f"p{page_number}_b{block_counter}",
                            block_type="text",
                            page=page_number,
                            content=tail_text,
                            bbox=tail_bbox,
                            source="pdfplumber",
                            metadata={"unit": unit, "company": company, "year": year},
                        )
                    )
            except Exception as e:
                logger.debug("Bỏ qua crop tail band trang %d: %s", page_number, e)

        return blocks

    def parse_pages(
        self,
        pdf: pdfplumber.PDF,
        page_numbers: list[int],
        company: str = "DOANH_NGHIEP",
        year: int = 2024,
    ) -> list[ParsedBlock]:
        """
        Bóc tách nhiều trang Digital PDF.

        Args:
            pdf: Đối tượng pdfplumber.PDF đã mở
            page_numbers: Danh sách số trang 1-indexed cần xử lý
            company: Mã công ty
            year: Năm tài chính

        Returns:
            list[ParsedBlock]: Danh sách ParsedBlock từ các trang digital
        """
        all_blocks: list[ParsedBlock] = []
        for p_num in page_numbers:
            if p_num < 1 or p_num > len(pdf.pages):
                continue
            page = pdf.pages[p_num - 1]
            p_blocks = self.parse_page(page, page_number=p_num, company=company, year=year)
            all_blocks.extend(p_blocks)
        return all_blocks

    def _process_extracted_table(
        self,
        extracted_cells: list[list[Any]],
        bbox: tuple[float, float, float, float],
        page_number: int,
        block_index: int,
        company: str,
        year: int,
    ) -> ParsedBlock | None:
        """Làm sạch ô và chuyển ma trận cells thành ParsedBlock table."""
        cleaned_rows = [
            [clean_cell_value(c) for c in row]
            for row in extracted_cells
            if row and any(clean_cell_value(c) for c in row)
        ]

        if not cleaned_rows:
            return None

        num_rows = len(cleaned_rows)
        num_cols = max(len(r) for r in cleaned_rows)

        # Kiểm tra xem có phải header 2 tầng không
        header_rows_count = 1
        if num_rows >= 3:
            first_row_txt = " ".join(cleaned_rows[0]).lower()
            second_row_txt = " ".join(cleaned_rows[1]).lower()
            if ("năm" in first_row_txt or "kỳ" in first_row_txt) and (
                "kỳ này" in second_row_txt or "đầu năm" in second_row_txt
            ):
                header_rows_count = 2

        markdown_table = format_table_to_markdown(cleaned_rows, header_rows_count=header_rows_count)
        if not markdown_table:
            return None

        num_density = compute_numeric_density(cleaned_rows)
        headers = cleaned_rows[0] if cleaned_rows else []
        unit = detect_currency_unit(" ".join(headers))

        return ParsedBlock(
            block_id=f"p{page_number}_b{block_index}",
            block_type="table",
            page=page_number,
            content=markdown_table,
            bbox=bbox,
            source="pdfplumber",
            metadata={
                "num_rows": num_rows,
                "num_cols": num_cols,
                "numeric_density": round(num_density, 3),
                "headers": headers,
                "unit": unit,
                "raw_rows_count": num_rows,
                "company": company,
                "year": year,
            },
        )
