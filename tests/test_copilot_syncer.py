"""tests/test_copilot_syncer.py — Unit tests cho CopilotSyncer (Dual-Storage)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from src.uploader.copilot_syncer import CopilotSyncer


def test_copilot_syncer_disabled(tmp_path: Path):
    """Khi ENABLE_COPILOT_SYNC=False, syncer bỏ qua mà không làm gì."""
    syncer = CopilotSyncer(enabled=False)
    res = syncer.sync_company_run(
        company="TEST",
        year=2025,
        output_dir=tmp_path,
    )
    assert res["status"] == "SKIPPED"
    assert res["reason"] == "SYNC_DISABLED"


def test_copilot_syncer_output_not_found(tmp_path: Path):
    """Khi thư mục output không tồn tại, trả về status ERROR an toàn."""
    syncer = CopilotSyncer(enabled=True)
    non_existent = tmp_path / "not_found"
    res = syncer.sync_company_run(
        company="TEST",
        year=2025,
        output_dir=non_existent,
    )
    assert res["status"] == "ERROR"
    assert res["reason"] == "OUTPUT_NOT_FOUND"


def test_copilot_syncer_mongo_unreachable(tmp_path: Path):
    """Khi không thể kết nối MongoDB, trả về status WARNING chứ không throw Exception (Graceful Degradation)."""
    # Cổng 9999 không có MongoDB lắng nghe
    syncer = CopilotSyncer(
        enabled=True,
        mongo_uri="mongodb://localhost:9999",
        db_name="test_db",
    )
    res = syncer.sync_company_run(
        company="TEST",
        year=2025,
        output_dir=tmp_path,
    )
    assert res["status"] == "WARNING"
    assert res["reason"] == "MONGO_UNREACHABLE"
