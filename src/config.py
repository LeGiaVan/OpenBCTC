"""
config.py — Quản lý tập trung toàn bộ cấu hình hệ thống FinAudit AI.
Kế thừa triết lý từ FinRisk AI: Không hardcode key/value trong logic,
mọi cấu hình được load tự động qua pydantic-settings từ file .env hoặc biến môi trường.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cấu hình toàn hệ thống FinAudit AI."""

    # ── 1. LLM Configuration (Text & Chat Models) ─────────────────────────
    # Môi trường dev mặc định dùng Groq hoặc Gemini
    llm_provider: Literal["groq", "gemini", "openai", "anthropic"] = "groq"
    
    # Groq API
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    # Google Gemini API
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-lite-latest"

    # OpenAI API
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Anthropic Claude API
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-latest"

    # Tham số sinh lời LLM (0.0 đảm bảo tính deterministic cho tài chính)
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4096

    # ── 2. Phase 1: Block Classifier & Parser Settings ────────────────────
    # Ngưỡng tin cậy (confidence) của Rule-based heuristic. Nếu < threshold thì fallback LLM
    rule_confidence_threshold: float = 0.75

    # Tỷ lệ ô chứa số tối thiểu để coi bảng là bảng số liệu tài chính (Numeric density)
    high_numeric_density_threshold: float = 0.40

    # Số dòng tối thiểu để xem xét là bảng báo cáo tài chính hoàn chỉnh
    min_table_rows_for_statement: int = 3

    # Kích thước tối đa của đoạn văn bản cho 1 text block trước khi tách tiếp
    max_text_block_chars: int = 2500

    # ── 3. Vision OCR API (Cloud Vision LLM cho BCTC Cốt Lõi) ─────────────
    enable_ocr_fallback: bool = True
    ocr_provider: Literal["auto", "gemini", "groq"] = "auto"
    gemini_vision_model: str = "gemini-flash-lite-latest"
    groq_vision_model: str = "llama-3.2-11b-vision-preview"
    ocr_resolution: int = 150
    ocr_min_char_threshold: int = 50

    # ── 4. Offline Local OCR (VietOCR + DBNet cho Thuyết Minh & RAG) ──────
    local_ocr_engine: Literal["auto", "vietocr", "rapidocr"] = "auto"
    local_ocr_model: str = "vgg_seq2seq"
    local_ocr_device: str = "auto"  # "auto" (ưu tiên CUDA nếu có) | "cuda" | "cpu"
    local_ocr_resolution: int = 150
    local_ocr_use_cache: bool = True

    # ── 5. Agentic Vision-LLM Zoom Corrector (Tự Sửa Sai Cục Bộ) ──────────
    zoom_max_retries: int = 2
    zoom_confidence_threshold: float = 0.70
    zoom_padding_px: int = 15
    zoom_crop_dpi: int = 200

    # ── 6. Accounting Verifier (Anti-GIGO Invariants) ─────────────────────
    accounting_tolerance_ratio: float = 0.0001  # Dung sai tương đối 0.01%
    accounting_absolute_tolerance: float = 2.0  # Dung sai tuyệt đối làm tròn số học

    # ── 7. Storage & Database Paths ───────────────────────────────────────
    default_db_path: str = "data/finaudit.db"
    default_cache_dir: str = "data/cache"
    default_output_dir: str = "outputs"

    # ── 8. LangSmith / LLMOps Observability ───────────────────────────────
    langchain_tracing_v2: bool = False
    langchain_project: str = "FinAudit_AI"
    langchain_api_key: str = ""
    langchain_endpoint: str = "https://api.smith.langchain.com"

    # ── 9. Môi trường & Logging ───────────────────────────────────────────
    environment: str = "development"
    log_level: str = "INFO"

    # ── 10. Tích Hợp Hệ Sinh Thái OpenBCTC Copilot (Dual-Storage) ──────────
    enable_copilot_sync: bool = True
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "openbctc"
    copilot_api_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Singleton pattern — parse .env một lần duy nhất và cache lại trong bộ nhớ.
    Có thể dùng dependency injection trong API hoặc mock trong test suite.
    """
    return Settings()


def get_run_dir(company: str = "VNM", year: int | str = 2025, project_root: Path | None = None) -> Path:
    """
    Trả về thư mục hợp nhất chứa toàn bộ output & cache của một kỳ BCTC:
    outputs/{company}_{year}/
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    c = (company or "VNM").upper().strip()
    y = str(year or 2025).strip()
    tag = f"{c}_{y}" if y and y != "0" else c
    d = project_root / "outputs" / tag
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_run_cache_dir(company: str = "VNM", year: int | str = 2025, sub: str = "notes", project_root: Path | None = None) -> Path:
    """
    Trả về thư mục cache hợp nhất: outputs/{company}_{year}/cache/{sub}/
    """
    run_d = get_run_dir(company, year, project_root)
    cache_d = run_d / "cache" / sub
    cache_d.mkdir(parents=True, exist_ok=True)
    return cache_d


def find_cache_file(company: str, year: int | str, sub: str, filename: str, project_root: Path | None = None) -> Path:
    """
    Tìm cache file: Ưu tiên outputs/{company}_{year}/cache/{sub}/{filename},
    sau đó fallback về data/cache/{sub}/{company}_{year}/{filename}.
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    c = (company or "VNM").upper().strip()
    y = str(year or 2025).strip()
    tag = f"{c}_{y}" if y and y != "0" else c

    cand1 = project_root / "outputs" / tag / "cache" / sub / filename
    if cand1.exists():
        return cand1
    cand2 = project_root / "data" / "cache" / sub / tag / filename
    if cand2.exists():
        return cand2
    return cand1
