"""
local_ocr.py — Engine bóc tách chuyên sâu cho các trang Thuyết minh & Narrative text (RAG).
Thực hiện Hướng A theo thiết kế kiến trúc:
  - 100% Offline, 0 Token API tiêu hao.
  - Phân tích Layout & Bảng biểu: Sử dụng MinerU (magic-pdf / mineru) giữ nguyên cấu trúc Markdown Table.
  - Nhận diện Chữ tiếng Việt: Sử dụng VietOCR (vgg_seq2seq) crop theo bounding box để giữ 100% dấu tiếng Việt.
  - Fallback Offline dự phòng: VietOCR + PaddleOCR DBNet (hoặc RapidOCR ONNX).

Toàn bộ kết quả đều được lưu Checkpoint Cache trên đĩa:
  data/cache/notes/{company}_{year}/page_{p}.json
"""

import io
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import pdfplumber

from src.config import Settings, get_settings
from src.models import ParsedBlock, StorageTarget
from src.parser.ocr_postprocess import clean_accounting_text, strip_boilerplate_lines
from src.parser.table_utils import compute_numeric_density, detect_currency_unit, postprocess_mineru_table
from src.parser.mineru_vietocr_adapter import extract_page_with_mineru_vietocr, is_mineru_available

logger = logging.getLogger(__name__)



def _polish_table_headers(headers: list[str], year: int = 2024) -> list[str]:
    """Làm sạch và gán ngữ nghĩa chuẩn cho tiêu đề cột bảng thuyết minh."""
    total_cols = len(headers)
    new_h = list(headers)
    for i in range(1, total_cols):
        clean_txt = clean_accounting_text(new_h[i])
        clean_txt = re.sub(r"\b(VND)\s+\1\b", r"\1", clean_txt, flags=re.IGNORECASE)
        # Nếu header quá dài do lẫn narrative câu văn -> reset để suy luận
        if len(clean_txt) > 40 and not re.search(r"31/12|1/1|nguyên giá|khấu hao|dự phòng|vốn", clean_txt, re.IGNORECASE):
            clean_txt = ""
        new_h[i] = clean_txt

    if total_cols == 3:
        col1_curr = bool(re.search(r"VND|USD", new_h[1], re.IGNORECASE))
        col2_curr = bool(re.search(r"VND|USD", new_h[2], re.IGNORECASE))
        if not new_h[1] or "Cột 1" in new_h[1] or new_h[1] == "VND" or (col1_curr and col2_curr and new_h[1] == new_h[2]):
            new_h[1] = f"31/12/{year} VND"
        if not new_h[2] or "Cột 2" in new_h[2] or new_h[2] == "VND" or (col1_curr and col2_curr and new_h[1] == new_h[2]):
            new_h[2] = f"1/1/{year} VND"
    elif total_cols == 5:
        if any("Cột " in x for x in new_h) or all(x in ("", "VND") for x in new_h[1:]):
            new_h[1] = f"31/12/{year} Giá gốc"
            new_h[2] = f"31/12/{year} Dự phòng / Khả dụng"
            new_h[3] = f"1/1/{year} Giá gốc"
            new_h[4] = f"1/1/{year} Dự phòng / Khả dụng"
    else:
        for i in range(1, total_cols):
            if not new_h[i] or "Cột " in new_h[i] or new_h[i] == "VND":
                if i == 1:
                    new_h[i] = f"Số cuối kỳ ({year}) VND"
                elif i == 2:
                    new_h[i] = f"Số đầu kỳ ({year}) VND"
                else:
                    new_h[i] = f"Chỉ tiêu {i}"
    return new_h


def _sanitize_and_polish_blocks(blocks: list[ParsedBlock], year: int = 2024) -> list[ParsedBlock]:
    """
    Thanh lọc và nâng cấp chất lượng các blocks (cả khi nạp cache và khi bóc tách mới):
      1. Khử triệt để pseudo-tables (bảng rác không có số liệu, chỉ chứa 1 hàng hoặc lẫn narrative).
      2. Nâng cấp tiêu đề cột 'Cột 1, Cột 2' hoặc 'VND, VND' thành các mốc thời gian BCTC chuẩn xác.
    """
    cleaned_blocks: list[ParsedBlock] = []
    for b in blocks:
        if not b.is_table:
            # Lọc bỏ blocks nhiễu thị giác: con dấu, hình ảnh base64
            from src.parser.ocr_postprocess import filter_noise_and_images
            cleaned_content = filter_noise_and_images(b.content)
            if not cleaned_content or len(cleaned_content.strip()) < 3:
                continue
            b.content = cleaned_content
            cleaned_blocks.append(b)
            continue

        # Nếu block đến từ MinerU Layout Engine, cấu trúc bảng đã được MinerU chuẩn hóa
        if b.metadata.get("engine") == "mineru_table":
            cleaned_blocks.append(b)
            continue

        tbl_lines = [l for l in b.content.splitlines() if l.strip()]
        density = b.metadata.get("numeric_density", None)
        num_rows = b.metadata.get("num_rows", 0)
        headers = b.metadata.get("headers", [])

        # Kiểm tra điều kiện pseudo-table:
        is_pseudo = (
            (density is not None and density == 0.0)
            or len(tbl_lines) < 3
            or (num_rows <= 1 and (not headers or any(len(h) > 40 for h in headers) or "Cột 1" in str(headers)))
        )

        if is_pseudo:
            collected_text: list[str] = []
            for h in headers[1:]:
                if len(h) > 20 and not h.startswith("Cột "):
                    collected_text.append(h)
            for row_line in tbl_lines[2:]:
                cells = [c.strip() for c in row_line.split("|")[1:-1]]
                non_empty = [c for c in cells if c]
                if non_empty:
                    collected_text.append(" ".join(non_empty))

            full_text = clean_accounting_text(" ".join(collected_text).strip())
            if full_text and len(full_text) >= 10:
                b.block_type = "text"
                b.content = full_text
                b.metadata["is_demoted_from_pseudo_table"] = True
                cleaned_blocks.append(b)
            continue

        # Nâng cấp bảng thật: Làm sạch tiêu đề cột
        if headers and len(tbl_lines) >= 2:
            new_headers = _polish_table_headers(headers, year=year)
            b.metadata["headers"] = new_headers
            tbl_lines[0] = "| " + " | ".join(new_headers) + " |"
            b.content = "\n".join(tbl_lines)

        cleaned_blocks.append(b)

    return cleaned_blocks


class LocalOCREngine:
    """
    Engine bóc tách các trang Thuyết minh / Narrative text (RAG).
    Hỗ trợ Hướng A (MinerU Layout + VietOCR Text Recognition, 100% offline, 0 API tokens),
    giúp giữ trọn vẹn cả cấu trúc bảng biểu và dấu tiếng Việt chuẩn xác.
    """

    def __init__(
        self,
        resolution: int = 150,
        engine: str = "auto",
        model_name: str = "vgg_seq2seq",
        device: str = "cpu",
        settings: Settings | None = None,
        use_cache: bool = True,
    ) -> None:
        self.resolution = resolution
        self.engine = engine
        self.model_name = model_name
        self.device = device
        self.settings = settings or get_settings()
        self.use_cache = use_cache
        self._rapid_ocr: Any = None
        self._viet_predictor: Any = None
        self._init_rapid_ocr()

    def _init_rapid_ocr(self) -> None:
        """Khởi tạo engine RapidOCR ONNX dự phòng."""
        try:
            from rapidocr_onnxruntime import RapidOCR

            self._rapid_ocr = RapidOCR()
        except ImportError:
            self._rapid_ocr = None

    @property
    def viet_predictor(self) -> Any:
        """Lazy loading cho mô hình VietOCR Predictor (100% offline, 0 API tokens)."""
        if self._viet_predictor is None and self.engine in ("auto", "vietocr"):
            try:
                from vietocr.tool.config import Cfg
                from vietocr.tool.predictor import Predictor

                config = Cfg.load_config_from_name(self.model_name)
                # Tự động ưu tiên CUDA GPU nếu có sẵn
                active_device = self.device
                if active_device in ("auto", "cpu"):
                    try:
                        import torch
                        if torch.cuda.is_available():
                            active_device = "cuda:0"
                    except Exception:
                        pass
                config["device"] = active_device
                self._viet_predictor = Predictor(config)
                logger.info(
                    "LocalOCREngine: Đã nạp thành công VietOCR (%s trên %s).",
                    self.model_name,
                    active_device,
                )
            except Exception as e:
                logger.warning(
                    "LocalOCREngine: Chưa thể nạp VietOCR (%s): %s. Sẽ fallback sang RapidOCR.",
                    self.model_name,
                    e,
                )
                self._viet_predictor = None
        return self._viet_predictor

    def process_scanned_page(
        self,
        page: pdfplumber.page.Page,
        page_number: int,
        company: str = "DOANH_NGHIEP",
        year: int = 2024,
    ) -> list[ParsedBlock]:
        """
        Bóc tách 1 trang Thuyết minh thành danh sách ParsedBlock có cấu trúc (100% Offline, 0 tokens):
          1. Nạp từ Checkpoint Cache nếu đã bóc tách trước đó (khi use_cache=True).
          2. Ưu tiên Hướng A: MinerU Layout (giữ bảng) + VietOCR (chuẩn dấu tiếng Việt).
          3. Nếu không có MinerU: Dùng VietOCR + PaddleOCR DBNet.
          4. Nếu không có VietOCR: Fallback sang RapidOCR ONNX.
          5. Lưu cache và trả về list[ParsedBlock].
        """
        cache_dir = Path("data/cache/notes") / f"{company}_{year}"
        cache_file = cache_dir / f"page_{page_number}.json"

        # 1. Nạp từ Cache nếu có
        if self.use_cache and cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as f:
                    cached_data = json.load(f)
                blocks = [ParsedBlock(**item) for item in cached_data]
                # Tự động thanh lọc các pseudo-tables cũ trong cache và nâng cấp headers chuẩn xác
                blocks = _sanitize_and_polish_blocks(blocks, year=year)

                logger.info(
                    "NotesExtractor: Trang %d nạp từ Checkpoint Cache (%d blocks, 0ms, 0 API calls).",
                    page_number,
                    len(blocks),
                )
                return blocks
            except Exception as e:
                logger.warning("NotesExtractor: Lỗi đọc cache trang %d: %s. Chạy bóc tách mới.", page_number, e)

        # 2. Quyết định chế độ bóc tách 100% Offline (0 API tokens)
        blocks: list[ParsedBlock] = []

        # Hướng A (MinerU Layout + VietOCR Text Recognition):
        # Dùng MinerU bóc tách cấu trúc bảng Markdown + VietOCR đọc text tiếng Việt có dấu
        if self.engine in ("auto", "mineru", "mineru_vietocr"):
            if self._is_mineru_available():
                logger.info("NotesExtractor: Chạy MinerU + VietOCR (Hướng A, 0 tokens) cho trang %d...", page_number)
                blocks = self._extract_with_mineru_and_vietocr(page, page_number, company, year)

        # Chế độ VietOCR Local Offline + DBNet (100% offline, 0 tokens)
        if not blocks and self.viet_predictor is not None:
            logger.info("NotesExtractor: Chạy VietOCR (Offline, 0 tokens) cho trang %d...", page_number)
            blocks = self._extract_with_vietocr(page, page_number, company, year)

        # Fallback sang RapidOCR nếu VietOCR chưa sẵn sàng (100% offline, 0 tokens)
        if not blocks and self._rapid_ocr is not None:
            logger.info("NotesExtractor: Chạy RapidOCR ONNX fallback (Offline, 0 tokens) cho trang %d...", page_number)
            blocks = self._extract_with_rapidocr(page, page_number, company, year)

        # Thanh lọc & nâng cấp blocks trước khi lưu cache
        blocks = _sanitize_and_polish_blocks(blocks, year=year)

        # Lưu Cache
        if blocks:
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump([b.model_dump() for b in blocks], f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning("NotesExtractor: Không thể ghi cache trang %d: %s", page_number, e)

        logger.info(
            "NotesExtractor: Trang %d hoàn tất bóc tách %d blocks có cấu trúc (RAG ready).",
            page_number,
            len(blocks),
        )
        return blocks

    def _find_mineru_binary(self) -> str | None:
        """Tìm đường dẫn thực thi của MinerU/magic-pdf CLI binary (hỗ trợ tương thích ngược)."""
        import shutil
        import sys

        for name in ("magic-pdf.exe", "magic-pdf"):
            script_path = Path(sys.prefix) / "Scripts" / name
            if script_path.exists():
                return str(script_path)
            bin_path = Path(sys.prefix) / "bin" / name
            if bin_path.exists():
                return str(bin_path)
            found = shutil.which(name)
            if found:
                return found

        return None

    def _is_mineru_available(self) -> bool:
        """Kiểm tra MinerU có sẵn trên hệ thống không (Python package hoặc CLI binary)."""
        return is_mineru_available() or (self._find_mineru_binary() is not None)


    def _extract_with_mineru_and_vietocr(
        self,
        page: pdfplumber.page.Page,
        page_number: int,
        company: str,
        year: int,
    ) -> list[ParsedBlock]:
        """
        Hướng A: Bóc tách Layout bằng MinerU (giữ cấu trúc bảng Markdown) +
        Nhận diện văn bản bằng VietOCR (chuẩn 100% dấu tiếng Việt).
        100% Offline, 0 Token API tiêu hao.
        """
        if not self._is_mineru_available():
            return []

        predictor = self.viet_predictor
        if predictor is None:
            return []

        pdf_path = getattr(getattr(page, "pdf", None), "stream", None)
        pdf_file_path = getattr(pdf_path, "name", None)

        if pdf_file_path and Path(pdf_file_path).exists():
            return extract_page_with_mineru_vietocr(
                pdf_path=pdf_file_path,
                page_number=page_number,
                predictor=predictor,
                company=company,
                year=year,
            )


        # Fallback nếu stream không trỏ trực tiếp đến file trên đĩa
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_pdf = Path(tmp_dir) / f"temp_page_{page_number}.pdf"
            try:
                import fitz

                if pdf_file_path and Path(pdf_file_path).exists():
                    src_doc = fitz.open(pdf_file_path)
                    new_doc = fitz.open()
                    new_doc.insert_pdf(src_doc, from_page=page_number - 1, to_page=page_number - 1)
                    new_doc.save(str(tmp_pdf))
                    new_doc.close()
                    src_doc.close()
                else:
                    return []
                return extract_page_with_mineru_vietocr(
                    pdf_path=tmp_pdf,
                    page_number=1,
                    predictor=predictor,
                    company=company,
                    year=year,
                )
            except Exception as e:
                logger.warning("Lỗi trích xuất trang tạm bằng PyMuPDF cho MinerU: %s", e)
                return []


    @staticmethod
    def _detect_and_rotate_if_landscape(
        pil_image: Any,
        ocr_results: list[Any],
        rapid_ocr: Any,
        page_number: int,
    ) -> tuple[Any, list[Any], bool]:
        """
        Tự động phát hiện trang bảng in ngang (A4 Landscape) bị scan theo chiều dọc.
        Dựa trên phân bố Aspect Ratio của Bounding Boxes:
        - Trang xuôi: các box dải ngang có width >= 1.5 * height.
        - Trang bị quay 90°: các box dải dọc có height >= 1.5 * width.
        Nếu số box dọc áp đảo (v_boxes > 15 và v_boxes > 2 * h_boxes),
        tự động xoay 90° Clockwise (rotate 270° expand trong PIL) và quét lại OCR.
        """
        if not ocr_results or rapid_ocr is None:
            return pil_image, ocr_results, False

        h_boxes = 0
        v_boxes = 0
        for r in ocr_results:
            box = r[0]
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            bw = max(xs) - min(xs)
            bh = max(ys) - min(ys)
            if bh > 0:
                if bw >= 1.5 * bh:
                    h_boxes += 1
                elif bh >= 1.5 * bw:
                    v_boxes += 1

        if v_boxes > 15 and v_boxes > h_boxes * 2:
            logger.info(
                "NotesExtractor: Phát hiện trang %d có cấu trúc bảng in ngang scan dọc (V=%d, H=%d). Tự động xoay 90°...",
                page_number, v_boxes, h_boxes
            )
            try:
                rot_img = pil_image.rotate(270, expand=True) # 90° Clockwise
                rot_arr = np.array(rot_img)
                rot_results, _ = rapid_ocr(rot_arr)
                if rot_results:
                    return rot_img, rot_results, True
            except Exception as e:
                logger.warning("NotesExtractor: Lỗi quét lại ảnh xoay trang %d: %s", page_number, e)

        return pil_image, ocr_results, False

    def _extract_with_vietocr(
        self,
        page: pdfplumber.page.Page,
        page_number: int,
        company: str,
        year: int,
    ) -> list[ParsedBlock]:
        """Bóc tách văn bản tiếng Việt 100% chuẩn có dấu bằng VietOCR + PaddleOCR DBNet (100% Offline, 0 tokens)."""
        try:
            pil_image = page.to_image(resolution=self.resolution).original
            img_arr = np.array(pil_image)
        except Exception as e:
            logger.error("NotesExtractor: Lỗi render ảnh trang %d: %s", page_number, e)
            return []

        if self._rapid_ocr is None:
            logger.warning("NotesExtractor: RapidOCR không khả dụng để detect bounding boxes.")
            return []

        try:
            ocr_results, _ = self._rapid_ocr(img_arr)
        except Exception as e:
            logger.error("NotesExtractor: Lỗi RapidOCR detection trang %d: %s", page_number, e)
            return []

        if not ocr_results:
            return []

        # Tự động phát hiện và xoay trang in ngang (Landscape) nếu bị scan dọc
        pil_image, ocr_results, is_rotated_landscape = self._detect_and_rotate_if_landscape(
            pil_image=pil_image,
            ocr_results=ocr_results,
            rapid_ocr=self._rapid_ocr,
            page_number=page_number,
        )

        predictor = self.viet_predictor
        if predictor is None:
            return []

        w, h = pil_image.size
        watermark_keywords = ["0300588569", "fiingroup", "dịch vụ thông tin", "thông tin tài chính"]
        viet_items: list[Any] = []

        # Phân loại: số/tiền tệ ưu tiên RapidOCR (chuẩn dấu chấm, ngoặc âm), văn bản gom vào batch cho VietOCR
        batch_crops: list[Image.Image] = []
        batch_indices: list[int] = []
        candidate_items: list[dict[str, Any]] = []

        for item in ocr_results:
            box = item[0]
            # Tính toán bounding box có padding 2px
            x_min = max(0, int(min(pt[0] for pt in box)) - 2)
            y_min = max(0, int(min(pt[1] for pt in box)) - 2)
            x_max = min(w, int(max(pt[0] for pt in box)) + 2)
            y_max = min(h, int(max(pt[1] for pt in box)) + 2)

            box_w = x_max - x_min
            box_h = y_max - y_min
            if box_w < 8 or box_h < 8:
                continue

            rapid_text = str(item[1]).strip()
            cand_idx = len(candidate_items)
            is_numeric = bool(
                re.search(r"\d{1,3}(?:\.\d{3})+|\(\d+", rapid_text)
                or rapid_text in ("-", "--", "( - )", "VND", "USD")
            )
            candidate_items.append({
                "box": box,
                "rapid_text": rapid_text,
                "text": rapid_text if is_numeric else None,
            })

            if not is_numeric:
                crop = pil_image.crop((x_min, y_min, x_max, y_max))
                batch_crops.append(crop)
                batch_indices.append(cand_idx)

        # Chạy VietOCR batch inference song song trên GPU/CPU (tăng tốc gấp 3-5 lần)
        if batch_crops and predictor is not None:
            BATCH_SIZE = 16
            pred_results: list[str] = []
            use_batch = hasattr(predictor, "predict_batch") and callable(getattr(predictor, "predict_batch", None))
            if use_batch:
                try:
                    for b_start in range(0, len(batch_crops), BATCH_SIZE):
                        b_sub = batch_crops[b_start : b_start + BATCH_SIZE]
                        b_preds = predictor.predict_batch(b_sub)
                        if isinstance(b_preds, (list, tuple)):
                            pred_results.extend([str(p).strip() for p in b_preds])
                        else:
                            raise TypeError("predict_batch không trả về list/tuple")
                except Exception as e:
                    logger.debug("VietOCR predict_batch fallback sang predict đơn dòng: %s", e)
                    pred_results = []
                    for c in batch_crops:
                        try:
                            pred_results.append(str(predictor.predict(c)).strip())
                        except Exception:
                            pred_results.append("")
            else:
                for c in batch_crops:
                    try:
                        pred_results.append(str(predictor.predict(c)).strip())
                    except Exception:
                        pred_results.append("")

            for cand_idx, pred_text in zip(batch_indices, pred_results):
                rapid_t = candidate_items[cand_idx]["rapid_text"]
                candidate_items[cand_idx]["text"] = pred_text or rapid_t

        for cand in candidate_items:
            text = cand.get("text") or cand.get("rapid_text") or ""
            if not text:
                continue

            text = clean_accounting_text(text)

            text_lower = text.lower()
            if any(kw in text_lower for kw in watermark_keywords):
                continue
            # Lọc các dòng bị lộn ngược do watermark chìm chéo
            if "uen pe" in text_lower or "pe!a" in text_lower:
                continue

            viet_items.append([cand["box"], text, 0.95])

        blocks = self._reconstruct_blocks_from_ocr_items(
            ocr_items=viet_items,
            page_number=page_number,
            company=company,
            year=year,
            engine_name=f"vietocr_{self.model_name}",
        )
        if is_rotated_landscape:
            for b in blocks:
                b.metadata["is_landscape"] = True
                b.metadata["rotation"] = 90
        return blocks

    def _extract_with_rapidocr(
        self,
        page: pdfplumber.page.Page,
        page_number: int,
        company: str,
        year: int,
    ) -> list[ParsedBlock]:
        """Bóc tách thô bằng RapidOCR (Fallback khi không có mạng/key)."""
        try:
            pil_image = page.to_image(resolution=self.resolution).original
            img_arr = np.array(pil_image)
            ocr_results, _ = self._rapid_ocr(img_arr)
        except Exception as e:
            logger.error("NotesExtractor: Lỗi RapidOCR trang %d: %s", page_number, e)
            return []

        if not ocr_results:
            return []

        blocks = self._reconstruct_blocks_from_ocr_items(
            ocr_items=ocr_results,
            page_number=page_number,
            company=company,
            year=year,
            engine_name="rapidocr_onnx",
        )
        return blocks

    def _reconstruct_blocks_from_ocr_items(
        self,
        ocr_items: list[Any],
        page_number: int,
        company: str,
        year: int,
        engine_name: str,
    ) -> list[ParsedBlock]:
        """
        Tái cấu trúc không gian 2D từ bounding boxes của OCR (100% Offline, 0 tokens):
          1. Module 1: Tiền xử lý & khử nhiễu ký hiệu kế toán (ngoặc âm, dấu cách trong số).
          2. Module 2: Gom hàng & Hàn số bị xé ngang (Number Stitcher).
          3. Phân đoạn Table vs Text.
          4. Module 3: Bắt trục căn phải (Right-Aligned Column Projection) cho các cột số kế toán.
          5. Module 4: Hợp nhất tiêu đề (Header Synthesis) & gom dòng mồ côi (Multi-line Row Grouping).
          6. Chuẩn hóa từ điển kế toán Thông tư 200 (Accounting Lexicon Normalizer).
        """
        if not ocr_items:
            return []

        num_pat = r"\(?[\d]{1,3}(?:\.[\d]{3})+\)?"
        items: list[dict[str, Any]] = []

        for r in ocr_items:
            box = r[0]
            raw_text = str(r[1]).strip()
            if not raw_text:
                continue

            # Khử nhiễu ký hiệu kế toán
            raw_text = re.sub(r"^\)+", "", raw_text)
            raw_text = re.sub(r"\)+(\(?[\d\.]+\)?)", r"\1", raw_text)
            # Sửa lỗi OCR thay dấu chấm bằng dấu cách trong cụm số (ví dụ: "9.262.413 822.949" -> "9.262.413.822.949")
            raw_text = re.sub(r"(?<=\d)\s+(?=\d{3}(?:\.|\b))", ".", raw_text)

            y_min = min(pt[1] for pt in box)
            y_max = max(pt[1] for pt in box)
            x_min = min(pt[0] for pt in box)
            x_max = max(pt[0] for pt in box)
            y_center = (y_min + y_max) / 2.0

            # Nếu có nhiều số lớn bị dính liền trong cùng 1 box OCR (ví dụ '20.899.554.450.000 23.225.734.296')
            nums = re.findall(num_pat, raw_text)
            if len(nums) >= 2 and len(raw_text) > 20:
                w = (x_max - x_min) / len(nums)
                for i, n in enumerate(nums):
                    sub_x0 = x_min + i * w
                    sub_x1 = sub_x0 + w
                    items.append({
                        "text": n,
                        "y_min": y_min,
                        "y_max": y_max,
                        "y_center": y_center,
                        "x_min": sub_x0,
                        "x_max": sub_x1,
                        "x_center": (sub_x0 + sub_x1) / 2.0,
                    })
            else:
                items.append({
                    "text": raw_text,
                    "y_min": y_min,
                    "y_max": y_max,
                    "y_center": y_center,
                    "x_min": x_min,
                    "x_max": x_max,
                    "x_center": (x_min + x_max) / 2.0,
                })

        if not items:
            return []

        items.sort(key=lambda it: it["y_center"])

        # Gom hàng theo y_center (ngưỡng 14px ở 150 DPI)
        rows: list[list[dict[str, Any]]] = []
        cur_row: list[dict[str, Any]] = []
        cur_y: float | None = None

        for it in items:
            if cur_y is None or abs(it["y_center"] - cur_y) <= 14.0:
                cur_row.append(it)
                cur_y = sum(x["y_center"] for x in cur_row) / len(cur_row)
            else:
                rows.append(cur_row)
                cur_row = [it]
                cur_y = it["y_center"]
        if cur_row:
            rows.append(cur_row)

        for r in rows:
            r.sort(key=lambda it: it["x_min"])

        # Module 2: Hàn số bị xé ngang (Number Stitcher) trong từng hàng
        for r in rows:
            i = 0
            while i < len(r) - 1:
                item_a = r[i]
                item_b = r[i + 1]
                text_a = item_a["text"].strip()
                text_b = item_b["text"].strip()
                gap = item_b["x_min"] - item_a["x_max"]

                # Kiểm tra 2 mảnh của cùng 1 con số bị xé (ví dụ: '23.225' và '734.296', hoặc '20.' và '899.554.450.000')
                is_num_a = bool(re.match(r"^\(?\d{1,3}(?:\.\d{3})*\.?$", text_a))
                is_num_b = bool(re.match(r"^\d{3}(?:\.\d{3})*\)?$", text_b))

                if is_num_a and is_num_b and gap < 35.0:
                    sep = "" if text_a.endswith(".") else "."
                    merged_text = text_a + sep + text_b
                    item_a["text"] = merged_text
                    item_a["x_max"] = item_b["x_max"]
                    item_a["x_center"] = (item_a["x_min"] + item_a["x_max"]) / 2.0
                    item_a["y_min"] = min(item_a["y_min"], item_b["y_min"])
                    item_a["y_max"] = max(item_a["y_max"], item_b["y_max"])
                    item_a["y_center"] = (item_a["y_min"] + item_a["y_max"]) / 2.0
                    r.pop(i + 1)
                else:
                    i += 1

        def is_tbl_row(r: list[dict[str, Any]]) -> bool:
            row_full_text = " ".join(c["text"].strip() for c in r).strip()
            # 0. Loại trừ các dòng chú thích tường thuật (Footnotes/Narrative Notes)
            if re.match(r"^(?:\(\d+\)|\(\*\)|\*|Ghi chú:|Note:|Trong đó:|Chi tiết:)\s+", row_full_text, re.IGNORECASE):
                return False
            # Nếu dòng quá dài (> 55 ký tự) không chứa cụm số kế toán lớn (hàng triệu trở lên)
            has_major_number = any(re.search(r"\b\d{1,3}(?:\.\d{3}){2,}\b", c["text"]) for c in r)
            if len(row_full_text) > 55 and not has_major_number:
                return False

            # 1. Hàng chứa số tài chính lớn hoặc ngoặc âm kế toán
            has_financial_num = any(
                re.search(r"\d{1,3}(?:\.\d{3})+", c["text"])
                or re.search(r"\(\d+", c["text"])
                or c["text"] in ("-", "--", "( - )", "—")
                for c in r
            )
            if has_financial_num:
                return True
            # 2. Hàng chứa đơn vị tiền tệ hoặc tỷ lệ %
            has_currency = any(c["text"] in ("VND", "USD", "%") for c in r)
            if has_currency and len(r) >= 2:
                return True
            # 3. Dòng tiêu đề cột điển hình (chứa năm hoặc ngày kết thúc kỳ kế toán)
            has_date_header = any(
                re.search(r"(?:31/12|1/1|\b20\d\d\b|Cuối năm|Đầu năm|Kỳ này|Kỳ trước)", c["text"], re.IGNORECASE)
                for c in r
            )
            if has_date_header and len(r) >= 2:
                return True
            # 4. Dòng có ít nhất 3 ô với khoảng cách ngang nhưng PHẢI có ít nhất 1 số hoặc đơn vị tiền tệ
            has_any_num = any(re.search(r"\d", c["text"]) for c in r)
            if len(r) >= 3 and (has_any_num or has_currency):
                return True
            return False

        # Phân đoạn segments: Gom các hàng liên tiếp cùng loại
        raw_segments: list[tuple[str, list[list[dict[str, Any]]]]] = []
        cur_type: str | None = None
        cur_seg: list[list[dict[str, Any]]] = []

        for r in rows:
            t_type = "table" if is_tbl_row(r) else "text"
            if cur_type is None:
                cur_type = t_type
                cur_seg = [r]
            elif t_type == cur_type:
                cur_seg.append(r)
            else:
                raw_segments.append((cur_type, cur_seg))
                cur_type = t_type
                cur_seg = [r]
        if cur_seg and cur_type is not None:
            raw_segments.append((cur_type, cur_seg))

        # Chuẩn hóa segments: table segment phải có ít nhất 2 hàng
        segments: list[tuple[str, list[list[dict[str, Any]]]]] = []
        for stype, srows in raw_segments:
            if stype == "table" and len(srows) < 2:
                segments.append(("text", srows))
            else:
                segments.append((stype, srows))

        blocks: list[ParsedBlock] = []
        tbl_count = 0
        txt_count = 0

        for stype, srows in segments:
            if stype == "table":
                # Module 1: Bắt trục căn phải (Right-Aligned Column Projection)
                numeric_items: list[dict[str, Any]] = []
                for r in srows:
                    for c in r:
                        c_text = c["text"].strip()
                        if (
                            re.search(r"\d{1,3}(?:\.\d{3})+", c_text)
                            or re.search(r"\(\d+", c_text)
                            or c_text in ("-", "--", "( - )", "—")
                        ):
                            numeric_items.append(c)

                if numeric_items:
                    min_num_x = min(c["x_min"] for c in numeric_items)
                    label_threshold = min_num_x - 15.0

                    # Gom cụm theo x_max (mép phải)
                    num_x_maxs = sorted(c["x_max"] for c in numeric_items)
                    clustered_col_rights: list[float] = []
                    cur_c: list[float] = []
                    for x in num_x_maxs:
                        if not cur_c or abs(x - (sum(cur_c) / len(cur_c))) <= 35.0:
                            cur_c.append(x)
                        else:
                            clustered_col_rights.append(sum(cur_c) / len(cur_c))
                            cur_c = [x]
                    if cur_c:
                        clustered_col_rights.append(sum(cur_c) / len(cur_c))
                else:
                    label_threshold = 400.0
                    clustered_col_rights = []

                # BẢO VỆ ANTI-PSEUDO-TABLE:
                # Nếu không có cột số liệu thực sự hoặc ít hơn 2 số tài chính -> chuyển thành văn bản thuần
                if not clustered_col_rights or len(numeric_items) < 2:
                    txt_count += 1
                    para_lines = []
                    for r in srows:
                        para_lines.append(" ".join(clean_accounting_text(c["text"]) for c in r))
                    full_text = clean_accounting_text("\n".join(para_lines).strip())
                    if full_text and len(full_text) >= 10:
                        block = ParsedBlock(
                            block_id=f"p{page_number}_txt_{txt_count}",
                            block_type="text",
                            page=page_number,
                            content=full_text,
                            source="local_ocr",
                            target=[StorageTarget.VECTOR],
                            metadata={
                                "company": company,
                                "year": year,
                                "ocr_engine": engine_name,
                                "is_note": True,
                            },
                        )
                        blocks.append(block)
                    continue

                tbl_count += 1
                total_cols = 1 + max(len(clustered_col_rights), 1)

                # Tách header rows vs data rows trong bảng, đồng thời gom trailing footnotes
                header_rows: list[list[dict[str, Any]]] = []
                data_rows: list[list[dict[str, Any]]] = []
                trailing_notes: list[str] = []

                for r in srows:
                    row_txt = " ".join(c["text"].strip() for c in r).strip()
                    # Nhận diện dòng footnote ở đuôi bảng
                    is_footnote = bool(re.match(r"^(?:\(\d+\)|\(\*\)|\*|Ghi chú:|Note:)\s+", row_txt, re.IGNORECASE))
                    if is_footnote and data_rows:
                        trailing_notes.append(row_txt)
                        continue

                    has_large_num = any(
                        re.search(r"\d{1,3}(?:\.\d{3}){2,}", c["text"])
                        or re.search(r"\(\d{1,3}(?:\.\d{3})+\)", c["text"])
                        for c in r
                    )
                    if not has_large_num and not data_rows:
                        header_rows.append(r)
                    else:
                        data_rows.append(r)

                if not data_rows:
                    data_rows = header_rows
                    header_rows = []

                # Module 3 & 4: Tổng hợp tiêu đề cột + làm sạch từ điển kế toán
                headers = ["Khoản mục / Chỉ tiêu"] + [""] * (total_cols - 1)
                for hr in header_rows:
                    for it in hr:
                        if it["x_max"] < min_num_x - 20.0 or not clustered_col_rights:
                            pass
                        else:
                            best_col = min(
                                range(len(clustered_col_rights)),
                                key=lambda i: min(
                                    abs(it["x_max"] - clustered_col_rights[i]),
                                    abs(it["x_center"] - (clustered_col_rights[i] - 40.0)),
                                ),
                            )
                            idx = 1 + best_col
                            if idx < total_cols:
                                clean_it_txt = clean_accounting_text(it["text"])
                                if len(clean_it_txt) < 45 and not re.match(r"^(?:Vào ngày|Ngày \d|Theo đó)", clean_it_txt, re.IGNORECASE):
                                    headers[idx] = (headers[idx] + " " + clean_it_txt).strip()

                for i in range(1, total_cols):
                    if not headers[i]:
                        headers[i] = f"Cột {i}"
                    else:
                        headers[i] = clean_accounting_text(headers[i])
                        headers[i] = re.sub(r"\b(VND)\s+\1\b", r"\1", headers[i], flags=re.IGNORECASE)

                # Gán dữ liệu vào ma trận
                raw_matrix: list[list[str]] = []
                for r in data_rows:
                    row_cells = [""] * total_cols
                    label_parts: list[str] = []
                    for it in r:
                        it_text = it["text"].strip()
                        has_large_num = bool(
                            re.search(r"\d{1,3}(?:\.\d{3})+", it_text)
                            or re.search(r"\(\d{1,3}(?:\.\d{3})+\)", it_text)
                            or it_text in ("-", "--", "( - )", "—")
                        )
                        # Nếu không chứa số tài chính lớn HOẶC bắt đầu từ lề trái -> Khoản mục (Cột 0)
                        if not has_large_num or it["x_min"] < min_num_x - 10.0 or not clustered_col_rights:
                            label_parts.append(clean_accounting_text(it_text))
                        else:
                            best_col = min(
                                range(len(clustered_col_rights)),
                                key=lambda i: abs(it["x_max"] - clustered_col_rights[i]),
                            )
                            idx = 1 + best_col
                            if idx < total_cols:
                                cell_val = it_text
                                cell_val = re.sub(r"^\)+", "", cell_val)
                                if row_cells[idx]:
                                    row_cells[idx] += " " + cell_val
                                else:
                                    row_cells[idx] = cell_val
                    row_cells[0] = clean_accounting_text(" ".join(label_parts))
                    raw_matrix.append(row_cells)

                # Module 3: Gom dòng mồ côi (Multi-line Row Grouping)
                matrix: list[list[str]] = []
                for r_cells in raw_matrix:
                    has_numeric_data = any(bool(c.strip()) for c in r_cells[1:])
                    label_text = r_cells[0].strip()

                    # Nếu là dòng mồ côi (chỉ có chữ ở khoản mục, không có số)
                    if not has_numeric_data and label_text:
                        is_section_header = bool(re.match(r"^(?:[I|V|X]+|\d+)\.\s+", label_text))
                        if is_section_header:
                            matrix.append(r_cells)
                        elif matrix and any(bool(c.strip()) for c in matrix[-1][1:]):
                            matrix[-1][0] = (matrix[-1][0] + " " + label_text).strip()
                        elif matrix:
                            matrix[-1][0] = (matrix[-1][0] + " " + label_text).strip()
                        else:
                            matrix.append(r_cells)
                    else:
                        if matrix and not any(bool(c.strip()) for c in matrix[-1][1:]):
                            prev_label = matrix[-1][0].strip()
                            if not re.match(r"^(?:[I|V|X]+|\d+)\.\s+", prev_label):
                                r_cells[0] = (prev_label + " " + r_cells[0]).strip()
                                matrix.pop()
                        matrix.append(r_cells)

                lines = [
                    "| " + " | ".join(headers) + " |",
                    "| " + " | ".join(["---"] * total_cols) + " |",
                ]
                for r_cells in matrix:
                    lines.append("| " + " | ".join(r_cells) + " |")

                markdown_tbl = "\n".join(lines)
                if trailing_notes:
                    markdown_tbl += "\n\n" + "\n".join(f"*{clean_accounting_text(n)}*" for n in trailing_notes)

                page_unit = detect_currency_unit(markdown_tbl)
                num_density = compute_numeric_density(matrix)

                block = ParsedBlock(
                    block_id=f"p{page_number}_tbl_{tbl_count}",
                    block_type="table",
                    page=page_number,
                    content=markdown_tbl,
                    source="local_ocr",
                    target=[StorageTarget.SQL, StorageTarget.VECTOR],
                    metadata={
                        "company": company,
                        "year": year,
                        "ocr_engine": engine_name,
                        "is_note": True,
                        "num_rows": len(matrix),
                        "num_cols": total_cols,
                        "headers": headers,
                        "unit": page_unit,
                        "numeric_density": round(num_density, 2),
                    },
                )
                blocks.append(block)

            else:
                txt_count += 1
                para_lines = []
                for r in srows:
                    para_lines.append(" ".join(clean_accounting_text(c["text"]) for c in r))
                full_text = clean_accounting_text("\n".join(para_lines).strip())
                if full_text and len(full_text) >= 10:
                    block = ParsedBlock(
                        block_id=f"p{page_number}_txt_{txt_count}",
                        block_type="text",
                        page=page_number,
                        content=full_text,
                        source="local_ocr",
                        target=[StorageTarget.VECTOR],
                        metadata={
                            "company": company,
                            "year": year,
                            "ocr_engine": engine_name,
                            "is_note": True,
                        },
                    )
                    blocks.append(block)

        return _sanitize_and_polish_blocks(blocks, year=year)


    @staticmethod
    def _release_memory() -> None:
        """Giải phóng triệt để bộ nhớ đệm RAM và VRAM GPU sau mỗi trang để chống phình RAM."""
        import gc
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        gc.collect()

    def process_pages(
        self,
        pdf: pdfplumber.PDF,
        page_numbers: list[int],
        company: str = "DOANH_NGHIEP",
        year: int = 2024,
    ) -> list[ParsedBlock]:
        """Xử lý danh sách các trang Thuyết minh tuần tự với nhịp độ pacing an toàn và dọn dẹp RAM liên tục."""
        all_blocks: list[ParsedBlock] = []
        for p_num in page_numbers:
            if 1 <= p_num <= len(pdf.pages):
                page = pdf.pages[p_num - 1]
                blocks = self.process_scanned_page(
                    page=page,
                    page_number=p_num,
                    company=company,
                    year=year,
                )
                all_blocks.extend(blocks)
                # Dọn dẹp RAM và VRAM sau mỗi trang
                self._release_memory()
        return all_blocks

    @staticmethod
    def _group_lines_into_paragraphs(ocr_items: list[Any], line_gap_threshold: float = 30.0) -> list[str]:
        """Nhóm các bounding box thành các đoạn văn mạch lạc."""
        extracted: list[tuple[float, float, float, str]] = []
        for item in ocr_items:
            box = item[0]
            text = str(item[1]).strip()
            if not text:
                continue
            y_top = min(p[1] for p in box)
            y_bottom = max(p[1] for p in box)
            x_left = min(p[0] for p in box)
            extracted.append((y_top, x_left, y_bottom, text))

        extracted.sort(key=lambda item: (item[0], item[1]))

        paragraphs: list[str] = []
        current_para_lines: list[str] = []
        last_y_bottom: float | None = None

        for y_top, _x_left, y_bottom, text in extracted:
            if last_y_bottom is None:
                current_para_lines.append(text)
                last_y_bottom = y_bottom
                continue

            gap = y_top - last_y_bottom
            if gap > line_gap_threshold:
                paragraphs.append(" ".join(current_para_lines))
                current_para_lines = [text]
            else:
                current_para_lines.append(text)

            last_y_bottom = max(last_y_bottom, y_bottom)

        if current_para_lines:
            paragraphs.append(" ".join(current_para_lines))

        return paragraphs
