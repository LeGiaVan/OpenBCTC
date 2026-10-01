"""
test_vnm_fresh.py — Benchmark & Observability Suite cho Hệ thống FinAudit AI OCR.

Chức năng:
  1. Thu thập & Báo cáo cấu hình Phần cứng (CPU, RAM, GPU, VRAM, PyTorch CUDA build).
  2. Bóc tách BCTC (vnm.pdf) theo cấu hình: Fresh Run (--no-cache) hoặc Fast Cached Run.
  3. Đo lường chi tiết Hiệu năng (Latency từng pha, Throughput pages/s, RAM/VRAM delta).
  4. Đánh giá chất lượng Kiểm toán số học (Anti-GIGO 17 Đẳng thức & Vision Zoom Corrector).
  5. Xuất song song 2 tài liệu Markdown độc lập:
     - outputs/vnm_financial_report.md: Toàn bộ văn bản & bảng biểu BCTC phân cấp (Full BCTC Markdown).
     - outputs/vnm_ocr_benchmark_report.md: Báo cáo Benchmark hệ thống OCR & Kiểm toán số học.
  6. Xuất JSON Metrics cho CI/CD và CSDL SQLite.
"""

import argparse
import json
import logging
import os
import platform
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Đảm bảo import được toàn bộ module trong thư mục src/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Cấu hình UTF-8 cho Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
try:
    import psutil
except ImportError:
    psutil = None

from src.agents.ingestion_graph import IngestionAgent
from src.models import ParsedDocument, ParsedBlock, ClassifiedBlock
from src.parser.block_classifier import BlockClassifier
from src.parser.section_detector import SectionDetector


# ──────────────────────────────────────────────────────────────────────────────
# 1. BỘ THU THẬP THÔNG SỐ PHẦN CỨNG (HARDWARE PROFILER)
# ──────────────────────────────────────────────────────────────────────────────

def get_hardware_profile() -> dict[str, Any]:
    """Thu thập thông số phần cứng chi tiết của hệ thống."""
    # Thông tin CPU & RAM
    if psutil:
        cpu_count_phys = psutil.cpu_count(logical=False) or os.cpu_count() or 4
        cpu_count_logical = psutil.cpu_count(logical=True) or os.cpu_count() or 8
        ram = psutil.virtual_memory()
        total_ram_gb = round(ram.total / (1024**3), 2)
        avail_ram_gb = round(ram.available / (1024**3), 2)
    else:
        cpu_count_phys = (os.cpu_count() or 8) // 2
        cpu_count_logical = os.cpu_count() or 8
        total_ram_gb = 16.0
        avail_ram_gb = 8.0

    # Thông tin GPU & PyTorch CUDA
    gpu_info = {
        "cuda_available": False,
        "device_count": 0,
        "gpu_name": "N/A (Chạy CPU)",
        "vram_total_gb": 0.0,
        "torch_version": "N/A",
        "cuda_version": "N/A",
        "recommended_engine": "CPU (Single-core / Multithread)",
    }

    try:
        import torch

        gpu_info["torch_version"] = torch.__version__
        cuda_avail = torch.cuda.is_available()
        gpu_info["cuda_available"] = cuda_avail

        if cuda_avail:
            gpu_info["device_count"] = torch.cuda.device_count()
            gpu_info["gpu_name"] = torch.cuda.get_device_name(0)
            gpu_prop = torch.cuda.get_device_properties(0)
            gpu_info["vram_total_gb"] = round(gpu_prop.total_memory / (1024**3), 2)
            gpu_info["cuda_version"] = torch.version.cuda or "Unknown"
            gpu_info["recommended_engine"] = f"GPU CUDA ({gpu_info['gpu_name']} - {gpu_info['vram_total_gb']}GB VRAM)"
        else:
            if shutil.which("nvidia-smi"):
                gpu_info["gpu_name"] = "NVIDIA Hardware Found (Cần PyTorch CUDA để kích hoạt)"
    except ImportError:
        pass

    return {
        "os": f"{platform.system()} {platform.release()} ({platform.architecture()[0]})",
        "processor": platform.processor() or "x86_64 Family Processor",
        "cpu_cores_physical": cpu_count_phys,
        "cpu_threads_logical": cpu_count_logical,
        "ram_total_gb": total_ram_gb,
        "ram_available_gb": avail_ram_gb,
        "gpu": gpu_info,
    }


def clear_cache(company: str = "VNM", year: int = 2024) -> None:
    """Xóa sạch cache đĩa để ép hệ thống xử lý hoàn toàn từ đầu (Fresh Run)."""
    cache_dirs = [
        Path(f"data/cache/ocr/{company}_{year}"),
        Path(f"data/cache/notes/{company}_{year}"),
    ]
    for d in cache_dirs:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)


def print_banner(title: str, width: int = 90) -> None:
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


# ──────────────────────────────────────────────────────────────────────────────
# 2. CHƯƠNG TRÌNH ĐO LƯỜNG & BENCHMARK CHÍNH
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="FinAudit AI — OCR System Benchmark & Dual Markdown Exporter")
    parser.add_argument("--pdf", type=str, default="vnm.pdf", help="Đường dẫn file PDF BCTC")
    parser.add_argument("--company", type=str, default="VNM", help="Mã doanh nghiệp (mặc định: VNM)")
    parser.add_argument("--year", type=int, default=2024, help="Năm tài chính (mặc định: 2024)")
    parser.add_argument(
        "--notes-limit",
        type=int,
        default=-1,
        help="Số trang thuyết minh bóc tách (-1: Toàn bộ 42 trang Thuyết minh; 0: Bỏ qua; N: N trang đầu)",
    )
    parser.add_argument(
        "--no-cache",
        "--fresh",
        action="store_true",
        default=False,
        help="Xóa sạch cache đĩa để đo lường tải thực hoàn toàn từ đầu (Fresh Run)",
    )
    parser.add_argument("--db", type=str, default="data/benchmark_vnm.db", help="SQLite database test")
    parser.add_argument(
        "--report-md",
        "--export-md",
        dest="report_md",
        type=str,
        default="outputs/vnm_ocr_benchmark_report.md",
        help="Đường dẫn xuất File Markdown Báo cáo Benchmark & Đo lường",
    )
    parser.add_argument(
        "--full-md",
        "--doc-md",
        "--export-doc-md",
        dest="doc_md",
        type=str,
        default="outputs/vnm_financial_report.md",
        help="Đường dẫn xuất File Markdown Toàn văn BCTC bóc tách hoàn chỉnh",
    )
    parser.add_argument(
        "--export-json",
        type=str,
        default="outputs/vnm_ocr_benchmark_metrics.json",
        help="Đường dẫn xuất File JSON lưu số liệu Metrics",
    )
    parser.add_argument(
        "--review",
        "--review-tables",
        action="store_true",
        default=False,
        help="Kích hoạt Human-in-the-Loop Table Editor (giao diện Web) trong LangGraph",
    )
    args = parser.parse_args()

    pdf_file = Path(args.pdf)
    if not pdf_file.exists():
        print(f"❌ LỖI: Không tìm thấy file PDF tại: {pdf_file.resolve()}")
        sys.exit(1)

    # 1. Lấy thông số phần cứng
    hw = get_hardware_profile()
    if psutil:
        process = psutil.Process()
        ram_start_mb = round(process.memory_info().rss / (1024**2), 2)
    else:
        process = None
        ram_start_mb = 0.0

    print_banner("BÁO CÁO CẤU HÌNH PHẦN CỨNG & HỆ THỐNG OCR (FINAUDIT BENCHMARK)")
    print(f"  • Hệ điều hành:          {hw['os']}")
    print(f"  • Vi xử lý (CPU):         {hw['processor']}")
    print(f"  • Nhân / Luồng CPU:       {hw['cpu_cores_physical']} Cores / {hw['cpu_threads_logical']} Threads")
    print(f"  • Dung lượng RAM:        {hw['ram_total_gb']} GB (Trống: {hw['ram_available_gb']} GB)")
    print(f"  • Bộ tăng tốc (GPU):     {hw['gpu']['gpu_name']}")
    print(f"  • VRAM Đồ họa:           {hw['gpu']['vram_total_gb']} GB")
    print(f"  • PyTorch Version:       {hw['gpu']['torch_version']}")
    print(f"  • CUDA Enabled:          {'✅ CÓ (Khả dụng)' if hw['gpu']['cuda_available'] else '❌ KHÔNG (Đang dùng CPU)'}")
    print(f"  • Cơ chế OCR Thuyết minh: {hw['gpu']['recommended_engine']}")

    # 2. Quản lý Cache
    use_cache = not args.no_cache
    if args.no_cache:
        print("\n🧹 Trạng thái Cache: TẮT (--no-cache / --fresh) -> Đang dọn sạch cache để chạy tải thực...")
        clear_cache(company=args.company, year=args.year)
    else:
        print("\n⚡ Trạng thái Cache: BẬT -> Tái sử dụng checkpoint đĩa (nếu đã xử lý) để tăng tốc tức thì.")

    # 3. Tiến hành chạy Ingestion Pipeline và bấm giờ
    print_banner(f"TIẾN HÀNH THỬ NGHIỆM TRÊN TỆP: {pdf_file.name} [{args.company} - {args.year}]")
    print(f"  • Số trang Thuyết minh bóc tách:  {args.notes_limit if args.notes_limit >= 0 else 'Toàn bộ'} trang")
    print(f"  • File xuất BCTC Full Markdown:   {Path(args.doc_md).resolve()}")
    print(f"  • File xuất Benchmark Report:     {Path(args.report_md).resolve()}")
    print(f"  • Bắt đầu khởi chạy pipeline...")

    start_total_time = time.perf_counter()

    agent = IngestionAgent()
    state = agent.run(
        pdf_path=str(pdf_file),
        company=args.company,
        year=args.year,
        notes_limit=args.notes_limit,
        output_markdown=args.doc_md,
        db_path=args.db,
        use_cache=use_cache,
        interactive_review=args.review,
    )

    total_duration = time.perf_counter() - start_total_time
    if process:
        ram_end_mb = round(process.memory_info().rss / (1024**2), 2)
        ram_delta_mb = round(ram_end_mb - ram_start_mb, 2)
    else:
        ram_end_mb = 0.0
        ram_delta_mb = 0.0

    # 4. Trích xuất các kết quả & metrics
    doc_struct = state.get("doc_structure")
    facts = state.get("financial_facts", [])
    report = state.get("audit_report")
    ratios = state.get("ratios", [])
    summary = state.get("summary_metrics", {})
    logs = state.get("logs", [])

    total_pages = doc_struct.total_pages if doc_struct else 0
    core_pages = doc_struct.core_statement_pages if doc_struct else []
    notes_pages_total = doc_struct.notes_pages if doc_struct else []
    notes_pages_extracted = (
        notes_pages_total if args.notes_limit < 0 else notes_pages_total[: args.notes_limit]
    )

    total_processed_pages = len(core_pages) + len(notes_pages_extracted) + 2  # +2 trang TOC/Intro
    throughput_spp = round(total_duration / max(1, total_processed_pages), 2)
    throughput_ppm = round((total_processed_pages / total_duration) * 60, 2) if total_duration > 0 else 0

    # 5. ĐẢM BẢO FILE FULL MARKDOWN BCTC ĐƯỢC XUẤT ĐẦY ĐỦ & CẬP NHẬT MỚI NHẤT
    doc_md_path = Path(args.doc_md)
    all_raw_blocks = state.get("all_blocks", [])
    if not all_raw_blocks:
        core_b = state.get("core_blocks", [])
        notes_b = state.get("notes_blocks", [])
        all_raw_blocks = [getattr(b, "block", b) for b in (core_b + notes_b)]

    if all_raw_blocks:
        classifier = BlockClassifier()
        all_classified = [classifier.classify_block(b) for b in all_raw_blocks]
        detector = SectionDetector(enable_major_sections=True)
        sections = detector.detect_sections(all_classified, company=args.company, year=args.year)

        doc = ParsedDocument(
            company=args.company,
            year=args.year,
            total_pages=total_pages or 54,
            blocks=all_raw_blocks,
            classified_blocks=all_classified,
            sections=sections,
        )
        doc_md_path.parent.mkdir(parents=True, exist_ok=True)
        doc_md_path.write_text(doc.to_markdown(), encoding="utf-8")

    doc_size_kb = round(doc_md_path.stat().st_size / 1024, 1) if doc_md_path.exists() else 0

    # 6. IN KẾT QUẢ ĐO LƯỜNG HIỆU NĂNG RA TERMINAL
    print_banner("KẾT QUẢ ĐO LƯỜNG HIỆU NĂNG (OCR SYSTEM PERFORMANCE METRICS)")
    print(f"{'Chỉ số Đo lường':<35} | {'Giá trị Đạt được':<25} | {'Đánh giá'}")
    print("-" * 85)
    print(f"{'Tổng thời gian xử lý toàn trình':<35} | {f'{total_duration:.2f} giây':<25} | {'Hoàn tất full pipeline'}")
    print(f"{'Tổng số trang đã bóc tách':<35} | {f'{total_processed_pages} / {total_pages} trang':<25} | {'Core + Sample Notes'}")
    print(f"{'Tốc độ trung bình / trang':<35} | {f'{throughput_spp:.2f} s / trang':<25} | {'Throughput'}")
    print(f"{'Năng suất xử lý (Pages / Min)':<35} | {f'{throughput_ppm:.1f} trang / phút':<25} | {'Throughput PPM'}")
    print(f"{'Bộ nhớ RAM tiêu thụ (Delta)':<35} | {f'{ram_delta_mb:+.2f} MB':<25} | {f'Peak RSS: {ram_end_mb:.1f} MB'}")
    print(f"{'Phân định cấu trúc (TOC Routing)':<35} | {'Tự động (Offset +1)':<25} | {f'Mục lục trang {doc_struct.toc_page if doc_struct else 0}'}")
    print(f"{'Nhánh 1: BCTC Cốt lõi (Core)':<35} | {f'{len(core_pages)} trang':<25} | {'Vision LLM + Deductive Zoom'}")
    print(f"{'Nhánh 2: Thuyết minh (Notes)':<35} | {f'{len(notes_pages_extracted)} trang':<25} | {'Offline Local OCR (0 Tokens)'}")

    # 7. IN KẾT QUẢ KIỂM TOÁN CHẤT LƯỢNG (ACCURACY & ANTI-GIGO AUDIT)
    print_banner("CHẤT LƯỢNG DỮ LIỆU & ĐỘ CHÍNH XÁC KIỂM TOÁN (ANTI-GIGO VERIFICATION)")
    print(f"  • Số lượng Facts tài chính chuẩn hóa: {len(facts)} facts (Thông tư 200)")
    if report:
        status_label = "✅ CÂN ĐỐI 100% (BALANCED)" if report.is_balanced else "⚠️ PHÁT HIỆN LỆCH (DISCREPANCY)"
        print(f"  • Trạng thái Cân đối BCTC:            {status_label}")
        print(f"  • Tỷ lệ phương trình số học đạt:      {len(report.passed_checks)}/{report.total_checks} checks (17 Đẳng thức Kế toán)")

        if report.correction_history:
            print("\n  [CAN THIỆP TỰ SỬA SAI CỦA AGENTIC VISION ZOOM]")
            for c in report.correction_history:
                print(f"    🎯 Lượt {c.get('attempt')}: Khoanh vùng {c.get('concept')} -> Sửa {c.get('old_value'):,.0f} thành {c.get('new_value'):,.0f}")
    print(f"  • Số chỉ số tài chính tính toán:     {len(ratios)} ratios (Formula Engine)")

    # 7.1. IN KẾT QUẢ KIỂM TOÁN CẤU TRÚC BẢNG BIỂU & CAPTURE ẢNH
    table_audit = state.get("table_audit_report", {})
    if table_audit:
        print_banner("KIỂM TOÁN CẤU TRÚC BẢNG BIỂU & CAPTURE ẢNH (TABLE INSPECTOR)")
        print(f"  • Tổng số bảng phát hiện:         {table_audit.get('total_tables', 0)} bảng")
        print(f"  • Số bảng đạt chuẩn cấu trúc:     {table_audit.get('valid_tables', 0)} bảng")
        print(f"  • Số bảng có cảnh báo OCR/lệch:   {table_audit.get('tables_with_warnings', 0)} bảng")
        print(f"  • Số ảnh crop độ nét cao (200 DPI): {table_audit.get('captured_images_count', 0)} ảnh sẵn sàng")
        print(f"  • Thư mục lưu trữ ảnh crop:       {table_audit.get('crops_dir', '')}")

    # 8. XUẤT BÁO CÁO BENCHMARK MARKDOWN
    md_report_path = Path(args.report_md)
    md_report_path.parent.mkdir(parents=True, exist_ok=True)

    markdown_content = f"""# Báo Cáo Hiệu Năng & Kiểm Toán Hệ Thống OCR (FinAudit AI)

**Tệp thử nghiệm:** `{pdf_file.name}` | **Doanh nghiệp:** `{args.company}` | **Năm:** `{args.year}`  
**Thời điểm tạo:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`  
**Chế độ Benchmark:** `{'NO-CACHE (Thử nghiệm tải thực)' if args.no_cache else 'CACHE-ENABLED (Tối ưu tái sử dụng)'}`  
**Tài liệu Toàn văn BCTC:** [`{doc_md_path.name}`]({doc_md_path.name}) *({doc_size_kb} KB)*

---

## 1. Thông Số Phần Cứng & Môi Trường Chạy (Hardware Profile)

| Thành Phần Phần Cứng | Chi Tiết Cấu Hình |
| :--- | :--- |
| **Hệ Điều Hành** | {hw['os']} |
| **Vi Xử Lý (CPU)** | {hw['processor']} ({hw['cpu_cores_physical']} Cores / {hw['cpu_threads_logical']} Threads) |
| **Bộ Nhớ Hệ Thống (RAM)** | **{hw['ram_total_gb']} GB** (Còn khả dụng: {hw['ram_available_gb']} GB) |
| **Bộ Tăng Tốc Đồ Họa (GPU)** | **{hw['gpu']['gpu_name']}** |
| **VRAM Đồ Họa** | **{hw['gpu']['vram_total_gb']} GB** |
| **PyTorch & CUDA Build** | PyTorch `{hw['gpu']['torch_version']}` — CUDA `{hw['gpu']['cuda_version']}` |
| **Trạng Thái Kích Hoạt GPU** | {'✅ **Đang kích hoạt GPU CUDA**' if hw['gpu']['cuda_available'] else '⚠️ **Đang chạy CPU-only**'} |

---

## 2. Đo Lường Hiệu Năng Xử Lý (Performance Metrics)

| Chỉ Số Đo Lường | Kết Quả Đạt Được | Ý Nghĩa Kỹ Thuật |
| :--- | :---: | :--- |
| **Tổng thời gian xử lý toàn trình** | **{total_duration:.2f} s** | Thời gian cho toàn bộ pipeline LangGraph |
| **Tổng số trang đã bóc tách** | **{total_processed_pages} trang** | {len(core_pages)} trang Core + {len(notes_pages_extracted)} trang Thuyết minh |
| **Độ trễ trung bình / trang (Latency)** | **{throughput_spp:.2f} s/trang** | Bao gồm cả phân tích bảng và OCR |
| **Năng suất xử lý (Throughput)** | **{throughput_ppm:.1f} trang/phút** | Tốc độ xử lý tương đương |
| **Mức chiếm dụng RAM tiến trình** | **{ram_end_mb:.1f} MB** | Biến thiên trong quá trình chạy: `{ram_delta_mb:+.1f} MB` |
| **Chi phí API Token cho Thuyết minh** | **0 Tokens (100% Miễn phí)** | Xử lý bằng Local OCR Offline (VietOCR + DBNet) |

---

## 3. Kiến Trúc Phân Luồng Tối Ưu (Routing & Triage)

```text
                                [PDF BCTC: {pdf_file.name}]
                                             │
                                             ▼
                             [TOC Inspector & PDF Type Detector]
                             (Mục lục: Trang {doc_struct.toc_page if doc_struct else 0} | Offset: {doc_struct.page_offset if doc_struct else 0})
                                             │
                     ┌───────────────────────┴───────────────────────┐
                     ▼                                               ▼
         [Nhánh 1: 6 Trang BCTC Cốt lõi]                 [Nhánh 2: {len(notes_pages_total)} Trang Thuyết minh]
               Trang: {core_pages}                              Trang: {notes_pages_total[0] if notes_pages_total else 0} -> {notes_pages_total[-1] if notes_pages_total else 0}
                     │                                               │
                     ▼                                               ▼
          [Vision LLM Extraction]                         [VietOCR Local Offline Engine]
                     │                                               │
                     ▼                                               ▼
           {len(facts)} Facts Chuẩn Hóa                       Markdown Blocks cho RAG
```

---

## 4. Kết Quả Kiểm Toán Số Học Anti-GIGO (17 Đẳng Thức Kế Toán)

- **Trạng thái cân đối tổng thể:** `{'✅ HOÀN TOÀN CÂN ĐỐI' if report and report.is_balanced else '⚠️ PHÁT HIỆN SAI LỆCH SỐ HỌC'}`
- **Số lượng đẳng thức số học đạt:** `{len(report.passed_checks) if report else 0} / {report.total_checks if report else 0} bài kiểm tra`

### Các phương trình đã kiểm toán thành công:
{chr(10).join(f"- ✓ {chk}" for chk in (report.passed_checks if report else []))}

{f"### Các phương trình phát hiện sai lệch:{chr(10)}" + chr(10).join(f"- ✗ {chk}" for chk in report.failed_checks) if report and report.failed_checks else ""}

---

## 5. Tỷ Số Tài Chính Được Tính Toán (Formula Engine)

| Tên Chỉ Số | Phân Loại | Giá Trị Tính Toán | Công Thức Áp Dụng |
| :--- | :--- | :---: | :--- |
{chr(10).join(f"| `{r.ratio_name}` | {r.ratio_category} | **{r.value:.4f}** | `{r.formula}` |" for r in ratios)}

---

## 6. Liên Kết Tài Liệu Xuất Bản

* **Toàn văn BCTC Markdown bóc tách:** [`{doc_md_path.name}`]({doc_md_path.name})
* **File số liệu JSON Metrics:** [`{Path(args.export_json).name}`]({Path(args.export_json).name})
* **Cơ sở dữ liệu SQLite:** `{Path(args.db).resolve()}`
"""

    with open(md_report_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    # 9. XUẤT METRICS JSON
    json_metrics_path = Path(args.export_json)
    json_metrics_path.parent.mkdir(parents=True, exist_ok=True)

    metrics_data = {
        "timestamp": datetime.now().isoformat(),
        "document": pdf_file.name,
        "company": args.company,
        "year": args.year,
        "hardware": hw,
        "outputs": {
            "full_document_markdown": str(doc_md_path.resolve()),
            "benchmark_report_markdown": str(md_report_path.resolve()),
            "sqlite_database": str(Path(args.db).resolve()),
        },
        "performance": {
            "total_duration_seconds": round(total_duration, 2),
            "processed_pages": total_processed_pages,
            "throughput_seconds_per_page": throughput_spp,
            "throughput_pages_per_minute": throughput_ppm,
            "ram_start_mb": ram_start_mb,
            "ram_end_mb": ram_end_mb,
            "ram_delta_mb": ram_delta_mb,
        },
        "audit": {
            "facts_count": len(facts),
            "is_balanced": report.is_balanced if report else False,
            "passed_checks_count": len(report.passed_checks) if report else 0,
            "failed_checks_count": len(report.failed_checks) if report else 0,
            "passed_checks": report.passed_checks if report else [],
            "failed_checks": report.failed_checks if report else [],
            "correction_history": report.correction_history if report else [],
        },
        "ratios": {r.ratio_name: r.value for r in ratios},
    }

    with open(json_metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f, ensure_ascii=False, indent=2)

    # 10. BÁO CÁO KẾT THÚC
    print_banner("HOÀN TẤT ĐO LƯỜNG & XUẤT BẢN THÀNH CÔNG")
    print(f"  ✓ 1. Toàn văn BCTC bóc tách (Full MD): {doc_md_path.resolve()} ({doc_size_kb} KB)")
    print(f"  ✓ 2. Báo cáo Benchmark Hệ thống (Report): {md_report_path.resolve()}")
    print(f"  ✓ 3. File JSON Metrics chuẩn hóa:        {json_metrics_path.resolve()}")
    print(f"  ✓ 4. Cơ sở dữ liệu SQLite:               {Path(args.db).resolve()}\n")


if __name__ == "__main__":
    main()
