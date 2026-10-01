"""
test_page.py — Công cụ test nhanh từng trang PDF cụ thể cho FinAudit AI.
Giúp kiểm tra chất lượng trích xuất (văn bản & bảng biểu) trên từng trang scan/text
mà không cần chờ chạy lại toàn bộ tài liệu 54 trang.

Sử dụng:
  # 1. Test trang 42 bằng Local OCR (Offline, 0 tokens, mặc định rapidocr / vietocr):
  python scripts/test_page.py --pdf vnm.pdf --page 42

  # 2. Test trang 42 ép chạy mới (không dùng cache cũ):
  python scripts/test_page.py --pdf vnm.pdf --page 42 --no-cache

  # 3. Test nhiều trang cụ thể (ví dụ trang 15 và 42):
  python scripts/test_page.py --pdf vnm.pdf --pages 15,42

  # 4. Test trang 8 bằng Vision LLM (Google Gemini Vision):
  python scripts/test_page.py --pdf vnm.pdf --page 8 --engine vision
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Đảm bảo import được module src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import pdfplumber

from src.parser.local_ocr import LocalOCREngine
from src.parser.ocr_pipeline import VisionOCRPipeline
from src.parser.ocr_postprocess import strip_boilerplate_lines
from src.parser.pdf_type_detector import PDFTypeDetector
from src.parser.text_parser import TextParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("FinAudit.TestPage")


def main() -> None:
    parser = argparse.ArgumentParser(description="FinAudit AI — Test trích xuất trang PDF cụ thể")
    parser.add_argument("--pdf", type=str, required=True, help="Đường dẫn file PDF BCTC (ví dụ: vnm.pdf)")
    parser.add_argument("--page", type=int, default=0, help="Số trang cần test (1-indexed, ví dụ: --page 42)")
    parser.add_argument("--pages", type=str, default="", help="Danh sách trang ngăn cách bằng phẩy (ví dụ: --pages 15,42,43)")
    parser.add_argument(
        "--engine",
        type=str,
        default="auto",
        choices=["auto", "local", "vietocr", "rapidocr", "vision", "text"],
        help="Engine OCR/Parser: 'auto' (Local OCR), 'vision' (Gemini), 'text' (pdfplumber)",
    )
    parser.add_argument("--company", type=str, default="VNM", help="Mã công ty (mặc định: VNM)")
    parser.add_argument("--year", type=int, default=2024, help="Năm tài chính (mặc định: 2024)")
    parser.add_argument("--no-cache", action="store_true", help="Bỏ qua cache, ép phân tích lại từ đầu")
    parser.add_argument("--output", type=str, default="", help="File lưu kết quả markdown (mặc định: outputs/test_page_X.md)")

    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Lỗi: Không tìm thấy file PDF tại: {pdf_path.resolve()}")
        sys.exit(1)

    # Xác định danh sách các trang cần test
    target_pages: list[int] = []
    if args.pages:
        for part in args.pages.split(","):
            part = part.strip()
            if part.isdigit():
                target_pages.append(int(part))
    elif args.page > 0:
        target_pages.append(args.page)
    else:
        print("Lỗi: Vui lòng chỉ định số trang cần test với --page <N> hoặc --pages <N1,N2>.")
        print("Ví dụ: python scripts/test_page.py --pdf vnm.pdf --page 42")
        sys.exit(1)

    use_cache = not args.no_cache

    with pdfplumber.open(str(pdf_path)) as pdf:
        total_pages = len(pdf.pages)
        print("\n" + "=" * 80)
        print(f"  FINAUDIT AI — TEST TRÍCH XUẤT NHANH TRANG CỤ THỂ")
        print(f"  Tài liệu: {pdf_path.name} ({total_pages} trang)")
        print(f"  Trang kiểm tra: {target_pages}")
        print(f"  Engine: {args.engine.upper()} | Cache: {'DÙNG CACHE' if use_cache else 'ÉP CHẠY MỚI (--no-cache)'}")
        print("=" * 80 + "\n")

        for p_num in target_pages:
            if p_num < 1 or p_num > total_pages:
                print(f"⚠️ Cảnh báo: Trang {p_num} vượt quá số trang của tài liệu (1-{total_pages}). Bỏ qua.")
                continue

            page = pdf.pages[p_num - 1]
            raw_text = (page.extract_text() or "").strip()
            is_native = len(raw_text) >= 50

            print(f">>> ĐANG XỬ LÝ TRANG {p_num} (Loại trang: {'Native Text' if is_native else 'Scanned Image'}) <<<")

            blocks = []
            if args.engine == "text" or (args.engine == "auto" and is_native):
                parser_inst = TextParser()
                blocks = parser_inst.parse_page(page, p_num, company=args.company, year=args.year)
            elif args.engine == "vision":
                vision_inst = VisionOCRPipeline()
                blocks = vision_inst.process_scanned_page(page, p_num, company=args.company, year=args.year)
            else:
                # Mặc định dùng Local OCR
                local_engine_type = args.engine if args.engine in ("vietocr", "rapidocr") else "auto"
                local_inst = LocalOCREngine(engine=local_engine_type, use_cache=use_cache)
                blocks = local_inst.process_scanned_page(page, p_num, company=args.company, year=args.year)

            print(f"Kết quả trang {p_num}: Đã bóc tách {len(blocks)} blocks.")
            tables_count = sum(1 for b in blocks if b.is_table)
            texts_count = sum(1 for b in blocks if not b.is_table)
            print(f"  * Bảng biểu (Tables): {tables_count} bảng")
            print(f"  * Văn bản (Texts):    {texts_count} đoạn\n")

            md_lines = [f"# KẾT QUẢ BÓC TÁCH TRANG {p_num} ({args.company} {args.year})\n"]
            for idx, b in enumerate(blocks):
                print("-" * 70)
                if b.is_table:
                    print(f"📊 BLOCK #{idx + 1} [TABLE] (ID: {b.block_id}, Rows: {b.metadata.get('num_rows')}, Cols: {b.metadata.get('num_cols')}):")
                    print(b.content)
                    md_lines.append(f"### Bảng #{idx + 1} (ID: `{b.block_id}`)\n")
                    md_lines.append(b.content + "\n")
                else:
                    clean_content = strip_boilerplate_lines(b.content)
                    if not clean_content:
                        continue
                    print(f"📄 BLOCK #{idx + 1} [TEXT] (ID: {b.block_id}):")
                    print(clean_content)
                    md_lines.append(f"### Văn bản #{idx + 1} (ID: `{b.block_id}`)\n")
                    md_lines.append(clean_content + "\n")

            # Lưu kết quả ra file markdown
            out_file = args.output or f"outputs/test_page_{p_num}.md"
            Path(out_file).parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w", encoding="utf-8") as f:
                f.write("\n".join(md_lines))
            print(f"\n💾 Đã lưu kết quả trang {p_num} vào file: {Path(out_file).resolve()}")
            print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
