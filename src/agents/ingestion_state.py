"""
ingestion_state.py — Định nghĩa trạng thái (State) cho LangGraph Ingestion & Triage Agent.
"""

from typing import Any, TypedDict
# TypedDict bản chất là 1 Dict nhưng có TypeHint

from src.agents.toc_inspector import DocumentStructure
from src.engine.formula_engine import FinancialRatio
from src.models import FinancialFact, ParsedBlock
from src.verifier.accounting_verifier import VerificationReport


class IngestionState(TypedDict, total=False):
    """Trạng thái luân chuyển giữa các node trong LangGraph Ingestion Agent."""

    # 1. Tham số đầu vào
    pdf_path: str
    company: str
    year: int
    db_path: str
    notes_limit: int  # 0: Không parse thuyết minh, N: Parse N trang đầu, -1: Parse toàn bộ
    output_markdown_path: str
    use_cache: bool  # True: nạp từ checkpoint cache nếu có, False: ép OCR lại từ đầu

    # 2. Thông tin phân loại tài liệu & cấu trúc mục lục
    pdf_type: str  # "native" | "scanned" | "hybrid"
    page_types: dict[int, str]  # {1: "scanned", 2: "text", ...}
    doc_structure: DocumentStructure | None

    # 3. Kết quả phân luồng trích xuất
    core_blocks: list[ParsedBlock]
    notes_blocks: list[ParsedBlock]
    all_blocks: list[ParsedBlock]

    # 4. Kiểm toán Anti-GIGO và Tỷ số tài chính (Nhánh Core)
    financial_facts: list[FinancialFact]
    audit_report: VerificationReport | None
    ratios: list[FinancialRatio]

    # 5. Metadata điều phối & Parent-Child RAG Catalog
    hierarchical_sections: list[dict[str, Any]]
    status: str
    logs: list[str]
    summary_metrics: dict[str, Any]

    # 6. Kiểm tra bảng biểu & Human-in-the-Loop Review (HITL Table Editor)
    interactive_review: bool  # True: khởi động giao diện HITL Table Reviewer (serve_md_editor), False: tự động
    table_audit_report: dict[str, Any]  # Kết quả kiểm toán cấu trúc & chất lượng bảng biểu
    table_crops_dir: str  # Thư mục lưu trữ ảnh crop bảng độ phân giải cao
    final_markdown_path: str  # Đường dẫn file Markdown sau khi rà soát/sửa chữa bảng biểu
