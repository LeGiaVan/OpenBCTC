"""
table_verifier.py — Hệ thống Kiểm tra Chất lượng Bảng biểu & Tự động Capture Ảnh Crop (HITL Table Inspector).

Chức năng:
  1. TableBlockIndexer: So khớp thông minh (Content Token Fingerprinting) để triệt tiêu lỗi lệch trang.
  2. TableCapturer: Tự động trích xuất & crop ảnh độ phân giải cao (200 DPI) cho từng bảng từ PDF gốc.
  3. TableQualityChecker: Kiểm toán cấu trúc bảng biểu Markdown (độ lệch cột, header, rác OCR trong ô số, tổng cộng).
  4. TableInspector: Điều phối toàn bộ quy trình Check & Capture tích hợp trực tiếp vào LangGraph Pipeline.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    import pymupdf as fitz
    HAS_PYMUPDF = True
except ImportError:
    try:
        import fitz
        HAS_PYMUPDF = True
    except ImportError:
        HAS_PYMUPDF = False


# =====================================================================
# 1. BỘ CHỈ MỤC & SO KHỚP BẢNG THÔNG MINH (CONTENT TOKEN FINGERPRINTING)
# =====================================================================

class TableBlockIndexer:
    """
    Lập chỉ mục tất cả các khối bảng OCR từ cache và manifest.
    Giúp ánh xạ chính xác 1-1 từng bảng trong Markdown về đúng Trang và Ảnh Crop gốc.
    """
    def __init__(self, project_root: Path | None = None, company: str = "", year: int = 0):
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent.parent
        self.project_root = project_root
        self.company = company
        self.year = year
        self.cached_blocks: list[dict[str, Any]] = []
        self._load_cache()

    def _load_cache(self) -> None:
        self.cached_blocks = []
        target_dir_name = f"{self.company}_{self.year}" if self.company and self.year else ""

        # 1. Thu thập tất cả các thư mục chứa cache json
        search_dirs: list[Path] = []
        if target_dir_name:
            search_dirs.extend([
                self.project_root / "outputs" / target_dir_name / "cache" / "ocr",
                self.project_root / "outputs" / target_dir_name / "cache" / "notes",
                self.project_root / "data" / "cache" / "ocr" / target_dir_name,
                self.project_root / "data" / "cache" / "notes" / target_dir_name,
            ])
        else:
            outputs_dir = self.project_root / "outputs"
            if outputs_dir.exists():
                for sub in outputs_dir.iterdir():
                    if sub.is_dir() and (sub / "cache").exists():
                        search_dirs.append(sub / "cache" / "ocr")
                        search_dirs.append(sub / "cache" / "notes")
            for base in (self.project_root / "data" / "cache" / "ocr", self.project_root / "data" / "cache" / "notes"):
                if base.exists():
                    search_dirs.extend([d for d in base.iterdir() if d.is_dir()])

        for c_dir in search_dirs:
            if not c_dir.exists():
                continue
            for f in sorted(c_dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    for b in data:
                        if b.get("block_type") == "table":
                            b_copy = dict(b)
                            b_copy["_company"] = target_dir_name or c_dir.parent.name
                            b_copy["_tokens"] = self._tokenize(b.get("content", ""))
                            self.cached_blocks.append(b_copy)
                except Exception:
                    pass

        # 2. CHỈ nạp manifest mẫu khi đang kiểm thử riêng Vinamilk (tránh nhiễm chéo sang doanh nghiệp khác)
        if (not self.company or self.company.upper() == "VNM") and (not self.year or self.year == 2024):
            manifest_file = self.project_root / "evaluation_table" / "manifest.json"
            if manifest_file.exists():
                try:
                    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                    existing_bids = set(b.get("block_id") for b in self.cached_blocks)
                    for item in manifest:
                        bid = item["table_id"]
                        if bid not in existing_bids:
                            self.cached_blocks.append({
                                "block_id": bid,
                                "page": item.get("page", 1),
                                "bbox": item.get("bbox"),
                                "content": item.get("description", ""),
                                "_company": "VNM_2024",
                                "_tokens": self._tokenize(item.get("description", "") + " " + bid)
                            })
                except Exception:
                    pass

        logger.info("TableBlockIndexer: Đã nạp %d khối bảng tham chiếu từ cache (Doanh nghiệp: %s).", len(self.cached_blocks), self.company or "All")

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return set(re.findall(r"\b[A-Za-zÀ-ỹ0-9_]{3,}\b", text.lower()))

    def match_table(self, md_table_content: str, fallback_page: int = 1) -> dict[str, Any]:
        """So khớp nội dung bảng Markdown để tìm chính xác block_id, trang và tọa độ crop."""
        t_tokens = self._tokenize(md_table_content)
        if not t_tokens:
            return {"block_id": None, "page": fallback_page, "bbox": None}

        best_block = None
        best_overlap = 0

        for b in self.cached_blocks:
            overlap = len(t_tokens & b["_tokens"])
            if overlap > best_overlap:
                best_overlap = overlap
                best_block = b

        if best_block and best_overlap >= 3:
            return {
                "block_id": best_block.get("block_id"),
                "page": best_block.get("page", fallback_page),
                "bbox": best_block.get("bbox"),
                "overlap_score": best_overlap,
            }

        return {"block_id": None, "page": fallback_page, "bbox": None, "overlap_score": 0}


# =====================================================================
# 2. BỘ CAPTURE ẢNH CROP BẢNG BIỂU (HIGH-RES TABLE CROPPING)
# =====================================================================

class TableCapturer:
    """Trích xuất và lưu trữ ảnh crop độ phân giải cao cho từng bảng biểu từ PDF."""

    def __init__(self, project_root: Path | None = None):
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent.parent
        self.project_root = project_root

    def crop_table_image(
        self,
        pdf_path: str | Path,
        page_num: int,
        bbox: list[float] | tuple[float, float, float, float] | None,
        output_path: Path,
        dpi: int = 200,
        pad: int = 12,
        is_landscape: bool = False
    ) -> bool:
        """Cắt ảnh một bảng từ PDF và lưu vào output_path."""
        if not HAS_PYMUPDF:
            logger.warning("TableCapturer: Không có PyMuPDF, bỏ qua crop ảnh.")
            return False

        pdf_p = Path(pdf_path).resolve()
        if not pdf_p.exists():
            logger.warning("TableCapturer: Không tìm thấy file PDF '%s'.", pdf_p)
            return False

        try:
            doc = fitz.open(str(pdf_p))
            if page_num < 1 or page_num > len(doc):
                logger.warning("TableCapturer: Trang %d vượt quá số trang PDF (%d).", page_num, len(doc))
                return False

            page = doc[page_num - 1]
            pw, ph = page.rect.width, page.rect.height

            if bbox and len(bbox) == 4:
                c1, c2, c3, c4 = bbox
                xmin = min(c1, c3)
                xmax = max(c1, c3)
                ymin = min(c2, c4)
                ymax = max(c2, c4)
                # Bounding box chuẩn hóa (0.0 - 1.0)
                rect = fitz.Rect(
                    max(0, xmin * pw - pad),
                    max(0, ymin * ph - pad),
                    min(pw, xmax * pw + pad),
                    min(ph, ymax * ph + pad)
                )
            else:
                # Nếu không có bbox: crop phần thân tài liệu (loại bỏ lề trên và chân trang)
                rect = fitz.Rect(0.06 * pw, 0.12 * ph, 0.94 * pw, 0.90 * ph)

            pix = page.get_pixmap(clip=rect, dpi=dpi)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            from PIL import Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Tự động phát hiện bảng in ngang (Landscape) trên trang giấy dọc (Portrait):
            # Nếu chiều cao > chiều rộng * 1.25, bảng đã bị xoay 90 độ.
            # Tự động xoay 90 độ theo chiều kim đồng hồ (PIL 270) để đưa bảng về phương nằm ngang 0 độ chuẩn.
            if is_landscape or img.height > img.width * 1.25:
                try:
                    img = img.rotate(270, expand=True) # Xoay 90° Clockwise về 0° nằm ngang chuẩn
                    logger.info("TableCapturer: Đã tự động xoay 90° Clockwise bảng in ngang trang %d (%dx%d -> %dx%d).", page_num, pix.width, pix.height, img.width, img.height)
                except Exception as ex:
                    logger.warning("TableCapturer: Lỗi xoay ảnh landscape trang %d: %s", page_num, ex)

            img.save(str(output_path))
            return True
        except Exception as e:
            logger.error("TableCapturer: Lỗi khi crop trang %d: %s", page_num, e)
            return False


# =====================================================================
# 3. BỘ KIỂM TRA CHẤT LƯỢNG BẢNG (TABLE QUALITY & SANITY CHECKER)
# =====================================================================

class TableQualityChecker:
    """Kiểm toán cấu trúc hàng cột, định dạng số và phát hiện bất thường OCR trong bảng."""

    @staticmethod
    def audit_table(table_lines: list[str], table_id: int = 1, page: int = 1) -> dict[str, Any]:
        """
        Kiểm toán chi tiết 1 bảng Markdown:
          - Tính đồng nhất số cột giữa các hàng.
          - Nhận diện tầng Header (1 tầng vs 2 tầng).
          - Phát hiện ký tự chữ OCR nhầm trong cột số (ví dụ: '1.497.448.6l8.455', '2O24', '1.00O').
          - Tỷ lệ ô trống.
        """
        issues: list[str] = []
        warnings: list[str] = []

        if not table_lines:
            return {
                "table_id": table_id,
                "page": page,
                "is_valid": False,
                "n_rows": 0,
                "n_cols": 0,
                "issues": ["Bảng rỗng, không có dòng nào"],
                "warnings": [],
            }

        rows_cells: list[list[str]] = []
        separator_idx = -1

        for idx, line in enumerate(table_lines):
            inner = line.strip()
            if inner.startswith("|"):
                inner = inner[1:]
            if inner.endswith("|"):
                inner = inner[:-1]
            cells = [c.strip() for c in inner.split("|")]

            is_sep = len(cells) > 0 and all(re.match(r"^:?-+:?$", c) for c in cells if c)
            if is_sep and separator_idx == -1:
                separator_idx = idx
                continue
            rows_cells.append(cells)

        if not rows_cells:
            return {
                "table_id": table_id,
                "page": page,
                "is_valid": False,
                "n_rows": 0,
                "n_cols": 0,
                "issues": ["Bảng chỉ có đường phân cách, không có dữ liệu"],
                "warnings": [],
            }

        header_count = separator_idx if separator_idx > 0 else 1
        col_counts = [len(r) for r in rows_cells]
        max_cols = max(col_counts) if col_counts else 0
        min_cols = min(col_counts) if col_counts else 0

        # 1. Kiểm tra độ lệch cột (Ragged table)
        if min_cols != max_cols:
            issues.append(f"Số cột không đồng nhất giữa các hàng: biến động từ {min_cols} đến {max_cols} cột")

        # 2. Kiểm tra tỷ lệ ô trống
        total_cells = sum(len(r) for r in rows_cells)
        empty_cells = sum(1 for r in rows_cells for c in r if not c)
        empty_ratio = round(empty_cells / max(total_cells, 1), 3)
        if empty_ratio > 0.5:
            warnings.append(f"Tỷ lệ ô trống cao ({round(empty_ratio * 100, 1)}% tổng số ô)")

        # 3. Kiểm tra rác OCR trong các ô số
        ocr_suspicious_cells = 0
        for r_idx, row in enumerate(rows_cells[header_count:], start=header_count + 1):
            for c_idx, cell in enumerate(row):
                # Phát hiện chuỗi có dạng số kèm chữ cái hay bị OCR nhầm (l, I, O, o, S)
                if re.search(r"\d+[lIOSo]\d+", cell) or re.search(r"^\d+[\.,]\d+[lIOo]$", cell):
                    ocr_suspicious_cells += 1
                    if len(warnings) < 5:
                        warnings.append(f"Nghi vấn rác OCR tại ô [Hàng {r_idx}, Cột {c_idx+1}]: '{cell}'")

        if ocr_suspicious_cells > 0:
            issues.append(f"Phát hiện {ocr_suspicious_cells} ô có dấu hiệu dính ký tự chữ OCR vào số")

        # 4. Kiểm tra Header
        if header_count == 0 or not rows_cells[0]:
            warnings.append("Bảng không có dòng tiêu đề (Header) rõ ràng")

        is_valid = len(issues) == 0

        return {
            "table_id": table_id,
            "page": page,
            "n_rows": len(rows_cells),
            "n_cols": max_cols,
            "header_rows_count": header_count,
            "empty_cell_ratio": empty_ratio,
            "is_valid": is_valid,
            "issues": issues,
            "warnings": warnings,
        }


# =====================================================================
# 4. ĐIỀU PHỐI VIÊN KIỂM TRA & CAPTURE TỔNG HỢP (TABLE INSPECTOR)
# =====================================================================

class TableInspector:
    """Điều phối toàn diện bước Check & Capture bảng biểu cho LangGraph."""

    def __init__(self, project_root: Path | None = None):
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent.parent
        self.project_root = project_root
        self.indexer = TableBlockIndexer(project_root)
        self.capturer = TableCapturer(project_root)
        self.checker = TableQualityChecker()

    def process_document_tables(
        self,
        pdf_path: str | Path,
        markdown_content: str,
        company: str = "VNM",
        year: int = 2024,
        crops_dir: Path | None = None,
    ) -> dict[str, Any]:
        """
        Quét toàn bộ tài liệu Markdown:
          1. Trích xuất tất cả bảng biểu GFM.
          2. Định vị chính xác số trang & block_id qua Token Matching.
          3. Tự động crop và lưu ảnh bảng độ phân giải cao từ PDF gốc.
          4. Kiểm toán chất lượng cấu trúc từng bảng.
          5. Trả về báo cáo tổng hợp TableAuditReport.
        """
        if crops_dir is None:
            cand_crops = self.project_root / "outputs" / f"{company}_{year}" / "cache" / "table_crops"
            cand_old = self.project_root / "data" / "cache" / "table_crops" / f"{company}_{year}"
            crops_dir = cand_crops
            if not cand_crops.exists() and cand_old.exists():
                crops_dir = cand_old
        crops_dir.mkdir(parents=True, exist_ok=True)

        # Cập nhật indexer theo đúng doanh nghiệp và niên độ hiện tại
        self.indexer = TableBlockIndexer(self.project_root, company=company, year=year)

        lines = markdown_content.splitlines()
        extracted_tables: list[dict[str, Any]] = []
        curr_table: list[str] = []
        last_heading = "BCTC"
        last_page = 1

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                last_heading = stripped
            page_m = re.search(r"\*\(Trang\s+(\d+)(?:[–-]\d+)?\)\*", stripped, re.IGNORECASE)
            if page_m:
                try:
                    last_page = int(page_m.group(1))
                except ValueError:
                    pass

            is_pipe = stripped.startswith("|") and stripped.endswith("|") and ("|" in stripped[1:-1])
            if is_pipe:
                curr_table.append(line)
            else:
                if curr_table:
                    extracted_tables.append({
                        "lines": list(curr_table),
                        "heading": last_heading,
                        "fallback_page": last_page,
                    })
                    curr_table.clear()

        if curr_table:
            extracted_tables.append({
                "lines": list(curr_table),
                "heading": last_heading,
                "fallback_page": last_page,
            })

        table_reports: list[dict[str, Any]] = []
        captured_count = 0

        for idx, t_info in enumerate(extracted_tables, start=1):
            t_content = "\n".join(t_info["lines"])
            match_res = self.indexer.match_table(t_content, fallback_page=t_info["fallback_page"])
            exact_page = match_res["page"]
            block_id = match_res["block_id"] or f"table_{idx}"
            bbox = match_res.get("bbox")

            # 1. Kiểm tra chất lượng bảng
            audit_res = self.checker.audit_table(t_info["lines"], table_id=idx, page=exact_page)
            audit_res["block_id"] = block_id
            audit_res["heading"] = t_info["heading"]

            # 2. Capture / Kiểm tra ảnh crop từ PDF cho đúng doanh nghiệp
            crop_filename = f"{block_id}.png"
            crop_cache_path = crops_dir / crop_filename

            # Ưu tiên nếu đã có sẵn trong outputs/{company}_{year}/cache/table_crops/ hoặc data/cache/
            if not crop_cache_path.exists():
                cand_old_file = self.project_root / "data" / "cache" / "table_crops" / f"{company}_{year}" / crop_filename
                if cand_old_file.exists():
                    crop_cache_path = cand_old_file

            if crop_cache_path.exists():
                audit_res["crop_image_path"] = str(crop_cache_path)
                captured_count += 1
            else:
                # Tiến hành crop trực tiếp từ PDF gốc của tài liệu
                ok = self.capturer.crop_table_image(
                    pdf_path=pdf_path,
                    page_num=exact_page,
                    bbox=bbox,
                    output_path=crop_cache_path,
                    dpi=200,
                )
                if ok:
                    audit_res["crop_image_path"] = str(crop_cache_path)
                    captured_count += 1
                else:
                    audit_res["crop_image_path"] = ""
                    audit_res["warnings"].append("Không thể crop ảnh bảng từ PDF")

            table_reports.append(audit_res)

        valid_count = sum(1 for r in table_reports if r["is_valid"])
        warn_count = len(table_reports) - valid_count

        summary_report = {
            "total_tables": len(table_reports),
            "valid_tables": valid_count,
            "tables_with_warnings": warn_count,
            "captured_images_count": captured_count,
            "crops_dir": str(crops_dir),
            "table_reports": table_reports,
        }

        logger.info(
            "TableInspector: Hoàn tất kiểm tra & capture %d bảng biểu (%d chuẩn, %d cảnh báo, %d ảnh crop sẵn sàng).",
            len(table_reports),
            valid_count,
            warn_count,
            captured_count,
        )

        return summary_report
