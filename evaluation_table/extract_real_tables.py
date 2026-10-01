"""
extract_real_tables.py — Trích xuất các bảng dữ liệu thực tế từ cache Notes OCR (MinerU + VietOCR).

Nguồn dữ liệu:
  - data/cache/notes/VNM_2024/*.json (49 bảng Thuyết minh thực tế)
  - Hoàn toàn KHÔNG lấy bảng từ BCTC chính (ocr/) và KHÔNG dùng dữ liệu giả lập.
  - KHÔNG tự động ghi đè Ground Truth (để thư mục ground_truth/ rỗng cho người dùng tự gán nhãn).

Phân loại chính xác theo 5 nhóm kiểm thử trong plan.md:
  1. Bảng đơn giản (1 tầng header) — Baseline đo TEDS-Struct
  2. Bảng có header 2 tầng ("Năm nay"/"Năm trước" gộp cột con / spans)
  3. Bảng có dòng "Cộng/Tổng cộng" kẻ khung đậm
  4. Bảng bị ngắt trang (trải dài 2+ trang PDF)
  5. Bảng có ô trống / gạch ngang "-" thay vì số
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

# Đảm bảo import được converter từ evaluation_table
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from evaluation_table.converter import auto_to_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ExtractRealNotesTables")

# Bảng ánh xạ các cặp bảng ngắt trang thực tế trong Thuyết minh VNM 2024
CROSS_PAGE_MAPPING = {
    # 1. Thuyết minh Cấu trúc Tập đoàn (trang 14 -> 15)
    "p14_mineru_tbl_1": {"title": "Thuyết minh Cấu trúc Tập đoàn (Công ty con P1)", "next": "p15_mineru_tbl_1", "part": 1},
    "p15_mineru_tbl_1": {"title": "Thuyết minh Cấu trúc Tập đoàn (Công ty con P2)", "prev": "p14_mineru_tbl_1", "part": 2},
    # 2. Thuyết minh Chi phí bán hàng (trang 47 -> 48)
    "p47_mineru_tbl_2": {"title": "Thuyết minh Chi phí bán hàng (Phần 1 - Trang 47)", "next": "p48_mineru_tbl_1", "part": 1},
    "p48_mineru_tbl_1": {"title": "Thuyết minh Chi phí bán hàng (Phần 2 - Trang 48)", "prev": "p47_mineru_tbl_2", "part": 2},
    # 3. Thuyết minh Chi phí quản lý doanh nghiệp (trang 48 -> 49)
    "p48_mineru_tbl_2": {"title": "Thuyết minh Chi phí quản lý doanh nghiệp (Phần 1 - Trang 48)", "next": "p49_mineru_tbl_1", "part": 1},
    "p49_mineru_tbl_1": {"title": "Thuyết minh Chi phí quản lý doanh nghiệp (Phần 2 - Trang 49)", "prev": "p48_mineru_tbl_2", "part": 2},
    # 4. Thuyết minh Giao dịch các bên liên quan (trang 51 -> 52)
    "p51_mineru_tbl_1": {"title": "Giao dịch các bên liên quan (Doanh thu & Mua hàng)", "next": "p52_mineru_tbl_1", "part": 1},
    "p52_mineru_tbl_1": {"title": "Giao dịch các bên liên quan (Số dư công nợ)", "prev": "p51_mineru_tbl_1", "part": 2},
}

GROUP_NAMES = {
    "group_1_simple_header": "Bảng đơn giản (1 tầng header)",
    "group_2_two_tier_header": "Bảng có header 2 tầng (gộp cột con / spans)",
    "group_3_has_subtotals": "Bảng có dòng 'Cộng / Tổng cộng'",
    "group_4_cross_page": "Bảng bị ngắt trang (trải dài 2+ trang PDF)",
    "group_5_dashes_and_empty": "Bảng có ô trống / gạch ngang '-'",
}


def load_notes_cached_tables(workspace_root: Path) -> list[dict[str, Any]]:
    """Tải 49 bảng thuyết minh thực tế từ cache notes (data/cache/notes/VNM_2024)."""
    notes_dir = workspace_root / "data" / "cache" / "notes" / "VNM_2024"

    if not notes_dir.exists():
        logger.error("Thư mục cache notes không tồn tại: %s", notes_dir)
        return []

    files = sorted(
        notes_dir.glob("page_*.json"),
        key=lambda p: int(p.stem.replace("page_", ""))
    )

    tables: list[dict[str, Any]] = []

    for f in files:
        try:
            blocks = json.loads(f.read_text(encoding="utf-8"))
            for i, b in enumerate(blocks):
                if b.get("block_type") == "table":
                    # Tự động trích xuất tiêu đề mục thuyết minh từ text block liền trước
                    note_title = ""
                    for j in range(i - 1, -1, -1):
                        prev = blocks[j]
                        if prev.get("block_type") == "text" and prev.get("content", "").strip():
                            lines = [l.strip() for l in prev["content"].splitlines() if l.strip()]
                            if lines:
                                # Lấy dòng tiêu đề gần nhất và làm sạch dấu markdown
                                note_title = re.sub(r"^[#*>\-\s]+", "", lines[-1]).strip()
                                break

                    b["note_title"] = note_title
                    b["source_type"] = "notes"
                    b["source_file"] = str(f.relative_to(workspace_root))
                    tables.append(b)
        except Exception as e:
            logger.error("Lỗi đọc file %s: %s", f, e)

    logger.info("Đã nạp tổng cộng %d bảng Thuyết minh thực tế từ notes cache.", len(tables))
    return tables


def classify_table(t: dict[str, Any]) -> tuple[str, list[str]]:
    """Phân loại bảng vào 1 trong 5 nhóm chính theo plan.md."""
    bid = t["block_id"]
    content = t.get("content", "")
    is_html = "<table" in content.lower()

    # 1. Phát hiện ô gộp / header 2 tầng
    has_spans = "colspan" in content.lower() or "rowspan" in content.lower()
    if not has_spans and is_html:
        has_spans = len(re.findall(r"<tr\b", content, re.I)) > 1 and bool(re.search(r"31/12|1/1|nguyên tệ|vnd", content, re.I))

    # 2. Phát hiện dòng Cộng / Tổng cộng
    has_subtotal = bool(re.search(r"(cộng|tổng|total)", content, re.I))

    # 3. Phát hiện ô trống / gạch ngang
    has_dash = bool(
        re.search(r"(\s-\s|\s-\||\|-\||<td>-</td>|<td>—</td>|\(- \)|\|\s*-\s*\|)", content)
        or any(l.strip().endswith("||") or "|||" in l for l in content.splitlines())
    )

    # 4. Phát hiện ngắt trang
    is_cross_page = bid in CROSS_PAGE_MAPPING

    tags = []
    if is_cross_page:
        tags.append("cross_page")
    if has_spans:
        tags.append("two_tier_header")
    if has_subtotal:
        tags.append("has_subtotals")
    if has_dash:
        tags.append("dashes_empty")
    if not has_spans and not is_cross_page:
        tags.append("simple_header")

    # Xác định nhóm chính theo độ ưu tiên đặc thù
    if is_cross_page:
        primary = "group_4_cross_page"
    elif has_spans:
        primary = "group_2_two_tier_header"
    elif has_subtotal:
        primary = "group_3_has_subtotals"
    elif has_dash:
        primary = "group_5_dashes_and_empty"
    else:
        primary = "group_1_simple_header"

    return primary, tags


def export_predictions_dataset(tables: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    """
    Xuất 100% bảng thực tế vào predictions/.
    Thư mục ground_truth/ được giữ nguyên rỗng theo yêu cầu để người dùng tự gán nhãn.
    """
    pred_dir = output_dir / "predictions"
    pred_dir.mkdir(parents=True, exist_ok=True)

    # Đảm bảo thư mục ground_truth/ tồn tại và rỗng
    gt_dir = output_dir / "ground_truth"
    gt_dir.mkdir(parents=True, exist_ok=True)
    for old_gt in gt_dir.glob("*"):
        try:
            old_gt.unlink()
        except Exception:
            pass

    # Xóa file cũ trong predictions trước khi xuất mới
    for old_pred in pred_dir.glob("*"):
        try:
            old_pred.unlink()
        except Exception:
            pass

    manifest_items = []

    for t in tables:
        bid = t["block_id"]
        page = t.get("page", 0)
        content = t.get("content", "").strip()
        is_html = "<table" in content.lower()
        ext = "html" if is_html else "md"

        group, tags = classify_table(t)

        # Tính toán nhanh kích thước dự đoán bằng converter
        schema = auto_to_schema(content)

        # Mô tả nghiệp vụ
        desc = t.get("note_title", "")
        if bid in CROSS_PAGE_MAPPING:
            desc = CROSS_PAGE_MAPPING[bid]["title"]
        elif not desc:
            desc = f"Bảng thuyết minh trang {page}"

        # 1. Lưu file bảng Prediction nguyên gốc (.html hoặc .md)
        pred_file = pred_dir / f"{bid}.{ext}"
        pred_file.write_text(content, encoding="utf-8")

        # 2. Lưu file Metadata chi tiết của Prediction (.json)
        meta_file = pred_dir / f"{bid}.json"
        pred_meta = {
            "table_id": bid,
            "page": page,
            "note_title": desc,
            "format": "html" if is_html else "markdown",
            "test_group": group,
            "group_name": GROUP_NAMES[group],
            "n_rows_pred": schema["n_rows"],
            "n_cols_pred": schema["n_cols"],
            "n_spans_pred": len(schema["spans"]),
            "spans_pred": schema["spans"],
            "tags": tags,
            "bbox": t.get("bbox"),
            "source_file": t.get("source_file", ""),
            "content": content,
        }
        meta_file.write_text(json.dumps(pred_meta, ensure_ascii=False, indent=2), encoding="utf-8")

        manifest_items.append({
            "table_id": bid,
            "page": page,
            "group_id": group,
            "group_name": GROUP_NAMES[group],
            "format": ext.upper(),
            "n_rows": schema["n_rows"],
            "n_cols": schema["n_cols"],
            "n_spans": len(schema["spans"]),
            "tags": tags,
            "description": desc,
            "prediction_file": f"{bid}.{ext}",
        })

    # 3. Ghi file manifest.json
    manifest_file = output_dir / "manifest.json"
    manifest_file.write_text(json.dumps(manifest_items, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4. Ghi file catalog Markdown trực quan
    catalog_md = generate_catalog_markdown(manifest_items)
    catalog_file = output_dir / "real_tables_catalog.md"
    catalog_file.write_text(catalog_md, encoding="utf-8")

    logger.info("Đã xuất hoàn tất %d bảng Thuyết minh thực tế vào predictions/.", len(manifest_items))
    return {
        "total_exported": len(manifest_items),
        "manifest_path": str(manifest_file),
        "catalog_path": str(catalog_file),
    }


def generate_catalog_markdown(manifest: list[dict[str, Any]]) -> str:
    """Tạo bảng danh mục Markdown chi tiết cho 49 bảng Thuyết minh thực tế."""
    lines = [
        "# DANH MỤC 49 BẢNG THUYẾT MINH THỰC TẾ (NOTES ONLY) — BCTC VNM 2024",
        "",
        "> **Nguồn gốc dữ liệu:** 100% trích xuất từ cache Notes (`data/cache/notes/VNM_2024/page_13.json` -> `page_54.json`).",
        "> **Tiêu chí kiểm thử:** Phân loại theo đúng 5 nhóm rủi ro cấu trúc bảng trong `evaluation_table/plan.md:L30`.",
        "> **Trạng thái Ground Truth:** Thư mục `ground_truth/` đã được dọn sạch để người dùng tự gán nhãn chuẩn vàng.",
        "",
        f"- **Tổng số bảng Thuyết minh:** `{len(manifest)}` bảng.",
        "",
        "---",
        "",
        "## 1. Thống kê theo 5 nhóm kiểm thử (Test Groups)",
        "",
        "| Nhóm bảng | Số lượng | Đặc điểm kiểm thử & Nguy cơ lỗi |",
        "|---|---|---|",
        f"| **1. {GROUP_NAMES['group_1_simple_header']}** | `{len([m for m in manifest if m['group_id'] == 'group_1_simple_header'])}` | Baseline đơn giản, kỳ vọng điểm số TEDS-Struct tuyệt đối |",
        f"| **2. {GROUP_NAMES['group_2_two_tier_header']}** | `{len([m for m in manifest if m['group_id'] == 'group_2_two_tier_header'])}` | Header 2 tầng (Năm nay/Năm trước gộp cột con), hay bị sai spans |",
        f"| **3. {GROUP_NAMES['group_3_has_subtotals']}** | `{len([m for m in manifest if m['group_id'] == 'group_3_has_subtotals'])}` | Dòng Cộng/Tổng cộng kẻ khung đậm, dễ bị cắt nhầm thành 2 bảng |",
        f"| **4. {GROUP_NAMES['group_4_cross_page']}** | `{len([m for m in manifest if m['group_id'] == 'group_4_cross_page'])}` | Bảng ngắt trang qua 2-3 trang PDF liên tiếp |",
        f"| **5. {GROUP_NAMES['group_5_dashes_and_empty']}** | `{len([m for m in manifest if m['group_id'] == 'group_5_dashes_and_empty'])}` | Ô trống hoặc gạch ngang '-', dễ bị hiểu nhầm cấu trúc |",
        "",
        "---",
        "",
        "## 2. Danh mục chi tiết 49 bảng Thuyết minh",
        "",
        "| STT | Table ID | Trang | Nhóm kiểm thử | Định dạng | Hàng x Cột | Ô gộp (Spans) | Thuyết minh / Nội dung |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for idx, m in enumerate(manifest):
        grid = f"{m['n_rows']} x {m['n_cols']}"
        lines.append(
            f"| {idx+1:02d} | `{m['table_id']}` | Trang {m['page']} | {m['group_name']} | `{m['format']}` | {grid} | {m['n_spans']} | {m['description']} |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Extract Real Tables from Notes Cache (Predictions only)")
    parser.add_argument("--output-dir", type=Path, default=current_dir, help="Thư mục xuất kết quả")
    args = parser.parse_args()

    tables = load_notes_cached_tables(project_root)
    res = export_predictions_dataset(tables, args.output_dir)

    print("\n" + "=" * 65)
    print(" ĐÃ XUẤT THÀNH CÔNG PREDICTIONS TỪ NOTES CACHE:")
    print(f" - Tổng số bảng: {res['total_exported']}")
    print(f" - Thư mục predictions: {args.output_dir / 'predictions'}")
    print(f" - Thư mục ground_truth: {args.output_dir / 'ground_truth'} (ĐÃ DỌN SẠCH)")
    print(f" - Manifest JSON: {res['manifest_path']}")
    print(f" - Danh mục Markdown: {res['catalog_path']}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
