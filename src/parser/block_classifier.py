"""
block_classifier.py — Phân loại block đa tầng cho FinAudit AI.
Kiến trúc kết hợp:
  - Rule-based Heuristic (80% trường hợp): Tốc độ microsecond, chính xác cao cho BCTC chuẩn
  - LLM Fallback (20% trường hợp): Kích hoạt khi rule phân vân (confidence < 0.75) hoặc cấu trúc phức tạp
  - Quyết định đích lưu trữ: target = ["sql"], ["vector"], hoặc cả hai ["sql", "vector"]
"""

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from src.config import Settings, get_settings
from src.models import BlockType, ClassifiedBlock, ParsedBlock, StorageTarget

logger = logging.getLogger(__name__)

# ─── BỘ TỪ ĐIỂN TÀI CHÍNH VIỆT NAM (DOMAIN KEYWORDS) ──────────────────────────

# Bảng BCTC chính (Bảng Cân đối kế toán, KQKD, LCTT)
_FINANCIAL_STATEMENT_KEYWORDS = [
    "bảng cân đối kế toán",
    "báo cáo kết quả hoạt động kinh doanh",
    "kết quả hoạt động kinh doanh",
    "báo cáo lưu chuyển tiền tệ",
    "chỉ tiêu",
    "mã số",
    "thuyết minh",
    "số cuối năm",
    "số đầu năm",
    "kỳ này",
    "kỳ trước",
    "năm nay",
    "năm trước",
    "cuối kỳ",
    "đầu kỳ",
    "tổng cộng tài sản",
    "tổng cộng nguồn vốn",
    "lợi nhuận sau thuế",
    "doanh thu thuần",
]

# Thuyết minh chi tiết số liệu (Numeric Notes)
_NUMERIC_NOTE_KEYWORDS = [
    "thuyết minh số",
    "chi tiết",
    "số dư cuối kỳ",
    "số dư đầu năm",
    "phải thu khách hàng",
    "hàng tồn kho",
    "tài sản cố định",
    "vay và nợ thuê tài chính",
    "chi phí sản xuất",
    "stt",
    "đối tượng",
    "số tiền",
    "nguyên giá",
    "giá trị hao mòn",
    "dự phòng",
    "tổng số",
]

# Chính sách & nguyên tắc kế toán (Policy)
_POLICY_KEYWORDS = [
    "chính sách kế toán",
    "nguyên tắc kế toán",
    "chuẩn mực kế toán",
    "ghi nhận doanh thu",
    "phương pháp khấu hao",
    "ước tính kế toán",
    "chế độ kế toán",
    "đơn vị tiền tệ kế toán",
    "cơ sở lập báo cáo tài chính",
    "nguyên tắc chuyển đổi ngoại tệ",
]

# Báo cáo Ban Điều Hành / MD&A
_MDA_KEYWORDS = [
    "báo cáo của ban giám đốc",
    "báo cáo của ban tổng giám đốc",
    "báo cáo của hội đồng quản trị",
    "đánh giá của hội đồng quản trị",
    "tình hình hoạt động",
    "kế hoạch sản xuất kinh doanh",
    "triển vọng tương lai",
]


class _LLMClassificationOutput(BaseModel):
    """Schema Pydantic cho Structured Output từ LLM Fallback."""
    block_type: BlockType = Field(description="Loại block tài chính")
    target: list[StorageTarget] = Field(description="Danh sách đích lưu trữ ('sql', 'vector' hoặc cả hai)")
    confidence: float = Field(ge=0.0, le=1.0, description="Độ tin cậy của phân loại")
    reasoning: str = Field(description="Lý do ngắn gọn giải thích nhãn phân loại")


class BlockClassifier:
    """Bộ phân loại block văn bản và bảng biểu cho FinAudit AI."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._llm = None

    def classify_block(self, block: ParsedBlock) -> ClassifiedBlock:
        """
        Phân loại 1 ParsedBlock đơn lẻ.
        Thực hiện theo 2 tầng: Rule-based Heuristic -> LLM Fallback (nếu cần).
        """
        # Tầng 1: Rule-based heuristic
        rule_result = self._rule_classify(block)

        # Nếu độ tin cậy đạt ngưỡng yêu cầu, chấp nhận kết quả heuristic ngay
        if rule_result.confidence >= self.settings.rule_confidence_threshold:
            return rule_result

        # Tầng 2: LLM Fallback nếu tự tin thấp và có cấu hình LLM
        logger.debug(
            "Block %s có confidence %.2f < %.2f. Kích hoạt LLM fallback...",
            block.block_id,
            rule_result.confidence,
            self.settings.rule_confidence_threshold,
        )

        llm_result = self._llm_classify(block, default_fallback=rule_result)
        return llm_result

    def classify_blocks(self, blocks: list[ParsedBlock]) -> list[ClassifiedBlock]:
        """Phân loại toàn bộ danh sách ParsedBlock trong tài liệu."""
        classified = [self.classify_block(b) for b in blocks]
        
        # Thống kê nhanh kết quả phân loại
        counts: dict[str, int] = {}
        for c in classified:
            counts[c.block_type.value] = counts.get(c.block_type.value, 0) + 1
        logger.info("Thống kê phân loại block: %s", counts)

        return classified

    # ─── TẦNG 1: RULE-BASED HEURISTICS ──────────────────────────────────────────

    def _rule_classify(self, block: ParsedBlock) -> ClassifiedBlock:
        """Phân loại dựa trên tập luật nghiệp vụ tài chính."""
        content_lower = block.content.lower()

        if block.is_table:
            return self._classify_table(block, content_lower)
        else:
            return self._classify_text(block, content_lower)

    def _classify_table(self, block: ParsedBlock, content_lower: str) -> ClassifiedBlock:
        """Phân loại bảng biểu dựa trên header, numeric density và số dòng/cột."""
        header_text = block.get_header_row().lower()
        num_rows = block.num_rows
        num_cols = block.num_cols
        numeric_density = block.metadata.get("numeric_density", 0.0)

        # 1. Bảng nhỏ hoặc bảng phi số liệu (Narrative table)
        if (num_rows <= 3 and num_cols <= 2 and numeric_density < 0.20) or (
            num_rows > 1 and numeric_density < 0.10
        ):
            return ClassifiedBlock(
                block=block,
                block_type=BlockType.NARRATIVE_TABLE,
                target=[StorageTarget.VECTOR],
                confidence=0.85,
                classification_method="rule_based",
                reasoning="Bảng có mật độ số thấp (< 0.15) hoặc ít dòng/cột dạng danh sách mô tả",
            )

        # 2. Bảng BCTC chính (Bảng Cân đối, KQKD, LCTT)
        # Đặc trưng: Có "chỉ tiêu" hoặc "mã số" hoặc "thuyết minh" VÀ các cột kỳ so sánh ("kỳ này", "kỳ trước"...)
        has_statement_indicator = any(
            kw in header_text or kw in content_lower[:300]
            for kw in [
                "bảng cân đối kế toán",
                "kết quả hoạt động kinh doanh",
                "lưu chuyển tiền tệ",
                "chỉ tiêu",
                "mã số",
            ]
        )
        has_period_columns = any(
            kw in header_text for kw in ["kỳ này", "kỳ trước", "năm nay", "năm trước", "số cuối năm", "số đầu năm"]
        )

        if (has_statement_indicator and has_period_columns) or (
            has_statement_indicator and numeric_density >= self.settings.high_numeric_density_threshold
        ):
            return ClassifiedBlock(
                block=block,
                block_type=BlockType.FINANCIAL_STATEMENT,
                target=[StorageTarget.SQL, StorageTarget.VECTOR],
                confidence=0.95,
                classification_method="rule_based",
                reasoning="Bảng chứa các chỉ tiêu tài chính chính và cột kỳ so sánh (vào SQL facts + Vector markdown)",
            )

        # 3. Thuyết minh số (Numeric Note)
        # Đặc trưng: Bảng chi tiết cho các khoản mục như tồn kho, công nợ, vay nợ...
        has_note_keywords = any(
            kw in header_text or kw in content_lower[:200]
            for kw in _NUMERIC_NOTE_KEYWORDS
        )

        if has_note_keywords or numeric_density >= self.settings.high_numeric_density_threshold:
            conf = 0.88 if has_note_keywords else 0.76
            return ClassifiedBlock(
                block=block,
                block_type=BlockType.NUMERIC_NOTE,
                target=[StorageTarget.SQL],
                confidence=conf,
                classification_method="rule_based",
                reasoning="Bảng số liệu chi tiết thuyết minh tài chính với mật độ số cao",
            )

        # 4. Trường hợp nhập nhằng ở bảng
        return ClassifiedBlock(
            block=block,
            block_type=BlockType.NUMERIC_NOTE,
            target=[StorageTarget.SQL],
            confidence=0.60,  # Dưới ngưỡng 0.75 để kích hoạt LLM fallback nếu có
            classification_method="rule_based",
            reasoning="Bảng chưa khớp quy tắc dứt khoát, tạm gán Numeric Note",
        )

    def _classify_text(self, block: ParsedBlock, content_lower: str) -> ClassifiedBlock:
        """Phân loại đoạn văn bản: Policy, MD&A, Mixed hoặc Narrative.

        Issue #4 fix: Thay thế first-match wins bằng score aggregation.
        Mỗi loại được đếm số lượng từ khóa khớp, loại có điểm cao nhất thắng.
        Tie-break ưu tiên MDA > POLICY > MIXED > NARRATIVE để tránh văn bản
        MD&A bị gán POLICY do chia sẻ từ khóa "chính sách kế toán".
        """
        # Đếm điểm cho từng loại
        policy_matches = sum(1 for kw in _POLICY_KEYWORDS if kw in content_lower)
        mda_matches = sum(1 for kw in _MDA_KEYWORDS if kw in content_lower)

        # Kiểm tra Mixed Block: đoạn văn có tỷ lệ số cao kèm đơn vị tiền tệ
        numbers_found = re.findall(r"\b\d+(?:[.,]\d+)?\b", block.content)
        financial_units = re.findall(r"\b(?:tỷ|triệu|nghìn|vnd|usd|%)\b", content_lower)
        is_mixed = len(numbers_found) >= 3 and len(financial_units) >= 1

        # Quyết định bằng aggregated score — không dùng first-match wins
        # Ưu tiên tiebreak: MDA > POLICY (MDA thường cũng chứa từ khóa policy)
        if mda_matches > 0 and mda_matches >= policy_matches:
            conf = min(0.95, 0.75 + mda_matches * 0.10)
            return ClassifiedBlock(
                block=block,
                block_type=BlockType.MDA,
                target=[StorageTarget.VECTOR],
                confidence=conf,
                classification_method="rule_based",
                reasoning=(
                    f"Đoạn văn chứa {mda_matches} từ khóa báo cáo ban giám đốc/HĐQT"
                    + (f" (policy_matches={policy_matches} bị override)" if policy_matches > 0 else "")
                ),
            )

        if policy_matches > 0:
            conf = min(0.95, 0.75 + policy_matches * 0.10)
            return ClassifiedBlock(
                block=block,
                block_type=BlockType.POLICY,
                target=[StorageTarget.VECTOR],
                confidence=conf,
                classification_method="rule_based",
                reasoning=f"Đoạn văn chứa {policy_matches} cụm từ khóa chính sách và chuẩn mực kế toán",
            )

        if is_mixed:
            return ClassifiedBlock(
                block=block,
                block_type=BlockType.MIXED,
                target=[StorageTarget.SQL, StorageTarget.VECTOR],
                confidence=0.82,
                classification_method="rule_based",
                reasoning=f"Đoạn văn thuyết minh chứa nhiều số liệu định lượng cụ thể ({len(numbers_found)} số liệu)",
            )

        # Văn bản thuyết minh thông thường (Narrative)
        return ClassifiedBlock(
            block=block,
            block_type=BlockType.NARRATIVE,
            target=[StorageTarget.VECTOR],
            confidence=0.85,
            classification_method="rule_based",
            reasoning="Đoạn văn thuyết minh diễn giải thông thường",
        )


    # ─── TẦNG 2: LLM FALLBACK (20%) ─────────────────────────────────────────────

    def _get_llm(self) -> Any:
        """Khởi tạo LLM client dựa trên provider cấu hình."""
        if self._llm is not None:
            return self._llm

        provider = self.settings.llm_provider.lower()
        try:
            if provider == "groq" and self.settings.groq_api_key:
                from langchain_groq import ChatGroq
                self._llm = ChatGroq(
                    model=self.settings.groq_model,
                    api_key=self.settings.groq_api_key,
                    temperature=self.settings.llm_temperature,
                )
            elif provider == "openai" and self.settings.openai_api_key:
                from langchain_openai import ChatOpenAI
                self._llm = ChatOpenAI(
                    model=self.settings.openai_model,
                    api_key=self.settings.openai_api_key,
                    temperature=self.settings.llm_temperature,
                )
            else:
                self._llm = None
        except Exception as e:
            logger.warning("Không thể khởi tạo LLM (%s): %s", provider, e)
            self._llm = None

        return self._llm

    def _llm_classify(self, block: ParsedBlock, default_fallback: ClassifiedBlock) -> ClassifiedBlock:
        """Gọi LLM phân loại khi rule heuristic có độ tin cậy thấp."""
        llm = self._get_llm()
        if llm is None:
            # Nếu không có API key hoặc offline: giữ nguyên kết quả rule với ghi chú
            default_fallback.reasoning += " (Fallback offline: Chưa cấu hình API key LLM)"
            return default_fallback

        snippet = block.content[:800]
        prompt = (
            "Bạn là chuyên gia Document Intelligence phân tích Báo cáo tài chính (BCTC).\n"
            "Hãy phân loại khối văn bản/bảng biểu sau thành một trong các nhãn:\n"
            "- FINANCIAL_STATEMENT: Bảng Cân đối kế toán, Kết quả kinh doanh, Lưu chuyển tiền tệ chính -> target: [\"sql\", \"vector\"]\n"
            "- NUMERIC_NOTE: Bảng thuyết minh số liệu chi tiết (tồn kho, công nợ, vay nợ...) -> target: [\"sql\"]\n"
            "- NARRATIVE: Đoạn văn diễn giải ngữ nghĩa -> target: [\"vector\"]\n"
            "- POLICY: Chính sách, nguyên tắc và chuẩn mực kế toán -> target: [\"vector\"]\n"
            "- MDA: Báo cáo ban tổng giám đốc, ban điều hành -> target: [\"vector\"]\n"
            "- MIXED: Đoạn văn có chứa nhiều số liệu tài chính cụ thể -> target: [\"sql\", \"vector\"]\n"
            "- NARRATIVE_TABLE: Bảng danh sách hoặc phi số liệu -> target: [\"vector\"]\n\n"
            f"Loại block: {block.block_type}\n"
            f"Trang: {block.page}\n"
            f"Nội dung:\n{snippet}\n\n"
            "Trả về kết quả JSON với format: {\"block_type\": \"...\", \"target\": [\"...\"], \"confidence\": 0.9, \"reasoning\": \"...\"}"
        )

        try:
            # Thử structured output nếu hỗ trợ
            if hasattr(llm, "with_structured_output"):
                structured_llm = llm.with_structured_output(_LLMClassificationOutput)
                res: _LLMClassificationOutput = structured_llm.invoke(prompt)
                return ClassifiedBlock(
                    block=block,
                    block_type=res.block_type,
                    target=res.target,
                    confidence=res.confidence,
                    classification_method="llm_fallback",
                    reasoning=f"[LLM Groq/OpenAI] {res.reasoning}",
                )

            # Fallback JSON parsing
            response = llm.invoke(prompt)
            raw_text = response.content if hasattr(response, "content") else str(response)
            # Trích xuất JSON từ text
            json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                b_type = BlockType(data.get("block_type", default_fallback.block_type.value))
                targets = [StorageTarget(t) for t in data.get("target", ["vector"])]
                conf = float(data.get("confidence", 0.85))
                reasoning = data.get("reasoning", "Phân loại bởi LLM fallback")
                return ClassifiedBlock(
                    block=block,
                    block_type=b_type,
                    target=targets,
                    confidence=conf,
                    classification_method="llm_fallback",
                    reasoning=f"[LLM JSON] {reasoning}",
                )
        except Exception as e:
            logger.warning("Lỗi khi gọi LLM Fallback cho block %s: %s", block.block_id, e)

        return default_fallback
