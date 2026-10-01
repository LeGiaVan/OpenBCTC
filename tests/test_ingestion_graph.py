"""
test_ingestion_graph.py — Unit tests cho LangGraph Ingestion & Triage Agent.
"""

from unittest.mock import MagicMock, patch

from src.agents.ingestion_graph import (
    build_ingestion_graph,
    check_and_capture_tables_node,
    compile_and_export_node,
    detect_pdf_type_node,
    extract_core_statements_node,
    extract_native_pipeline_node,
    extract_notes_rag_node,
    inspect_toc_node,
    route_after_table_check,
    route_by_pdf_type,
)
from src.agents.ingestion_state import IngestionState
from src.agents.toc_inspector import DocumentStructure
from src.models import FinancialFact, ParsedBlock, StorageTarget, VerificationReport


def test_build_ingestion_graph():
    """Kiểm tra việc biên dịch StateGraph thành công."""
    graph = build_ingestion_graph()
    assert graph is not None


def test_inspect_toc_node_mocked():
    """Kiểm tra thực thi node inspect_toc với mocked TOCInspector."""
    mock_struct = DocumentStructure(
        total_pages=54,
        toc_found=True,
        toc_page=2,
        core_statement_pages=[7, 8, 9, 10, 11],
        notes_pages=list(range(12, 55)),
        intro_pages=[1, 2, 3, 4, 5, 6],
        page_offset=1,
    )

    state: IngestionState = {
        "pdf_path": "fake.pdf",
        "company": "VNM",
        "year": 2024,
        "logs": [],
    }

    with patch("src.agents.ingestion_graph.TOCInspector.inspect", return_value=mock_struct):
        next_state = inspect_toc_node(state)

    assert next_state["status"] == "TOC_INSPECTED"
    assert next_state["doc_structure"].toc_page == 2
    assert next_state["doc_structure"].core_statement_pages == [7, 8, 9, 10, 11]
    assert len(next_state["logs"]) == 1


def test_compile_and_export_node(tmp_path):
    """Kiểm tra việc hợp nhất blocks và xuất Markdown."""
    out_md = tmp_path / "test_out.md"

    b1 = ParsedBlock(
        block_id="p7_b1",
        block_type="table",
        page=7,
        content="| Chỉ tiêu | Mã số | Số cuối năm |\n| TÀI SẢN NGẮN HẠN | 100 | 27.000.000.000 |",
        source="ocr",
        target=[StorageTarget.SQL, StorageTarget.VECTOR],
    )
    b2 = ParsedBlock(
        block_id="p12_b1",
        block_type="text",
        page=12,
        content="Thuyết minh số 1: Tóm tắt chính sách kế toán quan trọng.",
        source="local_ocr",
        target=[StorageTarget.VECTOR],
    )

    state: IngestionState = {
        "company": "VNM",
        "year": 2024,
        "core_blocks": [b1],
        "notes_blocks": [b2],
        "output_markdown_path": str(out_md),
        "logs": [],
    }

    next_state = compile_and_export_node(state)

    assert next_state["status"] == "COMPILED_AND_EXPORTED"
    assert next_state["summary_metrics"]["total_blocks"] == 2
    assert out_md.exists()
    content = out_md.read_text(encoding="utf-8")
    assert "BÁO CÁO TÀI CHÍNH — VNM" in content
    assert "TÀI SẢN NGẮN HẠN" in content


def test_extract_core_statements_node_native_routing(tmp_path):
    """Kiểm tra định tuyến sang TextParser (pdfplumber) khi các trang Core là Native Text."""
    dummy_pdf = tmp_path / "dummy_native.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    mock_struct = DocumentStructure(
        total_pages=10,
        toc_found=True,
        toc_page=2,
        core_statement_pages=[7, 8],
        notes_pages=[9, 10],
        intro_pages=[1, 2, 3, 4, 5, 6],
        page_offset=1,
    )

    state: IngestionState = {
        "pdf_path": str(dummy_pdf),
        "company": "VNM",
        "year": 2024,
        "db_path": str(tmp_path / "test.db"),
        "doc_structure": mock_struct,
        "logs": [],
    }

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "BẢNG CÂN ĐỐI KẾ TOÁN VĂN BẢN SỐ HÓA " * 5

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page] * 10

    mock_block = ParsedBlock(
        block_id="p7_b1",
        block_type="table",
        page=7,
        content="| Chỉ tiêu | Mã số | Số cuối năm |\n| TÀI SẢN NGẮN HẠN | 100 | 27000000000 |",
        source="pdfplumber",
    )

    with patch("pdfplumber.open") as mock_open, \
         patch("src.agents.ingestion_graph.TextParser.parse_pages", return_value=[mock_block]) as mock_text_parser, \
         patch("src.agents.ingestion_graph.VisionOCRPipeline.process_pages") as mock_vision_ocr:

        mock_open.return_value.__enter__.return_value = mock_pdf
        next_state = extract_core_statements_node(state)

    assert mock_text_parser.called
    assert not mock_vision_ocr.called
    assert next_state["status"] == "CORE_STATEMENTS_EXTRACTED"
    assert next_state["core_blocks"][0].block.source == "pdfplumber"


def test_extract_core_statements_node_scanned_routing(tmp_path):
    """Kiểm tra định tuyến sang VisionOCRPipeline khi các trang Core là Scanned Image."""
    dummy_pdf = tmp_path / "dummy_scanned.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    mock_struct = DocumentStructure(
        total_pages=10,
        toc_found=True,
        toc_page=2,
        core_statement_pages=[7],
        notes_pages=[8, 9, 10],
        intro_pages=[1, 2, 3, 4, 5, 6],
        page_offset=1,
    )

    state: IngestionState = {
        "pdf_path": str(dummy_pdf),
        "company": "VNM",
        "year": 2024,
        "db_path": str(tmp_path / "test.db"),
        "doc_structure": mock_struct,
        "logs": [],
    }

    mock_page = MagicMock()
    mock_page.extract_text.return_value = ""

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page] * 10

    mock_block = ParsedBlock(
        block_id="p7_b1",
        block_type="table",
        page=7,
        content="| Chỉ tiêu | Mã số | Số cuối năm |\n| TÀI SẢN NGẮN HẠN | 100 | 27000000000 |",
        source="ocr",
    )

    with patch("pdfplumber.open") as mock_open, \
         patch("src.agents.ingestion_graph.TextParser.parse_pages") as mock_text_parser, \
         patch("src.agents.ingestion_graph.VisionOCRPipeline.process_pages", return_value=[mock_block]) as mock_vision_ocr:

        mock_open.return_value.__enter__.return_value = mock_pdf
        next_state = extract_core_statements_node(state)

    assert mock_vision_ocr.called
    assert not mock_text_parser.called
    assert next_state["status"] == "CORE_STATEMENTS_EXTRACTED"
    assert next_state["core_blocks"][0].block.source == "ocr"


def test_extract_notes_rag_node_native_routing(tmp_path):
    """Kiểm tra định tuyến Thuyết minh sang TextParser (pdfplumber) khi trang là Native Text."""
    dummy_pdf = tmp_path / "dummy_notes.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    mock_struct = DocumentStructure(
        total_pages=15,
        toc_found=True,
        toc_page=2,
        core_statement_pages=[7, 8],
        notes_pages=[12, 13],
        intro_pages=[1, 2, 3, 4, 5, 6],
        page_offset=1,
    )

    state: IngestionState = {
        "pdf_path": str(dummy_pdf),
        "company": "VNM",
        "year": 2024,
        "doc_structure": mock_struct,
        "notes_limit": 2,
        "logs": [],
    }

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Thuyết minh báo cáo tài chính văn bản số hóa dạng native " * 5

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page] * 15

    mock_block = ParsedBlock(
        block_id="p12_b1",
        block_type="text",
        page=12,
        content="Thuyết minh số 1: Đặc điểm hoạt động...",
        source="pdfplumber",
    )

    with patch("pdfplumber.open") as mock_open, \
         patch("src.agents.ingestion_graph.TextParser.parse_pages", return_value=[mock_block]) as mock_text_parser, \
         patch("src.agents.ingestion_graph.LocalOCREngine.process_pages") as mock_local_ocr:

        mock_open.return_value.__enter__.return_value = mock_pdf
        next_state = extract_notes_rag_node(state)

    assert mock_text_parser.called
    assert not mock_local_ocr.called
    assert len(next_state["notes_blocks"]) == 1
    assert next_state["notes_blocks"][0].source == "pdfplumber"


def test_detect_pdf_type_node_native():
    """Kiểm tra Phase detect_pdf_type nhận diện tài liệu Native PDF."""
    from src.parser.pdf_type_detector import DocumentClassification, PageClassification

    mock_doc = DocumentClassification(
        total_pages=10,
        text_pages_count=10,
        scanned_pages_count=0,
        is_predominantly_scanned=False,
        pages=[PageClassification(page=i, page_type="text", char_count=100, images_count=0, has_tables=True) for i in range(1, 11)],
    )

    state: IngestionState = {"pdf_path": "fake_native.pdf", "logs": []}

    with patch("src.agents.ingestion_graph.PDFTypeDetector.classify_document", return_value=mock_doc):
        next_state = detect_pdf_type_node(state)

    assert next_state["status"] == "PDF_TYPE_DETECTED"
    assert next_state["pdf_type"] == "native"
    assert len(next_state["page_types"]) == 10


def test_detect_pdf_type_node_scanned():
    """Kiểm tra Phase detect_pdf_type nhận diện tài liệu Scanned PDF."""
    from src.parser.pdf_type_detector import DocumentClassification, PageClassification

    mock_doc = DocumentClassification(
        total_pages=10,
        text_pages_count=0,
        scanned_pages_count=10,
        is_predominantly_scanned=True,
        pages=[PageClassification(page=i, page_type="scanned", char_count=0, images_count=1, has_tables=False) for i in range(1, 11)],
    )

    state: IngestionState = {"pdf_path": "fake_scanned.pdf", "logs": []}

    with patch("src.agents.ingestion_graph.PDFTypeDetector.classify_document", return_value=mock_doc):
        next_state = detect_pdf_type_node(state)

    assert next_state["status"] == "PDF_TYPE_DETECTED"
    assert next_state["pdf_type"] == "scanned"


def test_route_by_pdf_type():
    """Kiểm tra hàm rẽ nhánh điều kiện route_by_pdf_type."""
    assert route_by_pdf_type({"pdf_type": "native"}) == "native"
    assert route_by_pdf_type({"pdf_type": "scanned"}) == "scanned_or_hybrid"
    assert route_by_pdf_type({"pdf_type": "hybrid"}) == "scanned_or_hybrid"


def test_full_graph_native_branch_execution(tmp_path):
    """Kiểm tra toàn bộ StateGraph rẽ nhánh sang extract_native_pipeline khi là Native PDF."""
    out_md = tmp_path / "native_out.md"
    dummy_pdf = tmp_path / "dummy.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    mock_struct = DocumentStructure(
        total_pages=10,
        toc_found=True,
        toc_page=2,
        core_statement_pages=[7, 8],
        notes_pages=[9, 10],
        intro_pages=[1, 2, 3, 4, 5, 6],
        page_offset=1,
    )

    mock_block = ParsedBlock(
        block_id="p7_b1",
        block_type="table",
        page=7,
        content="| Chỉ tiêu | Mã số | Số cuối năm |\n| TÀI SẢN NGẮN HẠN | 100 | 27000000000 |",
        source="pdfplumber",
    )

    state: IngestionState = {
        "pdf_path": str(dummy_pdf),
        "company": "VNM",
        "year": 2024,
        "db_path": str(tmp_path / "test.db"),
        "notes_limit": 2,
        "output_markdown_path": str(out_md),
        "logs": [],
    }

    from src.parser.pdf_type_detector import DocumentClassification, PageClassification
    mock_doc = DocumentClassification(
        total_pages=10,
        text_pages_count=10,
        scanned_pages_count=0,
        is_predominantly_scanned=False,
        pages=[PageClassification(page=i, page_type="text", char_count=100, images_count=0, has_tables=True) for i in range(1, 11)],
    )

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "TEXT CONTENT " * 10
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page] * 10

    mock_report = {
        "total_tables": 1,
        "valid_tables": 1,
        "tables_with_warnings": 0,
        "captured_images_count": 1,
        "crops_dir": str(tmp_path / "crops"),
        "table_reports": [{"table_id": 1, "is_valid": True, "n_rows": 2, "n_cols": 3}],
    }

    with patch("src.parser.pdf_type_detector.PDFTypeDetector.classify_document", return_value=mock_doc), \
         patch("src.agents.ingestion_graph.TOCInspector.inspect", return_value=mock_struct), \
         patch("pdfplumber.open") as mock_open, \
         patch("src.agents.ingestion_graph.TextParser.parse_pages", return_value=[mock_block]), \
         patch("src.agents.ingestion_graph.VisionOCRPipeline.process_pages") as mock_vision_ocr, \
         patch("src.verifier.table_verifier.TableInspector.process_document_tables", return_value=mock_report):

        mock_open.return_value.__enter__.return_value = mock_pdf

        graph = build_ingestion_graph()
        final_state = graph.invoke(state)

    # Đảm bảo nhánh Native PDF đã chạy trọn vẹn và không gọi Vision OCR
    assert final_state["status"] == "TABLES_CHECKED_AND_CAPTURED"
    assert final_state["pdf_type"] == "native"
    assert not mock_vision_ocr.called
    assert out_md.exists()


def test_extract_native_pipeline_triggers_zoom_corrector_when_imbalanced(tmp_path):
    """Kiểm tra nhánh Native PDF kích hoạt VisionZoomCorrector khi phát hiện sai lệch số học."""
    dummy_pdf = tmp_path / "dummy_native.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    mock_struct = DocumentStructure(
        total_pages=5,
        toc_found=True,
        toc_page=1,
        core_statement_pages=[2],
        notes_pages=[],
        intro_pages=[1],
        page_offset=1,
    )

    state: IngestionState = {
        "pdf_path": str(dummy_pdf),
        "company": "VNM",
        "year": 2024,
        "db_path": str(tmp_path / "test.db"),
        "notes_limit": 0,
        "logs": [],
    }

    mock_block = ParsedBlock(
        block_id="p2_b1",
        block_type="table",
        page=2,
        content="| Chỉ tiêu | Mã số | Số cuối năm |\n| TỔNG TÀI SẢN | 270 | 40000000000 |",
        source="pdfplumber",
    )

    imbalanced_report = VerificationReport(
        company="VNM",
        year=2024,
        is_balanced=False,
        failed_checks=["LỆCH_TÀI_SẢN: Báo cáo (40 tỷ) != Tính toán (45 tỷ)"],
    )
    balanced_report = VerificationReport(
        company="VNM",
        year=2024,
        is_balanced=True,
        passed_checks=["CỘNG_TỔNG_TÀI_SẢN"],
    )

    dummy_fact = FinancialFact(
        id="fact_1",
        prov_id="p2_r1",
        concept="TOTAL_ASSETS",
        standard_code="270",
        raw_label="TỔNG TÀI SẢN",
        value=40000000000.0,
        page=2,
    )
    fixed_fact = dummy_fact.model_copy(update={"value": 45000000000.0})

    mock_page = MagicMock()
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page] * 5

    with patch("src.agents.ingestion_graph.TOCInspector.inspect", return_value=mock_struct), \
         patch("pdfplumber.open") as mock_open, \
         patch("src.agents.ingestion_graph.TextParser.parse_pages", return_value=[mock_block]), \
         patch("src.agents.ingestion_graph.FinancialFactExtractor.extract_from_blocks", return_value=([dummy_fact], imbalanced_report)), \
         patch("src.verifier.vision_zoom_corrector.VisionZoomCorrector.run_self_correction", return_value=([fixed_fact], balanced_report, True)) as mock_zoom:

        mock_open.return_value.__enter__.return_value = mock_pdf

        result_state = extract_native_pipeline_node(state)

    # Đảm bảo Zoom Corrector đã được gọi để cứu nguy
    assert mock_zoom.called
    assert result_state["audit_report"].is_balanced is True
    assert any("Agentic Self-Correction (Native)" in log for log in result_state["logs"])


def test_check_and_capture_tables_node(tmp_path):
    """Kiểm tra Node check_and_capture_tables phân tích chất lượng bảng và tạo báo cáo."""
    dummy_md = tmp_path / "test_report.md"
    dummy_md.write_text(
        "# Báo cáo tài chính\n\n"
        "*(Trang 7)*\n\n"
        "| Chỉ tiêu | Mã số | Năm nay | Năm trước |\n"
        "| --- | --- | --- | --- |\n"
        "| Tiền | 110 | 100.000 | 80.000 |\n"
        "| Phải thu | 130 | 200.000 | 150.000 |\n",
        encoding="utf-8"
    )

    state: IngestionState = {
        "pdf_path": "fake.pdf",
        "company": "VNM",
        "year": 2024,
        "output_markdown_path": str(dummy_md),
        "logs": [],
    }

    mock_report = {
        "total_tables": 1,
        "valid_tables": 1,
        "tables_with_warnings": 0,
        "captured_images_count": 1,
        "crops_dir": str(tmp_path / "crops"),
        "table_reports": [{"table_id": 1, "is_valid": True, "n_rows": 2, "n_cols": 4}],
    }

    with patch("src.verifier.table_verifier.TableInspector.process_document_tables", return_value=mock_report):
        next_state = check_and_capture_tables_node(state)

    assert next_state["status"] == "TABLES_CHECKED_AND_CAPTURED"
    assert next_state["table_audit_report"]["total_tables"] == 1
    assert next_state["table_audit_report"]["valid_tables"] == 1
    assert any("Table Inspector: Đã kiểm toán & capture" in l for l in next_state["logs"])


def test_route_after_table_check():
    """Kiểm tra điều hướng rẽ nhánh sau khi kiểm tra bảng."""
    assert route_after_table_check({"interactive_review": True}) == "review"
    assert route_after_table_check({"interactive_review": False}) == "complete"
    assert route_after_table_check({}) == "complete"
