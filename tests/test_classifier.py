"""
test_classifier.py — Unit tests kiểm thử Block Classifier đa tầng của FinAudit AI.
"""

from unittest.mock import MagicMock

from src.config import Settings
from src.models import BlockType, ParsedBlock, StorageTarget
from src.parser.block_classifier import BlockClassifier
from src.parser.table_utils import format_table_to_markdown


class TestBlockClassifierRuleBased:
    """Kiểm thử tầng Rule-based Heuristics (80% trường hợp)."""

    def test_classify_financial_statement(self, sample_balance_sheet_table):
        """Bảng Cân đối kế toán -> FINANCIAL_STATEMENT -> target: ['sql', 'vector']."""
        classifier = BlockClassifier()
        md = format_table_to_markdown(sample_balance_sheet_table)
        block = ParsedBlock(
            block_id="p5_b1",
            block_type="table",
            page=5,
            content=md,
            metadata={
                "headers": sample_balance_sheet_table[0],
                "numeric_density": 0.50,
                "num_rows": len(sample_balance_sheet_table),
                "num_cols": len(sample_balance_sheet_table[0]),
            },
        )

        classified = classifier.classify_block(block)
        assert classified.block_type == BlockType.FINANCIAL_STATEMENT
        assert StorageTarget.SQL in classified.target
        assert StorageTarget.VECTOR in classified.target
        assert classified.confidence >= 0.90
        assert classified.classification_method == "rule_based"

    def test_classify_numeric_note(self, sample_numeric_note_inventory):
        """Bảng chi tiết hàng tồn kho -> NUMERIC_NOTE -> target: ['sql']."""
        classifier = BlockClassifier()
        md = format_table_to_markdown(sample_numeric_note_inventory)
        block = ParsedBlock(
            block_id="p15_b2",
            block_type="table",
            page=15,
            content=md,
            metadata={
                "headers": sample_numeric_note_inventory[0],
                "numeric_density": 0.45,
                "num_rows": len(sample_numeric_note_inventory),
                "num_cols": len(sample_numeric_note_inventory[0]),
            },
        )

        classified = classifier.classify_block(block)
        assert classified.block_type == BlockType.NUMERIC_NOTE
        assert classified.target == [StorageTarget.SQL]
        assert classified.is_sql_target is True
        assert classified.is_vector_target is False
        assert classified.confidence >= 0.75

    def test_classify_narrative_table(self, sample_narrative_table_board):
        """Bảng danh sách thành viên HĐQT (ít số) -> NARRATIVE_TABLE -> target: ['vector']."""
        classifier = BlockClassifier()
        md = format_table_to_markdown(sample_narrative_table_board)
        block = ParsedBlock(
            block_id="p4_b1",
            block_type="table",
            page=4,
            content=md,
            metadata={
                "headers": sample_narrative_table_board[0],
                "numeric_density": 0.0,
                "num_rows": 3,
                "num_cols": 3,
            },
        )

        classified = classifier.classify_block(block)
        assert classified.block_type == BlockType.NARRATIVE_TABLE
        assert classified.target == [StorageTarget.VECTOR]
        assert classified.is_vector_target is True

    def test_classify_policy_text(self, sample_policy_text_block):
        """Văn bản chính sách kế toán -> POLICY -> target: ['vector']."""
        classifier = BlockClassifier()
        classified = classifier.classify_block(sample_policy_text_block)

        assert classified.block_type == BlockType.POLICY
        assert classified.target == [StorageTarget.VECTOR]
        assert classified.confidence >= 0.85

    def test_classify_mda_text(self, sample_mda_text_block):
        """Văn bản Báo cáo Ban Giám Đốc -> MDA -> target: ['vector']."""
        classifier = BlockClassifier()
        classified = classifier.classify_block(sample_mda_text_block)

        assert classified.block_type == BlockType.MDA
        assert classified.target == [StorageTarget.VECTOR]
        assert classified.confidence >= 0.85

    def test_classify_mixed_text(self, sample_mixed_text_block):
        """Văn bản kèm nhiều số liệu định lượng cụ thể -> MIXED -> target: ['sql', 'vector']."""
        classifier = BlockClassifier()
        classified = classifier.classify_block(sample_mixed_text_block)

        assert classified.block_type == BlockType.MIXED
        assert StorageTarget.SQL in classified.target
        assert StorageTarget.VECTOR in classified.target

    def test_classify_narrative_text(self):
        """Văn bản thuyết minh thông thường -> NARRATIVE -> target: ['vector']."""
        classifier = BlockClassifier()
        block = ParsedBlock(
            block_id="p2_b1",
            block_type="text",
            page=2,
            content="Công ty được thành lập theo Giấy chứng nhận đăng ký doanh nghiệp số 0300588569 do Sở Kế hoạch và Đầu tư cấp.",
            metadata={},
        )
        classified = classifier.classify_block(block)
        assert classified.block_type == BlockType.NARRATIVE
        assert classified.target == [StorageTarget.VECTOR]


class TestBlockClassifierLLMFallback:
    """Kiểm thử tầng LLM Fallback (20% trường hợp khi rule confidence thấp)."""

    def test_llm_fallback_when_mocked(self):
        """Giả lập LLM fallback trả về kết quả Structured Output khi rule phân vân."""
        # Tạo block bảng nhập nhằng không khớp từ khóa rõ rệt
        block = ParsedBlock(
            block_id="p25_b3",
            block_type="table",
            page=25,
            content="| Danh mục | Số liệu |\n| --- | --- |\n| Khoản mục X | 50.000 |",
            metadata={"headers": ["Danh mục", "Số liệu"], "numeric_density": 0.30, "num_rows": 2, "num_cols": 2},
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_output = MagicMock()
        mock_output.block_type = BlockType.NUMERIC_NOTE
        mock_output.target = [StorageTarget.SQL]
        mock_output.confidence = 0.92
        mock_output.reasoning = "Bảng chi tiết số liệu bổ sung thuyết minh tài chính"
        mock_structured.invoke.return_value = mock_output
        mock_llm.with_structured_output.return_value = mock_structured

        classifier = BlockClassifier()
        classifier._llm = mock_llm

        classified = classifier.classify_block(block)
        assert classified.block_type == BlockType.NUMERIC_NOTE
        assert classified.classification_method == "llm_fallback"
        assert classified.confidence == 0.92
        assert "[LLM Groq/OpenAI]" in classified.reasoning

    def test_llm_fallback_graceful_when_no_key(self):
        """Khi không có API key LLM, hệ thống hạ cánh an toàn (graceful fallback) về kết quả rule."""
        settings = Settings(groq_api_key="", openai_api_key="", rule_confidence_threshold=0.99)
        classifier = BlockClassifier(settings=settings)

        block = ParsedBlock(
            block_id="p30_b1",
            block_type="table",
            page=30,
            content="| Cột A | Cột B |\n| --- | --- |\n| Data | 100 |",
            metadata={"headers": ["Cột A", "Cột B"], "numeric_density": 0.25, "num_rows": 2, "num_cols": 2},
        )

        classified = classifier.classify_block(block)
        # Vẫn trả về kết quả hợp lệ, không ném exception làm gián đoạn pipeline
        assert classified.block_type in (BlockType.NUMERIC_NOTE, BlockType.NARRATIVE_TABLE)
        assert "Fallback offline" in classified.reasoning
