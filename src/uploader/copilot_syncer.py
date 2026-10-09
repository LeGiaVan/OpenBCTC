"""src/uploader/copilot_syncer.py — Service đồng bộ dữ liệu OpenBCTC sang OpenBCTC Copilot.

Đặc điểm thiết kế:
- Tuân thủ nguyên tắc Lean Service: Nhẹ, tự chủ, không làm treo đồ thị LangGraph.
- Graceful Degradation: Nếu MongoDB/Docker chưa bật, service chỉ ghi cảnh báo và tiếp tục,
  tuyệt đối không gây crash pipeline OCR của OpenBCTC.
- Dual-Storage: Lưu song song cả Local File System và MongoDB GridFS + Collections.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("OpenBCTC.Syncer")

try:
    from pymongo import MongoClient
    import gridfs

    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    logger.warning("Thư viện 'pymongo' chưa được cài đặt. Đồng bộ Copilot sẽ tạm thời tắt.")

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class CopilotSyncer:
    """Đồng bộ tài sản OCR từ outputs/ của OpenBCTC sang MongoDB GridFS & Copilot API."""

    def __init__(
        self,
        mongo_uri: str | None = None,
        db_name: str | None = None,
        copilot_api_url: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.enabled = (
            enabled
            if enabled is not None
            else os.getenv("ENABLE_COPILOT_SYNC", "true").lower() in ("true", "1", "yes")
        )
        self.mongo_uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = db_name or os.getenv("MONGO_DB", "openbctc")
        self.copilot_api_url = copilot_api_url or os.getenv("COPILOT_API_URL", "http://localhost:8000")

    def sync_company_run(
        self,
        company: str,
        year: int,
        output_dir: Path | str,
        pdf_path: Path | str | None = None,
        trigger_ingest: bool = True,
    ) -> dict[str, Any]:
        """Bơm toàn bộ tài sản của một doanh nghiệp vào MongoDB của Copilot.

        Args:
            company: Mã cổ phiếu (VD: 'VNM').
            year: Năm tài chính (VD: 2025).
            output_dir: Thư mục chứa kết quả (VD: 'outputs/VNM_2025').
            pdf_path: Đường dẫn file PDF gốc.
            trigger_ingest: Tự động gửi webhook sang Copilot API để index Qdrant.
        """
        if not self.enabled:
            logger.info("Chế độ đồng bộ Copilot đang TẮT (ENABLE_COPILOT_SYNC=false). Bỏ qua.")
            return {"status": "SKIPPED", "reason": "SYNC_DISABLED"}

        if not PYMONGO_AVAILABLE:
            logger.warning("Thiếu thư viện pymongo. Dữ liệu vẫn được lưu an toàn tại thư mục local.")
            return {"status": "SKIPPED", "reason": "PYMONGO_MISSING"}

        out_path = Path(output_dir).resolve()
        if not out_path.exists():
            logger.error("Thư mục output không tồn tại: %s", out_path)
            return {"status": "ERROR", "reason": "OUTPUT_NOT_FOUND"}

        company_upper = company.upper()
        company_lower = company.lower()
        clean_stem = f"{company_upper}_{year}"

        logger.info("🚀 Bắt đầu đồng bộ dữ liệu [%s - %s] sang Copilot...", company_upper, year)

        try:
            # Kết nối Mongo với timeout 3 giây để tránh treo máy nếu Docker chưa bật
            client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=3000)
            client.admin.command("ping")
            db = client[self.db_name]
            fs = gridfs.GridFS(db)
            blocks_collection = db["document_blocks"]
            benchmarks_collection = db["ocr_benchmarks"]
        except Exception as e:
            logger.warning(
                "⚠️ Không thể kết nối MongoDB (%s). Dữ liệu vẫn an toàn tại thư mục local! Chi tiết: %s",
                self.mongo_uri,
                e,
            )
            return {"status": "WARNING", "reason": "MONGO_UNREACHABLE", "detail": str(e)}

        synced_items: list[str] = []

        # -------------------------------------------------------------
        # 1. ĐẨY FILE PDF GỐC VÀO GRIDFS (Dùng cho Streaming & Visual BBox)
        # -------------------------------------------------------------
        resolved_pdf: Path | None = None
        if pdf_path and Path(pdf_path).exists():
            resolved_pdf = Path(pdf_path).resolve()
        else:
            candidates = [
                Path(f"pdf_files/{clean_stem}.pdf"),
                Path(f"pdf_files/{company_upper}.pdf"),
                out_path / f"{clean_stem}.pdf",
                out_path / f"{company_upper}_{year}.pdf",
            ]
            for cand in candidates:
                if cand.exists():
                    resolved_pdf = cand.resolve()
                    break

        if resolved_pdf and resolved_pdf.exists():
            pdf_filename = f"{company_lower}_{year}.pdf"
            for old in fs.find({"filename": pdf_filename}):
                fs.delete(old._id)
            with open(resolved_pdf, "rb") as f:
                pdf_id = fs.put(
                    f,
                    filename=pdf_filename,
                    metadata={"company": company_upper, "year": year, "type": "pdf", "source": str(resolved_pdf)},
                )
            logger.info("  ✓ Đã nạp PDF vào GridFS: %s (ID: %s)", pdf_filename, pdf_id)
            synced_items.append("pdf")

        # -------------------------------------------------------------
        # 2. ĐẨY BÁO CÁO MARKDOWN HOÀN THIỆN VÀO GRIDFS
        # -------------------------------------------------------------
        md_final = out_path / f"{clean_stem}_financial_report_final.md"
        if not md_final.exists():
            md_final = out_path / f"{clean_stem}_financial_report.md"

        if md_final.exists():
            md_filename = f"{company_lower}_{year}_final.md"
            for old in fs.find({"filename": md_filename}):
                fs.delete(old._id)
            with open(md_final, "rb") as f:
                md_id = fs.put(
                    f,
                    filename=md_filename,
                    metadata={"company": company_upper, "year": year, "type": "markdown"},
                )
            logger.info("  ✓ Đã nạp Markdown vào GridFS: %s (ID: %s)", md_filename, md_id)
            synced_items.append("markdown")

        # -------------------------------------------------------------
        # 3. ĐẨY FILE SQLITE CSDL FACTS (Dùng cho SQL Fact Engine)
        # -------------------------------------------------------------
        db_file = out_path / f"benchmark_{clean_stem}.db"
        if db_file.exists():
            sqlite_filename = f"benchmark_{company_lower}_{year}.db"
            for old in fs.find({"filename": sqlite_filename}):
                fs.delete(old._id)
            with open(db_file, "rb") as f:
                db_id = fs.put(
                    f,
                    filename=sqlite_filename,
                    metadata={"company": company_upper, "year": year, "type": "sqlite"},
                )
            logger.info("  ✓ Đã nạp SQLite Facts DB vào GridFS: %s (ID: %s)", sqlite_filename, db_id)
            synced_items.append("sqlite")

        # -------------------------------------------------------------
        # 4. ĐẨY CÁC FILE JSON BLOCKS TRONG CACHE (Dùng cho Qdrant Chunking & BBox)
        # -------------------------------------------------------------
        notes_cache_dir = out_path / "cache" / "notes"
        if notes_cache_dir.exists():
            json_files = list(notes_cache_dir.glob("page_*.json"))
            blocks_collection.delete_many({"company": company_upper, "year": year})

            inserted_docs = []
            for jf in json_files:
                try:
                    with open(jf, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    blocks = data if isinstance(data, list) else data.get("blocks", [])
                    for b in blocks:
                        b["company"] = company_upper
                        b["year"] = year
                        b["source_file"] = jf.name
                        inserted_docs.append(b)
                except Exception as ex:
                    logger.warning("Bỏ qua file json lỗi %s: %s", jf.name, ex)

            if inserted_docs:
                blocks_collection.insert_many(inserted_docs)
                logger.info("  ✓ Đã nạp %d JSON Blocks vào Collection 'document_blocks'", len(inserted_docs))
                synced_items.append(f"json_blocks ({len(inserted_docs)})")

        # -------------------------------------------------------------
        # 5. ĐẨY BENCHMARK METRICS (Anti-GIGO Report) VÀO COLLECTION
        # -------------------------------------------------------------
        metrics_file = out_path / f"{clean_stem}_ocr_benchmark_metrics.json"
        if metrics_file.exists():
            with open(metrics_file, "r", encoding="utf-8") as f:
                metrics_data = json.load(f)
            benchmarks_collection.update_one(
                {"company": company_upper, "year": year},
                {"$set": {"company": company_upper, "year": year, "metrics": metrics_data}},
                upsert=True,
            )
            logger.info("  ✓ Đã cập nhật OCR Benchmark Metrics vào Collection 'ocr_benchmarks'")
            synced_items.append("metrics")

        # -------------------------------------------------------------
        # 6. TRIGGER TỰ ĐỘNG INGEST SANG COPILOT QDRANT
        # -------------------------------------------------------------
        if trigger_ingest and HTTPX_AVAILABLE:
            try:
                ingest_endpoint = f"{self.copilot_api_url.rstrip('/')}/api/v1/ingest"
                with httpx.Client(timeout=5.0) as client_http:
                    res = client_http.post(
                        ingest_endpoint,
                        json={"company": company_upper, "year": year},
                    )
                    if res.status_code in (200, 201, 202):
                        logger.info("  🎉 Đã kích hoạt Ingestion tự động tại Copilot: %s", res.text)
                        synced_items.append("copilot_triggered")
                    else:
                        logger.info(
                            "  ℹ️ Copilot Ingestion endpoint trả về mã: %d (Có thể chạy thủ công sau).",
                            res.status_code,
                        )
            except Exception as ex:
                logger.info("  ℹ️ Copilot API chưa chạy hoặc không phản hồi (%s). Dữ liệu đã sẵn sàng trong MongoDB.", ex)

        logger.info("✨ ĐỒNG BỘ THÀNH CÔNG VÀO COPILOT CHO [%s - %s]: %s", company_upper, year, synced_items)
        return {"status": "SUCCESS", "synced_items": synced_items}
