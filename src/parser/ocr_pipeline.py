"""
ocr_pipeline.py — Pipeline xử lý chuyên sâu cho các trang PDF Scan (ảnh chụp) bằng Free Vision API.
Thay thế các thư viện OCR offline nặng nề (PaddleOCR/VietOCR/RapidOCR) bằng Vision Multimodal LLM:
  1. Render trang scan thành hình ảnh (PIL / pypdfium2)
  2. Gửi ảnh đến Free Vision API (Google Gemini 2.0 Flash hoặc Groq Vision)
  3. Bóc tách phản hồi thành các Markdown Table và Text Paragraphs
  4. Hậu xử lý số liệu (clean_ocr_number) và kiểm định tính hợp lệ (validate_ocr_table)
Đầu ra: list[ParsedBlock] với source="ocr"
"""

import base64
import io
import json
import logging
import random
import re
import time
from pathlib import Path

import cv2
import numpy as np
import pdfplumber

from src.config import Settings, get_settings
from src.models import ParsedBlock
from src.parser.ocr_postprocess import (
    clean_ocr_number,
    clean_ocr_text_line,
    validate_ocr_table,
)
from src.parser.table_utils import (
    compute_numeric_density,
    detect_currency_unit,
    format_table_to_markdown,
)

logger = logging.getLogger(__name__)

VISION_OCR_SYSTEM_PROMPT = """Bạn là chuyên gia trích xuất tài liệu Báo cáo tài chính (BCTC) Việt Nam.
Nhiệm vụ của bạn là bóc tách toàn bộ nội dung từ hình ảnh của DUY NHẤT trang scan BCTC này với độ chính xác tuyệt đối:
1. BẢNG BIỂU TÀI CHÍNH:
   - Trích xuất toàn bộ bảng dưới định dạng Markdown Table chuẩn (| Cột 1 | Cột 2 | ... |).
   - QUAN TRỌNG VỀ DẤU ÂM: BCTC Việt Nam biểu thị số âm trong ngoặc đơn (ví dụ: (801.627.371.011) hoặc (2.295.631.275.842)). BẮT BUỘC giữ nguyên ngoặc đơn hoặc ghi dấu trừ (-), TUYỆT ĐỐI KHÔNG ĐƯỢC BỎ DẤU NGOẶC ĐƠN biến số âm thành số dương, đặc biệt ở các dòng tổng hợp Lưu chuyển tiền thuần (Mã 20, 30, 40, 50).
   - Giữ nguyên vẹn mọi số liệu, dấu chấm, dấu phẩy phân cách. Tuyệt đối không tự làm tròn, không tự sửa số.
   - Giữ nguyên các cột: Chỉ tiêu, Mã số, Thuyết minh, Số cuối năm/kỳ này, Số đầu năm/kỳ trước.
2. ĐOẠN VĂN BẢN (Text):
   - Trích xuất chính xác tiếng Việt có dấu các tiêu đề, báo cáo của Ban Giám đốc, chính sách kế toán, thuyết minh.
3. NGUYÊN TẮC CHỐNG ẢO GIÁC (ZERO HALLUCINATION):
   - CHỈ trích xuất nội dung thực tế có hiển thị trên trang ảnh này.
   - TUYỆT ĐỐI KHÔNG tự bịa số liệu, không tự hoàn thiện bảng nếu bị cắt ở chân trang, không suy đoán.
4. QUY CÁCH ĐẦU RA:
   - Phân tách rõ ràng giữa các bảng và các khối văn bản bằng dòng trống.
   - Chỉ trả về nội dung bóc tách Markdown trực tiếp, KHÔNG thêm lời giải thích mở đầu hay kết thúc."""


def preprocess_scanned_image(image_arr: np.ndarray, use_adaptive_thresh: bool = False) -> np.ndarray:
    """
    Tiền xử lý ảnh trang scan bằng OpenCV (tùy chọn) để làm nét hoặc khử nhiễu:
      - Chuyển ảnh xám (Grayscale)
      - Khử hạt nhiễu bằng Median Blur
      - Nhị phân hóa thích ứng (Adaptive Thresholding) nếu cần
    """
    if len(image_arr.shape) == 3:
        gray = cv2.cvtColor(image_arr, cv2.COLOR_RGB2GRAY)
    else:
        gray = image_arr

    denoised = cv2.medianBlur(gray, 3)

    if use_adaptive_thresh:
        thresh = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2,
        )
        return thresh

    return denoised


class VisionOCRPipeline:
    """Pipeline OCR chuyên dụng cho các trang Scan bằng Free Vision API."""

    _throttled_models: dict[str, float] = {}
    _last_api_call_time: float = 0.0  # Issue #5: Class-level timestamp — shared giữa mọi instances

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def process_pages(
        self,
        pdf: pdfplumber.PDF,
        page_numbers: list[int],
        company: str = "DOANH_NGHIEP",
        year: int = 2024,
    ) -> list[ParsedBlock]:
        """Bóc tách danh sách các trang Scan hoàn chỉnh bằng Vision API theo thứ tự từng trang một."""
        all_blocks: list[ParsedBlock] = []
        for p_num in page_numbers:
            if p_num < 1 or p_num > len(pdf.pages):
                continue

            page = pdf.pages[p_num - 1]
            p_blocks = self.process_scanned_page(
                page=page,
                page_number=p_num,
                company=company,
                year=year,
            )
            all_blocks.extend(p_blocks)
            import gc
            gc.collect()
        return all_blocks

    def process_scanned_page(
        self,
        page: pdfplumber.page.Page,
        page_number: int,
        company: str = "DOANH_NGHIEP",
        year: int = 2024,
    ) -> list[ParsedBlock]:
        """
        Bóc tách 1 trang Scan đơn lẻ:
          1. Kiểm tra Checkpoint Cache trên ổ đĩa (nếu đã bóc tách trước đó thì nạp ngay, 0 API calls).
          2. Render ảnh trang scan (150 DPI).
          3. Áp dụng Rate Limiting Pacing (tối thiểu 4.5s giữa các request để đảm bảo <= 13 RPM, không vượt quota 15 RPM).
          4. Gọi Vision API bóc tách Markdown text & table.
          5. Lưu vào Checkpoint Cache và trả về danh sách ParsedBlock.
        """
        # 1. Kiểm tra Checkpoint Cache trên đĩa
        cache_dir = Path("data/cache/ocr") / f"{company}_{year}"
        cache_file = cache_dir / f"page_{page_number}.json"
        if cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as f:
                    cached_data = json.load(f)
                cached_blocks = [ParsedBlock(**item) for item in cached_data]
                logger.info(
                    "VisionOCRPipeline: Trang scan %d nạp từ Checkpoint Cache (%d blocks, 0 API calls).",
                    page_number,
                    len(cached_blocks),
                )
                return cached_blocks
            except Exception as e:
                logger.warning("VisionOCRPipeline: Lỗi đọc cache trang %d: %s. Sẽ gọi API mới.", page_number, e)

        # 2. Render ảnh trang scan
        try:
            pil_image = page.to_image(resolution=self.settings.ocr_resolution).original
        except Exception as e:
            logger.warning("VisionOCRPipeline: Không thể render ảnh trang scan %d: %s", page_number, e)
            return []

        buffered = io.BytesIO()
        pil_image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # 3. Rate-limited Call: Pacing tối thiểu 4.5s giữa các cuộc gọi API
        # Issue #5: Dùng class-level timestamp — shared giữa mọi VisionOCRPipeline instances
        elapsed = time.time() - VisionOCRPipeline._last_api_call_time
        if elapsed < 4.5:
            wait_time = 4.5 - elapsed
            time.sleep(wait_time)
        VisionOCRPipeline._last_api_call_time = time.time()

        extracted_text = self._call_vision_api(img_b64)
        if not extracted_text:
            logger.warning(
                "VisionOCRPipeline: Trang scan %d không nhận được dữ liệu từ Cloud Vision API (quá tải 503 hoặc cạn quota). "
                "Tự động kích hoạt Graceful Degradation sang Local OCR Engine (Offline, 0 tokens) để bảo toàn dữ liệu bảng...",
                page_number,
            )
            try:
                from src.parser.local_ocr import LocalOCREngine

                local_engine = LocalOCREngine(
                    resolution=self.settings.ocr_resolution,
                    settings=self.settings,
                    use_cache=False,
                )
                fallback_blocks = local_engine.process_scanned_page(
                    page=page,
                    page_number=page_number,
                    company=company,
                    year=year,
                )
                for b in fallback_blocks:
                    b.metadata["is_fallback"] = True
                    b.metadata["fallback_reason"] = "vision_api_503_overloaded"
                if fallback_blocks:
                    logger.info(
                        "VisionOCRPipeline: Trang scan %d đã được cứu nguy thành công qua Local OCR (%d blocks).",
                        page_number,
                        len(fallback_blocks),
                    )
                    return fallback_blocks
            except Exception as loc_err:
                logger.error("VisionOCRPipeline: Lỗi khi chạy fallback Local OCR cho trang %d: %s", page_number, loc_err)
            return []

        # 4. Bóc tách text Markdown thành ParsedBlocks
        blocks = self._parse_markdown_to_blocks(
            markdown_content=extracted_text,
            page_number=page_number,
            company=company,
            year=year,
        )

        # 5. Lưu vào Checkpoint Cache
        if blocks:
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump([b.model_dump() for b in blocks], f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning("VisionOCRPipeline: Không thể lưu cache trang %d: %s", page_number, e)

        logger.info(
            "VisionOCRPipeline: Trang scan %d hoàn tất bóc tách %d blocks qua Vision API (source='ocr').",
            page_number,
            len(blocks),
        )
        return blocks

    def _call_vision_api(self, img_b64: str) -> str:
        """Điều phối gọi Google Gemini hoặc Groq Vision dựa trên cấu hình và API key sẵn có."""
        provider = self.settings.ocr_provider

        if provider == "gemini":
            text = self._call_gemini_vision(img_b64)
            if text:
                return text
            if self.settings.groq_api_key:
                logger.warning("VisionOCRPipeline: Gemini Vision thất bại, tự động fallback sang Groq Vision...")
                return self._call_groq_vision(img_b64)
            return ""

        if provider == "groq":
            text = self._call_groq_vision(img_b64)
            if text:
                return text
            if self.settings.gemini_api_key:
                logger.warning("VisionOCRPipeline: Groq Vision thất bại, tự động fallback sang Gemini Vision...")
                return self._call_gemini_vision(img_b64)
            return ""

        # Mặc định 'auto': Ưu tiên Gemini nếu có key, nếu thất bại tự động fallback Groq
        if self.settings.gemini_api_key:
            text = self._call_gemini_vision(img_b64)
            if text:
                return text

        if self.settings.groq_api_key:
            text = self._call_groq_vision(img_b64)
            if text:
                return text

        if not self.settings.gemini_api_key and not self.settings.groq_api_key:
            logger.warning(
                "VisionOCRPipeline: Chưa tìm thấy GEMINI_API_KEY trong .env. "
                "Để kích hoạt OCR trang scan miễn phí, vui lòng tạo Google Gemini API Key "
                "(hoàn toàn miễn phí 15 RPM tại https://aistudio.google.com) và thêm vào file .env: "
                "GEMINI_API_KEY=AIzaSy..."
            )
        return ""

    def _call_gemini_vision(self, img_b64: str) -> str:
        """Gọi Google Gemini Flash Vision API (Hoàn toàn miễn phí, 15 RPM) với Exponential Backoff + Jitter."""
        api_key = self.settings.gemini_api_key
        if not api_key:
            logger.warning("VisionOCRPipeline: GEMINI_API_KEY chưa được cấu hình.")
            return ""

        primary_model = self.settings.gemini_vision_model or "gemini-flash-lite-latest"
        preferred_order = [
            primary_model,
            "gemini-flash-lite-latest",
            "gemini-2.0-flash",
            "gemini-flash-latest",
            "gemini-3.5-flash-lite",
        ]
        all_candidates = list(dict.fromkeys(preferred_order))

        # Lọc bỏ hoặc đưa xuống cuối các model đang bị throttled (429/503) trong 60 giây qua
        now = time.time()
        active_candidates = [m for m in all_candidates if now >= self._throttled_models.get(m, 0)]
        throttled_candidates = [m for m in all_candidates if now < self._throttled_models.get(m, 0)]
        candidate_models = active_candidates if active_candidates else throttled_candidates

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": VISION_OCR_SYSTEM_PROMPT},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": img_b64,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 4096,
            },
        }

        try:
            import httpx

            with httpx.Client(timeout=60.0) as client:
                for attempt in range(3):
                    for model in candidate_models:
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                        try:
                            res = client.post(url, json=payload)
                        except Exception as req_err:
                            logger.warning("VisionOCRPipeline: Lỗi kết nối với model %s: %s", model, req_err)
                            continue

                        if res.status_code == 404:
                            logger.debug("VisionOCRPipeline: Model '%s' trả về 404, chuyển model kế tiếp...", model)
                            continue

                        if res.status_code in (429, 503):
                            # Đánh dấu model bị rate limit 60 giây
                            VisionOCRPipeline._throttled_models[model] = time.time() + 60.0
                            jitter = random.uniform(0.1, 0.4)
                            # Issue #5: Sửa backoff công thức: 2**attempt tăng dần (Exponential Backoff)
                            # Cũ: 0.5**attempt giảm dần (sai) | Mới: 2**attempt = 1s, 2s, 4s...
                            delay = (2 ** attempt) + jitter
                            logger.warning(
                                "VisionOCRPipeline: Model '%s' phản hồi %d (quá tải/rate limit). "
                                "Tự động cooldown 60s và chuyển ngay sang model kế tiếp...",
                                model,
                                res.status_code,
                            )
                            time.sleep(delay)
                            continue

                        res.raise_for_status()
                        data = res.json()
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        return text.strip()

                    # Nếu tất cả models đều chạm giới hạn trong vòng lặp này, chờ trước khi thử vòng mới
                    wait_sec = 4.0 * (attempt + 1) + random.uniform(1.0, 2.0)
                    logger.warning(
                        "VisionOCRPipeline: Toàn bộ candidate models đều bận/vượt quota, chờ %.1fs trước lần thử %d/3...",
                        wait_sec,
                        attempt + 1,
                    )
                    time.sleep(wait_sec)
        except Exception as e:
            logger.error("VisionOCRPipeline: Lỗi khi gọi Gemini Vision API: %s", e)
            return ""

        return ""

    def _call_groq_vision(self, img_b64: str) -> str:
        """Gọi Groq Vision API (Llama 3.2 Vision miễn phí với GROQ_API_KEY)."""
        api_key = self.settings.groq_api_key
        if not api_key:
            logger.warning("VisionOCRPipeline: GROQ_API_KEY chưa được cấu hình.")
            return ""

        try:
            from groq import Groq

            client = Groq(api_key=api_key)
            model = self.settings.groq_vision_model or "llama-3.2-11b-vision-preview"

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": VISION_OCR_SYSTEM_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                            },
                        ],
                    }
                ],
                temperature=0.0,
                max_tokens=4096,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            err_msg = str(e)
            if "model_decommissioned" in err_msg or "decommissioned" in err_msg:
                logger.error(
                    "VisionOCRPipeline: [QUAN TRỌNG] Groq đã khai tử model Vision 'llama-3.2-11b-vision-preview'. "
                    "Vui lòng chuyển sang dùng Google Gemini Flash API (hoàn toàn miễn phí 15 RPM tại https://aistudio.google.com) "
                    "bằng cách thêm GEMINI_API_KEY vào file .env."
                )
            else:
                logger.error("VisionOCRPipeline: Lỗi khi gọi Groq Vision API: %s", e)
            return ""

    def _parse_markdown_to_blocks(
        self,
        markdown_content: str,
        page_number: int,
        company: str,
        year: int,
    ) -> list[ParsedBlock]:
        """Tách nội dung Markdown từ Vision API thành các khối ParsedBlock (table và text)."""
        blocks: list[ParsedBlock] = []
        block_idx = 1
        page_unit = detect_currency_unit(markdown_content)

        # Tách theo khối bảng vs văn bản
        lines = markdown_content.splitlines()
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # Kiểm tra xem có phải dòng bảng Markdown (| col1 | col2 |)
            if line.startswith("|") and line.endswith("|"):
                table_lines = [line]
                j = i + 1
                while j < len(lines):
                    next_l = lines[j].strip()
                    if next_l.startswith("|") and next_l.endswith("|"):
                        table_lines.append(next_l)
                        j += 1
                    else:
                        break

                # Xử lý bảng Markdown
                raw_rows: list[list[str]] = []
                for tl in table_lines:
                    # Bỏ qua dòng phân cách Markdown |---|---|
                    if re.match(r"^\|[\s\-:|]+\|$", tl):
                        continue
                    cells = [c.strip() for c in tl.split("|")[1:-1]]
                    if cells and any(cells):
                        raw_rows.append(cells)

                if len(raw_rows) >= 2:
                    # Chạy validation layer
                    val_result = validate_ocr_table(raw_rows)

                    # Chuẩn hóa số liệu tài chính trong bảng
                    normalized_rows: list[list[str]] = []
                    for r_idx, row in enumerate(raw_rows):
                        if r_idx == 0:
                            normalized_rows.append(row)
                            continue
                        norm_row = []
                        for c_idx, cell in enumerate(row):
                            if c_idx > 0:
                                parsed_num = clean_ocr_number(cell)
                                if parsed_num is not None:
                                    norm_row.append(
                                        f"{parsed_num:,.0f}" if parsed_num.is_integer() else f"{parsed_num:,.2f}"
                                    )
                                else:
                                    norm_row.append(cell)
                            else:
                                norm_row.append(cell)
                        normalized_rows.append(norm_row)

                    md_table = format_table_to_markdown(normalized_rows)
                    density = compute_numeric_density(normalized_rows)
                    headers = normalized_rows[0] if normalized_rows else []

                    blocks.append(
                        ParsedBlock(
                            block_id=f"p{page_number}_b{block_idx}",
                            block_type="table",
                            page=page_number,
                            content=md_table,
                            source="ocr",
                            metadata={
                                "num_rows": len(normalized_rows),
                                "num_cols": max((len(r) for r in normalized_rows), default=0),
                                "numeric_density": round(density, 3),
                                "headers": headers,
                                "unit": page_unit,
                                "is_scanned": True,
                                "validation": val_result,
                                "company": company,
                                "year": year,
                            },
                        )
                    )
                    block_idx += 1
                    i = j
                    continue

            # Khối văn bản (Text Block)
            text_lines = [clean_ocr_text_line(line)]
            j = i + 1
            while j < len(lines):
                next_l = lines[j].strip()
                if not next_l or (next_l.startswith("|") and next_l.endswith("|")):
                    break
                text_lines.append(clean_ocr_text_line(next_l))
                j += 1

            combined_text = "\n".join(text_lines).strip()
            if combined_text:
                blocks.append(
                    ParsedBlock(
                        block_id=f"p{page_number}_b{block_idx}",
                        block_type="text",
                        page=page_number,
                        content=combined_text,
                        source="ocr",
                        metadata={
                            "unit": page_unit,
                            "is_scanned": True,
                            "company": company,
                            "year": year,
                        },
                    )
                )
                block_idx += 1
            i = j

        return blocks


# Alias để đảm bảo tương thích ngược với các import cũ
OCRPipeline = VisionOCRPipeline
