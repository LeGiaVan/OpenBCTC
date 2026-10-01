"""
evaluator.py — Bộ đánh giá toàn diện Table Structure cho pipeline FinAudit AI.

Cách sử dụng CLI:
    python evaluation_table/evaluator.py
    python evaluation_table/evaluator.py --gt-dir evaluation_table/ground_truth --pred-dir evaluation_table/predictions
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# Đảm bảo import được dù chạy trực tiếp 'python evaluation_table/evaluator.py' hay 'python -m evaluation_table.evaluator'
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from evaluation_table.converter import auto_to_schema, schema_to_html
from evaluation_table.metrics import (
    classify_table_error,
    count_accuracy,
    error_distribution,
    span_iou,
    compute_teds_struct,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TableEvaluator")


def load_table_file(file_path: Path) -> dict[str, Any]:
    """Đọc file ground truth hoặc prediction (hỗ trợ .json, .html, .md)."""
    text = file_path.read_text(encoding="utf-8").strip()
    if file_path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
            return auto_to_schema(data)
        except json.JSONDecodeError as e:
            logger.error("Lỗi parse JSON file %s: %s", file_path, e)
            raise
    else:
        return auto_to_schema(text)


def evaluate_table_pair(
    table_id: str,
    pred_data: dict[str, Any] | str,
    gt_data: dict[str, Any] | str,
) -> dict[str, Any]:
    """Đánh giá 1 cặp bảng (Prediction vs Ground Truth)."""
    pred_schema = auto_to_schema(pred_data)
    gt_schema = auto_to_schema(gt_data)

    # 1. Row/Col Count Accuracy
    count_res = count_accuracy(pred_schema, gt_schema)

    # 2. Span IoU (Merged cells)
    span_res = span_iou(pred_schema.get("spans", []), gt_schema.get("spans", []))

    # 3. TEDS-Struct
    pred_html = schema_to_html(pred_schema)
    gt_html = schema_to_html(gt_schema)
    teds_score = compute_teds_struct(pred_html, gt_html)

    # 4. Error Classification
    errors = classify_table_error(pred_schema, gt_schema, span_res)

    return {
        "table_id": table_id,
        "n_rows_gt": gt_schema["n_rows"],
        "n_rows_pred": pred_schema["n_rows"],
        "n_cols_gt": gt_schema["n_cols"],
        "n_cols_pred": pred_schema["n_cols"],
        "row_exact_match": count_res["row_exact_match"],
        "col_exact_match": count_res["col_exact_match"],
        "exact_grid_match": count_res["exact_grid_match"],
        "span_precision": span_res["precision"],
        "span_recall": span_res["recall"],
        "span_f1": span_res["f1"],
        "teds_struct": teds_score,
        "errors": errors,
    }


def run_evaluation(
    gt_dir: Path,
    pred_dir: Path,
    report_dir: Path | None = None,
) -> dict[str, Any]:
    """Chạy đánh giá toàn bộ các bảng trong thư mục test."""
    if not gt_dir.exists():
        raise FileNotFoundError(f"Thư mục ground_truth không tồn tại: {gt_dir}")
    if not pred_dir.exists():
        raise FileNotFoundError(f"Thư mục predictions không tồn tại: {pred_dir}")

    gt_files = {f.stem: f for f in gt_dir.iterdir() if f.is_file() and f.suffix in (".json", ".html", ".md")}
    pred_files = {f.stem: f for f in pred_dir.iterdir() if f.is_file() and f.suffix in (".json", ".html", ".md")}

    common_keys = sorted(set(gt_files.keys()).intersection(pred_files.keys()))
    if not common_keys:
        logger.warning("Không tìm thấy file nào khớp tên giữa GT (%s) và Pred (%s)!", gt_dir, pred_dir)
        return {"error": "No matching table pairs found"}

    logger.info("Bắt đầu đánh giá %d bảng khớp tên...", len(common_keys))

    results: list[dict[str, Any]] = []
    for key in common_keys:
        gt_schema = load_table_file(gt_files[key])
        pred_schema = load_table_file(pred_files[key])
        res = evaluate_table_pair(key, pred_schema, gt_schema)
        results.append(res)

    n = len(results)
    row_acc = sum(1 for r in results if r["row_exact_match"]) / n
    col_acc = sum(1 for r in results if r["col_exact_match"]) / n
    grid_acc = sum(1 for r in results if r["exact_grid_match"]) / n
    avg_span_f1 = sum(r["span_f1"] for r in results) / n
    avg_teds = sum(r["teds_struct"] for r in results) / n
    err_dist = error_distribution(results)

    summary = {
        "total_tables": n,
        "row_accuracy": round(row_acc, 4),
        "col_accuracy": round(col_acc, 4),
        "exact_grid_accuracy": round(grid_acc, 4),
        "avg_span_f1": round(avg_span_f1, 4),
        "avg_teds_struct": round(avg_teds, 4),
        "error_distribution": err_dist,
        "details": results,
    }

    # Xuất báo cáo nếu chỉ định report_dir
    if report_dir:
        report_dir.mkdir(parents=True, exist_ok=True)
        json_path = report_dir / "report_latest.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        md_path = report_dir / "report_latest.md"
        md_content = generate_markdown_summary(summary)
        md_path.write_text(md_content, encoding="utf-8")
        logger.info("Đã ghi báo cáo: JSON -> %s | Markdown -> %s", json_path, md_path)

    return summary


def generate_markdown_summary(summary: dict[str, Any]) -> str:
    """Tạo báo cáo tóm tắt Markdown chuyên nghiệp từ kết quả đánh giá."""
    n = summary["total_tables"]
    lines = [
        "# BÁO CÁO ĐÁNH GIÁ CẤU TRÚC BẢNG (TABLE STRUCTURE EVALUATION)",
        "",
        f"- **Tổng số bảng kiểm thử:** `{n}`",
        f"- **Độ chính xác số Hàng (Row Acc):** `{summary['row_accuracy'] * 100:.1f}%`",
        f"- **Độ chính xác số Cột (Col Acc):** `{summary['col_accuracy'] * 100:.1f}%`",
        f"- **Độ khớp Ma trận Lưới (Grid Exact Match):** `{summary['exact_grid_accuracy'] * 100:.1f}%`",
        f"- **Span F1 (Ô gộp / Header 2 tầng):** `{summary['avg_span_f1'] * 100:.1f}%`",
        f"- **TEDS-Struct (Tree Edit Distance):** `{summary['avg_teds_struct']:.4f}`",
        "",
        "---",
        "",
        "## 1. Phân bố các loại lỗi (Error Distribution)",
        "",
        "| Phân loại lỗi | Số lượng bảng | Ý nghĩa & Hướng xử lý |",
        "|---|---|---|",
    ]

    meanings = {
        "COLUMN_COUNT_MISMATCH": "Lệch số cột — Thường do Header 2 tầng bị gộp phẳng làm mất cột con.",
        "MISSING_ROWS": "Thiếu dòng — Có thể do bảng bị ngắt trang qua 2 trang PDF hoặc OCR gộp dòng.",
        "EXTRA_ROWS": "Thừa dòng — Dòng kẻ ngang, khoảng trắng hoặc ghi chú chân trang bị coi là dữ liệu.",
        "MISSED_MERGED_HEADER": "Bỏ sót ô gộp — Model coi header đa tầng là các ô riêng rẽ độc lập.",
        "HALLUCINATED_MERGE": "Gộp ô ảo — Model tự động gộp các ô không có thật.",
        "HEADER_DEPTH_MISMATCH": "Lệch số tầng header — Số dòng tiêu đề bảng nhận diện sai.",
        "OK": "Cấu trúc hoàn hảo — Khớp 100% kích thước và vị trí ô gộp.",
    }

    for err, cnt in summary.get("error_distribution", {}).items():
        desc = meanings.get(err, "Lỗi bất thường cần kiểm tra log chi tiết.")
        lines.append(f"| `{err}` | **{cnt}** ({cnt / n * 100:.1f}%) | {desc} |")

    lines.extend([
        "",
        "---",
        "",
        "## 2. Chi tiết từng bảng kiểm thử",
        "",
        "| Table ID | Hàng (Pred/GT) | Cột (Pred/GT) | Span F1 | TEDS-Struct | Lỗi ghi nhận |",
        "|---|---|---|---|---|---|",
    ])

    for d in summary.get("details", []):
        r_str = f"{d['n_rows_pred']}/{d['n_rows_gt']}"
        c_str = f"{d['n_cols_pred']}/{d['n_cols_gt']}"
        err_str = ", ".join(f"`{e}`" for e in d["errors"])
        teds_val = f"{d['teds_struct']:.3f}"
        span_val = f"{d['span_f1']:.2f}"
        lines.append(f"| `{d['table_id']}` | {r_str} | {c_str} | {span_val} | **{teds_val}** | {err_str} |")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="FinAudit AI Table Structure Evaluator")
    base_dir = Path(__file__).resolve().parent
    parser.add_argument("--gt-dir", type=Path, default=base_dir / "ground_truth", help="Thư mục chứa Ground Truth")
    parser.add_argument("--pred-dir", type=Path, default=base_dir / "predictions", help="Thư mục chứa Predictions")
    parser.add_argument("--report-dir", type=Path, default=base_dir / "reports", help="Thư mục lưu Reports")

    args = parser.parse_args()

    summary = run_evaluation(args.gt_dir, args.pred_dir, args.report_dir)
    print("\n" + "=" * 65)
    print(" KẾT QUẢ ĐÁNH GIÁ TABLE STRUCTURE:")
    print(f" - Tổng số bảng: {summary.get('total_tables', 0)}")
    print(f" - Row Accuracy: {summary.get('row_accuracy', 0)*100:.1f}%")
    print(f" - Col Accuracy: {summary.get('col_accuracy', 0)*100:.1f}%")
    print(f" - Span F1 (Ô gộp): {summary.get('avg_span_f1', 0)*100:.1f}%")
    print(f" - TEDS-Struct: {summary.get('avg_teds_struct', 0):.4f}")
    print(f" - Phân bố lỗi: {summary.get('error_distribution', {})}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
