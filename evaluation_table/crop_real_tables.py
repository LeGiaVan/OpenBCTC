"""
crop_real_tables.py — Tự động cắt ảnh (crop) 49 bảng thuyết minh từ file gốc vnm.pdf.

Lưu ảnh sắc nét (DPI=200) vào thư mục: evaluation_table/images/{table_id}.png
Phục vụ gán nhãn Ground Truth độc lập 100% trên Label Studio.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import pymupdf as fitz

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CropRealTables")

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent


def crop_all_tables(
    pdf_path: Path,
    manifest_path: Path,
    output_dir: Path,
    dpi: int = 200,
) -> int:
    """Cắt ảnh từng bảng dựa vào tọa độ bbox trong manifest/predictions."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file PDF gốc: {pdf_path}")
    if not manifest_path.exists():
        raise FileNotFoundError(f"Không tìm thấy manifest.json: {manifest_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    logger.info("Đã mở file PDF: %s (%d trang)", pdf_path.name, total_pages)

    success_count = 0

    for item in manifest:
        bid = item["table_id"]
        page_num = item["page"]  # 1-indexed
        
        # Đọc file prediction json để lấy bbox chính xác
        pred_json_file = current_dir / "predictions" / f"{bid}.json"
        bbox = None
        if pred_json_file.exists():
            try:
                pred_meta = json.loads(pred_json_file.read_text(encoding="utf-8"))
                bbox = pred_meta.get("bbox")
            except Exception:
                pass

        if page_num < 1 or page_num > total_pages:
            logger.warning("Trang %d vượt quá giới hạn PDF (%d)", page_num, total_pages)
            continue

        page = doc[page_num - 1]
        rect = page.rect

        if bbox and len(bbox) == 4 and any(v > 0 for v in bbox):
            x0_r, y0_r, x1_r, y1_r = bbox
            # Bounding box chuẩn hóa (0.0 -> 1.0)
            x0 = x0_r * rect.width
            y0 = y0_r * rect.height
            x1 = x1_r * rect.width
            y1 = y1_r * rect.height

            # Mở rộng lề 12pt để không bị cắt lẹm viền bảng hoặc tiêu đề
            crop_rect = fitz.Rect(
                max(0, x0 - 12),
                max(0, y0 - 12),
                min(rect.width, x1 + 12),
                min(rect.height, y1 + 12),
            )
        else:
            # Fallback: chụp toàn bộ trang nếu không có bbox
            crop_rect = rect

        pix = page.get_pixmap(clip=crop_rect, dpi=dpi)
        out_img_path = output_dir / f"{bid}.png"
        pix.save(str(out_img_path))
        success_count += 1
        logger.debug("Đã lưu crop bảng: %s (%dx%d px)", out_img_path.name, pix.width, pix.height)

    logger.info("Đã cắt thành công %d / %d ảnh bảng vào %s", success_count, len(manifest), output_dir)
    return success_count


if __name__ == "__main__":
    pdf_file = project_root / "vnm.pdf"
    manifest_f = current_dir / "manifest.json"
    img_dir = current_dir / "images"

    crop_all_tables(pdf_file, manifest_f, img_dir, dpi=200)
