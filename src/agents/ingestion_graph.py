"""
ingestion_graph.py — LangGraph Ingestion & Triage Agent điều phối phân luồng BCTC.
Xây dựng đồ thị StateGraph hai nhánh:
  - Nhánh 1 (Core Financial Statements): Vision LLM -> Fact Extraction -> Anti-GIGO Verifier -> SQLite
  - Nhánh 2 (Notes & Narrative Text): Local Fast OCR (RapidOCR/ONNX) -> RAG Chunks (0 quota API)
"""

import logging
from pathlib import Path

import pdfplumber
from langgraph.graph import END, START, StateGraph

from src.agents.ingestion_state import IngestionState
from src.agents.toc_inspector import TOCInspector
from src.database.db_manager import DatabaseManager
from src.engine.formula_engine import FormulaEngine
from src.extractor.fact_extractor import FinancialFactExtractor
from src.models import ParsedDocument
from src.parser.block_classifier import BlockClassifier
from src.parser.local_ocr import LocalOCREngine
from src.parser.normalizer import OutputNormalizer
from src.parser.ocr_pipeline import VisionOCRPipeline
from src.parser.pdf_type_detector import PDFTypeDetector
from src.parser.section_detector import SectionDetector
from src.parser.text_parser import TextParser

logger = logging.getLogger(__name__)


def detect_pdf_type_node(state: IngestionState) -> IngestionState:
    """
    Node 0 (Phase 1): Phân loại tài liệu PDF (Native vs Scanned vs Hybrid).
    Quét từng trang bằng PDFTypeDetector để xác định:
      - 'native': Nếu toàn bộ hoặc đại đa số trang là Digital Text (char_count >= 50)
      - 'scanned': Nếu toàn bộ hoặc đại đa số trang là Scanned Image (char_count < 50)
      - 'hybrid': Nếu có sự kết hợp đan xen giữa trang scan và trang text
    """
    pdf_path = state.get("pdf_path", "")
    logs = list(state.get("logs", []))

    logger.info("LangGraph [detect_pdf_type]: Đang quét phân loại loại file PDF '%s'...", Path(pdf_path).name)
    detector = PDFTypeDetector()
    doc_class = detector.classify_document(pdf_path)

    # Đánh giá nhãn tài liệu
    if doc_class.scanned_pages_count == 0:
        pdf_type = "native"
    elif doc_class.text_pages_count == 0:
        pdf_type = "scanned"
    else:
        # Nếu tỷ lệ text >= 75% -> ưu tiên xử lý native, ngược lại là hybrid
        if doc_class.text_pages_count / max(doc_class.total_pages, 1) >= 0.75:
            pdf_type = "native"
        else:
            pdf_type = "hybrid"

    page_types = {p.page: p.page_type for p in doc_class.pages}

    msg = (
        f"PDF Type Detector: Tài liệu '{Path(pdf_path).name}' ({doc_class.total_pages} trang) -> "
        f"Phân loại: [{pdf_type.upper()}] ({doc_class.text_pages_count} trang text, "
        f"{doc_class.scanned_pages_count} trang scan)."
    )
    logs.append(msg)
    logger.info("LangGraph [detect_pdf_type]: %s", msg)

    return {
        **state,
        "pdf_type": pdf_type,
        "page_types": page_types,
        "logs": logs,
        "status": "PDF_TYPE_DETECTED",
    }


def route_by_pdf_type(state: IngestionState) -> str:
    """
    Conditional Edge: Điều phối rẽ nhánh LangGraph dựa trên loại tài liệu PDF.
    - 'native' -> Rẽ sang nhánh 'extract_native_pipeline' (100% pdfplumber, 0 API tokens, < 1s)
    - 'scanned_or_hybrid' -> Rẽ sang nhánh 'inspect_toc' (Vision LLM & Local OCR Pipeline)
    """
    pdf_type = state.get("pdf_type", "scanned")
    if pdf_type == "native":
        logger.info("LangGraph [Router]: Rẽ nhánh -> [extract_native_pipeline] (Native pdfplumber, 0 API tokens)")
        return "native"
    logger.info("LangGraph [Router]: Rẽ nhánh -> [inspect_toc] (Scanned/Hybrid OCR Pipeline)")
    return "scanned_or_hybrid"


def extract_native_pipeline_node(state: IngestionState) -> IngestionState:
    """
    Nhánh Chuyên biệt cho Native PDF:
    Bóc tách 100% dữ liệu qua TextParser (pdfplumber) mà không cần gọi Vision OCR hay Local OCR.
    Quy trình:
      1. Trinh sát mục lục nhanh qua text (TOCInspector)
      2. Bóc tách Core Statements qua TextParser (pdfplumber)
      3. Bóc tách Thuyết minh qua TextParser (pdfplumber)
      4. Trích xuất Facts tài chính và Kiểm toán Anti-GIGO
      5. Tính toán 13 chỉ số tài chính
    """
    pdf_path = state.get("pdf_path", "")
    company = state.get("company", "VNM")
    year = state.get("year", 2024)
    db_path = state.get("db_path", "data/finaudit.db")
    notes_limit = state.get("notes_limit", 5)
    logs = list(state.get("logs", []))

    logger.info(
        "LangGraph [extract_native]: Kích hoạt nhánh Native PDF cho file '%s' qua pdfplumber...",
        Path(pdf_path).name,
    )

    # 1. Trinh sát Mục lục nhanh (TOCInspector tự dùng TextParser vì trang là native)
    inspector = TOCInspector()
    doc_struct = inspector.inspect(pdf_path=pdf_path, company=company, year=year)
    logs.append(f"TOC Inspector (Native): {doc_struct.summary()}")

    core_pages = doc_struct.core_statement_pages
    all_notes_pages = doc_struct.notes_pages
    notes_pages = all_notes_pages if notes_limit < 0 else all_notes_pages[:notes_limit] if notes_limit > 0 else []

    text_parser = TextParser()
    core_blocks = []
    notes_blocks = []

    with pdfplumber.open(pdf_path) as pdf:
        # 2. Bóc tách BCTC cốt lõi
        core_blocks = text_parser.parse_pages(pdf, page_numbers=core_pages, company=company, year=year)

        # 3. Bóc tách Thuyết minh
        if notes_pages:
            notes_blocks = text_parser.parse_pages(pdf, page_numbers=notes_pages, company=company, year=year)

    # 4. Chuẩn hóa & Phân loại
    normalizer = OutputNormalizer()
    norm_core_blocks = normalizer.normalize(text_blocks=core_blocks)
    classifier = BlockClassifier()
    classified_core = [classifier.classify_block(b) for b in norm_core_blocks]

    # 5. Anti-GIGO Facts Extraction
    db_mgr = DatabaseManager(db_path=db_path)
    extractor = FinancialFactExtractor(db_manager=db_mgr)
    facts, audit_report = extractor.extract_from_blocks(classified_core, company=company, year=year)

    # Kích hoạt Agentic Vision-LLM Zoom Corrector nếu phát hiện sai lệch số học
    if not audit_report.is_balanced and pdf_path:
        from src.verifier.vision_zoom_corrector import VisionZoomCorrector

        zoom_corrector = VisionZoomCorrector()
        facts, audit_report, is_corrected = zoom_corrector.run_self_correction(
            pdf_path=pdf_path,
            facts=facts,
            report=audit_report,
            company=company,
            year=year,
        )
        if is_corrected:
            correction_msg = (
                f"🎯 Agentic Self-Correction (Native): Đã phóng to và tự động sửa thành công các dòng số liệu bị lỗi trích xuất! "
                f"BCTC hiện tại: {'✅ HOÀN TOÀN CÂN ĐỐI' if audit_report.is_balanced else '⚠️ ĐÃ CẢI THIỆN'}"
            )
            logs.append(correction_msg)
            logger.info("LangGraph [extract_native]: %s", correction_msg)
            # Cập nhật lại facts và report trong SQLite DB
            db_mgr.save_facts(facts)
            db_mgr.save_verification_report(audit_report)

    # 6. Formula Engine (sử dụng facts đã được chuẩn hóa/sửa lỗi)
    formula_engine = FormulaEngine(db_manager=db_mgr)
    ratios = formula_engine.compute_all_ratios(facts, company=company, year=year)
    if db_mgr:
        db_mgr.save_ratios(ratios)

    msg = (
        f"Native Pipeline: Hoàn tất trích xuất 100% qua pdfplumber (0 API tokens). "
        f"Core: {len(classified_core)} blocks, Notes: {len(notes_blocks)} blocks, {len(facts)} facts. "
        f"Kiểm toán Anti-GIGO: {'CÂN ĐỐI' if audit_report.is_balanced else 'CÓ CHÊNH LỆCH'}."
    )
    logs.append(msg)
    logger.info("LangGraph [extract_native]: %s", msg)

    return {
        **state,
        "doc_structure": doc_struct,
        "core_blocks": classified_core,
        "notes_blocks": notes_blocks,
        "financial_facts": facts,
        "audit_report": audit_report,
        "ratios": ratios,
        "logs": logs,
        "status": "NATIVE_PIPELINE_EXTRACTED",
    }


def inspect_toc_node(state: IngestionState) -> IngestionState:
    """Node 1: Trinh sát Mục lục để xác định ranh giới các phần trong tài liệu."""
    pdf_path = state.get("pdf_path", "")
    company = state.get("company", "VNM")
    year = state.get("year", 2024)
    logs = list(state.get("logs", []))

    logger.info("LangGraph [inspect_toc]: Đang quét mục lục file '%s'...", Path(pdf_path).name)
    inspector = TOCInspector()
    doc_struct = inspector.inspect(pdf_path=pdf_path, company=company, year=year)

    summary_msg = doc_struct.summary()
    logs.append(f"TOC Inspector: {summary_msg}")
    logger.info("LangGraph [inspect_toc]:\n%s", summary_msg)

    return {
        **state,
        "doc_structure": doc_struct,
        "logs": logs,
        "status": "TOC_INSPECTED",
    }


def extract_core_statements_node(state: IngestionState) -> IngestionState:
    """
    Node 2: Xử lý nhánh Báo cáo Tài chính cốt lõi (Core Statements).
    Định tuyến thông minh:
      - Trang Native Text (char_count >= 50) -> TextParser (pdfplumber, 0 API tokens, < 100ms)
      - Trang Scanned Image (char_count < 50) -> VisionOCRPipeline (Gemini/Groq Vision)
    Sau đó chuẩn hóa qua OutputNormalizer, bóc tách Facts tài chính và Kiểm toán số học (Anti-GIGO).
    """
    pdf_path = state.get("pdf_path", "")
    company = state.get("company", "VNM")
    year = state.get("year", 2024)
    db_path = state.get("db_path", "data/finaudit.db")
    doc_struct = state.get("doc_structure")
    logs = list(state.get("logs", []))

    core_pages = doc_struct.core_statement_pages if doc_struct else [7, 8, 9, 10, 11]
    logger.info(
        "LangGraph [extract_core]: Bắt đầu bóc tách BCTC cốt lõi trang %s...",
        core_pages,
    )

    type_detector = PDFTypeDetector()
    text_parser = TextParser()
    vision_ocr = VisionOCRPipeline()

    text_blocks = []
    ocr_blocks = []

    with pdfplumber.open(pdf_path) as pdf:
        text_page_nums = []
        scanned_page_nums = []

        for p_num in core_pages:
            if p_num < 1 or p_num > len(pdf.pages):
                continue
            page = pdf.pages[p_num - 1]
            raw_text = (page.extract_text() or "").strip()
            if len(raw_text) >= type_detector.min_char_threshold:
                text_page_nums.append(p_num)
            else:
                scanned_page_nums.append(p_num)

        # 1. Nhánh Native Text -> pdfplumber (0 API calls, < 100ms)
        if text_page_nums:
            logger.info(
                "LangGraph [extract_core]: Định tuyến %d trang Core Native Text sang TextParser (pdfplumber): %s",
                len(text_page_nums),
                text_page_nums,
            )
            text_blocks = text_parser.parse_pages(
                pdf=pdf,
                page_numbers=text_page_nums,
                company=company,
                year=year,
            )

        # 2. Nhánh Scanned Image -> Vision OCR Pipeline
        if scanned_page_nums:
            logger.info(
                "LangGraph [extract_core]: Định tuyến %d trang Core Scanned Image sang VisionOCRPipeline: %s",
                len(scanned_page_nums),
                scanned_page_nums,
            )
            ocr_blocks = vision_ocr.process_pages(
                pdf=pdf,
                page_numbers=scanned_page_nums,
                company=company,
                year=year,
            )

    # Chuẩn hóa qua OutputNormalizer (hợp nhất và nối bảng nếu cần)
    normalizer = OutputNormalizer()
    norm_core_blocks = normalizer.normalize(text_blocks=text_blocks, ocr_blocks=ocr_blocks)

    # Phân loại block
    classifier = BlockClassifier()
    classified_blocks = [classifier.classify_block(b) for b in norm_core_blocks]

    # Trích xuất Facts tài chính và Kiểm toán số học (Anti-GIGO)
    db_mgr = DatabaseManager(db_path=db_path)
    extractor = FinancialFactExtractor(db_manager=db_mgr)
    facts, audit_report = extractor.extract_from_blocks(classified_blocks, company=company, year=year)

    # Kích hoạt Agentic Vision-LLM Zoom Corrector nếu phát hiện sai lệch số học
    if not audit_report.is_balanced and pdf_path:
        from src.verifier.vision_zoom_corrector import VisionZoomCorrector

        zoom_corrector = VisionZoomCorrector()
        facts, audit_report, is_corrected = zoom_corrector.run_self_correction(
            pdf_path=pdf_path,
            facts=facts,
            report=audit_report,
            company=company,
            year=year,
        )
        if is_corrected:
            correction_msg = (
                f"🎯 Agentic Self-Correction: Đã phóng to và tự động sửa thành công các dòng số liệu bị lỗi OCR! "
                f"BCTC hiện tại: {'✅ HOÀN TOÀN CÂN ĐỐI' if audit_report.is_balanced else '⚠️ ĐÃ CẢI THIỆN'}"
            )
            logs.append(correction_msg)
            logger.info("LangGraph [extract_core]: %s", correction_msg)
            # Cập nhật lại facts và report trong SQLite DB
            db_mgr.save_facts(facts)
            db_mgr.save_verification_report(audit_report)

    # Tính toán 13 chỉ số tài chính (sử dụng facts đã được chuẩn hóa/sửa lỗi)
    formula_engine = FormulaEngine(db_manager=db_mgr)
    ratios = formula_engine.compute_all_ratios(facts, company=company, year=year)
    if db_mgr:
        db_mgr.save_ratios(ratios)

    source_summary = []
    if text_blocks:
        source_summary.append(f"{len(text_blocks)} blocks từ pdfplumber")
    if ocr_blocks:
        source_summary.append(f"{len(ocr_blocks)} blocks từ Vision OCR")

    fallback_pages = sorted(list({cb.block.page for cb in classified_blocks if cb.block.metadata.get("is_fallback")}))
    if fallback_pages:
        source_summary.append(f"⚠️ {len(fallback_pages)} trang cứu nguy qua Local OCR (trang {fallback_pages})")
        fallback_msg = (
            f"⚠️ Cảnh báo Agent: Trang {fallback_pages} gặp sự cố quá tải Vision API (503), "
            f"đã tự động kích hoạt Local OCR cứu nguy số liệu thành công."
        )
        logs.append(fallback_msg)
        logger.warning("LangGraph [extract_core]: %s", fallback_msg)

    extracted_pages = {cb.block.page for cb in classified_blocks}
    missing_pages = [p for p in core_pages if p not in extracted_pages]
    if missing_pages:
        warn_missing = (
            f"⚠️ Cảnh báo nghiêm trọng: Trang cốt lõi {missing_pages} không trích xuất được khối nào do lỗi kết nối/API."
        )
        logs.append(warn_missing)
        logger.warning("LangGraph [extract_core]: %s", warn_missing)

    msg = (
        f"Core Extractor: Đã bóc tách {len(classified_blocks)} blocks ({', '.join(source_summary) if source_summary else '0 blocks'}), "
        f"{len(facts)} facts tài chính. "
        f"Kiểm toán số học: {'CÂN ĐỐI' if audit_report.is_balanced else 'CÓ CHÊNH LỆCH'}. "
        f"Đã tính {len(ratios)} chỉ số tài chính."
    )
    logs.append(msg)
    logger.info("LangGraph [extract_core]: %s", msg)

    return {
        **state,
        "core_blocks": classified_blocks,
        "financial_facts": facts,
        "audit_report": audit_report,
        "ratios": ratios,
        "logs": logs,
        "status": "CORE_STATEMENTS_EXTRACTED",
    }


def extract_notes_rag_node(state: IngestionState) -> IngestionState:
    """
    Node 3: Xử lý nhánh Thuyết minh BCTC (Notes / Narrative text cho RAG).
    Định tuyến thông minh:
      - Trang Native Text (char_count >= 50) -> TextParser (pdfplumber, 0 API tokens, 0 OCR compute)
      - Trang Scanned Image (char_count < 50) -> Local Fast OCR (RapidOCR ONNX offline, 0 quota)
    """
    pdf_path = state.get("pdf_path", "")
    company = state.get("company", "VNM")
    year = state.get("year", 2024)
    doc_struct = state.get("doc_structure")
    notes_limit = state.get("notes_limit", 5)
    logs = list(state.get("logs", []))

    all_notes_pages = doc_struct.notes_pages if doc_struct else []
    if notes_limit == 0 or not all_notes_pages:
        logger.info("LangGraph [extract_notes]: Bỏ qua trích xuất Thuyết minh theo cấu hình (notes_limit=0).")
        logs.append("Notes Extractor: Đã bỏ qua theo cấu hình (notes_limit=0).")
        return {**state, "notes_blocks": [], "logs": logs}

    pages_to_extract = all_notes_pages if notes_limit < 0 else all_notes_pages[:notes_limit]
    logger.info(
        "LangGraph [extract_notes]: Bắt đầu bóc tách %d trang Thuyết minh: %s...",
        len(pages_to_extract),
        pages_to_extract,
    )

    use_cache = state.get("use_cache", True)
    type_detector = PDFTypeDetector()
    text_parser = TextParser()
    local_ocr = LocalOCREngine(use_cache=use_cache)

    note_blocks = []
    with pdfplumber.open(pdf_path) as pdf:
        text_notes_pages = []
        scanned_notes_pages = []

        for p_num in pages_to_extract:
            if p_num < 1 or p_num > len(pdf.pages):
                continue
            page = pdf.pages[p_num - 1]
            raw_text = (page.extract_text() or "").strip()
            if len(raw_text) >= type_detector.min_char_threshold:
                text_notes_pages.append(p_num)
            else:
                scanned_notes_pages.append(p_num)

        # 1. Nhánh Native Text -> pdfplumber
        if text_notes_pages:
            logger.info(
                "LangGraph [extract_notes]: Định tuyến %d trang Thuyết minh Native Text sang TextParser (pdfplumber): %s",
                len(text_notes_pages),
                text_notes_pages,
            )
            text_blocks = text_parser.parse_pages(
                pdf=pdf,
                page_numbers=text_notes_pages,
                company=company,
                year=year,
            )
            note_blocks.extend(text_blocks)

        # 2. Nhánh Scanned Image -> Local Fast OCR
        if scanned_notes_pages:
            logger.info(
                "LangGraph [extract_notes]: Định tuyến %d trang Thuyết minh Scanned Image sang LocalOCREngine: %s",
                len(scanned_notes_pages),
                scanned_notes_pages,
            )
            scan_blocks = local_ocr.process_pages(
                pdf=pdf,
                page_numbers=scanned_notes_pages,
                company=company,
                year=year,
            )
            note_blocks.extend(scan_blocks)

    # Sắp xếp note_blocks theo thứ tự số trang
    note_blocks.sort(key=lambda b: b.page)

    msg = (
        f"Notes Extractor: Hoàn tất bóc tách {len(note_blocks)} blocks text từ "
        f"{len(pages_to_extract)} trang thuyết minh "
        f"({len(text_notes_pages)} trang pdfplumber, {len(scanned_notes_pages)} trang Local OCR)."
    )
    logs.append(msg)
    logger.info("LangGraph [extract_notes]: %s", msg)

    return {
        **state,
        "notes_blocks": note_blocks,
        "logs": logs,
        "status": "NOTES_EXTRACTED",
    }


def compile_and_export_node(state: IngestionState) -> IngestionState:
    """Node 4: Hợp nhất dữ liệu hai nhánh, phát hiện Sections và xuất Markdown tổng hợp."""
    company = state.get("company", "VNM")
    year = state.get("year", 2024)
    core_blocks = list(state.get("core_blocks", []))
    notes_blocks = list(state.get("notes_blocks", []))
    output_md = state.get("output_markdown_path", "") or state.get("output_md", "")
    logs = list(state.get("logs", []))

    # Chuẩn hóa toàn bộ thành ClassifiedBlock và ParsedBlock
    classifier = BlockClassifier()
    all_classified = []
    all_raw_blocks = []

    for item in core_blocks + notes_blocks:
        if hasattr(item, "block") and hasattr(item, "block_type"):
            all_classified.append(item)
            all_raw_blocks.append(item.block)
        else:
            cb = classifier.classify_block(item)
            all_classified.append(cb)
            all_raw_blocks.append(item)

    # Phát hiện section ngữ nghĩa
    section_detector = SectionDetector(enable_major_sections=True)
    sections = section_detector.detect_sections(all_classified, company=company, year=year)

    doc = ParsedDocument(
        company=company,
        year=year,
        total_pages=max((b.page for b in all_raw_blocks), default=1),
        blocks=all_raw_blocks,
        classified_blocks=all_classified,
        sections=sections,
    )

    if output_md:
        out_path = Path(output_md)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(doc.to_markdown())
        logs.append(f"Exporter: Đã lưu Markdown tổng hợp tại: {out_path.resolve()}")
        logger.info("LangGraph [compile]: Đã xuất Markdown tại %s", out_path.resolve())

    summary_metrics = {
        "total_blocks": len(all_classified),
        "core_blocks_count": len(core_blocks),
        "notes_blocks_count": len(notes_blocks),
        "facts_count": len(state.get("financial_facts", [])),
        "ratios_count": len(state.get("ratios", [])),
        "sections_count": len(sections),
        "is_balanced": state.get("audit_report").is_balanced if state.get("audit_report") else False,
    }

    return {
        **state,
        "all_blocks": all_raw_blocks,
        "hierarchical_sections": [s.child_metadata for s in sections],
        "summary_metrics": summary_metrics,
        "logs": logs,
        "status": "COMPILED_AND_EXPORTED",
    }


def check_and_capture_tables_node(state: IngestionState) -> IngestionState:
    """
    Node 5: Kiểm tra cấu trúc & Tự động Capture ảnh crop 200 DPI cho toàn bộ bảng biểu.
    - Tìm và định vị tất cả bảng biểu trong file Markdown vừa xuất.
    - Tự động crop ảnh 200 DPI cho từng bảng từ PDF gốc để sẵn sàng hiển thị (0 độ trễ).
    - Kiểm toán chất lượng bảng: độ lệch cột, rác OCR ô số, tỷ lệ ô trống.
    """
    pdf_path = state.get("pdf_path", "")
    company = state.get("company", "VNM")
    year = state.get("year", 2024)
    output_md = state.get("output_markdown_path", "") or state.get("output_md", "")
    logs = list(state.get("logs", []))

    from src.verifier.table_verifier import TableInspector

    inspector = TableInspector()
    md_content = ""
    if output_md and Path(output_md).exists():
        md_content = Path(output_md).read_text(encoding="utf-8")
    else:
        all_blocks = state.get("all_blocks", [])
        table_blocks = [b.content for b in all_blocks if getattr(b, "is_table", False)]
        md_content = "\n\n".join(table_blocks)

    logger.info("LangGraph [check_and_capture_tables]: Bắt đầu kiểm toán cấu trúc & capture ảnh crop bảng...")
    audit_res = inspector.process_document_tables(
        pdf_path=pdf_path,
        markdown_content=md_content,
        company=company,
        year=year,
    )

    msg = (
        f"Table Inspector: Đã kiểm toán & capture {audit_res['total_tables']} bảng biểu. "
        f"{audit_res['valid_tables']} bảng đạt chuẩn, {audit_res['tables_with_warnings']} bảng có cảnh báo. "
        f"Đã lưu trữ {audit_res['captured_images_count']} ảnh crop bảng (200 DPI) tại: {audit_res['crops_dir']}."
    )
    logs.append(msg)
    logger.info("LangGraph [check_and_capture_tables]: %s", msg)

    return {
        **state,
        "table_audit_report": audit_res,
        "table_crops_dir": audit_res["crops_dir"],
        "logs": logs,
        "status": "TABLES_CHECKED_AND_CAPTURED",
    }


def route_after_table_check(state: IngestionState) -> str:
    """
    Conditional Edge: Điều phối rẽ nhánh sau khi kiểm tra bảng.
    - 'review' (interactive_review == True) -> Rẽ sang Node 'review_tables' (HITL Web Editor)
    - 'complete' (interactive_review == False) -> Kết thúc đồ thị (END)
    """
    if state.get("interactive_review", False):
        logger.info("LangGraph [Router]: Rẽ nhánh -> [review_tables] (Kích hoạt Human-in-the-Loop Web Editor)")
        return "review"
    logger.info("LangGraph [Router]: Rẽ nhánh -> [END] (Hoàn tất không qua bước tương tác)")
    return "complete"


def review_tables_node(state: IngestionState) -> IngestionState:
    """
    Node 6 (HITL): Giao diện rà soát & chỉnh sửa bảng biểu Markdown (Human-in-the-Loop).
    - Khởi động serve_md_editor trên port 8502.
    - Cho phép chuyên viên tài chính đối chiếu ảnh crop và chỉnh sửa số liệu trực tiếp.
    - Cập nhật đường dẫn file Markdown đã qua phê duyệt lần cuối (_final.md).
    """
    output_md = state.get("output_markdown_path", "") or state.get("output_md", "")
    logs = list(state.get("logs", []))

    if not output_md or not Path(output_md).exists():
        logger.warning("LangGraph [review_tables]: Không tìm thấy file Markdown để review, bỏ qua.")
        return state

    from serve_md_editor import run_editor_server

    md_file = Path(output_md).resolve()
    final_file = md_file.parent / f"{md_file.stem}_final.md"

    logger.info(
        "LangGraph [review_tables]: Đang khởi động HITL Table Editor cho file '%s'...",
        md_file.name,
    )
    msg = f"HITL Table Reviewer: Khởi động giao diện Web Review tại http://localhost:8502 cho file {md_file.name}."
    logs.append(msg)

    try:
        run_editor_server(file_path=md_file, port=8502, auto_open=True)
    except KeyboardInterrupt:
        pass

    if final_file.exists():
        msg_fin = f"HITL Table Reviewer: Người dùng đã hoàn tất chỉnh sửa và xuất file cuối: {final_file.resolve()}"
        logs.append(msg_fin)
        logger.info("LangGraph [review_tables]: %s", msg_fin)
    else:
        final_file = md_file

    return {
        **state,
        "final_markdown_path": str(final_file),
        "logs": logs,
        "status": "COMPLETED_WITH_HITL_REVIEW",
    }


def build_ingestion_graph():
    """Xây dựng và compile đồ thị LangGraph Ingestion & Triage Agent với phân nhánh Native vs Scanned và HITL Table Review."""
    workflow = StateGraph(IngestionState)

    # Thêm các Nodes
    workflow.add_node("detect_pdf_type", detect_pdf_type_node)
    workflow.add_node("extract_native_pipeline", extract_native_pipeline_node)
    workflow.add_node("inspect_toc", inspect_toc_node)
    workflow.add_node("extract_core_statements", extract_core_statements_node)
    workflow.add_node("extract_notes_rag", extract_notes_rag_node)
    workflow.add_node("compile_and_export", compile_and_export_node)
    workflow.add_node("check_and_capture_tables", check_and_capture_tables_node)
    workflow.add_node("review_tables", review_tables_node)

    # 1. Bắt đầu từ Node phát hiện loại tài liệu PDF
    workflow.add_edge(START, "detect_pdf_type")

    # 2. Rẽ nhánh điều kiện:
    #    - 'native' -> Nhánh Native PDF (pdfplumber)
    #    - 'scanned_or_hybrid' -> Nhánh Scanned/Hybrid (TOC -> Vision LLM -> Local OCR)
    workflow.add_conditional_edges(
        "detect_pdf_type",
        route_by_pdf_type,
        {
            "native": "extract_native_pipeline",
            "scanned_or_hybrid": "inspect_toc",
        },
    )

    # Nhánh 1 (Native PDF):
    workflow.add_edge("extract_native_pipeline", "compile_and_export")

    # Nhánh 2 (Scanned/Hybrid PDF):
    workflow.add_edge("inspect_toc", "extract_core_statements")
    workflow.add_edge("extract_core_statements", "extract_notes_rag")
    workflow.add_edge("extract_notes_rag", "compile_and_export")

    # 3. Bước Check & Capture Bảng (Chung cho cả 2 nhánh sau khi compile & export)
    workflow.add_edge("compile_and_export", "check_and_capture_tables")

    # 4. Rẽ nhánh điều kiện: Review tương tác (HITL) hoặc Kết thúc
    workflow.add_conditional_edges(
        "check_and_capture_tables",
        route_after_table_check,
        {
            "review": "review_tables",
            "complete": END,
        },
    )

    # Kết thúc sau khi review
    workflow.add_edge("review_tables", END)

    return workflow.compile()


class IngestionAgent:
    """Lớp giao diện thuận tiện để kích hoạt LangGraph Ingestion Pipeline."""

    def __init__(self) -> None:
        self.graph = build_ingestion_graph()

    def run(
        self,
        pdf_path: str,
        company: str = "VNM",
        year: int = 2024,
        notes_limit: int = 5,
        output_markdown: str = "",
        db_path: str = "data/finaudit.db",
        use_cache: bool = True,
        interactive_review: bool = False,
    ) -> IngestionState:
        """Thực thi toàn bộ luồng Ingestion."""
        initial_state: IngestionState = {
            "pdf_path": pdf_path,
            "company": company,
            "year": year,
            "notes_limit": notes_limit,
            "output_markdown_path": output_markdown,
            "db_path": db_path,
            "use_cache": use_cache,
            "interactive_review": interactive_review,
            "logs": [],
            "status": "INITIALIZED",
        }
        final_state = self.graph.invoke(initial_state)
        return final_state
