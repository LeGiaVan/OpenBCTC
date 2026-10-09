"""
parse_bctc.py — CLI tool kiểm thử và bóc tách Báo cáo tài chính cho FinAudit AI.
Cho phép người dùng kiểm tra nhanh toàn bộ luồng Giai đoạn 1:
  PDF Parser -> Table Normalizer -> Block Classifier -> Section Detector

Sử dụng:
  # 1. Chạy với dữ liệu mẫu hoàn chỉnh (Demo mode)
  python scripts/parse_bctc.py --demo

  # 2. Chạy với file PDF BCTC thật
  python scripts/parse_bctc.py --pdf data/bctc_sample.pdf --company VNM --year 2024

  # 3. Xuất kết quả ra file JSON
  python scripts/parse_bctc.py --demo --output outputs/demo_result.json
"""

import argparse
import logging
import sys
from pathlib import Path

# Đảm bảo đường dẫn gốc được nhận diện khi chạy trực tiếp từ CLI
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Khắc phục triệt để lỗi mã hóa tiếng Việt trên Windows console (cp1252)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.database.db_manager import DatabaseManager
from src.engine.formula_engine import FormulaEngine
from src.extractor.fact_extractor import FinancialFactExtractor
from src.models import (
    ParsedBlock,
    ParsedDocument,
    StorageTarget,
)
from src.parser.block_classifier import BlockClassifier
from src.parser.pdf_parser import PDFParser
from src.parser.section_detector import SectionDetector
from src.parser.table_utils import format_table_to_markdown

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("FinAudit.CLI")


def generate_demo_blocks(company: str = "VNM", year: int = 2024) -> list[ParsedBlock]:
    """Tạo bộ dữ liệu ParsedBlock mẫu đa dạng để người dùng test ngay mà không cần PDF."""
    blocks: list[ParsedBlock] = []

    # 1. Block mở đầu
    blocks.append(
        ParsedBlock(
            block_id="p1_b1",
            block_type="text",
            page=1,
            content=(
                f"CÔNG TY CỔ PHẦN SỮA VIỆT NAM ({company})\n"
                f"BÁO CÁO TÀI CHÍNH HỢP NHẤT CHO NĂM TÀI CHÍNH KẾT THÚC NGÀY 31/12/{year}\n"
                "Đơn vị tính: Đồng Việt Nam"
            ),
            metadata={"unit": "VND", "company": company, "year": year},
        )
    )

    # 2. Tiêu đề Báo cáo Ban Tổng Giám đốc
    blocks.append(
        ParsedBlock(
            block_id="p3_b1",
            block_type="text",
            page=3,
            content=(
                "BÁO CÁO CỦA BAN TỔNG GIÁM ĐỐC\n\n"
                "Năm 2024 ghi nhận sự phục hồi mạnh mẽ của thị trường tiêu dùng nội địa. "
                "Ban Giám đốc đã tập trung tối ưu hóa hệ thống phân phối và mở rộng danh mục sản phẩm organic, "
                "kỳ vọng duy trì đà tăng trưởng doanh thu 10-15% trong năm 2025."
            ),
            metadata={"company": company, "year": year},
        )
    )

    # 3. BẢNG CÂN ĐỐI KẾ TOÁN (Tiêu đề + Bảng)
    blocks.append(
        ParsedBlock(
            block_id="p5_b1",
            block_type="text",
            page=5,
            content="BẢNG CÂN ĐỐI KẾ TOÁN\nTại ngày 31 tháng 12 năm 2024\nĐơn vị tính: Đồng Việt Nam",
            metadata={"unit": "VND", "company": company, "year": year},
        )
    )

    bs_raw = [
        ["CHỈ TIÊU", "Mã số", "Thuyết minh", "Số cuối năm", "Số đầu năm"],
        ["A - TÀI SẢN NGẮN HẠN", "100", "", "35.200.500.000.000", "28.150.000.000.000"],
        ["I. Tiền và tương đương tiền", "110", "V.01", "5.400.000.000.000", "4.200.000.000.000"],
        ["II. Đầu tư tài chính ngắn hạn", "120", "V.02", "12.000.000.000.000", "9.500.000.000.000"],
        ["III. Phải thu ngắn hạn khách hàng", "130", "V.03", "8.600.500.000.000", "7.100.000.000.000"],
        ["IV. Hàng tồn kho", "140", "V.04", "9.200.000.000.000", "7.350.000.000.000"],
        ["B - TÀI SẢN DÀI HẠN", "200", "", "20.100.000.000.000", "18.500.000.000.000"],
        ["TỔNG CỘNG TÀI SẢN (270 = 100 + 200)", "270", "", "55.300.500.000.000", "46.650.000.000.000"],
    ]
    blocks.append(
        ParsedBlock(
            block_id="p5_b2",
            block_type="table",
            page=5,
            content=format_table_to_markdown(bs_raw),
            metadata={
                "headers": bs_raw[0],
                "numeric_density": 0.55,
                "num_rows": len(bs_raw),
                "num_cols": len(bs_raw[0]),
                "unit": "VND",
                "company": company,
                "year": year,
            },
        )
    )

    # 3b. BẢNG CÂN ĐỐI KẾ TOÁN (NGUỒN VỐN)
    eq_raw = [
        ["CHỈ TIÊU", "Mã số", "Thuyết minh", "Số cuối năm", "Số đầu năm"],
        ["C - NỢ PHẢI TRẢ", "300", "", "18.000.000.000.000", "15.200.000.000.000"],
        ["I. Nợ ngắn hạn", "310", "V.12", "16.000.000.000.000", "13.500.000.000.000"],
        ["II. Nợ dài hạn", "330", "V.13", "2.000.000.000.000", "1.700.000.000.000"],
        ["D - VỐN CHỦ SỞ HỮU", "400", "", "37.300.500.000.000", "31.450.000.000.000"],
        ["I. Vốn đầu tư của chủ sở hữu", "411", "V.22", "20.899.554.450.000", "20.899.554.450.000"],
        ["TỔNG CỘNG NGUỒN VỐN (440 = 300 + 400)", "440", "", "55.300.500.000.000", "46.650.000.000.000"],
    ]
    blocks.append(
        ParsedBlock(
            block_id="p5_b3",
            block_type="table",
            page=5,
            content=format_table_to_markdown(eq_raw),
            metadata={
                "headers": eq_raw[0],
                "numeric_density": 0.55,
                "num_rows": len(eq_raw),
                "num_cols": len(eq_raw[0]),
                "unit": "VND",
                "company": company,
                "year": year,
            },
        )
    )

    # 4. BÁO CÁO KẾT QUẢ KINH DOANH (Có số âm ngoặc đơn)
    blocks.append(
        ParsedBlock(
            block_id="p7_b1",
            block_type="text",
            page=7,
            content="BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH\nCho năm tài chính kết thúc ngày 31/12/2024",
            metadata={"unit": "VND", "company": company, "year": year},
        )
    )

    is_raw = [
        ["Chỉ tiêu", "Mã số", "Thuyết minh", "Kỳ này", "Kỳ trước"],
        ["1. Doanh thu bán hàng và CCDV", "01", "VI.25", "62.500.000.000.000", "55.000.000.000.000"],
        ["2. Các khoản giảm trừ doanh thu", "02", "VI.26", "(1.200.000.000.000)", "(950.000.000.000)"],
        ["3. Doanh thu thuần (10 = 01 - 02)", "10", "VI.25", "61.300.000.000.000", "54.050.000.000.000"],
        ["4. Giá vốn hàng bán", "11", "VI.27", "(38.000.000.000.000)", "(34.000.000.000.000)"],
        ["5. Lợi nhuận gộp (20 = 10 - 11)", "20", "", "23.300.000.000.000", "20.050.000.000.000"],
        ["6. Chi phí tài chính", "22", "VI.28", "(1.100.000.000.000)", "(980.000.000.000)"],
        ["7. Lợi nhuận thuần từ hoạt động kinh doanh", "30", "", "12.200.000.000.000", "10.500.000.000.000"],
        ["8. Lợi nhuận sau thuế TNDN", "60", "", "9.800.000.000.000", "8.500.000.000.000"],
    ]
    blocks.append(
        ParsedBlock(
            block_id="p7_b2",
            block_type="table",
            page=7,
            content=format_table_to_markdown(is_raw),
            metadata={
                "headers": is_raw[0],
                "numeric_density": 0.50,
                "num_rows": len(is_raw),
                "num_cols": len(is_raw[0]),
                "unit": "VND",
                "company": company,
                "year": year,
            },
        )
    )

    # 5. THUYẾT MINH BÁO CÁO TÀI CHÍNH — CHÍNH SÁCH KẾ TOÁN (Policy)
    blocks.append(
        ParsedBlock(
            block_id="p12_b1",
            block_type="text",
            page=12,
            content=(
                "IV. CÁC CHÍNH SÁCH KẾ TOÁN ÁP DỤNG\n\n"
                "1. Nguyên tắc ghi nhận doanh thu: Doanh thu bán sản phẩm sữa và nước giải khát "
                "được ghi nhận khi khách hàng đã tiếp nhận quyền sở hữu hàng hóa và rủi ro được chuyển giao.\n"
                "2. Phương pháp khấu hao tài sản cố định: Áp dụng phương pháp đường thẳng dựa trên thời gian "
                "hữu dụng ước tính của từng loại máy móc nhà xưởng (từ 5 đến 20 năm)."
            ),
            metadata={"company": company, "year": year},
        )
    )

    # 6. THUYẾT MINH CHI TIẾT SỐ LIỆU — HÀNG TỒN KHO (Numeric Note)
    blocks.append(
        ParsedBlock(
            block_id="p16_b1",
            block_type="text",
            page=16,
            content="V. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC\n\n4. Chi tiết Hàng tồn kho",
            metadata={"company": company, "year": year},
        )
    )

    inv_raw = [
        ["Đối tượng", "Giá gốc", "Dự phòng", "Giá trị thuần"],
        ["Nguyên vật liệu chế biến sữa", "4.500.000.000.000", "(50.000.000.000)", "4.450.000.000.000"],
        ["Công cụ, phụ tùng", "800.000.000.000", "-", "800.000.000.000"],
        ["Thành phẩm tại kho và chi nhánh", "3.900.000.000.000", "(80.000.000.000)", "3.820.000.000.000"],
        ["Tổng số", "9.200.000.000.000", "(130.000.000.000)", "9.070.000.000.000"],
    ]
    blocks.append(
        ParsedBlock(
            block_id="p16_b2",
            block_type="table",
            page=16,
            content=format_table_to_markdown(inv_raw),
            metadata={
                "headers": inv_raw[0],
                "numeric_density": 0.50,
                "num_rows": len(inv_raw),
                "num_cols": len(inv_raw[0]),
                "unit": "VND",
                "company": company,
                "year": year,
            },
        )
    )

    # 7. ĐOẠN VĂN HỖN HỢP (Mixed Block)
    blocks.append(
        ParsedBlock(
            block_id="p22_b1",
            block_type="text",
            page=22,
            content=(
                "Trong kỳ, công ty đã giải ngân 1.850 tỷ đồng đầu tư dây chuyền sản xuất mới tại Bình Dương. "
                "Đồng thời, thực hiện chi trả cổ tức đợt 1 năm 2024 với tổng số tiền 2.450 tỷ VND (tương đương 25%), "
                "tổng dư nợ vay ngân hàng ngắn hạn tại Vietcombank giảm 600 tỷ đồng."
            ),
            metadata={"company": company, "year": year},
        )
    )

    return blocks


def print_banner(text: str) -> None:
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def run_pipeline(blocks: list[ParsedBlock], company: str, year: int) -> ParsedDocument:
    """Chạy trọn vẹn pipeline Giai đoạn 1 từ ParsedBlock -> ClassifiedBlock -> Sections."""
    classifier = BlockClassifier()
    section_detector = SectionDetector()

    print_banner(f"BƯỚC 1: BLOCK CLASSIFICATION (Rule-based 80% + LLM Fallback 20%) — [{company} {year}]")
    classified_blocks = classifier.classify_blocks(blocks)

    print(f"\n{'ID':<10} | {'Loại Block':<22} | {'Targets':<18} | {'Conf':<6} | {'Phương pháp':<14} | {'Lý do'}")
    print("-" * 105)
    for cb in classified_blocks:
        target_str = ",".join(t.value for t in cb.target)
        reason_short = cb.reasoning[:45] + "..." if len(cb.reasoning) > 45 else cb.reasoning
        print(f"{cb.block_id:<10} | {cb.block_type.value:<22} | {target_str:<18} | {cb.confidence:<6.2f} | {cb.classification_method:<14} | {reason_short}")

    print_banner(f"BƯỚC 2: SECTION DETECTION (Heading-based Semantic Segmentation) — [{company} {year}]")
    sections = section_detector.detect_sections(classified_blocks, company=company, year=year)

    print(f"\n{'Section ID':<42} | {'Trang':<8} | {'Số block':<8} | {'Tiêu đề Section'}")
    print("-" * 105)
    for sec in sections:
        page_range = f"p.{sec.page_start}-{sec.page_end}" if sec.page_start != sec.page_end else f"p.{sec.page_start}"
        title_short = sec.title[:45] + "..." if len(sec.title) > 45 else sec.title
        print(f"{sec.id:<42} | {page_range:<8} | {len(sec.blocks):<8} | {title_short}")

    # Thống kê tổng kết
    total_sql = sum(1 for cb in classified_blocks if StorageTarget.SQL in cb.target)
    total_vector = sum(1 for cb in classified_blocks if StorageTarget.VECTOR in cb.target)
    total_both = sum(1 for cb in classified_blocks if StorageTarget.SQL in cb.target and StorageTarget.VECTOR in cb.target)

    print_banner("BƯỚC 3: TỔNG KẾT ĐỊNH TUYẾN DỮ LIỆU (DATA ROUTING SUMMARY)")
    print(f"  * Tổng số blocks:              {len(classified_blocks)}")
    print(f"  * Đích đến SQL DB (facts):     {total_sql} blocks (để Fact Extractor bóc tách ở Tuần 2)")
    print(f"  * Đích đến Vector DB (chunks): {total_vector} blocks (để Parent-Child Chunker index ở Tuần 3)")
    print(f"  * Thuộc cả hai đích (Both):    {total_both} blocks (bảng chính & narrative quan trọng)")
    print(f"  * Tổng số Sections tạo ra:     {len(sections)} sections (đóng vai trò Parent context)")
    print("=" * 80 + "\n")

    return ParsedDocument(
        company=company,
        year=year,
        total_pages=max((b.page for b in blocks), default=1),
        blocks=blocks,
        classified_blocks=classified_blocks,
        sections=sections,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="FinAudit AI — PDF Parser & Block Classifier CLI")
    parser.add_argument("--demo", action="store_true", help="Chạy pipeline với bộ dữ liệu BCTC mẫu đầy đủ")
    parser.add_argument("--pdf", type=str, default="", help="Đường dẫn file PDF BCTC thật để xử lý")
    parser.add_argument("--pages", type=str, default="", help="Khoảng trang cần parse (ví dụ: '1-10', '5-8'). Để trống để parse tất cả")
    parser.add_argument("--company", type=str, default="VNM", help="Mã doanh nghiệp (mặc định: VNM)")
    parser.add_argument("--year", type=int, default=2024, help="Năm tài chính (mặc định: 2024)")
    parser.add_argument("--output", type=str, default="", help="Đường dẫn file xuất kết quả (.json hoặc .md)")
    parser.add_argument("--export-md", type=str, default="", help="Đường dẫn file Markdown (.md) xuất toàn bộ tài liệu")
    parser.add_argument("--review-tables", action="store_true", help="Mở giao diện Web Editor để rà soát và chỉnh sửa bảng biểu Markdown trước khi xuất lần cuối")
    parser.add_argument("--extract-facts", action="store_true", help="Bóc tách facts tài chính, kiểm toán số học (Anti-GIGO) và tính 13 chỉ số tài chính")
    parser.add_argument("--db", type=str, default="data/finaudit.db", help="Đường dẫn CSDL SQLite (mặc định: data/finaudit.db)")

    args = parser.parse_args()

    if not args.demo and not args.pdf:
        print("Vui lòng chọn chế độ chạy: --demo (thử dữ liệu mẫu) hoặc --pdf <duong_dan_file.pdf>")
        print("Ví dụ: python scripts/parse_bctc.py --demo --export-md outputs/demo.md --extract-facts")
        print("Hoặc:  python scripts/parse_bctc.py --pdf vnm.pdf --pages 5-8 --export-md outputs/vnm.md --extract-facts")
        sys.exit(1)

    page_range = None
    if args.pages:
        try:
            if "-" in args.pages:
                parts = args.pages.split("-")
                page_range = (int(parts[0]), int(parts[1]))
            else:
                page_val = int(args.pages)
                page_range = (page_val, page_val)
        except Exception:
            print("Cảnh báo: Định dạng --pages không hợp lệ (hãy dùng dạng '6-10' hoặc '6'). Sẽ parse toàn bộ file.")

    if args.pdf:
        pdf_path = Path(args.pdf)
        if not pdf_path.exists():
            print(f"Lỗi: File PDF không tồn tại: {pdf_path.resolve()}")
            sys.exit(1)
        pdf_parser = PDFParser()
        pages_msg = f" (Trang {page_range[0]} đến {page_range[1]})" if page_range else ""
        print_banner(f"ĐANG BÓC TÁCH FILE PDF: {pdf_path.name}{pages_msg}")
        blocks = pdf_parser.parse_pdf(pdf_path, company=args.company, year=args.year, page_range=page_range)
        if not blocks:
            print("\n⚠️  CẢNH BÁO: Không có khối dữ liệu nào được bóc tách từ file PDF.")
            print("  1. File PDF này là PDF Scan (ảnh chụp) và cần gọi Vision OCR API.")
            print("  2. Do Groq đã ngừng hỗ trợ Vision model miễn phí, bạn cần dùng Google Gemini Flash API.")
            print("  3. Hãy lấy API Key miễn phí (15 RPM) tại: https://aistudio.google.com/app/apikey")
            print("  4. Thêm vào file .env dòng: GEMINI_API_KEY=AIzaSy... rồi chạy lại lệnh.")
    else:
        print_banner(f"CHẾ ĐỘ DEMO — TẠO DỮ LIỆU MẪU BCTC [{args.company} {args.year}]")
        blocks = generate_demo_blocks(company=args.company, year=args.year)

    doc = run_pipeline(blocks, company=args.company, year=args.year)

    # Xuất Markdown nếu được yêu cầu qua --export-md hoặc --output kết thúc bằng .md
    md_target = args.export_md or (args.output if args.output.endswith(".md") else "")
    if md_target:
        md_path = Path(md_target)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(doc.to_markdown())
        print(f"✓ Đã xuất toàn bộ tài liệu sang Markdown: {md_path.resolve()}")
        
        if args.review_tables:
            from serve_md_editor import run_editor_server
            print("\n" + "=" * 70)
            print(" 🚀 KHỞI ĐỘNG CÔNG CỤ CHỈNH SỬA BẢNG BIỂU MARKDOWN (HITL REVIEWER)...")
            print("=" * 70 + "\n")
            run_editor_server(file_path=md_path, port=8502, auto_open=True)

    # Xuất JSON nếu output được cung cấp và không phải file .md
    if args.output and not args.output.endswith(".md"):
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(doc.model_dump_json(indent=2))
        print(f"✓ Đã xuất cấu trúc dữ liệu JSON ra: {out_path.resolve()}")

    # Bóc tách Facts, Tự kiểm toán số học (Anti-GIGO) và Tính tỷ số tài chính
    if args.extract_facts:
        print_banner(f"BƯỚC 4: FINANCIAL FACT EXTRACTION & ANTI-GIGO AUDITING — [{args.company} {args.year}]")
        db_mgr = DatabaseManager(db_path=args.db)
        extractor = FinancialFactExtractor(db_manager=db_mgr)
        facts, report = extractor.extract_from_blocks(
            doc.classified_blocks, company=args.company, year=args.year
        )

        print(f"\n✓ Đã bóc tách thành công {len(facts)} Facts tài chính.")
        print(f"\n{'Concept':<25} | {'Mã':<5} | {'Kỳ':<8} | {'Giá trị (VND)':<22} | {'Trạng thái':<12} | {'Prov ID'}")
        print("-" * 95)
        for f in facts[:25]:
            status_str = f.verification_status.value if hasattr(f.verification_status, "value") else str(f.verification_status)
            val_str = f"{f.value:,.0f}"
            print(f"{f.concept:<25} | {f.standard_code:<5} | {f.period_type:<8} | {val_str:<22} | {status_str:<12} | {f.prov_id}")
        if len(facts) > 25:
            print(f"... và {len(facts) - 25} facts khác đã được lưu vào CSDL.")

        print_banner("KẾT QUẢ KIỂM TOÁN SỐ HỌC (SELF-AUDITING INVARIANTS REPORT)")
        print(f"  * Cân đối tổng thể (is_balanced): {'✓ ĐẠT CHUẨN' if report.is_balanced else '❌ PHÁT HIỆN SAI LỆCH'}")
        print(f"  * Tổng số phép kiểm tra:        {report.total_checks}")
        print(f"  * Số phương trình cân khớp:     {len(report.passed_checks)}")
        for check in report.passed_checks:
            print(f"      [PASSED] {check}")
        if report.failed_checks:
            print(f"  * Số phương trình sai lệch:     {len(report.failed_checks)}")
            for check in report.failed_checks:
                print(f"      [FAILED] {check}")

        print_banner("BƯỚC 5: DETERMINISTIC FORMULA ENGINE — 13 CHỈ SỐ TÀI CHÍNH")
        engine = FormulaEngine(db_manager=db_mgr)
        ratios = engine.compute_all_ratios(facts, company=args.company, year=args.year)

        print(f"\n{'Tên chỉ số':<24} | {'Phân nhóm':<16} | {'Giá trị':<10} | {'Công thức':<35} | {'Input Facts (Provenance)'}")
        print("-" * 115)
        for r in ratios:
            prov_preview = ",".join(r.input_prov_ids[:2])
            if len(r.input_prov_ids) > 2:
                prov_preview += f" (+{len(r.input_prov_ids)-2})"
            print(f"{r.ratio_name:<24} | {r.ratio_category:<16} | {r.value:<10.4f} | {r.formula:<35} | {prov_preview}")

        summary = db_mgr.get_summary(args.company, args.year)
        print_banner("THỐNG KÊ CƠ SỞ DỮ LIỆU SQLITE (DATA/FINAUDIT.DB)")
        print(f"  * Doanh nghiệp:                {summary['company']}")
        print(f"  * Năm tài chính:               {summary['year']}")
        print(f"  * Tổng số Facts lưu trữ:       {summary['total_facts']}")
        print(f"  * Số Facts đã kiểm toán đúng:  {summary['verified_facts']}")
        print(f"  * Số Facts có chênh lệch:      {summary['discrepancy_facts']}")
        print(f"  * Tổng số chỉ số tài chính:    {summary['total_ratios']}")
        print(f"  * Đường dẫn CSDL:              {Path(args.db).resolve()}")
        print("=" * 80 + "\n")

        # BƯỚC 6: TỰ ĐỘNG ĐỒNG BỘ SANG OPENBCTC COPILOT (DUAL-STORAGE)
        try:
            from src.uploader.copilot_syncer import CopilotSyncer
            syncer = CopilotSyncer()
            if syncer.enabled:
                print_banner(f"BƯỚC 6: ĐỒNG BỘ DỮ LIỆU SANG OPENBCTC COPILOT — [{args.company} {args.year}]")
                syncer.sync_company_run(
                    company=args.company,
                    year=args.year,
                    output_dir=args.output_dir,
                    pdf_path=args.pdf,
                    trigger_ingest=True,
                )
        except Exception as ex_sync:
            logger.warning("CopilotSyncer warning trong parse_bctc: %s", ex_sync)


if __name__ == "__main__":
    main()

