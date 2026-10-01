"""
vision_zoom_corrector.py — Bộ Tự Sửa Sai Cục Bộ qua Vision-LLM Zoom (Agentic Self-Correction Loop).
Khi AccountingVerifier phát hiện sai lệch số học (is_balanced == False), module này:
  1. Phân tích Deductive Elimination để khoanh vùng các Concept / Fact bị nghi ngờ.
  2. Định vị tọa độ Bounding Box của dòng chứa Fact trên trang PDF (4-strategy waterfall).
  3. Cắt ảnh composite (header + dòng mục tiêu) độ phân giải cao.
  4. Gửi ảnh phóng to đến Vision API (Gemini/Groq) với prompt siêu tập trung để đọc lại số.
  5. Hot-patch Fact và kích hoạt re-verify tự động nhằm đưa BCTC về trạng thái cân đối.
"""

import base64
import io
import json
import logging
import re
from typing import Any, NamedTuple

import pdfplumber
from PIL import Image

from src.config import Settings, get_settings
from src.models import FinancialFact, VerificationReport, VerificationStatus
from src.parser.ocr_postprocess import clean_ocr_number
from src.verifier.accounting_verifier import AccountingVerifier

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

class RowBBox(NamedTuple):
    """Kết quả định vị dòng: tọa độ pdfplumber (points), strategy đã dùng, độ tin cậy."""
    top: float
    bottom: float
    source: str        # "table_extract" | "col_bounded_code" | "fuzzy_label" | "projection_local_ocr"
    confidence: float  # 0.0 – 1.0


class CropQuality(NamedTuple):
    valid: bool
    reason: str        # "ok" | "nearly_blank" | "no_text_pixels" | "no_numeric_content"


# ─────────────────────────────────────────────────────────────────────────────
# CONCEPT_REGEX map — pre-built regex cho từng concept trong 3 bảng BCTC cốt lõi
# Pattern khớp tên dòng BCTC Việt Nam (case-insensitive) HOẶC mã số TT200
# ─────────────────────────────────────────────────────────────────────────────

CONCEPT_REGEX: dict[str, str] = {
    # ── CF (B03-DN) ──────────────────────────────────────────────────────────
    "CF_PROFIT_BEFORE_TAX":  r"l[oợ]i nhu[aậ]n.*tr[uướ]c thu[eế]|\b01\b",
    "CF_DEPRECIATION":       r"kh[aấ]u hao|\b02\b",
    "CF_PROVISIONS":         r"d[uự] ph[oò]ng|\b03\b",
    "CF_FX_LOSS":            r"t[yỷ] gi[aá]|\b04\b",
    "CF_INVEST_PROFIT":      r"l[oợ]i nhu[aậ]n.*[dđ][aầ]u t[uư]|\b05\b",
    "CF_INTEREST_EXPENSE":   r"chi ph[ií] l[aã]i vay|\b06\b",
    "CF_OPERATING_PROFIT":   r"l[oợ]i nhu[aậ]n.*v[oố]n l[uư][uư] [dđ][oộ]ng|\b08\b",
    "CF_RECEIVABLES_CHANGE": r"ph[aả]i thu.*ng[aắ]n h[aạ]n|\b09\b",
    "CF_INVENTORY_CHANGE":   r"h[aà]ng t[oồ]n kho|\b10\b",
    "CF_PAYABLES_CHANGE":    r"ph[aả]i tr[aả]|\b11\b",
    "CF_PREPAID_CHANGE":     r"tr[aả] tr[uướ]c|\b12\b",
    "CF_INTEREST_PAID":      r"l[aã]i.*[dđ][aã] tr[aả]|\b14\b",
    "CF_TAX_PAID":           r"thu[eế].*[dđ][aã] n[oộ]p|\b15\b",
    "CF_OTHER_OPERATING":    r"ho[aạ]t [dđ][oộ]ng kh[aá]c|\b17\b",
    "CF_NET_OPERATING":      r"l[uư]u chuy[eể]n ti[eề]n thu[aầ]n.*kinh doanh|\b20\b",
    "CF_CAPEX":              r"mua s[aắ]m.*t[aà]i s[aả]n|\b21\b",
    "CF_CAPEX_PROCEEDS":     r"thanh l[yý].*t[aà]i s[aả]n|\b22\b",
    "CF_LOAN_GIVEN":         r"cho vay|\b23\b",
    "CF_LOAN_COLLECTED":     r"thu h[oồ]i.*cho vay|\b24\b",
    "CF_INVEST_EQUITY":      r"g[oó]p v[oố]n.*c[oô]ng ty|\b25\b",
    "CF_DIVIDENDS_RECEIVED": r"c[oổ] t[uứ]c.*nh[aậ]n|\b27\b",
    "CF_NET_INVESTING":      r"l[uư]u chuy[eể]n ti[eề]n thu[aầ]n.*[dđ][aầ]u t[uư]|\b30\b",
    "CF_EQUITY_ISSUANCE":    r"ph[aá]t h[aà]nh.*c[oổ] phi[eế]u|\b31\b",
    "CF_CAPITAL_REFUND":     r"ho[aà]n tr[aả].*v[oố]n g[oó]p|\b32\b",
    "CF_BORROWINGS":         r"ti[eề]n vay|\b33\b",
    "CF_REPAYMENTS":         r"tr[aả] n[oợ]|\b34\b",
    "CF_LEASE_REPAYMENTS":   r"thu[eê] t[aà]i ch[iính]nh|\b35\b",
    "CF_DIVIDENDS_PAID":     r"c[oổ] t[uứ]c.*tr[aả]|\b36\b",
    "CF_NET_FINANCING":      r"l[uư]u chuy[eể]n ti[eề]n thu[aầ]n.*t[aà]i ch[iính]nh|\b40\b",
    "CF_NET_CHANGE":         r"l[uư]u chuy[eể]n ti[eề]n thu[aầ]n.*k[yỳ]|\b50\b",
    "CF_BEGINNING_CASH":     r"ti[eề]n.*[dđ][aầ]u k[yỳ]|\b60\b",
    "CF_EXCHANGE_RATE_DIFF": r"t[yỷ] gi[aá].*[dđ][aầ]u k[yỳ]|\b61\b",
    "CF_ENDING_CASH":        r"ti[eề]n.*cu[oố]i k[yỳ]|\b70\b",

    # ── BS (B01-DN) ──────────────────────────────────────────────────────────
    "TOTAL_ASSETS":             r"t[oổ]ng (?:c[oộ]ng )?t[aà]i s[aả]n|\b270\b",
    "TOTAL_RESOURCES":          r"t[oổ]ng (?:c[oộ]ng )?ngu[oồ]n v[oố]n|\b440\b",
    "CURRENT_ASSETS":           r"t[aà]i s[aả]n ng[aắ]n h[aạ]n|(?<![=\+])\b100\b(?![=\+])",
    "CASH_AND_EQUIVALENTS":     r"ti[eề]n.*t[uư][oơ]ng [dđ][uư][oơ]ng|\b110\b",
    "SHORT_TERM_INVESTMENTS":   r"[dđ][aầ]u t[uư].*ng[aắ]n h[aạ]n|\b120\b",
    "SHORT_TERM_RECEIVABLES":   r"ph[aả]i thu.*ng[aắ]n h[aạ]n|\b130\b",
    "INVENTORIES":              r"h[aà]ng t[oồ]n kho|\b140\b",
    "OTHER_CURRENT_ASSETS":     r"t[aà]i s[aả]n ng[aắ]n h[aạ]n kh[aá]c|\b150\b",
    "NON_CURRENT_ASSETS":       r"t[aà]i s[aả]n d[aà]i h[aạ]n|(?<![=\+])\b200\b(?![=\+])",
    "LONG_TERM_RECEIVABLES":    r"ph[aả]i thu d[aà]i h[aạ]n|\b210\b",
    "FIXED_ASSETS":             r"t[aà]i s[aả]n c[oố] [dđ][iị]nh|\b220\b",
    "INVESTMENT_PROPERTIES":    r"b[aấ]t [dđ][oộ]ng s[aả]n [dđ][aầ]u t[uư]|\b230\b",
    "LONG_TERM_ASSETS_IN_PROGRESS": r"x[aâ]y d[uự]ng d[oở] dang|\b240\b",
    "LONG_TERM_INVESTMENTS":    r"[dđ][aầ]u t[uư] d[aà]i h[aạ]n|\b250\b",
    "OTHER_NON_CURRENT_ASSETS": r"t[aà]i s[aả]n d[aà]i h[aạ]n kh[aá]c|\b260\b",
    "CURRENT_LIABILITIES":      r"n[oợ] ng[aắ]n h[aạ]n|\b310\b",
    "NON_CURRENT_LIABILITIES":  r"n[oợ] d[aà]i h[aạ]n|\b330\b",
    "LIABILITIES":              r"n[oợ] ph[aả]i tr[aả]|\b300\b",
    "EQUITY":                   r"v[oố]n ch[uủ] s[oở] h[uữ]u|\b400\b",

    # ── IS (B02-DN) ──────────────────────────────────────────────────────────
    "GROSS_REVENUE":         r"doanh thu b[aá]n h[aà]ng|\b01\b",
    "REVENUE_DEDUCTIONS":    r"gi[aả]m tr[uừ]|\b02\b",
    "NET_REVENUE":           r"doanh thu thu[aầ]n|\b10\b",
    "COGS":                  r"gi[aá] v[oố]n h[aà]ng b[aá]n|\b11\b",
    "GROSS_PROFIT":          r"l[oợ]i nhu[aậ]n g[oộ]p|\b20\b",
    "FINANCIAL_INCOME":      r"doanh thu t[aà]i ch[iính]nh|\b21\b",
    "FINANCIAL_EXPENSES":    r"chi ph[ií] t[aà]i ch[iính]nh|\b22\b",
    "SELLING_EXPENSES":      r"chi ph[ií] b[aá]n h[aà]ng|\b24\b",
    "ADMIN_EXPENSES":        r"qu[aả]n l[yý] doanh nghi[eệ]p|\b25\b",
    "OPERATING_PROFIT":      r"l[oợ]i nhu[aậ]n thu[aầ]n.*kinh doanh|\b30\b",
    "OTHER_INCOME":          r"thu nh[aậ]p kh[aá]c|\b31\b",
    "OTHER_EXPENSES":        r"chi ph[ií] kh[aá]c|\b32\b",
    "OTHER_PROFIT":          r"l[oợ]i nhu[aậ]n kh[aá]c|\b40\b",
    "PROFIT_BEFORE_TAX":     r"l[oợ]i nhu[aậ]n tr[uướ]c thu[eế]|\b50\b",
    "CURRENT_TAX_EXPENSE":   r"hi[eệ]n h[aà]nh|\b51\b",
    "DEFERRED_TAX_EXPENSE":  r"ho[aã]n l[aạ]i|\b52\b",
    "NET_PROFIT":            r"l[oợ]i nhu[aậ]n sau thu[eế]|\b60\b",
}


# ─────────────────────────────────────────────────────────────────────────────
# Vision Prompt V2 — bao gồm tên cột cần đọc
# ─────────────────────────────────────────────────────────────────────────────

ZOOM_SYSTEM_PROMPT_V2 = """Bạn là chuyên gia kiểm toán Báo cáo tài chính (BCTC) Việt Nam.
Ảnh bên dưới gồm 2 phần được ghép dọc:
  (1) DÒNG TIÊU ĐỀ CỘT của bảng (header row)
  (2) DÒNG SỐ LIỆU cần đọc (target row)

Thông tin dòng mục tiêu:
- Tên khoản mục : {raw_label}
- Mã số TT200   : {standard_code}
- CỘT CẦN ĐỌC  : {target_column}

LƯU Ý ĐẶC BIỆT:
1. Dấu ngoặc đơn = số âm: (1.232.840.887.367) → -1232840887367
2. Dấu phân cách nghìn là dấu CHẤM (.) trong BCTC Việt Nam
3. Đọc đúng CỘT "{target_column}", KHÔNG đọc cột kề bên
4. Số bị mờ/lem: 8↔0, 3↔8, 1↔7 — suy luận từ context

Chỉ trả về một đối tượng JSON duy nhất (không giải thích thêm):
{{
  "raw_text": "chuỗi văn bản đọc được từ ô đó",
  "value_current": <float hoặc null>,
  "value_previous": <float hoặc null>,
  "is_negative": <bool>,
  "target_column_read": "{target_column}",
  "confidence": <float 0.0-1.0>
}}"""


# ─────────────────────────────────────────────────────────────────────────────
# StructuredTableCropper — 4-strategy waterfall để định vị & crop dòng mục tiêu
# ─────────────────────────────────────────────────────────────────────────────

class StructuredTableCropper:
    """
    Định vị dòng số liệu trong PDF bằng 4 strategy theo thứ tự ưu tiên:
      Strategy 1: pdfplumber native table extraction (PDF vector, ưu tiên cao nhất)
      Strategy 2: Column-bounded standard code match (tránh match nhầm cột số)
      Strategy 3: Fuzzy label keyword match trong vùng cột nhãn
      Strategy 4: Horizontal Projection Profile + Local OCR (scanned PDF fallback)
    """

    def __init__(self, ocr_engine: Any = None):
        self._ocr_engine = ocr_engine
        self._page_band_labels_cache: dict[int, list[tuple[FinancialFact, tuple[int, int]]]] = {}

    # ── Strategy 1: pdfplumber native table ──────────────────────────────────

    def _strategy_table_extract(
        self,
        page: Any,
        clean_code: str,
    ) -> RowBBox | None:
        """
        Dùng pdfplumber.find_tables() để lấy tọa độ chính xác của row mục tiêu.
        Match theo standard_code trong cột Mã số (thường cột index 1).
        """
        try:
            tables = page.find_tables()
            for table in tables:
                extracted = table.extract()
                if not extracted:
                    continue
                for row_idx, row in enumerate(extracted):
                    if not row:
                        continue
                    # Cột Mã số thường là cột thứ 2 (index 1) trong BCTC Việt Nam
                    # Thử cả cột 0 và 1 để linh hoạt hơn
                    candidate_cells = [row[i] for i in range(min(3, len(row))) if row[i]]
                    for cell in candidate_cells:
                        if re.sub(r"\D", "", str(cell)) == clean_code:
                            try:
                                row_obj = table.rows[row_idx]
                                if row_obj and row_obj.bbox:
                                    return RowBBox(
                                        top=row_obj.bbox[1],
                                        bottom=row_obj.bbox[3],
                                        source="table_extract",
                                        confidence=1.0,
                                    )
                            except (IndexError, AttributeError):
                                pass
        except Exception as e:
            logger.debug("Strategy 1 (table_extract) failed: %s", e)
        return None

    # ── Strategy 2: Column-bounded standard code match ───────────────────────

    def _strategy_column_bounded_code(
        self,
        page: Any,
        clean_code: str,
    ) -> RowBBox | None:
        """
        Tìm mã số chỉ trong vùng X của cột 'Mã số' (30–50% page width).
        Tránh match nhầm vào năm '2025', số tiền trong cột giá trị.

        Layout chuẩn BCTC Mẫu B01/B02/B03-DN:
          Cột Tên khoản mục : x ∈ [0,     ~35%]
          Cột Mã số         : x ∈ [~30%,  ~48%]  ← tìm tại đây
          Cột Thuyết minh   : x ∈ [~45%,  ~55%]
          Cột Năm hiện tại  : x ∈ [~55%,  ~78%]
          Cột Năm trước     : x ∈ [~78%,  100%]
        """
        try:
            code_x0 = page.width * 0.28
            code_x1 = page.width * 0.52
            words = page.extract_words()
            for w in words:
                if not (code_x0 <= w.get("x0", 0) <= code_x1):
                    continue
                if re.sub(r"\D", "", w["text"]) == clean_code:
                    return RowBBox(
                        top=w["top"],
                        bottom=w["bottom"],
                        source="col_bounded_code",
                        confidence=0.90,
                    )
        except Exception as e:
            logger.debug("Strategy 2 (col_bounded_code) failed: %s", e)
        return None

    # ── Strategy 3: Fuzzy label keyword match ────────────────────────────────

    def _strategy_fuzzy_label(
        self,
        page: Any,
        raw_label: str,
    ) -> RowBBox | None:
        """
        Tìm dòng chứa nhiều keyword nhất từ raw_label, chỉ trong vùng cột nhãn (x < 42%).
        """
        try:
            label_col_x1 = page.width * 0.42
            _STOPWORDS = {"báo", "cáo", "tài", "chính", "phần", "mục", "các", "và", "của"}
            keywords = [
                k for k in re.findall(r"\w+", raw_label.lower())
                if len(k) >= 3 and k not in _STOPWORDS
            ]
            if not keywords:
                return None

            words = page.extract_words()
            # Group theo dòng (top ± 4pt)
            lines: dict[int, list[dict]] = {}
            for w in words:
                if w.get("x1", page.width) > label_col_x1:
                    continue
                y_key = int(w["top"] // 4) * 4
                lines.setdefault(y_key, []).append(w)

            best_score, best_bbox = 0.0, None
            n_kw = max(len(keywords), 1)
            for line_words in lines.values():
                line_text = " ".join(w["text"].lower() for w in line_words)
                matched = sum(1 for kw in keywords if kw in line_text)
                score = matched / n_kw
                if score > best_score:
                    best_score = score
                    best_bbox = (
                        min(w["top"] for w in line_words),
                        max(w["bottom"] for w in line_words),
                    )

            if best_bbox and best_score >= 0.5:
                return RowBBox(
                    top=best_bbox[0],
                    bottom=best_bbox[1],
                    source="fuzzy_label",
                    confidence=best_score * 0.75,
                )
        except Exception as e:
            logger.debug("Strategy 3 (fuzzy_label) failed: %s", e)
        return None

    # ── Strategy 4: Projection Profile + Local OCR (scanned PDF) ─────────────

    def _strategy_projection_profile(
        self,
        full_img: Image.Image,
        suspect_facts: list[FinancialFact],
        page_num: int | None = None,
    ) -> list[tuple[FinancialFact, tuple[int, int]]]:
        """
        Dành cho PDF scan (không có native text).

        [4a] Horizontal Projection → TextBand list (tất cả dòng text trên trang).
        [4b] OCR từng band bằng LocalOCREngine (RapidOCR detect + VietOCR read)
             → gán nhãn concept qua CONCEPT_REGEX map.
        [4c] Map suspect_facts (theo rank từ identify_suspect_facts) → band đã gán nhãn.

        Returns:
            [(fact, (top_px, bot_px))] theo thứ tự suspect rank để xử lý tuần tự.
        """
        # Kiểm tra cache theo page_num để tránh OCR lặp lại trên cùng 1 trang
        if page_num is not None and page_num in self._page_band_labels_cache:
            cached_results = self._page_band_labels_cache[page_num]
            mapped: list[tuple[FinancialFact, tuple[int, int]]] = []
            for fact in suspect_facts:
                for c_fact, bbox in cached_results:
                    if c_fact.concept == fact.concept:
                        mapped.append((fact, bbox))
                        break
            if mapped:
                logger.debug("Strategy 4: Sử dụng cache bands trang %d (%d facts).", page_num, len(mapped))
                return mapped

        try:
            import numpy as np
        except ImportError:
            logger.warning("Strategy 4 yêu cầu numpy.")
            return []
        # L là Luminance => Gray Scale
        gray = np.array(full_img.convert("L"))
        img_h, img_w = gray.shape

        # ── [4a] Horizontal Projection ────────────────────────────────────────
        dark_per_row = np.sum(gray < 128, axis=1).astype(float)
        dark_smooth  = np.convolve(dark_per_row, np.ones(3) / 3, mode="same")
        is_text_row  = dark_smooth >= img_w * 0.015  # ≥ 1.5% width là text

        bands: list[tuple[int, int]] = []
        in_band = False
        band_top = 0
        for r, is_text in enumerate(is_text_row):
            if is_text and not in_band:
                in_band, band_top = True, r
            elif not is_text and in_band:
                in_band = False
                if r - band_top >= 4:   # bỏ band nhiễu quá mỏng
                    bands.append((band_top, r))

        if not bands:
            logger.debug("Strategy 4: Không tìm thấy text band nào.")
            return []

        logger.debug("Strategy 4: Phát hiện %d text bands.", len(bands))

        # ── [4b] OCR từng band bằng LocalOCREngine ───────────────────────────
        # Dùng RapidOCR (nhanh, offline) để nhận diện text tiếng Việt và khớp CONCEPT_REGEX
        band_labels: dict[int, str] = {}

        try:
            if self._ocr_engine is None:
                from src.parser.local_ocr import LocalOCREngine
                self._ocr_engine = LocalOCREngine(engine="auto")

            ocr_engine = self._ocr_engine
            rapid_ocr  = ocr_engine._rapid_ocr
            predictor  = ocr_engine.viet_predictor if rapid_ocr is None else None

            if rapid_ocr is None and predictor is None:
                logger.warning("Strategy 4: Cả RapidOCR và VietOCR đều không khả dụng.")
                return []

            import numpy as np2

            for i, (top, bot) in enumerate(bands):
                band_img = full_img.crop((0, max(0, top - 2), img_w, min(img_h, bot + 2)))
                band_arr = np2.array(band_img)

                ocr_text_parts: list[str] = []

                if rapid_ocr is not None:
                    try:
                        ocr_results, _ = rapid_ocr(band_arr)
                        if ocr_results:
                            for item in ocr_results:
                                rapid_text = str(item[1]).strip()
                                if rapid_text:
                                    ocr_text_parts.append(rapid_text)
                    except Exception as e:
                        logger.debug("Strategy 4 RapidOCR band %d: %s", i, e)

                elif predictor is not None:
                    # Chỉ dùng VietOCR nếu hệ thống hoàn toàn không có RapidOCR
                    try:
                        viet_text = predictor.predict(band_img)
                        if viet_text:
                            ocr_text_parts.append(str(viet_text).strip())
                    except Exception as e:
                        logger.debug("Strategy 4 VietOCR band %d: %s", i, e)

                if not ocr_text_parts:
                    continue

                ocr_text = " ".join(ocr_text_parts).lower()
                logger.debug("  Band %02d [%d-%d]: %r", i, top, bot, ocr_text[:80])

                # Match CONCEPT_REGEX
                for concept, pattern in CONCEPT_REGEX.items():
                    if re.search(pattern, ocr_text, re.IGNORECASE):
                        band_labels[i] = concept
                        logger.debug("    → Gán nhãn: %s", concept)
                        break

        except ImportError as e:
            logger.warning("Strategy 4: LocalOCREngine không khả dụng: %s", e)
            return []
        except Exception as e:
            logger.warning("Strategy 4 OCR thất bại: %s", e)
            return []

        logger.debug(
            "Strategy 4: Gán nhãn được %d / %d bands.",
            len(band_labels), len(bands),
        )

        # ── [4c] Map suspect_facts (rank order) → band ───────────────────────
        results: list[tuple[FinancialFact, tuple[int, int]]] = []
        for fact in suspect_facts:
            for band_idx, concept in band_labels.items():
                if concept == fact.concept:
                    results.append((fact, bands[band_idx]))
                    break   # mỗi fact chỉ map 1 band

        if page_num is not None:
            self._page_band_labels_cache[page_num] = results

        return results  # thứ tự = suspect rank, caller xử lý lần lượt


    # ── Locate table header ───────────────────────────────────────────────────

    def _locate_table_header(
        self,
        page: Any,
    ) -> tuple[float, float] | None:
        """
        Tìm dòng header của bảng (dòng chứa 'Năm nay', '2025', 'VND', hoặc tương đương).
        Chỉ tìm trong 1/3 trên cùng của trang.
        """
        try:
            header_patterns = [r"\bVND\b", r"\b20\d{2}\b", r"n[aă]m nay", r"k[yỳ] n[aà]y", r"s[oố] ti[eề]n"]
            words = page.extract_words()
            top_limit = page.height * 0.40

            # Group words theo dòng
            lines: dict[int, list[dict]] = {}
            for w in words:
                if w.get("top", page.height) > top_limit:
                    continue
                y_key = int(w["top"] // 4) * 4
                lines.setdefault(y_key, []).append(w)

            best_match_count, best_y = 0, None
            for line_words in lines.values():
                line_text = " ".join(w["text"] for w in line_words)
                match_count = sum(1 for p in header_patterns if re.search(p, line_text, re.IGNORECASE))
                if match_count > best_match_count:
                    best_match_count = match_count
                    best_y = (
                        min(w["top"] for w in line_words),
                        max(w["bottom"] for w in line_words),
                    )

            return best_y if best_match_count >= 1 else None
        except Exception as e:
            logger.debug("_locate_table_header failed: %s", e)
            return None

    # ── Context-aware Composite Crop ─────────────────────────────────────────

    def _build_composite_crop(
        self,
        page: Any,
        target_bbox: RowBBox,
        resolution: int,
    ) -> Image.Image:
        """
        Ghép [Header row] + [separator] + [Target row] thành 1 ảnh composite.
        Giúp Vision LLM biết chắc đang đọc cột nào (2025 hay 2024).
        """
        pad = 8.0
        target_img = page.crop((
            0,
            max(0.0, target_bbox.top - pad),
            float(page.width),
            min(float(page.height), target_bbox.bottom + pad),
        )).to_image(resolution=resolution).original

        header_y = self._locate_table_header(page)
        if header_y:
            header_img = page.crop((
                0,
                max(0.0, header_y[0] - 2),
                float(page.width),
                min(float(page.height), header_y[1] + 2),
            )).to_image(resolution=resolution).original

            # Ghép dọc: header + separator + target
            sep = Image.new("RGB", (target_img.width, 3), color=(180, 180, 180))
            # Resize header cùng width với target nếu khác
            if header_img.width != target_img.width:
                header_img = header_img.resize(
                    (target_img.width, header_img.height),
                    Image.LANCZOS,
                )
            total_h = header_img.height + sep.height + target_img.height
            composite = Image.new("RGB", (target_img.width, total_h), color=(255, 255, 255))
            composite.paste(header_img, (0, 0))
            composite.paste(sep, (0, header_img.height))
            composite.paste(target_img, (0, header_img.height + sep.height))
            return composite

        # Không tìm được header → trả về target đơn thuần
        return target_img

    # ── Crop Quality Validation ───────────────────────────────────────────────

    def _validate_crop_quality(self, pil_img: Image.Image) -> CropQuality:
        """
        Kiểm tra ảnh crop có chứa dữ liệu hữu ích không trước khi gửi LLM.
        """
        try:
            import numpy as np
            arr = np.array(pil_img.convert("L"))

            # Gần như toàn trắng
            if arr.mean() > 248:
                return CropQuality(valid=False, reason="nearly_blank")

            # Quá ít pixel tối (không có text)
            dark_pixels = int(np.sum(arr < 128))
            if dark_pixels < 30:
                return CropQuality(valid=False, reason="no_text_pixels")

            # Optional: kiểm tra có cụm số không
            try:
                import pytesseract
                text = pytesseract.image_to_string(pil_img, config="--psm 6")
                if not re.search(r"\d{3,}", text):
                    return CropQuality(valid=False, reason="no_numeric_content")
            except Exception:
                pass  # Bỏ qua nếu không có tesseract

        except Exception:
            pass  # numpy không có → bỏ qua validation

        return CropQuality(valid=True, reason="ok")

    # ── Main entry: waterfall 4 strategies ───────────────────────────────────

    def locate_row(
        self,
        page: Any,
        fact: FinancialFact,
        clean_code: str,
    ) -> RowBBox | None:
        """
        Chạy waterfall 4 strategy để định vị dòng chứa fact.
        Trả về RowBBox đầu tiên tìm được, hoặc None nếu tất cả thất bại.
        """
        # Strategy 1: pdfplumber native table
        if clean_code:
            result = self._strategy_table_extract(page, clean_code)
            if result:
                logger.debug("StructuredTableCropper: Strategy 1 (table_extract) thành công.")
                return result

        # Strategy 2: Column-bounded code match
        if clean_code:
            result = self._strategy_column_bounded_code(page, clean_code)
            if result:
                logger.debug("StructuredTableCropper: Strategy 2 (col_bounded_code) thành công.")
                return result

        # Strategy 3: Fuzzy label match
        result = self._strategy_fuzzy_label(page, fact.raw_label)
        if result:
            logger.debug("StructuredTableCropper: Strategy 3 (fuzzy_label) thành công.")
            return result

        logger.debug(
            "StructuredTableCropper: Tất cả strategy native text thất bại cho fact '%s'. "
            "Cần Strategy 4 (projection OCR) từ caller.",
            fact.concept,
        )
        return None


# ─────────────────────────────────────────────────────────────────────────────
# VisionZoomCorrector — Orchestrator chính
# ─────────────────────────────────────────────────────────────────────────────

class VisionZoomCorrector:
    """Bộ tự động phát hiện, phóng to (Zoom) và sửa lỗi OCR cho các dòng số liệu tài chính."""

    def __init__(
        self,
        settings: Settings | None = None,
        verifier: AccountingVerifier | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.verifier = verifier or AccountingVerifier()
        self.cropper = StructuredTableCropper()

    def identify_suspect_facts(
        self,
        report: VerificationReport,
        facts: list[FinancialFact],
    ) -> list[FinancialFact]:
        """
        Dùng phương pháp Suy luận Loại trừ (Deductive Elimination) để khoanh vùng
        và sắp xếp thứ tự ưu tiên các Fact bị nghi ngờ gây ra sai lệch số học.
        """
        if report.is_balanced or not report.discrepancies:
            return []

        # Bản đồ liên kết giữa tên bài kiểm tra và các concepts cấu thành cho cả 3 bảng cốt lõi
        check_to_concepts: dict[str, list[str]] = {
            # ── BẢNG 1: CÂN ĐỐI KẾ TOÁN (BS) ───────────────────────────────────
            "TOTAL_ASSETS == TOTAL_RESOURCES": ["TOTAL_ASSETS", "TOTAL_RESOURCES"],
            "TOTAL_ASSETS == CURRENT + NON_CURRENT": ["TOTAL_ASSETS", "CURRENT_ASSETS", "NON_CURRENT_ASSETS"],
            "CURRENT_ASSETS == SUM_CHILDREN": [
                "CURRENT_ASSETS",
                "CASH_AND_EQUIVALENTS",
                "SHORT_TERM_INVESTMENTS",
                "SHORT_TERM_RECEIVABLES",
                "INVENTORIES",
                "OTHER_CURRENT_ASSETS",
            ],
            "NON_CURRENT_ASSETS == SUM_CHILDREN": [
                "NON_CURRENT_ASSETS",
                "LONG_TERM_RECEIVABLES",
                "FIXED_ASSETS",
                "INVESTMENT_PROPERTIES",
                "LONG_TERM_ASSETS_IN_PROGRESS",
                "LONG_TERM_INVESTMENTS",
                "OTHER_NON_CURRENT_ASSETS",
            ],
            "TOTAL_RESOURCES == LIABILITIES + EQUITY": ["TOTAL_RESOURCES", "LIABILITIES", "EQUITY"],
            "LIABILITIES == CURRENT + NON_CURRENT": ["LIABILITIES", "CURRENT_LIABILITIES", "NON_CURRENT_LIABILITIES"],

            # ── BẢNG 2: KẾT QUẢ KINH DOANH (IS) ────────────────────────────────
            "NET_REVENUE == GROSS_REVENUE - REVENUE_DEDUCTIONS": ["NET_REVENUE", "GROSS_REVENUE", "REVENUE_DEDUCTIONS"],
            "GROSS_PROFIT == NET_REVENUE - COGS": ["GROSS_PROFIT", "NET_REVENUE", "COGS"],
            "OPERATING_PROFIT == GROSS_PROFIT + FINANCIAL - EXPENSES": [
                "OPERATING_PROFIT",
                "GROSS_PROFIT",
                "FINANCIAL_INCOME",
                "FINANCIAL_EXPENSES",
                "SELLING_EXPENSES",
                "ADMIN_EXPENSES",
            ],
            "OTHER_PROFIT == OTHER_INCOME - OTHER_EXPENSES": ["OTHER_PROFIT", "OTHER_INCOME", "OTHER_EXPENSES"],
            "PROFIT_BEFORE_TAX == OPERATING_PROFIT + OTHER_PROFIT": ["PROFIT_BEFORE_TAX", "OPERATING_PROFIT", "OTHER_PROFIT"],
            "NET_PROFIT == PROFIT_BEFORE_TAX - TAXES": ["NET_PROFIT", "PROFIT_BEFORE_TAX", "CURRENT_TAX_EXPENSE", "DEFERRED_TAX_EXPENSE"],

            # ── BẢNG 3: LƯU CHUYỂN TIỀN TỆ (CF) ────────────────────────────────
            "CF_NET_CHANGE == OPERATING + INVESTING + FINANCING": [
                "CF_NET_CHANGE",
                "CF_NET_OPERATING",
                "CF_NET_INVESTING",
                "CF_NET_FINANCING",
            ],
            "CF_ENDING_CASH == BEGINNING + NET_CHANGE": [
                "CF_ENDING_CASH",
                "CF_BEGINNING_CASH",
                "CF_NET_CHANGE",
                "CF_EXCHANGE_RATE_DIFF",
            ],
            "CF_NET_FINANCING == 31 - 32 + 33 - 34 - 35 - 36": [
                "CF_NET_FINANCING",
                "CF_EQUITY_ISSUANCE",
                "CF_CAPITAL_REFUND",
                "CF_BORROWINGS",
                "CF_REPAYMENTS",
                "CF_LEASE_REPAYMENTS",
                "CF_DIVIDENDS_PAID",
            ],

            # ── ĐỐI CHIẾU CHÉO (CROSS-STATEMENT) ───────────────────────────────
            "CROSS_CHECK_CASH == CF_ENDING vs BS_CASH": ["CF_ENDING_CASH", "CASH_AND_EQUIVALENTS"],
            "CROSS_CHECK_PBT == CF_01 vs IS_50": ["CF_PROFIT_BEFORE_TAX", "PROFIT_BEFORE_TAX"],
        }

        # 1. Đếm số lần concept xuất hiện trong các bài kiểm tra thất bại
        suspect_scores: dict[str, int] = {}
        for disc in report.discrepancies:
            check_name = disc.get("check", "")
            for check_key, concepts in check_to_concepts.items():
                if check_key in check_name:
                    for c in concepts:
                        suspect_scores[c] = suspect_scores.get(c, 0) + 10

        # 2. Áp dụng Deductive Elimination: Nếu 1 phương trình nội bộ ĐẠT, giảm điểm nghi ngờ
        passed_text = " ".join(report.passed_checks)
        if "CỘNG_TỔNG_TÀI_SẢN" in passed_text:
            suspect_scores["TOTAL_ASSETS"] = suspect_scores.get("TOTAL_ASSETS", 0) - 15
            suspect_scores["CURRENT_ASSETS"] = suspect_scores.get("CURRENT_ASSETS", 0) - 10
            suspect_scores["NON_CURRENT_ASSETS"] = suspect_scores.get("NON_CURRENT_ASSETS", 0) - 10

        if "CỘNG_DỌC_NGẮN_HẠN" in passed_text:
            suspect_scores["CURRENT_ASSETS"] = suspect_scores.get("CURRENT_ASSETS", 0) - 15
            suspect_scores["CASH_AND_EQUIVALENTS"] = suspect_scores.get("CASH_AND_EQUIVALENTS", 0) - 10
            suspect_scores["SHORT_TERM_INVESTMENTS"] = suspect_scores.get("SHORT_TERM_INVESTMENTS", 0) - 10
            suspect_scores["SHORT_TERM_RECEIVABLES"] = suspect_scores.get("SHORT_TERM_RECEIVABLES", 0) - 10
            suspect_scores["INVENTORIES"] = suspect_scores.get("INVENTORIES", 0) - 10
            suspect_scores["OTHER_CURRENT_ASSETS"] = suspect_scores.get("OTHER_CURRENT_ASSETS", 0) - 10

        if "CỘNG_DỌC_DÀI_HẠN" in passed_text:
            suspect_scores["NON_CURRENT_ASSETS"] = suspect_scores.get("NON_CURRENT_ASSETS", 0) - 15

        if "CỘNG_NGUỒN_VỐN" in passed_text:
            suspect_scores["TOTAL_RESOURCES"] = suspect_scores.get("TOTAL_RESOURCES", 0) - 15
            suspect_scores["LIABILITIES"] = suspect_scores.get("LIABILITIES", 0) - 10
            suspect_scores["EQUITY"] = suspect_scores.get("EQUITY", 0) - 10

        if "CỘNG_NỢ_PHẢI_TRẢ" in passed_text:
            suspect_scores["LIABILITIES"] = suspect_scores.get("LIABILITIES", 0) - 15
            suspect_scores["CURRENT_LIABILITIES"] = suspect_scores.get("CURRENT_LIABILITIES", 0) - 10
            suspect_scores["NON_CURRENT_LIABILITIES"] = suspect_scores.get("NON_CURRENT_LIABILITIES", 0) - 10

        if "CÂN_ĐỐI_DOANH_THU" in passed_text:
            suspect_scores["NET_REVENUE"] = suspect_scores.get("NET_REVENUE", 0) - 10
            suspect_scores["GROSS_REVENUE"] = suspect_scores.get("GROSS_REVENUE", 0) - 10
            suspect_scores["REVENUE_DEDUCTIONS"] = suspect_scores.get("REVENUE_DEDUCTIONS", 0) - 10

        if "CÂN_ĐỐI_LỢI_NHUẬN_GỘP" in passed_text:
            suspect_scores["GROSS_PROFIT"] = suspect_scores.get("GROSS_PROFIT", 0) - 10
            suspect_scores["NET_REVENUE"] = suspect_scores.get("NET_REVENUE", 0) - 10
            suspect_scores["COGS"] = suspect_scores.get("COGS", 0) - 10

        if "CÂN_ĐỐI_LN_THUẦN_HĐKD" in passed_text:
            suspect_scores["OPERATING_PROFIT"] = suspect_scores.get("OPERATING_PROFIT", 0) - 15
            suspect_scores["GROSS_PROFIT"] = suspect_scores.get("GROSS_PROFIT", 0) - 10

        if "CÂN_ĐỐI_LN_KHÁC" in passed_text:
            suspect_scores["OTHER_PROFIT"] = suspect_scores.get("OTHER_PROFIT", 0) - 10
            suspect_scores["OTHER_INCOME"] = suspect_scores.get("OTHER_INCOME", 0) - 10
            suspect_scores["OTHER_EXPENSES"] = suspect_scores.get("OTHER_EXPENSES", 0) - 10

        if "CỘNG_LN_TRƯỚC_THUẾ" in passed_text:
            suspect_scores["PROFIT_BEFORE_TAX"] = suspect_scores.get("PROFIT_BEFORE_TAX", 0) - 10
            suspect_scores["OPERATING_PROFIT"] = suspect_scores.get("OPERATING_PROFIT", 0) - 10
            suspect_scores["OTHER_PROFIT"] = suspect_scores.get("OTHER_PROFIT", 0) - 10

        if "CÂN_ĐỐI_LN_SAU_THUẾ" in passed_text:
            suspect_scores["NET_PROFIT"] = suspect_scores.get("NET_PROFIT", 0) - 10
            suspect_scores["PROFIT_BEFORE_TAX"] = suspect_scores.get("PROFIT_BEFORE_TAX", 0) - 10

        if "CÂN_ĐỐI_LCTT_THUẦN" in passed_text:
            suspect_scores["CF_NET_CHANGE"] = suspect_scores.get("CF_NET_CHANGE", 0) - 15
            suspect_scores["CF_NET_OPERATING"] = suspect_scores.get("CF_NET_OPERATING", 0) - 10
            suspect_scores["CF_NET_INVESTING"] = suspect_scores.get("CF_NET_INVESTING", 0) - 10
            suspect_scores["CF_NET_FINANCING"] = suspect_scores.get("CF_NET_FINANCING", 0) - 10

        if "CÂN_ĐỐI_TIỀN_CUỐI_KỲ" in passed_text:
            suspect_scores["CF_ENDING_CASH"] = suspect_scores.get("CF_ENDING_CASH", 0) - 15
            suspect_scores["CF_BEGINNING_CASH"] = suspect_scores.get("CF_BEGINNING_CASH", 0) - 10
            suspect_scores["CF_NET_CHANGE"] = suspect_scores.get("CF_NET_CHANGE", 0) - 10

        if "CÂN_ĐỐI_LCTT_HĐTC" in passed_text:
            suspect_scores["CF_NET_FINANCING"] = suspect_scores.get("CF_NET_FINANCING", 0) - 15
            suspect_scores["CF_BORROWINGS"] = suspect_scores.get("CF_BORROWINGS", 0) - 10
            suspect_scores["CF_REPAYMENTS"] = suspect_scores.get("CF_REPAYMENTS", 0) - 10
            suspect_scores["CF_DIVIDENDS_PAID"] = suspect_scores.get("CF_DIVIDENDS_PAID", 0) - 10

        if "ĐỐI_CHIẾU_CHÉO_TIỀN" in passed_text:
            suspect_scores["CF_ENDING_CASH"] = suspect_scores.get("CF_ENDING_CASH", 0) - 15
            suspect_scores["CASH_AND_EQUIVALENTS"] = suspect_scores.get("CASH_AND_EQUIVALENTS", 0) - 15

        if "ĐỐI_CHIẾU_CHÉO_LN_TRƯỚC_THUẾ" in passed_text:
            suspect_scores["CF_PROFIT_BEFORE_TAX"] = suspect_scores.get("CF_PROFIT_BEFORE_TAX", 0) - 15
            suspect_scores["PROFIT_BEFORE_TAX"] = suspect_scores.get("PROFIT_BEFORE_TAX", 0) - 15

        # 3. Suy luận đối chiếu chéo khi có mâu thuẫn liên bảng:
        failed_text = " ".join(report.failed_checks)
        if "LỆCH_ĐỐI_CHIẾU_CHÉO_TIỀN" in failed_text:
            if "CỘNG_DỌC_NGẮN_HẠN" in passed_text:
                # Tiền mặt bên CĐKT đã cân với 100 -> CĐKT đúng, LCTT sai
                suspect_scores["CASH_AND_EQUIVALENTS"] = suspect_scores.get("CASH_AND_EQUIVALENTS", 0) - 20
                suspect_scores["CF_ENDING_CASH"] = suspect_scores.get("CF_ENDING_CASH", 0) + 15
            elif "CÂN_ĐỐI_TIỀN_CUỐI_KỲ" in passed_text:
                # Tiền mặt bên LCTT đã cân với đầu kỳ + thuần -> LCTT đúng, CĐKT sai
                suspect_scores["CF_ENDING_CASH"] = suspect_scores.get("CF_ENDING_CASH", 0) - 20
                suspect_scores["CASH_AND_EQUIVALENTS"] = suspect_scores.get("CASH_AND_EQUIVALENTS", 0) + 15

        # Lọc các concept có điểm nghi ngờ > 0 và sắp xếp giảm dần
        sorted_suspect_concepts = sorted(
            [c for c, score in suspect_scores.items() if score > 0],
            key=lambda c: suspect_scores[c],
            reverse=True,
        )

        # Lấy Fact tương ứng kỳ hiện tại
        current_facts = [f for f in facts if f.period_type == "current"]
        suspect_facts: list[FinancialFact] = []
        for concept in sorted_suspect_concepts:
            matching = [f for f in current_facts if f.concept == concept]
            if matching:
                suspect_facts.append(matching[0])

        return suspect_facts

    def _infer_target_column(self, fact: FinancialFact) -> str:
        """Suy luận tên cột cần đọc dựa trên period_type của fact."""
        if hasattr(fact, "period_type") and fact.period_type == "previous":
            return "Năm trước (2024)"
        return "Năm nay (2025)"

    def locate_and_crop_row(
        self,
        pdf_path: str,
        fact: FinancialFact,
        suspect_facts: list[FinancialFact] | None = None,
        resolution: int = 180,
        save_debug_dir: str | None = None,
    ) -> tuple[Image.Image, str, str] | None:
        """
        Định vị dòng chứa Fact trên trang PDF và cắt ảnh composite độ phân giải cao.
        Sử dụng 4-strategy waterfall qua StructuredTableCropper.

        Returns:
            tuple[PIL.Image, str, str]: (Ảnh composite, base64 PNG, tên cột cần đọc) hoặc None
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_idx = fact.page - 1
                if page_idx < 0 or page_idx >= len(pdf.pages):
                    logger.warning(
                        "VisionZoomCorrector: Trang %d ngoài phạm vi PDF (%d trang).",
                        fact.page, len(pdf.pages),
                    )
                    return None

                page = pdf.pages[page_idx]
                clean_code = re.sub(r"[^\d]", "", str(fact.standard_code)) if fact.standard_code else ""
                target_column = self._infer_target_column(fact)

                # ── Strategy 1-3: native PDF text waterfall ─────────────────
                row_bbox = self.cropper.locate_row(page, fact, clean_code)
                pil_img: Image.Image | None = None
                pixel_box: tuple[int, int, int, int] | None = None

                if row_bbox:
                    pil_img = self.cropper._build_composite_crop(page, row_bbox, resolution)
                    # Pixel box để vẽ debug annotation
                    full_img = page.to_image(resolution=resolution).original
                    img_h = full_img.size[1]
                    scale_y = img_h / float(page.height)
                    pixel_box = (
                        0,
                        int(row_bbox.top * scale_y),
                        full_img.size[0],
                        int(row_bbox.bottom * scale_y),
                    )
                    logger.info(
                        "VisionZoomCorrector: Đã crop dòng '%s' qua strategy '%s' (confidence=%.2f).",
                        fact.concept, row_bbox.source, row_bbox.confidence,
                    )
                else:
                    # ── Strategy 4: Projection OCR (scanned PDF) ────────────
                    # Chỉ kích hoạt khi Strategy 1-3 thất bại toàn bộ
                    full_img = page.to_image(resolution=resolution).original
                    _suspects = suspect_facts or [fact]
                    ranked_bands = self.cropper._strategy_projection_profile(full_img, _suspects, page_num=fact.page)

                    # Tìm band tương ứng với fact hiện tại
                    for ranked_fact, (top_px, bot_px) in ranked_bands:
                        if ranked_fact.concept == fact.concept:
                            pad_px = int(10 * resolution / 72)
                            pil_img = full_img.crop((
                                0,
                                max(0, top_px - pad_px),
                                full_img.size[0],
                                min(full_img.size[1], bot_px + pad_px),
                            ))
                            pixel_box = (0, top_px, full_img.size[0], bot_px)
                            logger.info(
                                "VisionZoomCorrector: Strategy 4 (projection_ocr) đã locate dòng '%s'.",
                                fact.concept,
                            )
                            break

                if pil_img is None:
                    logger.warning(
                        "VisionZoomCorrector: Tất cả 4 strategy đều thất bại cho fact '%s'.",
                        fact.concept,
                    )
                    return None

                # ── Quality gate ─────────────────────────────────────────────
                quality = self.cropper._validate_crop_quality(pil_img)
                if not quality.valid:
                    logger.warning(
                        "VisionZoomCorrector: Ảnh crop '%s' không đạt chất lượng (%s). Bỏ qua.",
                        fact.concept, quality.reason,
                    )
                    return None

                # ── Debug save ───────────────────────────────────────────────
                if save_debug_dir and pixel_box:
                    self._save_debug(
                        save_debug_dir=save_debug_dir,
                        pil_img=pil_img,
                        full_img=full_img if "full_img" in dir() else page.to_image(resolution=resolution).original,
                        pixel_box=pixel_box,
                        fact=fact,
                    )

                # ── Encode Base64 PNG ────────────────────────────────────────
                buffered = io.BytesIO()
                pil_img.save(buffered, format="PNG")
                img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                return pil_img, img_b64, target_column

        except Exception as e:
            logger.error("VisionZoomCorrector: Lỗi khi crop dòng cho Fact %s: %s", fact.concept, e)
            return None

    def _save_debug(
        self,
        save_debug_dir: str,
        pil_img: Image.Image,
        full_img: Image.Image,
        pixel_box: tuple[int, int, int, int],
        fact: FinancialFact,
    ) -> None:
        """Lưu ảnh debug và ảnh annotated trang đầy đủ."""
        try:
            import cv2
            import numpy as np
            from pathlib import Path

            out_dir = Path(save_debug_dir)
            out_dir.mkdir(parents=True, exist_ok=True)

            crop_filename = out_dir / f"zoomed_row_{fact.concept}_p{fact.page}.png"
            pil_img.save(crop_filename)

            annotated = np.array(full_img)
            x0, y0, x1, y1 = pixel_box
            cv2.rectangle(annotated, (x0 + 4, y0), (x1 - 4, y1), (255, 0, 0), 4)
            label_tag = f"Suspect: {fact.concept} (Code {fact.standard_code})"
            cv2.putText(
                annotated, label_tag,
                (x0 + 20, max(30, y0 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2,
            )
            annotated_filename = out_dir / f"annotated_page_{fact.page}_{fact.concept}.png"
            Image.fromarray(annotated).save(annotated_filename)
            logger.info(
                "VisionZoomCorrector: Debug ảnh đã lưu: %s, %s",
                crop_filename, annotated_filename,
            )
        except Exception as save_err:
            logger.warning("VisionZoomCorrector: Không thể lưu ảnh debug: %s", save_err)

    def inspect_row_image(
        self,
        img_b64: str,
        fact: FinancialFact,
        target_column: str = "Năm nay (2025)",
    ) -> dict[str, Any]:
        """Gửi ảnh composite đến Vision API để thẩm định lại con số."""
        prompt = ZOOM_SYSTEM_PROMPT_V2.format(
            raw_label=fact.raw_label,
            standard_code=fact.standard_code or "Không có",
            target_column=target_column,
        )

        provider = self.settings.ocr_provider

        # Ưu tiên Gemini Vision
        if (provider in ("auto", "gemini")) and self.settings.gemini_api_key:
            res_text = self._call_gemini_zoom(img_b64=img_b64, prompt=prompt)
            if res_text:
                parsed = self._parse_json_result(res_text)
                if parsed:
                    return parsed

        # Fallback sang Groq Vision
        if (provider in ("auto", "groq")) and self.settings.groq_api_key:
            res_text = self._call_groq_zoom(img_b64=img_b64, prompt=prompt)
            if res_text:
                parsed = self._parse_json_result(res_text)
                if parsed:
                    return parsed

        return {}

    def _call_gemini_zoom(self, img_b64: str, prompt: str) -> str:
        """Gọi Gemini Flash Vision với prompt phóng to cục bộ và cơ chế fallback model."""
        api_key = self.settings.gemini_api_key
        if not api_key:
            return ""

        primary_model = self.settings.gemini_vision_model or "gemini-flash-lite-latest"
        candidate_models = list(dict.fromkeys([
            primary_model,
            "gemini-flash-lite-latest",
            "gemini-2.0-flash",
            "gemini-flash-latest",
        ]))

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
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
                "maxOutputTokens": 512,
            },
        }

        try:
            import httpx

            with httpx.Client(timeout=30.0) as client:
                for model in candidate_models:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                    try:
                        res = client.post(url, json=payload)
                        if res.status_code == 200:
                            data = res.json()
                            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                return parts[0]["text"].strip()
                        elif res.status_code in (404, 503, 429):
                            logger.debug(
                                "VisionZoomCorrector: Model '%s' trả về HTTP %d, chuyển model dự phòng...",
                                model, res.status_code,
                            )
                            continue
                    except Exception as err:
                        logger.warning("VisionZoomCorrector: Lỗi kết nối model %s: %s", model, err)
                        continue
        except Exception as e:
            logger.warning("VisionZoomCorrector: Lỗi gọi Gemini Zoom API: %s", e)

        return ""

    def _call_groq_zoom(self, img_b64: str, prompt: str) -> str:
        """Gọi Groq Vision API để thẩm định ảnh zoom."""
        api_key = self.settings.groq_api_key
        if not api_key:
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
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                            },
                        ],
                    }
                ],
                temperature=0.0,
                max_tokens=512,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("VisionZoomCorrector: Lỗi gọi Groq Zoom API: %s", e)
            return ""

    def _parse_json_result(self, text: str) -> dict[str, Any] | None:
        """Trích xuất và parse an toàn JSON từ kết quả LLM."""
        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                raw_json = match.group(0)
                data = json.loads(raw_json)
                return data
        except Exception as e:
            logger.warning(
                "VisionZoomCorrector: Không thể parse JSON từ Vision Zoom '%s': %s",
                text[:100], e,
            )
        return None

    def run_self_correction(
        self,
        pdf_path: str,
        facts: list[FinancialFact],
        report: VerificationReport,
        company: str = "DOANH_NGHIEP",
        year: int = 2024,
        max_attempts: int = 5,
        save_debug_dir: str | None = None,
    ) -> tuple[list[FinancialFact], VerificationReport, bool]:
        """
        Kích hoạt vòng lặp tự sửa sai cục bộ (Closed-loop Self-Correction):
          1. Khoanh vùng các Fact bị nghi ngờ (identify_suspect_facts).
          2. Cắt ảnh composite và gọi Vision LLM đọc lại số.
          3. Hot-patch số mới và re-verify tự động.
          4. Nếu BCTC cân đối (is_balanced == True), cập nhật trạng thái và thoát thành công.

        Returns:
            tuple[list[FinancialFact], VerificationReport, bool]: (facts_mới, report_mới, is_corrected)
        """
        if report.is_balanced:
            return facts, report, False

        suspect_facts = self.identify_suspect_facts(report, facts)
        if not suspect_facts:
            logger.info("VisionZoomCorrector: Không xác định được suspect facts khả dĩ để Zoom.")
            return facts, report, False

        logger.info(
            "VisionZoomCorrector: Phát hiện %d suspect facts cần Zoom thẩm định: %s",
            len(suspect_facts),
            [f.concept for f in suspect_facts[:max_attempts]],
        )

        current_facts = list(facts)
        current_report = report

        for attempt, suspect in enumerate(suspect_facts[:max_attempts], start=1):
            logger.info(
                "VisionZoomCorrector [Lần %d/%d]: Phóng to dòng '%s' (Mã %s, Giá trị hiện tại: %s, Trang %d)...",
                attempt,
                max_attempts,
                suspect.raw_label,
                suspect.standard_code,
                f"{suspect.value:,.0f}",
                suspect.page,
            )

            crop_result = self.locate_and_crop_row(
                pdf_path=pdf_path,
                fact=suspect,
                suspect_facts=suspect_facts,   # truyền toàn bộ rank list cho Strategy 4
                save_debug_dir=save_debug_dir,
            )
            if not crop_result:
                continue

            _, img_b64, target_column = crop_result
            inspection = self.inspect_row_image(
                img_b64=img_b64,
                fact=suspect,
                target_column=target_column,
            )

            raw_val = inspection.get("value_current")
            if raw_val is None and "raw_text" in inspection:
                raw_val = clean_ocr_number(inspection["raw_text"])

            if raw_val is None:
                continue

            new_value = float(raw_val)
            old_value = suspect.value

            # Nếu con số đọc lại khác biệt đáng kể so với con số cũ
            if abs(new_value - old_value) > self.verifier.absolute_tolerance:
                logger.info(
                    "VisionZoomCorrector: Phát hiện giá trị mới từ Vision Zoom: %s (Cũ: %s). Thử hot-patch...",
                    f"{new_value:,.0f}",
                    f"{old_value:,.0f}",
                )

                # Áp dụng tạm thời giá trị mới
                suspect.value = new_value

                # Re-verify toàn bộ facts
                new_report = self.verifier.verify_facts(current_facts, company=company, year=year)

                # Tính tổng sai số tuyệt đối (total absolute residual) của các bài kiểm tra thất bại
                current_residual = sum(
                    abs(float(d.get("delta", 0.0) or d.get("discrepancy", 0.0)))
                    for d in current_report.discrepancies
                )
                new_residual = sum(
                    abs(float(d.get("delta", 0.0) or d.get("discrepancy", 0.0)))
                    for d in new_report.discrepancies
                )
                residual_improved = (
                    len(new_report.failed_checks) <= len(current_report.failed_checks)
                    and new_residual < current_residual - self.verifier.absolute_tolerance
                )

                if new_report.is_balanced or len(new_report.failed_checks) < len(current_report.failed_checks) or residual_improved:
                    # Sửa lỗi thành công (toàn phần hoặc 1 phần)!
                    history_entry = {
                        "concept": suspect.concept,
                        "standard_code": suspect.standard_code,
                        "raw_label": suspect.raw_label,
                        "old_value": old_value,
                        "new_value": new_value,
                        "page": suspect.page,
                        "target_column": target_column,
                        "reason": "Vision-LLM Zoom Self-Correction",
                    }
                    new_report.correction_history.append(history_entry)

                    if new_report.is_balanced:
                        suspect.verification_status = VerificationStatus.VERIFIED_AFTER_ZOOM_CORRECTION
                        suspect.verification_detail = (
                            f"Đã tự động sửa lỗi OCR từ {old_value:,.0f} sang {new_value:,.0f} qua Vision-LLM Zoom."
                        )
                        new_report.summary += (
                            f" [✅ Tự sửa thành công dòng {suspect.concept} từ {old_value:,.0f} -> {new_value:,.0f}]"
                        )
                        logger.info("VisionZoomCorrector: ✅ TỰ SỬA LỖI THÀNH CÔNG! BCTC đã trở nên HOÀN TOÀN CÂN ĐỐI.")
                        return current_facts, new_report, True

                    logger.info(
                        "VisionZoomCorrector: Giá trị mới giúp cải thiện độ cân đối BCTC (Tổng sai số: %s -> %s). Tiếp tục hoàn thiện...",
                        f"{current_residual:,.0f}",
                        f"{new_residual:,.0f}",
                    )
                    # Cải thiện được 1 phần, tiếp tục vòng lặp
                    current_report = new_report
                else:
                    # Nếu sửa xong lại làm sai lệch nhiều hơn -> Revert
                    logger.warning("VisionZoomCorrector: Giá trị mới không giúp cân đối BCTC. Revert về giá trị cũ.")
                    suspect.value = old_value

        return current_facts, current_report, False
