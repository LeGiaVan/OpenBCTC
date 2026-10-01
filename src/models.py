"""
models.py — Data Contracts và Schemas cho toàn bộ Ingestion Pipeline của FinAudit AI.
Sử dụng Pydantic v2 để đảm bảo validation nghiêm ngặt, type safety và khả năng serialization.
"""

from enum import StrEnum
# Vừa là Enum, vừa là String
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BlockType(StrEnum):
    """Phân loại nghiệp vụ cho từng block trong BCTC."""
    FINANCIAL_STATEMENT = "FINANCIAL_STATEMENT"  # Bảng Cân đối kế toán, KQKD, LCTT chính
    NUMERIC_NOTE = "NUMERIC_NOTE"                # Thuyết minh chi tiết số liệu (khoản mục cụ thể)
    NARRATIVE = "NARRATIVE"                      # Đoạn văn thuyết minh ngữ nghĩa thuần
    POLICY = "POLICY"                            # Chính sách và nguyên tắc kế toán áp dụng
    MDA = "MDA"                                  # Báo cáo/đánh giá của Ban Giám đốc, HĐQT
    MIXED = "MIXED"                              # Bảng kết hợp lời văn dẫn dắt quan trọng
    NARRATIVE_TABLE = "NARRATIVE_TABLE"          # Bảng phi số liệu (danh sách thành viên, mô tả)


class StorageTarget(StrEnum):
    """Đích đến lưu trữ sau khi phân loại block."""
    SQL = "sql"        # Trích xuất facts có cấu trúc vào SQL DB
    VECTOR = "vector"  # Chunking và embed vào Vector DB để ngữ nghĩa hóa


class ParsedBlock(BaseModel):
    """Đại diện cho 1 khối văn bản hoặc bảng biểu được bóc tách từ PDF."""
    block_id: str                                          # Định danh block: "p{page}_b{index}"
    block_type: Literal["table", "text"]                  # Loại block nguyên bản từ parser
    page: int                                              # Số thứ tự trang trong tài liệu (1-indexed)
    content: str                                           # Nội dung: Markdown table nếu là bảng, text nếu là văn bản
    bbox: tuple[float, float, float, float] | None = None  # (x0, top, x1, bottom) tọa độ trên trang
    source: Literal["pdfplumber", "ocr", "local_ocr"] = "pdfplumber"    # Nguồn gốc trích xuất: pdfplumber, vision ocr, hoặc local_ocr
    metadata: dict[str, Any] = Field(default_factory=dict) # Metadata: headers, num_rows, num_cols, raw_table, unit...

    model_config = ConfigDict(frozen=False)
    # Cho phép sửa (Mutable) sau khi tạo Object

    @property 
    # Chuyển hàm thành Biến
    def is_table(self) -> bool:
        return self.block_type == "table"

    @property
    def num_rows(self) -> int:
        return self.metadata.get("num_rows", 0)

    @property
    def num_cols(self) -> int:
        return self.metadata.get("num_cols", 0)

    def get_header_row(self) -> str:
        """Lấy chuỗi tiêu đề của bảng (nếu có) để phân tích keyword."""
        headers = self.metadata.get("headers", [])
        if isinstance(headers, list) and headers:
            return " ".join(str(h) for h in headers if h)
        return ""


class ClassifiedBlock(BaseModel):
    """
    Khối văn bản/bảng biểu sau khi qua Block Classifier.
    Đây là Data Contract cốt lõi quyết định block nào vào SQL, block nào vào Vector DB.
    """
    block: ParsedBlock
    block_type: BlockType
    target: list[StorageTarget]
    confidence: float = Field(ge=0.0, le=1.0, description="Độ tin cậy của nhãn phân loại (0.0 - 1.0)")
    classification_method: Literal["rule_based", "llm_fallback"]
    reasoning: str = ""

    breadcrumb: str = ""                                   # Đường dẫn phân cấp đề mục (Breadcrumb)
    heading_level: int = 0                                  # 0: nội dung body, 2-5: tiêu đề tương ứng H2-H5

    model_config = ConfigDict(frozen=False)

    @property
    def block_id(self) -> str:
        return self.block.block_id

    @property
    def page(self) -> int:
        return self.block.page

    @property
    def content(self) -> str:
        return self.block.content

    @property
    def is_sql_target(self) -> bool:
        return StorageTarget.SQL in self.target

    @property
    def is_vector_target(self) -> bool:
        return StorageTarget.VECTOR in self.target

    @property
    def is_table(self) -> bool:
        return getattr(self.block, "is_table", False)


class Section(BaseModel):
    """
    Section là đơn vị phân đoạn ngữ nghĩa (không phụ thuộc vào số trang).
    Được nhận diện dựa trên cấu trúc phân cấp cây BCTC (TT 200/2014/TT-BTC).
    Là đơn vị hạt nhân để xây dựng Parent Chunk & Child Chunks trong Parent-Child Retriever.
    """
    id: str                                                 # Semantic id, ví dụ: "vnm_2024_s_v_19_von_chu_so_huu"
    title: str                                              # Tiêu đề chuẩn hóa, ví dụ: "19. Vốn chủ sở hữu"
    company: str | None = None
    year: int | None = None
    page_start: int
    page_end: int
    blocks: list[ClassifiedBlock] = Field(default_factory=list)
    section_type: str | None = None                         # "core_statement", "notes_part", "note_item", etc.
    level: int = 3                                          # 2: H2 (Phần lớn), 3: H3 (La Mã / Core), 4: H4 (Mục số), 5: H5 (Tiểu mục)
    parent_id: str | None = None                            # ID của Section cha
    canonical_code: str | None = None                       # Mã khái niệm chuẩn (CORE_BALANCE_SHEET, NOTE_ITEM_EQUITY...)
    reference_code: str | None = None                       # Mã tham chiếu kế toán ("V.19", "VI.1"...)
    breadcrumb: str = ""                                    # Đường dẫn phân cấp ("Thuyết minh BCTC > V. BCĐKT > 19. Vốn CSH")
    child_metadata: dict[str, Any] = Field(default_factory=dict) # Metadata phục vụ vector/hybrid search
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=False)

    @property
    def total_blocks(self) -> int:
        return len(self.blocks)

    def get_full_text(self) -> str:
        """Ghép toàn bộ nội dung markdown của các blocks trong section."""
        return "\n\n".join(b.content for b in self.blocks)


class ParsedDocument(BaseModel):
    """Đại diện cho toàn bộ tài liệu BCTC sau khi parsing, phân loại và phân đoạn."""
    company: str
    year: int
    total_pages: int
    blocks: list[ParsedBlock] = Field(default_factory=list)
    classified_blocks: list[ClassifiedBlock] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=False)
    # Cho phép sửa, Mutable

    def to_markdown(self, include_metadata_header: bool = True, include_page_tags: bool = True) -> str:
        """
        Xuất toàn bộ tài liệu BCTC thành một văn bản Markdown (.md) chuẩn GitHub Flavored Markdown.
        - Phân cấp tiêu đề thứ bậc (#, ##, ###, ####, #####) chuẩn TT 200
        - Giữ nguyên cấu trúc bảng biểu Markdown Table
        - Tự động thanh lọc rác hành chính lặp lại
        """
        lines: list[str] = []

        if include_metadata_header:
            lines.append(f"# BÁO CÁO TÀI CHÍNH — {self.company.upper()} ({self.year})")
            lines.append("")
            lines.append(
                f"> **Doanh nghiệp:** {self.company.upper()} | **Năm tài chính:** {self.year} | "
                f"**Tổng số trang:** {self.total_pages} | **Số khối trích xuất:** {len(self.blocks)}"
            )
            lines.append("")
            lines.append("---")
            lines.append("")

        from src.parser.ocr_postprocess import filter_noise_and_images, strip_boilerplate_lines

        def _demote_inner_headings(text: str, parent_level: int) -> str:
            """
            Chuẩn hóa các heading markdown (##, ###...) bên trong nội dung khối văn bản.
            Đảm bảo không bao giờ vượt cấp hoặc ngang cấp với tiêu đề mục cha (parent_level).
            Ví dụ: nếu parent_level == 4 (#### 4. Cấu trúc Tập đoàn),
            thì bất kỳ '## Các chi nhánh bán hàng' nào bên trong nội dung cũng sẽ được
            hạ cấp xuống ít nhất cấp 5 (#####) hoặc 6 (######) hoặc in đậm nếu vượt quá cấp 6.
            """
            out_lines = []
            for line in text.splitlines():
                m = re.match(r"^(#{1,6})\s+(.*)$", line)
                if m:
                    hashes, title = m.groups()
                    current_lvl = len(hashes)
                    if current_lvl <= parent_level:
                        target_lvl = min(6, parent_level + 1)
                        if target_lvl <= 6 and parent_level < 6:
                            new_hashes = "#" * target_lvl
                            out_lines.append(f"{new_hashes} {title}")
                        else:
                            out_lines.append(f"**{title}**")
                    else:
                        out_lines.append(line)
                else:
                    out_lines.append(line)
            return "\n".join(out_lines)

        if self.sections:
            for sec in self.sections:
                page_info = f"Trang {sec.page_start}" if sec.page_start == sec.page_end else f"Trang {sec.page_start}–{sec.page_end}"
                heading_hashes = "#" * max(2, min(6, sec.level))
                lines.append(f"{heading_hashes} {sec.title}")
                if include_page_tags and sec.level <= 3:
                    lines.append(f"*({page_info})*")
                lines.append("")

                first_block = True
                for cb in sec.blocks:
                    content = cb.content.strip()
                    if not cb.is_table:
                        content = filter_noise_and_images(content)
                        content = strip_boilerplate_lines(content)
                        if first_block and content:
                            c_lines = content.splitlines()
                            f_line = c_lines[0].strip()
                            f_clean = re.sub(r"^[#*>\-\s]+", "", f_line).strip().lower()
                            t_clean = sec.title.strip().lower()
                            # Khử lặp lại tiêu đề (chính xác hoặc tiền tố/hậu tố)
                            if (
                                f_clean == t_clean
                                or f_clean.startswith(t_clean)
                                or t_clean.startswith(f_clean)
                                or f_clean in ("l thông tin doanh nghiệp", "i. thông tin doanh nghiệp", "thông tin doanh nghiệp")
                            ):
                                content = "\n".join(c_lines[1:]).strip()
                        if content:
                            content = _demote_inner_headings(content, parent_level=sec.level)
                    else:
                        content = filter_noise_and_images(content)
                    if content:
                        lines.append(content)
                        lines.append("")
                    first_block = False

                if sec.level <= 3:
                    lines.append("---")
                    lines.append("")
        else:
            current_page = None
            for b in self.blocks:
                if include_page_tags and b.page != current_page:
                    current_page = b.page
                    lines.append(f"### Trang {current_page}")
                    lines.append("")
                content = b.content.strip()
                if not b.is_table:
                    content = filter_noise_and_images(content)
                    content = strip_boilerplate_lines(content)
                else:
                    content = filter_noise_and_images(content)
                if content:
                    lines.append(content)
                    lines.append("")

        return "\n".join(lines).strip()


class VerificationStatus(StrEnum):
    """Trạng thái kiểm toán số học đối với Fact tài chính."""
    VERIFIED = "VERIFIED"                                              # Đã xác thực bằng phương trình kế toán cân (sai số < 0.01%)
    VERIFIED_AFTER_ZOOM_CORRECTION = "VERIFIED_AFTER_ZOOM_CORRECTION"  # Đã tự động sửa lỗi và xác thực thành công nhờ Vision-LLM Zoom
    DISCREPANCY = "DISCREPANCY"                                        # Phát hiện sai lệch số học trong phương trình
    UNCHECKED = "UNCHECKED"                                            # Khoản mục không thuộc phương trình cộng dồn (thuyết minh lẻ)


class FinancialFact(BaseModel):
    """
    Thực thể Fact tài chính nguyên tử được trích xuất từ BCTC để lưu vào SQL Database.
    Gắn liền với provenance_id và trạng thái kiểm toán số học (Verification Status).
    """
    id: str                                                  # "VNM_2024_p7_t1_r3"
    prov_id: str                                             # Mã truy vết nguồn gốc: "VNM_2024_p7_t1_r3"
    concept: str                                             # Canonical concept: "TOTAL_ASSETS", "CASH"...
    standard_code: str = ""                                  # Mã số chuẩn TT 200: "100", "110", "270"...
    raw_label: str                                           # Tên khoản mục nguyên bản: "TỔNG CỘNG TÀI SẢN"
    value: float                                             # Giá trị số thực
    unit: str = "VND"                                        # "VND", "TRIEU_DONG", "TY_DONG"
    period: str = "2024"                                     # Năm hoặc kỳ: "2024", "2023"
    period_type: Literal["current", "previous"] = "current"  # Kỳ này / kỳ trước
    company: str = "DOANH_NGHIEP"                            # Mã công ty
    year: int = 2024                                         # Năm tài chính
    page: int = 1                                            # Trang tài liệu
    table_id: str = "t1"                                     # Định danh bảng
    row_label: str = ""                                      # Tên hàng
    confidence: float = 1.0                                  # Độ tin cậy trích xuất
    source: Literal["pdfplumber", "ocr"] = "pdfplumber"      # Nguồn bóc tách
    verification_status: VerificationStatus = VerificationStatus.UNCHECKED
    verification_detail: str = ""                            # Chi tiết kiểm toán phương trình

    model_config = ConfigDict(frozen=False)


class FinancialRatio(BaseModel):
    """Chỉ số tài chính tính toán deterministic bằng Python Formula Engine."""
    id: str                                                  # "VNM_2024_current_ratio"
    company: str
    year: int
    ratio_name: str                                          # "current_ratio", "roe", "gross_margin"...
    ratio_category: str                                      # "liquidity", "solvency", "profitability", "efficiency"
    value: float                                             # Giá trị tính được
    formula: str                                             # Mô tả công thức: "CURRENT_ASSETS / CURRENT_LIABILITIES"
    input_prov_ids: list[str] = Field(default_factory=list)  # Danh sách prov_id của các facts đầu vào
    is_deterministic: bool = True                            # Luôn là True vì tính bằng code Python, không do LLM sinh

    model_config = ConfigDict(frozen=False)


class VerificationReport(BaseModel):
    """Báo cáo kết quả kiểm toán số học toàn diện cho 1 BCTC."""
    company: str
    year: int
    is_balanced: bool = True
    total_checks: int = 0
    passed_checks: list[str] = Field(default_factory=list)
    failed_checks: list[str] = Field(default_factory=list)
    discrepancies: list[dict[str, Any]] = Field(default_factory=list)
    correction_history: list[dict[str, Any]] = Field(default_factory=list)  # Lịch sử tự sửa lỗi qua Vision Zoom
    summary: str = ""

    model_config = ConfigDict(frozen=False)
