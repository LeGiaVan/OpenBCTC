"""
triage_bctc.py — CLI Tool chạy LangGraph Ingestion & Triage Agent cho Báo cáo tài chính.
Phân luồng tự động:
  - Báo cáo tài chính cốt lõi -> Vision LLM + Fact Extractor + Anti-GIGO Verifier + Formula Engine -> SQLite
  - Thuyết minh BCTC -> Local Fast OCR (RapidOCR/ONNX) -> Chunks văn bản cho RAG (0 API calls)
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Đảm bảo import được module gốc
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Khắc phục triệt để lỗi mã hóa tiếng Việt trên Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.agents.ingestion_graph import IngestionAgent

# Đồng bộ logging vào sys.stdout để tránh hiện tượng log và print chèn dòng nhau trên Windows terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("FinAudit.TriageCLI")


def print_banner(text: str) -> None:
    print("\n" + "=" * 85)
    print(f"  {text}")
    print("=" * 85)


def main() -> None:
    parser = argparse.ArgumentParser(description="FinAudit AI — LangGraph Ingestion & Triage Agent CLI")
    parser.add_argument("--pdf", type=str, required=True, help="Đường dẫn file PDF BCTC (ví dụ: vnm.pdf)")
    parser.add_argument("--company", type=str, default="VNM", help="Mã doanh nghiệp (mặc định: VNM)")
    parser.add_argument("--year", type=int, default=2024, help="Năm tài chính (mặc định: 2024)")
    parser.add_argument(
        "--notes-limit",
        type=int,
        default=3,
        help="Số trang thuyết minh bóc tách bằng Local OCR (0: bỏ qua, N: N trang đầu, -1: toàn bộ). Mặc định: 3",
    )
    parser.add_argument("--export-md", type=str, default="", help="Đường dẫn file Markdown xuất kết quả")
    parser.add_argument("--export-manifest", type=str, default="", help="Đường dẫn file JSON Observability Manifest")
    parser.add_argument("--db", type=str, default="data/finaudit.db", help="Đường dẫn CSDL SQLite")
    parser.add_argument("--no-cache", action="store_true", help="Bỏ qua checkpoint cache, ép chạy lại OCR mới")
    parser.add_argument(
        "--page",
        type=int,
        default=0,
        help="Chỉ định test 1 trang cụ thể (1-indexed). Tiết kiệm thời gian, không cần chạy cả PDF.",
    )

    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Lỗi: Không tìm thấy file PDF tại: {pdf_path.resolve()}")
        sys.exit(1)

    # Chế độ test nhanh 1 trang cụ thể
    if args.page > 0:
        import subprocess
        cmd = [
            sys.executable,
            "scripts/test_page.py",
            "--pdf", str(pdf_path),
            "--page", str(args.page),
            "--company", args.company,
            "--year", str(args.year),
        ]
        if args.no_cache:
            cmd.append("--no-cache")
        subprocess.run(cmd)
        return

    export_md = args.export_md or f"outputs/{args.company.lower()}_{args.year}_triaged.md"
    export_manifest = args.export_manifest or f"outputs/{args.company.lower()}_{args.year}_manifest.json"

    use_cache = not args.no_cache
    print_banner(f"KÍCH HOẠT LANGGRAPH INGESTION AGENT: {pdf_path.name} [{args.company} {args.year}]")
    print(f"  * CSDL SQLite:               {Path(args.db).resolve()}")
    print(f"  * File xuất Markdown:        {Path(export_md).resolve()}")
    print(f"  * File Observability Report: {Path(export_manifest).resolve()}")
    print(f"  * Giới hạn trang Thuyết minh: {args.notes_limit if args.notes_limit >= 0 else 'Toàn bộ (Full)'} trang")
    print(f"  * Sử dụng Checkpoint Cache:  {'CÓ' if use_cache else 'KHÔNG (--no-cache)'}")

    agent = IngestionAgent()
    state = agent.run(
        pdf_path=str(pdf_path),
        company=args.company,
        year=args.year,
        notes_limit=args.notes_limit,
        output_markdown=export_md,
        db_path=args.db,
        use_cache=use_cache,
    )

    doc_struct = state.get("doc_structure")
    facts = state.get("financial_facts", [])
    report = state.get("audit_report")
    ratios = state.get("ratios", [])
    summary = state.get("summary_metrics", {})
    logs = state.get("logs", [])

    print_banner("BƯỚC 1: KẾT QUẢ TRINH SÁT MỤC LỤC (TOC INSPECTOR)")
    if doc_struct:
        print(doc_struct.summary())

    print_banner("BƯỚC 2: BÁO CÁO CỐT LÕI (VISION LLM + ANTI-GIGO AUDITING)")
    print(f"  * Số Facts tài chính bóc tách:  {len(facts)}")
    if report:
        print(f"  * Trạng thái cân đối kế toán:  {'✓ ĐẠT CHUẨN' if report.is_balanced else '❌ PHÁT HIỆN SAI LỆCH'}")
        print(f"  * Số phép kiểm tra cân khớp:   {len(report.passed_checks)} / {report.total_checks}")
        for p in report.passed_checks:
            print(f"      [PASSED] {p}")
        if report.failed_checks:
            for f in report.failed_checks:
                print(f"      [FAILED] {f}")

    print_banner("BƯỚC 3: CÔNG THỨC ĐỊNH LƯỢNG — 13 CHỈ SỐ TÀI CHÍNH CỐT LÕI")
    if ratios:
        print(f"\n{'Tên chỉ số':<24} | {'Phân nhóm':<16} | {'Giá trị':<10} | {'Công thức':<35}")
        print("-" * 90)
        for r in ratios:
            print(f"{r.ratio_name:<24} | {r.ratio_category:<16} | {r.value:<10.4f} | {r.formula:<35}")
    else:
        print("  (Chưa đủ dữ liệu để tính đầy đủ các tỷ số - cần đầy đủ trang Bảng CĐKT và KQKD)")

    print_banner("BƯỚC 4: THUYẾT MINH BCTC (LOCAL VIETNAMESE OCR CHO RAG)")
    print(f"  * Số blocks văn bản (narrative): {summary.get('notes_blocks_count', 0)}")
    print("  * Cơ chế: VietOCR + PaddleOCR DBNet (100% Offline, 0 tokens, tiếng Việt chuẩn có dấu)")

    # 5. XUẤT OBSERVABILITY MANIFEST (JSON AUDIT TRAIL)
    notes_pages_extracted = []
    if doc_struct and doc_struct.notes_pages:
        notes_pages_extracted = (
            doc_struct.notes_pages if args.notes_limit < 0 else doc_struct.notes_pages[: args.notes_limit]
        )

    manifest_data = {
        "timestamp": datetime.now().isoformat(),
        "document": str(pdf_path.name),
        "company": args.company,
        "year": args.year,
        "status": state.get("status"),
        "routing": {
            "total_pages": doc_struct.total_pages if doc_struct else 0,
            "toc_found": doc_struct.toc_found if doc_struct else False,
            "toc_page": doc_struct.toc_page if doc_struct else 0,
            "page_offset": doc_struct.page_offset if doc_struct else 0,
            "intro_pages": doc_struct.intro_pages if doc_struct else [],
            "core_statement_pages": doc_struct.core_statement_pages if doc_struct else [],
            "notes_pages_total": len(doc_struct.notes_pages) if doc_struct else 0,
            "notes_pages_extracted": notes_pages_extracted,
        },
        "branch_1_core": {
            "engine": "Vision LLM (Google Gemini Flash Lite / Fast-Failover)",
            "pages": doc_struct.core_statement_pages if doc_struct else [],
            "blocks_count": summary.get("core_blocks_count", 0),
            "financial_facts_count": len(facts),
            "anti_gigo_audit": {
                "is_balanced": report.is_balanced if report else False,
                "passed_checks": report.passed_checks if report else [],
                "failed_checks": report.failed_checks if report else [],
            },
            "financial_ratios": {r.ratio_name: r.value for r in ratios},
            "target_storage": "SQLite (tables: financial_statements, financial_facts, financial_ratios)",
        },
        "branch_2_notes": {
            "engine": "Local Offline Vietnamese OCR (PaddleOCR DBNet ONNX + VietOCR Seq2Seq)",
            "pages": notes_pages_extracted,
            "blocks_count": summary.get("notes_blocks_count", 0),
            "token_cost": 0,
            "api_calls": 0,
            "execution_mode": "100% Offline Local CPU",
            "target_storage": "Markdown / Vector DB Chunks",
        },
        "artifacts": {
            "markdown_triaged": str(Path(export_md).resolve()),
            "sqlite_db": str(Path(args.db).resolve()),
            "manifest_json": str(Path(export_manifest).resolve()),
            "cache_dir_core": f"data/cache/ocr/{args.company}_{args.year}/",
            "cache_dir_notes": f"data/cache/notes/{args.company}_{args.year}/",
        },
        "parent_child_rag_catalog": state.get("hierarchical_sections", []),
        "langsmith_observability": {
            "enabled": os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true",
            "project": os.getenv("LANGCHAIN_PROJECT", "FinAudit_AI"),
        },
        "logs": logs,
    }

    manifest_path = Path(export_manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)

    # 6. IN BẢNG ĐO LƯỜNG OBSERVABILITY
    core_pages_count = len(doc_struct.core_statement_pages if doc_struct else [])
    notes_pages_count = len(notes_pages_extracted)
    core_blocks_str = f"{summary.get('core_blocks_count', 0)} blocks"
    notes_blocks_str = f"{summary.get('notes_blocks_count', 0)} blocks"
    core_pages_str = f"{core_pages_count} trang"
    notes_pages_str = f"{notes_pages_count} trang"

    print_banner("BẢNG QUAN SÁT & ĐO LƯỜNG TIẾN TRÌNH INGESTION (OBSERVABILITY DASHBOARD)")
    print(f"{'Chỉ tiêu Observability':<30} | {'Nhánh 1: Core Statements':<25} | {'Nhánh 2: Thuyết minh RAG':<25}")
    print("-" * 88)
    print(f"{'Engine bóc tách':<30} | {'Vision LLM (Gemini)':<25} | {'VietOCR + DBNet (Offline)':<25}")
    print(f"{'Số trang xử lý':<30} | {core_pages_str:<25} | {notes_pages_str:<25}")
    print(f"{'Token tiêu hao / Quota API':<30} | {'~3.5k tokens (0 nếu Cache)':<25} | {'0 Tokens (100% Free)':<25}")
    print(f"{'Số blocks trích xuất':<30} | {core_blocks_str:<25} | {notes_blocks_str:<25}")
    print(f"{'Chốt chặn kiểm toán':<30} | {'Anti-GIGO 5 Invariants':<25} | {'Watermark & Noise Filter':<25}")
    print(f"{'Đích lưu trữ dữ liệu':<30} | {'SQLite DB (Facts/Ratios)':<25} | {'Markdown (Parent Chunks)':<25}")
    print(f"{'Checkpoint Cache đĩa':<30} | {'data/cache/ocr/...':<25} | {'data/cache/notes/...':<25}")

    print("\n  * Kênh quan sát (Observability Channels):")
    print(f"    [1] Báo cáo chi tiết JSON Manifest: {manifest_path.resolve()}")
    print(f"    [2] Tài liệu Markdown hợp nhất:     {Path(export_md).resolve()}")
    print(f"    [3] Cơ sở dữ liệu SQLite:          {Path(args.db).resolve()}")
    ls_status = "ĐÃ BẬT (Live Streaming DAG)" if manifest_data["langsmith_observability"]["enabled"] else "CHƯA BẬT (Thiết lập LANGCHAIN_TRACING_V2=true trong .env để xem trace trực quan)"
    print(f"    [4] LangSmith LLMOps Tracing:      {ls_status}")
    print("=" * 85 + "\n")


if __name__ == "__main__":
    main()

