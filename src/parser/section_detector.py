"""
section_detector.py — Nhận diện tiêu đề và phân đoạn Section cho Báo cáo tài chính.
Áp dụng Kiến trúc Chuẩn Hóa Phân Cấp 4 Tầng (Hierarchical Section & Heading Engine):
  - Tầng 1: Canonical Taxonomy (Hệ thống khái niệm chuẩn hóa TT 200/VAS/IFRS)
  - Tầng 2: Multi-Strategy Pattern Matcher (Prefix + Fuzzy Dictionary + TOC Alignment)
  - Tầng 3: Monotonic Hierarchy State Machine (Cây phân cấp một chiều chống nhảy cóc)
  - Tầng 4: Đóng gói Metadata phục vụ Parent-Child RAG (Child = Breadcrumb & Ref; Parent = Full Content)
"""

from dataclasses import dataclass
import logging
import re
import unicodedata
from typing import Any

from src.models import ClassifiedBlock, Section
from src.parser.ocr_postprocess import strip_boilerplate_lines

logger = logging.getLogger(__name__)

# ==============================================================================
# TẦNG 1: CANONICAL TAXONOMY & CONCEPT ONTOLOGY (TT 200 / VAS / IFRS)
# ==============================================================================

# Báo cáo cốt lõi (Level 3 - H3)
CORE_STATEMENT_CANONICAL = {
    "CORE_BALANCE_SHEET": "BẢNG CÂN ĐỐI KẾ TOÁN",
    "CORE_INCOME_STATEMENT": "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH",
    "CORE_CASH_FLOW": "BÁO CÁO LƯU CHUYỂN TIỀN TỆ",
}

# 9 Phần La Mã chuẩn trong Bản Thuyết minh BCTC theo TT200/2014/TT-BTC (Level 3 - H3)
# Lưu ý: Phần V (hoạt động liên tục) là tùy chọn — DN không đáp ứng giả định
# hoạt động liên tục mới phải thuyết minh, nhưng template TT200 vẫn có đủ 9 phần.
ROMAN_CANONICAL = {
    "I":    ("NOTE_SEC_GENERAL_INFO",         "I. ĐẶC ĐIỂM HOẠT ĐỘNG CỦA DOANH NGHIỆP",                                                              1),
    "II":   ("NOTE_SEC_ACCOUNTING_PERIOD",    "II. KỲ KẾ TOÁN VÀ ĐƠN VỊ TIỀN TỆ SỬ DỤNG TRONG KẾ TOÁN",                                             2),
    "III":  ("NOTE_SEC_ACCOUNTING_STANDARDS", "III. CHUẨN MỰC VÀ CHẾ ĐỘ KẾ TOÁN ÁP DỤNG",                                                           3),
    "IV":   ("NOTE_SEC_ACCOUNTING_POLICIES",  "IV. CÁC CHÍNH SÁCH KẾ TOÁN ÁP DỤNG",                                                                  4),
    "V":    ("NOTE_SEC_GOING_CONCERN",        "V. CÁC CHÍNH SÁCH KẾ TOÁN ÁP DỤNG (KHÔNG ĐÁP ỨNG HOẠT ĐỘNG LIÊN TỤC)",                               5),
    "VI":   ("NOTE_SEC_BALANCE_SHEET",        "VI. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BẢNG CÂN ĐỐI KẾ TOÁN",                      6),
    "VII":  ("NOTE_SEC_INCOME_STATEMENT",     "VII. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH",    7),
    "VIII": ("NOTE_SEC_CASH_FLOW",            "VIII. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BÁO CÁO LƯU CHUYỂN TIỀN TỆ",             8),
    "IX":   ("NOTE_SEC_OTHER_INFO",           "IX. NHỮNG THÔNG TIN KHÁC",                                                                             9),
}

# ── Lookup dicts chuẩn TT200 phục vụ canonical matching ──────────────────────
# 30 mục Thuyết minh Bảng CĐKT (Phần VI theo TT200)
TT200_VI_BALANCE_SHEET_NOTES: dict[int, str] = {
    1: "Tiền",
    2: "Các khoản đầu tư tài chính",
    3: "Phải thu của khách hàng",
    4: "Phải thu khác",
    5: "Tài sản thiếu chờ xử lý",
    6: "Nợ xấu",
    7: "Hàng tồn kho",
    8: "Tài sản dở dang dài hạn",
    9: "Tăng, giảm tài sản cố định hữu hình",
    10: "Tăng, giảm tài sản cố định vô hình",
    11: "Tăng, giảm tài sản cố định thuê tài chính",
    12: "Tăng, giảm bất động sản đầu tư",
    13: "Chi phí trả trước",
    14: "Tài sản khác",
    15: "Vay và nợ thuê tài chính",
    16: "Phải trả người bán",
    17: "Thuế và các khoản phải nộp nhà nước",
    18: "Chi phí phải trả",
    19: "Phải trả khác",
    20: "Doanh thu chưa thực hiện",
    21: "Trái phiếu phát hành",
    22: "Cổ phiếu ưu đãi phân loại là nợ phải trả",
    23: "Dự phòng phải trả",
    24: "Tài sản và thuế thu nhập hoãn lại phải trả",
    25: "Vốn chủ sở hữu",
    26: "Chênh lệch đánh giá lại tài sản",
    27: "Chênh lệch tỷ giá",
    28: "Nguồn kinh phí",
    29: "Các khoản mục ngoài Bảng cân đối kế toán",
    30: "Các thông tin khác do doanh nghiệp tự thuyết minh",
}

# 11 mục Thuyết minh Báo cáo KQKD (Phần VII theo TT200)
TT200_VII_INCOME_STATEMENT_NOTES: dict[int, str] = {
    1: "Tổng doanh thu bán hàng và cung cấp dịch vụ",
    2: "Các khoản giảm trừ doanh thu",
    3: "Giá vốn hàng bán",
    4: "Doanh thu hoạt động tài chính",
    5: "Chi phí tài chính",
    6: "Thu nhập khác",
    7: "Chi phí khác",
    8: "Chi phí bán hàng và chi phí quản lý doanh nghiệp",
    9: "Chi phí sản xuất kinh doanh theo yếu tố",
    10: "Chi phí thuế thu nhập doanh nghiệp hiện hành",
    11: "Chi phí thuế thu nhập doanh nghiệp hoãn lại",
}

# Danh sách tiêu đề BCTC cấp 1 phổ biến tại Việt Nam (hỗ trợ legacy matching)
_PRIMARY_STATEMENTS = [
    ("bảng cân đối kế toán", "financial_statements"),
    ("báo cáo tình hình tài chính", "financial_statements"),
    ("báo cáo kết quả hoạt động kinh doanh", "financial_statements"),
    ("báo cáo kết quả kinh doanh", "financial_statements"),
    ("báo cáo lưu chuyển tiền tệ", "financial_statements"),
    ("thuyết minh báo cáo tài chính", "notes"),
    ("bản thuyết minh báo cáo tài chính", "notes"),
    ("báo cáo của công ty kiểm toán độc lập", "auditor_report"),
    ("báo cáo kiểm toán độc lập", "auditor_report"),
    ("báo cáo của ban tổng giám đốc", "mda"),
    ("báo cáo của ban giám đốc", "mda"),
    ("báo cáo của hội đồng quản trị", "mda"),
]


def slugify_vietnamese(text: str) -> str:
    """
    Chuyển đổi tiêu đề tiếng Việt thành slug ASCII chuẩn làm section_id.

    Quy trình: Xóa dấu qua Unicode NFKD (kèm đ->d), lọc bỏ ký tự đặc biệt,
    thay khoảng trắng bằng dấu gạch dưới, giới hạn tối đa 40 ký tự.
    Ví dụ: 'Báo cáo Ban Giám đốc' -> 'bao_cao_ban_giam_doc'.
    """
    if not text:
        return "section"
    text = text.lower().replace("đ", "d")
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    slug = re.sub(r"[^\w\s-]", "", without_accents)
    slug = re.sub(r"[-\s]+", "_", slug).strip("_")
    return slug[:40] or "section"


@dataclass
class HeadingMatch:
    """Thực thể kết quả nhận diện tiêu đề."""
    title: str
    level: int                                              # 2: H2, 3: H3, 4: H4, 5: H5
    canonical_code: str | None = None
    roman_code: str | None = None
    item_code: str | None = None
    sub_code: str | None = None
    section_type: str = "notes"


class HierarchyState:
    """Máy trạng thái theo dõi ngữ cảnh cây phân cấp tài liệu BCTC."""
    def __init__(self):
        self.emitted_core_major: bool = False
        self.emitted_notes_major: bool = False
        self.current_major_id: str | None = None
        self.current_major_title: str = ""
        
        self.current_roman: str = ""
        self.current_roman_num: int = 0
        self.current_roman_title: str = ""
        self.current_roman_sec_id: str | None = None
        self.current_canonical_code: str = ""
        
        self.current_note_num: int = 0
        self.current_note_title: str = ""
        self.current_note_sec_id: str | None = None

        self.current_sub_code: str = ""
        self.current_sub_sec_id: str | None = None
        self.current_sub_title: str = ""


class SectionDetector:
    """Bộ nhận diện tiêu đề và phân đoạn Section phân cấp chuẩn TT 200."""

    def __init__(self, enable_major_sections: bool = False) -> None:
        self.enable_major_sections = enable_major_sections

    def detect_sections(
        self,
        blocks: list[ClassifiedBlock],
        company: str = "DOANH_NGHIEP",
        year: int = 2024,
        toc_ranges: dict[str, tuple[int, int]] | None = None,
    ) -> list[Section]:
        """
        Duyệt qua danh sách ClassifiedBlock và gom nhóm thành cây Section ngữ nghĩa có cấu trúc.

        Issue #6 fix: Sử dụng toc_ranges để:
          1. Xây dựng page_to_toc_section mapping từ thông tin TOC
          2. Gắn toc_hint vào metadata của mỗi section để downstream biết loại section
          3. Ưu tiên canonical_code từ TOC khi block nằm đúng page range
        """
        if not blocks:
            return []

        # Issue #6: Xây dựng mapping page → tên section theo TOC để dùng làm hint
        _page_to_toc: dict[int, str] = {}
        if toc_ranges:
            for sec_name, (page_start, page_end) in toc_ranges.items():
                for pg in range(page_start, page_end + 1):
                    _page_to_toc[pg] = sec_name
            logger.debug(
                "SectionDetector: Đã nạp %d toc_ranges → %d page mappings",
                len(toc_ranges),
                len(_page_to_toc),
            )

        # Bước tiền xử lý: Tách các block lớn nếu chứa nhiều tiêu đề nội bộ
        refined_blocks = self._preprocess_split_blocks(blocks)

        sections: list[Section] = []
        current_section: Section | None = None
        state = HierarchyState()
        section_idx = 1
        for block in refined_blocks:
            match = self._extract_heading(block, state)

            if match:
                # Nếu kích hoạt major sections (Level 2), tự động chèn Section H2 phân tách đại phân vùng
                if self.enable_major_sections:
                    major_sec = self._maybe_create_major_section(block, match, state, company, year)
                    if major_sec:
                        if current_section and current_section.blocks:
                            sections.append(current_section)
                            current_section = None
                        sections.append(major_sec)

                # Nếu tiêu đề trùng với canonical_code đang active (ví dụ báo cáo LCTT hoặc BCĐKT kéo dài 2 trang tiếp theo)
                if (
                    current_section
                    and match.canonical_code
                    and current_section.canonical_code == match.canonical_code
                ):
                    current_section.blocks.append(block)
                    current_section.page_end = max(current_section.page_end, block.page)
                    block.breadcrumb = current_section.breadcrumb
                    continue

                # Đóng section trước đó nếu đã có
                if current_section and current_section.blocks:
                    sections.append(current_section)

                # Tạo Section mới theo cấp bậc
                slug = slugify_vietnamese(match.title)
                ref_str = f"_{slugify_vietnamese(match.item_code)}" if match.item_code else ""
                sec_id = f"{company.lower()}_{year}_s_{slug}{ref_str}_{section_idx}"
                section_idx += 1

                # Xác định parent_id và breadcrumb theo phân cấp
                parent_id, breadcrumb = self._resolve_hierarchy(match, state)

                # Cập nhật State Machine
                self._update_state(match, sec_id, state)

                # Issue #6: Gắn toc_hint nếu block nằm trong page range của TOC
                sec_metadata: dict = {"heading_source": block.block_id}
                toc_hint = _page_to_toc.get(block.page)
                if toc_hint:
                    sec_metadata["toc_hint"] = toc_hint
                    logger.debug(
                        "SectionDetector: Trang %d → TOC hint '%s' gắn vào section '%s'",
                        block.page,
                        toc_hint,
                        match.title,
                    )

                current_section = Section(
                    id=sec_id,
                    title=match.title,
                    company=company,
                    year=year,
                    page_start=block.page,
                    page_end=block.page,
                    blocks=[block],
                    section_type=match.section_type,
                    level=match.level,
                    parent_id=parent_id,
                    canonical_code=match.canonical_code,
                    reference_code=match.item_code,
                    breadcrumb=breadcrumb,
                    metadata=sec_metadata,
                )
                block.breadcrumb = breadcrumb
                block.heading_level = match.level

            else:
                # Nếu chưa có section nào (đầu tài liệu), tạo section mở đầu
                if current_section is None:
                    sec_id = f"{company.lower()}_{year}_s_thong_tin_chung"
                    current_section = Section(
                        id=sec_id,
                        title="THÔNG TIN CHUNG VÀ MỞ ĐẦU",
                        company=company,
                        year=year,
                        page_start=block.page,
                        page_end=block.page,
                        blocks=[block],
                        section_type="general_info",
                        level=2,
                        breadcrumb="Báo cáo tài chính > Thông tin chung",
                    )
                    state.current_major_id = sec_id
                    state.current_major_title = "THÔNG TIN CHUNG VÀ MỞ ĐẦU"
                    block.breadcrumb = current_section.breadcrumb
                else:
                    current_section.blocks.append(block)
                    current_section.page_end = max(current_section.page_end, block.page)
                    block.breadcrumb = current_section.breadcrumb

        # Lưu section cuối cùng
        if current_section and current_section.blocks:
            sections.append(current_section)

        # Gắn child_metadata cho tất cả sections (phục vụ Parent-Child RAG)
        for sec in sections:
            sec.child_metadata = {
                "chunk_id": sec.id,
                "title": sec.title,
                "level": sec.level,
                "reference_code": sec.reference_code or "",
                "canonical_code": sec.canonical_code or "",
                "breadcrumb": sec.breadcrumb,
                "parent_id": sec.parent_id or "",
                "page_start": sec.page_start,
                "page_end": sec.page_end,
                "block_count": len(sec.blocks),
                "has_table": any(b.is_table for b in sec.blocks),
                # Issue #6: Truyền toc_hint xuống child_metadata để RAG retriever dùng
                "toc_hint": sec.metadata.get("toc_hint", ""),
            }

        logger.info(
            "SectionDetector: Đã phân đoạn thành công %d sections có phân cấp cho BCTC %s_%d.",
            len(sections),
            company,
            year,
        )
        return sections

    def _extract_heading(self, block: ClassifiedBlock, state: HierarchyState) -> HeadingMatch | None:
        """Nhận diện tiêu đề đa chiến lược (Core Statements, Roman, Numbered Note, Sub-items)."""
        # 1. Bảng BCTC chính mà header chứa tên báo cáo
        if block.block.is_table:
            header = block.block.get_header_row().lower()
            for title_kw, sec_type in _PRIMARY_STATEMENTS:
                if title_kw in header:
                    return HeadingMatch(
                        title=title_kw.title(),
                        level=3,
                        section_type=sec_type,
                    )
            return None

        # 2. Văn bản Text: làm sạch rác boilerplate trước khi kiểm tra dòng đầu
        clean_content = strip_boilerplate_lines(block.content)
        lines = [l.strip() for l in clean_content.splitlines() if l.strip()]
        if not lines:
            return None

        first_line = lines[0]
        first_clean = re.sub(r"^[#*>\-\s]+", "", first_line).strip()
        first_low = first_clean.lower()

        # a. Nhận diện Phần La Mã (Level 3 - H3: I, II, III, IV, V, VI, VII, VIII)
        roman_res = self._match_roman_section(first_clean, first_low)
        if roman_res:
            can_code, canon_title, r_num = roman_res
            if r_num >= state.current_roman_num:
                m_pref = re.match(r"^(IX|VIII|VII|VI|V|IV|III|II|I)[\.:\s\-]+", canon_title)
                roman_str = m_pref.group(1).upper() if m_pref else list(ROMAN_CANONICAL.keys())[r_num - 1]
                return HeadingMatch(
                    title=canon_title,
                    level=3,
                    canonical_code=can_code,
                    roman_code=roman_str,
                    section_type="notes",
                )

        # b. Nhận diện Báo cáo tài chính cốt lõi (Level 3 - H3: Trang 5-12)
        if block.page <= 12 and not any(k in first_low for k in ["thông tin bổ sung", "thuyết minh", "bổ sung"]):
            if (
                re.match(r"^(báo cáo tình hình tài chính|bảng cân đối kế toán)", first_low)
                or (len(first_clean) < 75 and any(kw in first_low for kw in ["báo cáo tình hình tài chính", "bảng cân đối kế toán"]))
            ):
                return HeadingMatch(
                    title=CORE_STATEMENT_CANONICAL["CORE_BALANCE_SHEET"],
                    level=3,
                    canonical_code="CORE_BALANCE_SHEET",
                    section_type="financial_statements",
                )
            if (
                re.match(r"^(báo cáo kết quả hoạt động kinh doanh|báo cáo kết quả kinh doanh)", first_low)
                or (len(first_clean) < 75 and any(kw in first_low for kw in ["báo cáo kết quả hoạt động kinh doanh", "báo cáo kết quả kinh doanh"]))
            ):
                return HeadingMatch(
                    title=CORE_STATEMENT_CANONICAL["CORE_INCOME_STATEMENT"],
                    level=3,
                    canonical_code="CORE_INCOME_STATEMENT",
                    section_type="financial_statements",
                )
            if (
                re.match(r"^(báo cáo lưu chuyển tiền tệ)", first_low)
                or (len(first_clean) < 75 and "báo cáo lưu chuyển tiền tệ" in first_low)
            ):
                return HeadingMatch(
                    title=CORE_STATEMENT_CANONICAL["CORE_CASH_FLOW"],
                    level=3,
                    canonical_code="CORE_CASH_FLOW",
                    section_type="financial_statements",
                )

        # c. Nhận diện Mục số Thuyết minh (Level 4 - H4: "1. Tiền...", "19. Vốn chủ sở hữu...")
        clean_first = re.sub(r"^(\d{1,2})\.0{1,2}\s+", r"\1. ", first_clean)
        num_res = self._match_numbered_note(clean_first, first_low, state)
        if num_res:
            num, clean_title = num_res
            ref_code = f"{state.current_roman}.{num}" if state.current_roman else f"{num}"
            return HeadingMatch(
                title=f"{num}. {clean_title}",
                level=4,
                item_code=ref_code,
                section_type="numeric_note",
            )

        # d. Nhận diện Tiểu mục số thập phân (Level 5 - H5: "1.1 Các giao dịch...", "19.1 Thay đổi vốn...")
        dec_res = self._match_decimal_note(first_clean, first_low, state)
        if dec_res and (state.current_note_num > 0 or state.current_roman_num > 0):
            code_str, clean_title = dec_res
            ref_code = f"{state.current_roman}.{code_str}" if state.current_roman else code_str
            return HeadingMatch(
                title=f"{code_str} {clean_title}",
                level=5,
                sub_code=code_str,
                item_code=ref_code,
                section_type="sub_item",
            )

        # e. Nhận diện Tiểu mục chữ Thuyết minh (Level 5 - H5: "(a) Các công ty con...", "(c) Đơn vị trực thuộc:")
        sub_res = self._match_sub_item(first_clean, first_low, state=state)
        if sub_res and (state.current_note_num > 0 or state.current_roman_num > 0):
            sub_code, clean_title = sub_res
            ref_code = f"{state.current_roman}.{state.current_note_num}({sub_code})" if state.current_roman and state.current_note_num else f"({sub_code})"
            return HeadingMatch(
                title=f"({sub_code}) {clean_title}",
                level=5,
                sub_code=sub_code,
                item_code=ref_code,
                section_type="sub_item",
            )

        # f. Nhận diện Nhóm/Phân mục trực thuộc tiểu mục (Level 6 - H6: "Các chi nhánh bán hàng", "Các nhà máy sản xuất"...)
        grp_res = self._match_sub_group(first_clean, first_low, state=state)
        if grp_res:
            return HeadingMatch(
                title=grp_res,
                level=6,
                section_type="sub_group",
            )

        # g. Fallback kiểm tra danh sách _PRIMARY_STATEMENTS cho các văn bản khác (Kiểm toán, HĐQT)
        for title_kw, sec_type in _PRIMARY_STATEMENTS:
            if title_kw == first_low or first_low.startswith(title_kw):
                return HeadingMatch(
                    title=first_clean.upper(),
                    level=3,
                    section_type=sec_type,
                )

        return None

    def _match_roman_section(self, text: str, text_low: str) -> tuple[str, str, int] | None:
        """Nhận diện phần La Mã dựa trên Prefix Regex và Từ khóa Thông tư 200 (9 phần)."""
        # 1. Prefix La Mã trực tiếp — hỗ trợ I→IX
        m = re.match(r"^(IX|VIII|VII|VI|IV|V|III|II|I|L|1)[\.:\s\-]+(.*)$", text, re.I)
        if m:
            pref = m.group(1).upper()
            rest = m.group(2).strip().lower()
            if pref in ("L", "1") and ("thông tin doanh nghiệp" in rest or "đặc điểm" in rest):
                return ROMAN_CANONICAL["I"]
            if pref in ("L", "1"):
                # "1" là chữ số, không phải số La Mã! Nếu không phải Section I thì không match
                return None
            # Kiểm tra ngữ nghĩa nội dung — ưu tiên semantic trước numeric prefix
            if "những thông tin khác" in rest or "nhung thong tin khac" in rest:
                return ROMAN_CANONICAL["IX"]
            if "lưu chuyển" in rest and "tiền tệ" in rest:
                if pref == "VII":
                    return ("NOTE_SEC_CASH_FLOW", f"{pref}. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BÁO CÁO LƯU CHUYỂN TIỀN TỆ", 7)
                return ROMAN_CANONICAL["VIII"]
            if "kết quả" in rest and ("kinh doanh" in rest or "hoạt động" in rest):
                if pref == "VI":
                    return ("NOTE_SEC_INCOME_STATEMENT", f"{pref}. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH", 6)
                return ROMAN_CANONICAL["VII"]
            if "bảng cân đối" in rest or "cân đối kế toán" in rest or "tình hình tài chính" in rest:
                if pref == "V":
                    return ("NOTE_SEC_BALANCE_SHEET", f"{pref}. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BÁO CÁO TÌNH HÌNH TÀI CHÍNH", 5)
                return ROMAN_CANONICAL["VI"]
            if "không đáp ứng" in rest and ("hoạt động liên tục" in rest or "lien_tuc" in rest):
                return ROMAN_CANONICAL["V"]
            if "chính sách kế toán" in rest:
                return ROMAN_CANONICAL["IV"]
            if "chuẩn mực" in rest or "chế độ kế toán" in rest:
                return ROMAN_CANONICAL["III"]
            if "kỳ kế toán" in rest or "đơn vị tiền tệ" in rest:
                return ROMAN_CANONICAL["II"]
            if "đặc điểm" in rest or "thông tin doanh nghiệp" in rest:
                return ROMAN_CANONICAL["I"]
            if pref in ROMAN_CANONICAL and len(rest) > 2:
                return ROMAN_CANONICAL[pref]

        # 2. Nhận diện từ khóa không phụ thuộc số La Mã (kháng lỗi dấu thanh OCR)
        slug = slugify_vietnamese(text)
        if "thong_tin_doanh_nghiep" in slug or "dac_diem_hoat_dong" in slug:
            return ROMAN_CANONICAL["I"]
        if "ky_ke_toan" in slug and "tien_te" in slug:
            return ROMAN_CANONICAL["II"]
        if "chuan_muc" in slug and "che_do_ke_toan" in slug:
            return ROMAN_CANONICAL["III"]
        if "chinh_sach_ke_toan" in slug and len(text) < 80:
            return ROMAN_CANONICAL["IV"]
        if "hoat_dong_lien_tuc" in slug and "khong_dap_ung" in slug:
            return ROMAN_CANONICAL["V"]
        if (
            ("thong_tin_bo_sung" in slug or "va_va_thong_tin_bo_sung" in slug or "v_v_thong_tin_bo_sung" in slug)
            and ("bang_can_doi" in slug or "can_doi_ke_toan" in slug or "tinh_hinh_tai_chinh" in slug or "tai_chinh_rieng" in slug)
        ):
            return ("NOTE_SEC_BALANCE_SHEET", "VI. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BÁO CÁO TÌNH HÌNH TÀI CHÍNH", 6)
        if "thong_tin_bo_sung" in slug and ("ket_qua" in slug or "hoat_dong_kinh_doanh" in slug):
            return ROMAN_CANONICAL["VII"]
        if "thong_tin_bo_sung" in slug and "luu_chuyen" in slug:
            return ROMAN_CANONICAL["VIII"]
        if "nhung_thong_tin_khac" in slug:
            return ROMAN_CANONICAL["IX"]

        return None

    def _match_numbered_note(self, text: str, text_low: str, state: HierarchyState) -> tuple[int, str] | None:
        """Nhận diện mục số thuyết minh (ví dụ: '1. Tiền...', '13 Dự phòng', '25. Vốn chủ sở hữu')."""
        clean_text = re.sub(r"^[#*>\-\s]+", "", text).strip()
        clean_text = re.sub(r"^(\d{1,2})\.0{1,2}\s+", r"\1. ", clean_text)
        clean_text = re.sub(r"[:\s\.]+$", "", clean_text).strip()

        # Title PHẢI bắt đầu bằng ký tự chữ cái (không phải số) để tránh false-positive
        # với số liệu bảng dạng '20.5 ...' hay '1.234.567 Doanh thu'
        m = re.match(r"^(\d{1,2})[\.:\s\-]+([A-ZÀ-Ỹa-zà-ỹ][A-ZÀ-Ỹa-zà-ỹ0-9\s,–—\-\/]{2,79})$", clean_text)
        if not m:
            # Thử pattern không có dấu phân cách (OCR bỏ dấu chấm): '13 Dự phòng'
            m = re.match(r"^(\d{1,2})\s+([A-ZÀ-Ỹa-zà-ỹ][A-ZÀ-Ỹa-zà-ỹ0-9\s,–—\-\/]{2,79})$", clean_text)
        if not m:
            return None

        num = int(m.group(1))
        title = m.group(2).strip()
        # Khử watermark hoặc ký hiệu OCR dính vào đuôi tiêu đề
        title = re.sub(r"\s+(?:NHH|NH|KP|TN|CY|ÁNI|OCY)$", "", title, flags=re.IGNORECASE).strip()

        # Loại trừ các câu không phải đề mục
        if title.endswith(";") or title.endswith(","):
            return None
        if any(unit in text_low for unit in ["vnd", "triệu đồng", "tỷ đồng", "%"]):
            return None
        if re.search(r"\b(ngày \d+|\d{1,2}/\d{1,2}/\d{4})\b", text_low):
            return None
        if re.search(r"\b\d{1,3}\.\d{3}\b", title):  # chứa số tiền dạng 10.000
            return None

        # Chuẩn hóa lỗi chính tả OCR phổ biến trong tiêu đề mục
        title_normalized = title
        ocr_replacements = [
            (r"\bDụ phong\b", "Dự phòng"),
            (r"\bDu phong\b", "Dự phòng"),
            (r"\bbữu binh\b", "hữu hình"),
            (r"\bbuu binh\b", "hữu hình"),
            (r"\bvũ bình\b", "vô hình"),
            (r"\bvu binh\b", "vô hình"),
            (r"\bdử dang\b", "dở dang"),
            (r"\bdô dang\b", "dở dang"),
            (r"\bphái thu\b", "phải thu"),
            (r"\bphái trả\b", "phải trả"),
            (r"\bphái trá\b", "phải trả"),
            (r"\bphai tra\b", "phải trả"),
            (r"\bphố thông\b", "phổ thông"),
            (r"\bpho thong\b", "phổ thông"),
            (r"\bCơ Sử\b", "Cơ sở"),
            (r"\bngăn hạn\b", "ngắn hạn"),
            (r"\bngãn ban\b", "ngắn hạn"),
            (r"\bdải hạn\b", "dài hạn"),
            (r"\bquân lý\b", "quản lý"),
            (r"\bbản hàng\b", "bán hàng"),
        ]
        for pat, rep in ocr_replacements:
            title_normalized = re.sub(pat, rep, title_normalized, flags=re.IGNORECASE)

        # Guard tính đơn điệu trong cùng một phần La Mã:
        if state.current_roman_num in (4, 5, 6, 8) and state.current_note_num > 0:
            # Nếu số đột ngột rơi về <= 5 trong khi note_num >= 20,
            # khả năng cao là tài liệu đã chuyển sang Phần La Mã tiếp theo mà tiêu đề La Mã bị OCR làm méo mó
            if state.current_note_num >= 20 and num <= 5:
                state.current_note_num = 0
            elif num <= state.current_note_num:
                return None

        # Giới hạn số mục tối đa chính xác theo TT200/2014/TT-BTC
        canonical_max_notes = {
            "NOTE_SEC_GENERAL_INFO": 7,
            "NOTE_SEC_ACCOUNTING_PERIOD": 2,
            "NOTE_SEC_ACCOUNTING_STANDARDS": 5,
            "NOTE_SEC_ACCOUNTING_POLICIES": 30,
            "NOTE_SEC_GOING_CONCERN": 5,
            "NOTE_SEC_BALANCE_SHEET": 35,
            "NOTE_SEC_INCOME_STATEMENT": 15,
            "NOTE_SEC_CASH_FLOW": 6,
            "NOTE_SEC_OTHER_INFO": 10,
        }
        if state.current_canonical_code in canonical_max_notes:
            if num > canonical_max_notes[state.current_canonical_code]:
                return None
        else:
            max_notes_map = {
                1: 7,   # I: 7 mục đặc điểm hoạt động
                2: 2,   # II: 2 mục kỳ kế toán & đơn vị tiền tệ
                3: 5,   # III: 5 mục chuẩn mực & chế độ kế toán
                4: 30,  # IV: 30 mục chính sách kế toán
                5: 35,  # V: 35 mục chính sách khi không hoạt động liên tục
                6: 35,  # VI: 35 mục bổ sung Bảng CĐKT (01→30)
                7: 15,  # VII: 15 mục bổ sung Báo cáo KQKD (1→11)
                8: 6,   # VIII: 6 mục bổ sung Báo cáo LCTT
                9: 10,  # IX: 10 mục thông tin khác
            }
            if state.current_roman_num in max_notes_map and num > max_notes_map[state.current_roman_num]:
                return None

        # Loại bỏ các từ vô nghĩa do watermark/nhiễu OCR đơn từ (ví dụ "NAPHO", "KP", "CHIN")
        words = title_normalized.split()
        if len(words) == 1 and len(title_normalized) <= 6 and title_normalized.isupper():
            return None

        return num, title_normalized

    def _match_decimal_note(self, text: str, text_low: str, state: HierarchyState) -> tuple[str, str] | None:
        """Nhận diện tiểu mục số thập phân (Level 5 - H5: ví dụ '1.1 Các giao dịch...', '19.1 Thay đổi vốn...')."""
        clean_text = re.sub(r"^[#*>\-\s]+", "", text).strip()
        clean_text = re.sub(r"[:\s\.]+$", "", clean_text).strip()
        m = re.match(r"^(\d{1,2}\.\d{1,2})[\.:\s\-]+([A-ZÀ-Ỹa-zà-ỹ][A-ZÀ-Ỹa-zà-ỹ0-9\s,–—\-\/\(\)&'\"]{2,90})$", clean_text)
        if not m:
            return None
        code_str = m.group(1)
        title = m.group(2).strip()
        if title.endswith(";") or title.endswith(","):
            return None
        if any(unit in text_low for unit in ["vnd", "triệu đồng", "tỷ đồng", "%"]):
            return None
        return code_str, title

    def _match_sub_item(self, text: str, text_low: str, state: HierarchyState | None = None) -> tuple[str, str] | None:
        """Nhận diện tiểu mục chữ (ví dụ: '(a) Các công ty con', '(b) Mua lại...', '(c) Đơn vị trực thuộc:')."""
        clean_text = re.sub(r"^[#*>\-\s]+", "", text).strip()
        clean_text = re.sub(r"[:\s\.]+$", "", clean_text).strip()

        # (a), (b), (c), (aa), a), b)...
        m = re.match(r"^\(([a-zđ]{1,2})\)[\s\.:\-]+([A-ZÀ-Ỹa-zà-ỹ0-9\s,–—\-\/\(\)&'\"]{2,100})$", clean_text)
        if not m:
            m = re.match(r"^([a-zđ]{1,2})\)[\s\.:\-]+([A-ZÀ-Ỹa-zà-ỹ0-9\s,–—\-\/\(\)&'\"]{2,100})$", clean_text)
        # Bổ sung: nhận diện trường hợp OCR đọc nhầm "(a)" thành "1." khi tiêu đề rõ ràng là tiểu mục "Phải thu ngắn hạn..."
        if not m and state and state.current_roman_num == 5 and state.current_note_num == 3:
            m_a = re.match(r"^1[\.:\s\-]+(Phải thu\s+ng[ắăâ]n\s+h[ạa]n\s+khác.*)$", clean_text, re.IGNORECASE)
            if m_a:
                sub_code = "a"
                title = m_a.group(1).strip()
                title = re.sub(r"\bngăn hạn\b", "ngắn hạn", title, flags=re.IGNORECASE)
                return sub_code, title

        if not m:
            return None

        sub_code = m.group(1).lower()
        title = m.group(2).strip()

        if title.endswith(";") or title.endswith(","):
            return None
        if any(unit in text_low for unit in ["vnd", "triệu đồng"]):
            return None

        # Chuẩn hóa chính tả OCR cho tiểu mục
        ocr_replacements = [
            (r"\bphố thông\b", "phổ thông"),
            (r"\bpho thong\b", "phổ thông"),
            (r"\bbản hàng\b", "bán hàng"),
            (r"\bban hang\b", "bán hàng"),
            (r"\btiền lài\b", "tiền lãi"),
            (r"\btư cổ tức\b", "từ cổ tức"),
            (r"\bdải hạn\b", "dài hạn"),
            (r"\bngăn hạn\b", "ngắn hạn"),
        ]
        for pat, rep in ocr_replacements:
            title = re.sub(pat, rep, title, flags=re.IGNORECASE)

        return sub_code, title

    def _match_sub_group(self, text: str, text_low: str, state: HierarchyState) -> str | None:
        """
        Nhận diện nhóm/phân mục trực thuộc tiểu mục (Level 6 - H6: ví dụ: 'Các chi nhánh bán hàng',
        'Các nhà máy sản xuất', 'Các kho vận', 'Phòng khám', 'Trung tâm thu mua sữa tươi', 'Dự phòng trợ cấp thôi việc').
        """
        clean = re.sub(r"^[#*>\-\s]+", "", text).strip()
        clean = re.sub(r"[:\s\.]+$", "", clean).strip()

        # Chỉ kích hoạt khi đang ở trong một tiểu mục chữ (Level 5) hoặc mục số (Level 4)
        if not (state.current_sub_code or state.current_note_num > 0):
            return None

        if len(clean) > 60 or len(clean) < 5:
            return None

        if clean.endswith(".") or clean.endswith(";") or clean.endswith(","):
            return None

        if any(unit in text_low for unit in ["vnd", "triệu", "tỷ", "%"]):
            return None

        sub_group_patterns = [
            r"^Các\s+(?:chi\s+nhánh|nhà\s+máy|kho\s+vận|văn\s+phòng|đơn\s+vị|công\s+ty|khoản|quỹ|bộ\s+phận)",
            r"^(?:Phòng\s+khám|Trung\s+tâm\s+thu\s+mua|Dự\s+phòng\s+trợ\s+cấp|Trang\s+trại|Nhà\s+máy)",
        ]
        if any(re.search(pat, clean, re.IGNORECASE) for pat in sub_group_patterns):
            return clean

        return None

    def _maybe_create_major_section(
        self,
        block: ClassifiedBlock,
        match: HeadingMatch,
        state: HierarchyState,
        company: str,
        year: int,
    ) -> Section | None:
        """Tự động chèn Section H2 phân tách giữa Phần BCTC Cốt Lõi và Bản Thuyết Minh."""
        if match.canonical_code in CORE_STATEMENT_CANONICAL and not state.emitted_core_major:
            state.emitted_core_major = True
            sec_id = f"{company.lower()}_{year}_s_part_1_core"
            state.current_major_id = sec_id
            state.current_major_title = "PHẦN 1: BÁO CÁO TÀI CHÍNH CỐT LÕI"
            return Section(
                id=sec_id,
                title="PHẦN 1: BÁO CÁO TÀI CHÍNH CỐT LÕI",
                company=company,
                year=year,
                page_start=block.page,
                page_end=block.page,
                blocks=[],
                section_type="major_part",
                level=2,
                breadcrumb="Báo cáo tài chính > PHẦN 1: BÁO CÁO TÀI CHÍNH CỐT LÕI",
            )

        # PHẦN 2: Thuyết minh chỉ kích hoạt sau khi đã có Core Major (hoặc trang >= 12) và gặp tiêu đề Thuyết minh/La Mã
        if (
            (match.roman_code or match.section_type in ("notes", "numeric_note"))
            and not state.emitted_notes_major
            and (state.emitted_core_major or block.page >= 12)
        ):
            state.emitted_notes_major = True
            sec_id = f"{company.lower()}_{year}_s_part_2_notes"
            state.current_major_id = sec_id
            state.current_major_title = "PHẦN 2: BẢN THUYẾT MINH BÁO CÁO TÀI CHÍNH"
            return Section(
                id=sec_id,
                title="PHẦN 2: BẢN THUYẾT MINH BÁO CÁO TÀI CHÍNH",
                company=company,
                year=year,
                page_start=block.page,
                page_end=block.page,
                blocks=[],
                section_type="major_part",
                level=2,
                breadcrumb="Báo cáo tài chính > PHẦN 2: BẢN THUYẾT MINH BÁO CÁO TÀI CHÍNH",
            )

        return None

    def _resolve_hierarchy(self, match: HeadingMatch, state: HierarchyState) -> tuple[str | None, str]:
        """Xác định parent_id và breadcrumb phân cấp cho từng Section."""
        major_title = state.current_major_title or "Báo cáo tài chính"
        
        if match.level == 2:
            return None, major_title

        if match.level == 3:
            parent_id = state.current_major_id
            breadcrumb = f"{major_title} > {match.title}"
            return parent_id, breadcrumb

        if match.level == 4:
            parent_id = state.current_roman_sec_id or state.current_major_id
            roman_title = state.current_roman_title or "Thuyết minh BCTC"
            breadcrumb = f"{major_title} > {roman_title} > {match.title}"
            return parent_id, breadcrumb

        if match.level == 5:
            parent_id = state.current_note_sec_id or state.current_roman_sec_id or state.current_major_id
            roman_title = state.current_roman_title or "Thuyết minh BCTC"
            note_title = state.current_note_title or "Mục chi tiết"
            breadcrumb = f"{major_title} > {roman_title} > {note_title} > {match.title}"
            return parent_id, breadcrumb

        if match.level == 6:
            parent_id = state.current_sub_sec_id or state.current_note_sec_id or state.current_roman_sec_id or state.current_major_id
            roman_title = state.current_roman_title or "Thuyết minh BCTC"
            note_title = state.current_note_title or "Mục chi tiết"
            sub_title = state.current_sub_title or (f"({state.current_sub_code})" if state.current_sub_code else "")
            if sub_title:
                breadcrumb = f"{major_title} > {roman_title} > {note_title} > {sub_title} > {match.title}"
            else:
                breadcrumb = f"{major_title} > {roman_title} > {note_title} > {match.title}"
            return parent_id, breadcrumb

        return state.current_major_id, f"{major_title} > {match.title}"

    def _update_state(self, match: HeadingMatch, sec_id: str, state: HierarchyState):
        """Cập nhật trạng thái của Hierarchy State Tracker."""
        if match.level == 2:
            state.current_major_id = sec_id
            state.current_major_title = match.title
        elif match.level == 3:
            if match.roman_code:
                state.current_roman = match.roman_code
                state.current_roman_num = ROMAN_CANONICAL.get(match.roman_code, (None, None, 1))[2]
                state.current_roman_title = match.title
                state.current_roman_sec_id = sec_id
                state.current_canonical_code = match.canonical_code or ""
                state.current_note_num = 0
                state.current_note_title = ""
                state.current_sub_code = ""
                state.current_sub_title = ""
        elif match.level == 4:
            state.current_note_sec_id = sec_id
            state.current_note_title = match.title
            m = re.match(r"^(\d+)", match.title)
            if m:
                state.current_note_num = int(m.group(1))
            state.current_sub_code = ""
            state.current_sub_title = ""
        elif match.level == 5:
            state.current_sub_sec_id = sec_id
            state.current_sub_code = match.sub_code or ""
            state.current_sub_title = match.title
        elif match.level == 6:
            pass

    def _preprocess_split_blocks(self, blocks: list[ClassifiedBlock]) -> list[ClassifiedBlock]:
        """
        Tiền xử lý: Nếu một khối văn bản chứa nhiều tiêu đề phân cấp liên tiếp
        (ví dụ: 'L THÔNG TIN DOANH NGHIỆP' và '1. Hình thức sở hữu vốn'),
        tự động phân tách thành các blocks độc lập để mỗi đề mục sở hữu nội dung riêng.
        """
        output: list[ClassifiedBlock] = []
        for cb in blocks:
            if cb.is_table or not cb.content:
                output.append(cb)
                continue

            cleaned = strip_boilerplate_lines(cb.content)
            lines = [l.strip() for l in cleaned.splitlines() if l.strip()]
            if len(lines) <= 1:
                output.append(cb)
                continue

            # Tìm các vị trí dòng là tiêu đề mới (từ dòng 1 trở đi)
            split_indices = []
            for idx in range(1, len(lines)):
                line = lines[idx]
                line_clean = re.sub(r"^[#*>\-\s]+", "", line).strip()
                line_low = line_clean.lower()
                slug_line = slugify_vietnamese(line_clean)
                # Kiểm tra xem dòng có phải là tiêu đề số, La Mã, hoặc tiểu mục chữ
                is_heading_candidate = (
                    re.match(r"^\d{1,2}(?:\.0{1,2}|[\.:\s\-])\s*[A-ZÀ-Ỹ]", line_clean)
                    or re.match(r"^\d{1,2}\.\d{1,2}[\.:\s\-]\s*[A-ZÀ-Ỹ]", line_clean)
                    or re.match(r"^[IVXLCDM]+(?:[\.:\s]\s*|\s+)[A-ZÀ-Ỹ]", line_clean)
                    or re.match(r"^\([a-zđ]{1,2}\)[\s\.:\-]+[A-ZÀ-Ỹ]", line_clean)
                    or re.match(r"^[a-zđ]\)[\s\.:\-]+[A-ZÀ-Ỹ]", line_clean)
                    or re.match(r"^Các\s+(?:chi\s+nhánh|nhà\s+máy|kho\s+vận|văn\s+phòng|đơn\s+vị|công\s+ty|khoản|quỹ)", line_clean)
                    or re.match(r"^(?:Phòng\s+khám|Trung\s+tâm\s+thu\s+mua|Dự\s+phòng\s+trợ\s+cấp)", line_clean)
                    or (
                        len(line_clean) < 90
                        and any(
                            kw in slug_line
                            for kw in [
                                "chuan_muc_va_che_do_ke_toan",
                                "ky_ke_toan_va_don_vi_tien_te",
                                "chinh_sach_ke_toan",
                                "thong_tin_bo_sung_cho_cac_khoan_muc",
                                "nhung_thong_tin_khac",
                                "thong_tin_doanh_nghiep",
                                "dac_diem_hoat_dong",
                            ]
                        )
                    )
                )
                if is_heading_candidate:
                    # Loại trừ các trường hợp dòng ngày tháng hoặc đơn vị tiền tệ
                    if not any(unit in line_low for unit in ["vnd", "triệu đồng", "tỷ đồng", "%"]):
                        if not re.search(r"\b(ngày \d+|\d{1,2}/\d{1,2}/\d{4})\b", line_low):
                            split_indices.append(idx)

            if not split_indices:
                output.append(cb)
                continue

            # Thực hiện phân tách
            prev_idx = 0
            split_indices.append(len(lines))
            for chunk_i, split_idx in enumerate(split_indices):
                sub_lines = lines[prev_idx:split_idx]
                if sub_lines:
                    sub_content = "\n".join(sub_lines)
                    from src.models import ParsedBlock
                    new_pb = ParsedBlock(
                        block_id=f"{cb.block_id}_sub_{chunk_i}",
                        block_type=cb.block.block_type,
                        page=cb.page,
                        content=sub_content,
                        bbox=cb.block.bbox,
                        source=cb.block.source,
                        metadata=cb.block.metadata.copy() if cb.block.metadata else {},
                    )
                    new_cb = ClassifiedBlock(
                        block=new_pb,
                        block_type=cb.block_type,
                        target=list(cb.target),
                        confidence=cb.confidence,
                        classification_method=cb.classification_method,
                        reasoning=cb.reasoning,
                    )
                    output.append(new_cb)
                prev_idx = split_idx

        return output
