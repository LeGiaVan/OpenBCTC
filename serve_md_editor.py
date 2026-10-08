"""
serve_md_editor.py — Công cụ Web Review & Chỉnh Sửa Bảng Biểu trong file Markdown (Human-in-the-Loop Table Editor).

Quy trình:
    OCR (PDF -> MD)  ==>  serve_md_editor (Người dùng rà soát & chỉnh sửa 100% bảng trực quan từ Cache)  ==>  Xuất file MD lần cuối (.md)

Tính năng nổi bật:
    1. Trích xuất 100% tất cả các bảng từ Cache OCR & Thuyết minh (hỗ trợ cả HTML Table và Markdown Pipe Table).
    2. Đối chiếu ảnh crop 200 DPI chuẩn xác tuyệt đối từng bảng từ file PDF gốc của chính doanh nghiệp đó (triệt tiêu 100% rò rỉ dữ liệu chéo).
    3. Hỗ trợ zoom, phóng to ảnh crop để kiểm tra các con số nhỏ/mờ.
    4. Sửa trực quan dạng bảng tính (Spreadsheet), thêm/xóa hàng cột, định dạng số, xuất file cuối cùng bảo toàn 100% văn bản gốc.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import mimetypes
import os
import re
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

# Đảm bảo in UTF-8 không lỗi trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MdTableEditor")

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_PORT = 8502

try:
    import pymupdf as fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


# =====================================================================
# 1. BỘ CHUYỂN ĐỔI BẢNG THÔNG MINH (HTML TABLE & PIPE TABLE SANG 2D GRID)
# =====================================================================

def html_to_grid(html_str: str) -> list[list[str]]:
    """Chuyển đổi bảng HTML (kể cả có rowspan, colspan) thành ma trận 2D chữ nhật."""
    if not HAS_BS4:
        # Fallback regex đơn giản nếu không có bs4
        rows_data = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html_str, re.IGNORECASE | re.DOTALL):
            cells = [re.sub(r"<[^>]+>", " ", c).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.IGNORECASE | re.DOTALL)]
            if cells:
                rows_data.append(cells)
        return rows_data

    soup = BeautifulSoup(html_str, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")
    grid: list[list[str]] = []
    occupied: dict[tuple[int, int], str] = {}

    for r_idx, tr in enumerate(rows):
        col_idx = 0
        row_cells: list[str] = []
        for cell in tr.find_all(["td", "th"]):
            while (r_idx, col_idx) in occupied:
                row_cells.append(occupied[(r_idx, col_idx)])
                col_idx += 1
            
            text = cell.get_text(separator=" ", strip=True)
            try:
                rowspan = int(cell.get("rowspan", 1))
            except (ValueError, TypeError):
                rowspan = 1
            try:
                colspan = int(cell.get("colspan", 1))
            except (ValueError, TypeError):
                colspan = 1

            for r in range(r_idx, r_idx + rowspan):
                for c in range(col_idx, col_idx + colspan):
                    occupied[(r, c)] = text if (r == r_idx and c == col_idx) else ""

            row_cells.append(text)
            col_idx += 1
            for _ in range(colspan - 1):
                row_cells.append("")
                col_idx += 1

        while (r_idx, col_idx) in occupied:
            row_cells.append(occupied[(r_idx, col_idx)])
            col_idx += 1

        grid.append(row_cells)

    max_cols = max((len(r) for r in grid), default=0)
    for r in grid:
        while len(r) < max_cols:
            r.append("")

    return grid


def pipe_to_grid(pipe_str: str) -> list[list[str]]:
    """Phân tách bảng Markdown dạng Pipe (| a | b |) thành ma trận 2D."""
    lines = [l.strip() for l in pipe_str.strip().splitlines() if l.strip()]
    rows: list[list[str]] = []
    for l in lines:
        inner = l.strip()
        if inner.startswith("|"):
            inner = inner[1:]
        if inner.endswith("|"):
            inner = inner[:-1]
        cells = [c.strip() for c in inner.split("|")]
        # Bỏ qua dòng separator | --- | --- |
        if all(re.match(r"^:?-+:?$", c) for c in cells if c) and len(cells) > 0:
            continue
        rows.append(cells)

    max_cols = max((len(r) for r in rows), default=0)
    for r in rows:
        while len(r) < max_cols:
            r.append("")
    return rows


def auto_alignments(rows: list[list[str]], header_rows_count: int = 1) -> list[str]:
    """Tự động suy luận căn lề phải cho cột số, căn trái cho văn bản."""
    if not rows:
        return []
    n_cols = max((len(r) for r in rows), default=0)
    alignments = []
    for c in range(n_cols):
        num_numeric = 0
        count = 0
        for r in range(header_rows_count, len(rows)):
            if c < len(rows[r]):
                val = rows[r][c].replace(".", "").replace(",", "").replace("(", "").replace(")", "").replace("-", "").strip()
                if val:
                    count += 1
                    if val.isdigit():
                        num_numeric += 1
        if count > 0 and num_numeric / count >= 0.6:
            alignments.append("right")
        else:
            alignments.append("left")
    return alignments


def format_grid_to_markdown(
    rows: list[list[str]],
    header_rows_count: int = 1,
    alignments: list[str] | None = None
) -> list[str]:
    """Format ma trận 2D thành GFM Markdown Table cân đối."""
    if not rows:
        return []

    n_cols = max((len(r) for r in rows), default=0)
    if n_cols == 0:
        return []

    norm_rows: list[list[str]] = []
    for r in rows:
        nr = [str(c).replace("\n", " ").strip() for c in r]
        while len(nr) < n_cols:
            nr.append("")
        norm_rows.append(nr)

    if not alignments or len(alignments) < n_cols:
        alignments = auto_alignments(norm_rows, header_rows_count)

    col_widths = [4] * n_cols
    for r in norm_rows:
        for c, cell in enumerate(r):
            col_widths[c] = max(col_widths[c], len(cell))

    output_lines: list[str] = []
    actual_hdr_count = max(1, min(header_rows_count, len(norm_rows)))

    for h in range(actual_hdr_count):
        cells = [norm_rows[h][c].ljust(col_widths[c]) for c in range(n_cols)]
        output_lines.append("| " + " | ".join(cells) + " |")

    sep_cells = []
    for c in range(n_cols):
        align = alignments[c] if c < len(alignments) else "left"
        w = max(3, col_widths[c])
        if align == "center":
            sep = ":" + "-" * (w - 2) + ":"
        elif align == "right":
            sep = "-" * (w - 1) + ":"
        else:
            sep = "-" * w
        sep_cells.append(sep)
    output_lines.append("| " + " | ".join(sep_cells) + " |")

    for r in range(actual_hdr_count, len(norm_rows)):
        cells = []
        for c in range(n_cols):
            val = norm_rows[r][c]
            align = alignments[c] if c < len(alignments) else "left"
            if align == "right":
                cells.append(val.rjust(col_widths[c]))
            elif align == "center":
                cells.append(val.center(col_widths[c]))
            else:
                cells.append(val.ljust(col_widths[c]))
        output_lines.append("| " + " | ".join(cells) + " |")

    return output_lines


# =====================================================================
# 2. TRÍCH XUẤT 100% BẢNG BIỂU TỪ CACHE (OCR CORE & NOTES)
# =====================================================================

def detect_latest_company_year() -> tuple[str, int]:
    """Tự động xác định doanh nghiệp và năm mới nhất có trong outputs/ hoặc cache."""
    candidates = []

    # 1. Quét các thư mục trong outputs/{company}_{year}
    outputs_dir = PROJECT_ROOT / "outputs"
    if outputs_dir.exists():
        for p in outputs_dir.iterdir():
            if p.is_dir() and "_" in p.name:
                candidates.append((p.stat().st_mtime, p.name))

    # 2. Quét cache cũ nếu chưa có outputs
    notes_dir = PROJECT_ROOT / "data" / "cache" / "notes"
    ocr_dir = PROJECT_ROOT / "data" / "cache" / "ocr"
    for base in (notes_dir, ocr_dir):
        if base.exists():
            for p in base.iterdir():
                if p.is_dir() and "_" in p.name:
                    candidates.append((p.stat().st_mtime, p.name))

    if candidates:
        candidates.sort(reverse=True)
        latest_name = candidates[0][1]
        parts = latest_name.split("_")
        comp = parts[0]
        try:
            yr = int(parts[1])
        except (ValueError, IndexError):
            yr = 2025
        return comp, yr

    return "VNM", 2025


def find_pdf_for_company(company: str, year: int) -> Path | None:
    """Tìm đúng file PDF của công ty trong pdf_files, uploads hoặc thư mục gốc."""
    comp_upper = company.upper()
    search_dirs = [
        PROJECT_ROOT / "pdf_files",
        PROJECT_ROOT / "data" / "uploads",
        PROJECT_ROOT / "data" / "bctc_pdfs",
        PROJECT_ROOT,
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for f in d.glob("*.pdf"):
            if comp_upper in f.name.upper():
                return f
        all_pdfs = list(d.glob("*.pdf"))
        if len(all_pdfs) == 1 and comp_upper in ("VNM", "VIC"):
            return all_pdfs[0]

    if comp_upper == "VNM" and (PROJECT_ROOT / "vnm.pdf").exists():
        return PROJECT_ROOT / "vnm.pdf"

    return None


def load_all_tables_from_cache(company: str, year: int) -> list[dict[str, Any]]:
    """
    Trích xuất 100% các bảng biểu từ cache OCR và Thuyết minh.
    Ưu tiên tìm trong outputs/{company}_{year}/cache/, sau đó fallback data/cache/.
    """
    tag = f"{company}_{year}"
    candidate_dirs = [
        PROJECT_ROOT / "outputs" / tag / "cache" / "ocr",
        PROJECT_ROOT / "outputs" / tag / "cache" / "notes",
        PROJECT_ROOT / "data" / "cache" / "ocr" / tag,
        PROJECT_ROOT / "data" / "cache" / "notes" / tag,
    ]

    all_json_files: list[Path] = []
    seen_files = set()
    for d in candidate_dirs:
        if d.exists():
            for jf in d.glob("*.json"):
                if jf.name not in seen_files:
                    seen_files.add(jf.name)
                    all_json_files.append(jf)

    def extract_page_num(p: Path) -> int:
        m = re.search(r"p(?:age_)?(\d+)", p.stem)
        return int(m.group(1)) if m else 9999

    all_json_files.sort(key=extract_page_num)

    tables: list[dict[str, Any]] = []
    table_idx = 0

    for f in all_json_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue

        last_heading = "Báo cáo tài chính"
        pre_texts: list[str] = []

        for b in data:
            btype = b.get("block_type", "")
            cnt = b.get("content", "").strip()

            if btype == "text":
                if cnt.startswith("#") or "báo cáo" in cnt.lower() or "thuyết minh" in cnt.lower() or re.match(r"^\d+\.\s+", cnt):
                    last_heading = re.sub(r"^[#*>\-\s]+", "", cnt).strip()
                pre_texts.append(cnt)
                if len(pre_texts) > 3:
                    pre_texts.pop(0)

            elif btype == "table":
                table_idx += 1
                page = b.get("page", 1)
                bid = b.get("block_id") or f"p{page}_tbl_{table_idx}"
                bbox = b.get("bbox")

                if "<table" in cnt.lower():
                    grid = html_to_grid(cnt)
                else:
                    grid = pipe_to_grid(cnt)

                clean_heading = last_heading[:85] if last_heading else f"Bảng {table_idx}"
                pre_text_str = "\n".join(pre_texts[-2:]) if pre_texts else ""

                tables.append({
                    "table_id": table_idx,
                    "block_id": bid,
                    "page": page,
                    "bbox": bbox,
                    "heading": clean_heading,
                    "pre_text": pre_text_str,
                    "n_rows": len(grid),
                    "n_cols": len(grid[0]) if grid else 0,
                    "header_rows_count": 1,
                    "alignments": auto_alignments(grid, 1),
                    "rows": grid,
                    "raw_markdown": cnt,
                    "company": company,
                    "year": year,
                    "is_edited": False,
                })
                pre_texts.clear()

    logger.info("Đã nạp thành công %d bảng biểu từ cache của %s (%d).", len(tables), company, year)
    return tables


def reconstruct_full_document(
    original_md_path: Path,
    edited_tables: dict[int, dict[str, Any]],
    all_tables: list[dict[str, Any]]
) -> str:
    """Ráp nối tài liệu Markdown với các bảng đã qua chỉnh sửa, bảo toàn 100% văn bản ngoài bảng."""
    if not original_md_path.exists():
        # Nếu chưa có file MD gốc, ghép các bảng lại
        lines = [f"# BÁO CÁO TÀI CHÍNH ĐÃ RÀ SOÁT\n\n"]
        for t in all_tables:
            tid = t["table_id"]
            cur = edited_tables.get(tid, t)
            lines.append(f"### {cur.get('heading', f'Bảng {tid}')} *(Trang {cur.get('page', 1)})*\n")
            if cur.get("pre_text"):
                lines.append(cur["pre_text"] + "\n")
            tbl_lines = format_grid_to_markdown(cur["rows"], cur.get("header_rows_count", 1))
            lines.extend(tbl_lines)
            lines.append("\n---\n")
        return "\n".join(lines)

    content = original_md_path.read_text(encoding="utf-8")
    table_pattern = re.compile(
        r'(<table[\s\S]*?</table>)|((?:^[ \t]*\|[^\n]+\|[ \t]*$\n?)+)',
        re.MULTILINE | re.IGNORECASE
    )

    replacements: list[tuple[int, int, str]] = []

    for tid, edited in edited_tables.items():
        orig_t = next((t for t in all_tables if t["table_id"] == tid), None)
        if not orig_t:
            continue

        new_md = "\n".join(format_grid_to_markdown(
            rows=edited["rows"],
            header_rows_count=edited.get("header_rows_count", 1),
            alignments=edited.get("alignments")
        ))

        # Ưu tiên 1: Khớp chính xác chuỗi raw_markdown nếu tồn tại nguyên vẹn
        orig_raw = orig_t.get("raw_markdown", "").strip()
        if orig_raw and orig_raw in content:
            pos = content.find(orig_raw)
            replacements.append((pos, pos + len(orig_raw), new_md))
            continue

        # Ưu tiên 2: Token matching theo các ô dữ liệu đặc trưng của bảng
        orig_rows = orig_t.get("rows", [])
        tokens = set()
        for r in orig_rows:
            for cell in r:
                c = str(cell).strip()
                if len(c) >= 3 and not c.startswith("|") and not c.startswith("-"):
                    tokens.add(c[:35])

        if not tokens:
            for r in edited.get("rows", []):
                for cell in r:
                    c = str(cell).strip()
                    if len(c) >= 3 and not c.startswith("|") and not c.startswith("-"):
                        tokens.add(c[:35])

        doc_matches = list(table_pattern.finditer(content))
        best_match = None
        best_score = 0
        for m in doc_matches:
            tbl_text = m.group(0)
            score = sum(1 for tok in tokens if tok in tbl_text)
            if score > best_score:
                best_score = score
                best_match = m

        if best_match and best_score >= 1:
            replacements.append((best_match.start(), best_match.end(), new_md))
        else:
            # Ưu tiên 3: Tìm theo tiêu đề hoặc ngữ cảnh gần nhất
            heading = orig_t.get("heading", "")
            if heading and heading in content:
                h_pos = content.find(heading)
                post_content = content[h_pos:]
                m_near = table_pattern.search(post_content)
                if m_near and m_near.start() < 1500:
                    replacements.append((h_pos + m_near.start(), h_pos + m_near.end(), new_md))

    # Sắp xếp các đoạn cần thay thế theo vị trí giảm dần để không làm lệch offset
    replacements.sort(key=lambda x: x[0], reverse=True)
    for start, end, new_text in replacements:
        content = content[:start] + new_text + content[end:]

    return content



# =====================================================================
# 3. GIAO DIỆN WEB HIỆN ĐẠI (CHUYÊN BIỆT CHO CROP BẢNG TỪ CACHE)
# =====================================================================

EDITOR_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FinAudit AI — Markdown Table Editor (HITL)</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b1120;
      --panel-bg: #1e293b;
      --card-bg: #182234;
      --border: #334155;
      --border-focus: #3b82f6;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --success: #10b981;
      --success-hover: #059669;
      --warning: #f59e0b;
      --danger: #ef4444;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --cell-selected: #1e3a8a;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', sans-serif;
      background-color: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }
    header {
      background-color: var(--panel-bg);
      border-bottom: 1px solid var(--border);
      padding: 10px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 15px;
      flex-shrink: 0;
    }
    .brand-section { display: flex; align-items: center; gap: 14px; }
    .brand-logo { font-size: 1.15rem; font-weight: 700; color: #60a5fa; display: flex; align-items: center; gap: 8px; }
    
    /* Document Badge (Thay thế dropdown chọn nguồn) */
    .company-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: linear-gradient(135deg, rgba(30, 58, 138, 0.4), rgba(15, 23, 42, 0.6));
      border: 1px solid #3b82f6;
      padding: 5px 12px;
      border-radius: 9999px;
      font-size: 0.85rem;
      font-weight: 600;
      color: #93c5fd;
    }
    .badge-icon { font-size: 0.95rem; }
    .badge-divider { color: #475569; }
    .badge-tag {
      background-color: rgba(16, 185, 129, 0.2);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.4);
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .header-actions { display: flex; align-items: center; gap: 10px; }
    .btn {
      padding: 7px 14px;
      border-radius: 6px;
      font-weight: 600;
      font-size: 0.85rem;
      cursor: pointer;
      border: 1px solid transparent;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s ease;
    }
    .btn-primary { background-color: var(--primary); color: #fff; }
    .btn-primary:hover { background-color: var(--primary-hover); }
    .btn-success { background-color: var(--success); color: #fff; }
    .btn-success:hover { background-color: var(--success-hover); }
    .btn-secondary { background-color: #334155; color: var(--text); border-color: #475569; }
    .btn-secondary:hover { background-color: #475569; }
    .btn-sm { padding: 4px 8px; font-size: 0.78rem; }

    /* Workspace Split */
    .workspace {
      display: flex;
      flex: 1;
      height: calc(100vh - 110px);
      overflow: hidden;
    }
    .left-panel {
      width: 44%;
      background-color: var(--card-bg);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .right-panel {
      width: 56%;
      background-color: var(--bg);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .panel-header {
      padding: 8px 16px;
      background-color: #1e293b;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .tab-group { display: flex; gap: 6px; }
    .tab-btn {
      background: none;
      border: none;
      color: var(--text-muted);
      padding: 6px 12px;
      font-size: 0.83rem;
      font-weight: 600;
      border-radius: 4px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .tab-btn.active {
      background-color: #334155;
      color: #60a5fa;
    }

    .panel-body {
      flex: 1;
      overflow: auto;
      padding: 16px;
      position: relative;
    }
    .context-box {
      background-color: #0f172a;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
      font-size: 0.88rem;
      line-height: 1.6;
      margin-bottom: 16px;
    }
    .context-box h4 { color: #60a5fa; margin-bottom: 8px; font-size: 0.95rem; }

    /* CHUYÊN BIỆT CHO ẢNH CROP BẢNG (FIX CỐ ĐỊNH TOOLBAR, KHÔNG BỊ TRÔI) */
    #imageView {
      display: flex;
      flex-direction: column;
      overflow: hidden;
      padding: 10px;
      height: 100%;
    }
    .crop-viewer-container {
      width: 100%;
      height: 100%;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background-color: #0f172a;
      border-radius: 8px;
      border: 1px solid var(--border);
    }
    .crop-toolbar {
      flex-shrink: 0;
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      background-color: #1e293b;
      padding: 6px 12px;
      border-bottom: 1px solid var(--border);
      box-sizing: border-box;
      overflow-x: auto;
    }
    .crop-toolbar-actions {
      display: flex;
      gap: 6px;
      align-items: center;
      flex-shrink: 0;
    }
    .crop-btn {
      height: 32px;
      padding: 0 10px;
      font-size: 0.78rem;
      font-weight: 500;
      white-space: nowrap;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
      border-radius: 6px;
      box-sizing: border-box;
      line-height: 1;
      flex-shrink: 0;
      cursor: pointer;
      border: 1px solid #475569;
      background-color: #334155;
      color: var(--text);
      transition: all 0.2s ease;
    }
    .crop-btn:hover {
      background-color: #475569;
      color: #fff;
    }
    .crop-btn.btn-warning {
      background-color: #d97706;
      color: #fff;
      border-color: #b45309;
      font-weight: 600;
    }
    .crop-btn.btn-warning:hover {
      background-color: #f59e0b;
    }
    .crop-image-wrapper {
      flex: 1;
      width: 100%;
      display: flex;
      justify-content: center;
      align-items: flex-start;
      overflow: auto;
      padding: 12px;
    }
    .crop-image {
      max-width: 100%;
      height: auto;
      border-radius: 6px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.6);
      border: 1px solid #475569;
      transition: transform 0.2s ease;
      cursor: zoom-in;
    }
    .crop-image.zoomed {
      max-width: none;
      transform: scale(1.4);
      transform-origin: top center;
      cursor: zoom-out;
    }

    /* Editor Toolbar */
    .editor-toolbar {
      padding: 8px 16px;
      background-color: #1e293b;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
    }
    .toolbar-group { display: flex; align-items: center; gap: 6px; }
    .table-stats-badge {
      background-color: #0f172a;
      border: 1px solid #334155;
      padding: 4px 10px;
      border-radius: 4px;
      font-size: 0.8rem;
      font-family: 'JetBrains Mono', monospace;
      color: #38bdf8;
    }

    /* Spreadsheet Grid */
    .grid-container {
      flex: 1;
      overflow: auto;
      padding: 16px;
      background-color: #0f172a;
    }
    .sheet-table {
      border-collapse: collapse;
      width: 100%;
      font-family: 'Inter', sans-serif;
      font-size: 0.85rem;
    }
    .sheet-table th, .sheet-table td {
      border: 1px solid #334155;
      padding: 6px 8px;
      min-width: 90px;
      position: relative;
    }
    .sheet-table th {
      background-color: #1e293b;
      color: #93c5fd;
      font-weight: 600;
      text-align: center;
      user-select: none;
    }
    .corner-th { width: 40px; min-width: 40px !important; background-color: #0f172a !important; color: #64748b !important; }
    .row-header-th {
      background-color: #1e293b;
      color: #64748b;
      width: 40px;
      min-width: 40px !important;
      text-align: center;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem;
    }
    .header-tier-row td { background-color: #1a2844; font-weight: 600; color: #bfdbfe; }
    .cell-input {
      width: 100%;
      background: transparent;
      border: none;
      outline: none;
      color: var(--text);
      font-family: inherit;
      font-size: inherit;
    }
    .cell-input:focus {
      background-color: rgba(59, 130, 246, 0.25);
      border-radius: 2px;
      box-shadow: 0 0 0 1px var(--primary);
    }

    .raw-textarea {
      width: 100%;
      height: 100%;
      background-color: #0f172a;
      color: #f1f5f9;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.86rem;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px;
      resize: none;
      line-height: 1.5;
    }

    footer {
      height: 52px;
      background-color: #1e293b;
      border-top: 1px solid var(--border);
      padding: 0 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
    }
    .table-nav { display: flex; align-items: center; gap: 12px; }
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 3px 10px;
      border-radius: 9999px;
      font-size: 0.78rem;
      font-weight: 600;
    }
    .badge-edited { background-color: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #059669; }
    .badge-unmodified { background-color: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid #475569; }

    .modal-overlay {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.7);
      backdrop-filter: blur(4px);
      z-index: 1000;
      justify-content: center;
      align-items: center;
    }
    .modal-card {
      background-color: var(--panel-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      width: 90%;
      max-width: 650px;
      padding: 24px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.6);
    }
  </style>
</head>
<body>

  <!-- Top Bar -->
  <header>
    <div class="brand-section">
      <div class="brand-logo">
        <span>📑</span> FinAudit AI — Table Reviewer
      </div>
      <div class="company-badge" id="currentDocBadge">
        <span class="badge-icon">🏢</span>
        <span id="badgeCompanyText">Đang tải...</span>
        <span class="badge-divider">•</span>
        <span id="badgeTableCount">0 Bảng</span>
        <span class="badge-tag">100% Trích xuất từ Cache</span>
      </div>
    </div>
    <div class="header-actions">
      <button class="btn btn-secondary" onclick="openPreviewModal()">
        👁️ Xem toàn văn MD
      </button>
      <button class="btn btn-primary" id="saveBtn" onclick="saveCurrentTable()">
        💾 Lưu Bảng (Ctrl+S)
      </button>
    </div>
  </header>

  <!-- Split Workspace -->
  <div class="workspace">
    <!-- Cột trái: Ảnh Crop Bảng từ PDF & Ngữ cảnh -->
    <div class="left-panel">
      <div class="panel-header">
        <div class="tab-group">
          <button class="tab-btn active" id="tabImageBtn" onclick="switchLeftTab('image')">
            🖼️ Ảnh crop bảng gốc (PDF)
          </button>
          <button class="tab-btn" id="tabContextBtn" onclick="switchLeftTab('context')">
            📄 Văn cảnh BCTC
          </button>
          <button class="tab-btn" id="tabRawBtn" onclick="switchLeftTab('raw')">
            📝 Raw Table (Markdown/HTML)
          </button>
        </div>
        <div id="pageBadge" style="font-size: 0.8rem; color: #38bdf8; font-weight: 600;">
          Trang --
        </div>
      </div>

      <!-- Tab: Ảnh CROP BẢNG (MẶC ĐỊNH) -->
      <div class="panel-body" id="imageView" style="padding: 10px;">
        <div class="crop-viewer-container">
          <div class="crop-toolbar">
            <span id="cropInfoLabel" style="font-size: 0.76rem; color: #94a3b8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 190px; flex-shrink: 1;">
              Đang tải ảnh crop chính xác từ PDF...
            </span>
            <div class="crop-toolbar-actions">
              <button class="crop-btn" id="rotateLeftBtn" onclick="rotateImage(-90)" title="Xoay ảnh 90° ngược chiều kim đồng hồ (-90°)">
                ↺ -90°
              </button>
              <button class="crop-btn" id="rotateBtn" onclick="rotateImage(90)" title="Xoay ảnh 90° theo chiều kim đồng hồ (+90°)">
                ↻ +90°
              </button>
              <button class="crop-btn btn-warning" id="reocrBtn" onclick="reocrCurrentTable()" title="Chạy lại OCR trên ảnh đã xoay đúng chiều">
                ⚡ OCR lại bảng
              </button>
              <button class="crop-btn" onclick="toggleZoom()" id="zoomBtn">
                🔍 Phóng to (135%)
              </button>
              <button class="crop-btn" onclick="openImageNewTab()" title="Mở ảnh kích thước gốc trong tab mới">
                ↗ Mở riêng
              </button>
            </div>
          </div>
          <div class="crop-image-wrapper">
            <img id="pdfCropImage" class="crop-image" src="" alt="Đang tải ảnh crop bảng từ PDF..." onclick="toggleZoom()" />
          </div>
        </div>
      </div>

      <!-- Tab: Văn cảnh -->
      <div class="panel-body" id="contextView" style="display: none;">
        <div class="context-box">
          <div style="font-size: 0.75rem; text-transform: uppercase; color: #64748b; font-weight: 700; margin-bottom: 4px;">Phân mục / Thuyết minh:</div>
          <h4 id="tableHeadingText">--</h4>
          <div style="font-size: 0.82rem; color: #cbd5e1; margin-top: 6px; white-space: pre-wrap;" id="tablePreText">
            --
          </div>
        </div>
        <div style="font-size: 0.82rem; color: #94a3b8; line-height: 1.5;">
          💡 <b>Hướng dẫn rà soát nhanh:</b><br>
          • <b>Đối chiếu số liệu:</b> So khớp bảng tính bên phải với ảnh crop bên trái.<br>
          • <b>Sửa số dính OCR:</b> Bấm trực tiếp vào ô để sửa (ví dụ <code>1.497.448.618.455</code>).<br>
          • <b>Thêm/Xóa dòng/cột:</b> Sử dụng các nút bấm trên thanh công cụ.<br>
          • <b>Lưu & Tiếp tục:</b> Phím tắt <kbd>Ctrl + S</kbd> để lưu và chuyển bảng kế tiếp.
        </div>
      </div>

      <!-- Tab: Raw Markdown / HTML -->
      <div class="panel-body" id="rawView" style="display: none;">
        <textarea id="rawMarkdownArea" class="raw-textarea" spellcheck="false"></textarea>
        <div style="margin-top: 8px; text-align: right;">
          <button class="btn btn-secondary btn-sm" onclick="applyRawMarkdownToGrid()">
            📥 Cập nhật vào lưới Visual Grid
          </button>
        </div>
      </div>
    </div>

    <!-- Cột phải: Visual Spreadsheet Editor -->
    <div class="right-panel">
      <div class="editor-toolbar">
        <div class="toolbar-group">
          <span class="table-stats-badge" id="gridDimensionsBadge">0 rows × 0 cols</span>
          <label style="font-size: 0.8rem; color: #94a3b8; display: flex; align-items: center; gap: 4px; margin-left: 6px;">
            Số dòng Header:
            <select id="headerCountSelect" class="btn btn-secondary btn-sm" onchange="changeHeaderCount(this.value)">
              <option value="1">1 tầng (Chuẩn)</option>
              <option value="2">2 tầng (Phân cấp)</option>
            </select>
          </label>
        </div>

        <div class="toolbar-group">
          <button class="btn btn-secondary btn-sm" onclick="insertRow('above')" title="Thêm 1 hàng phía trên ô đang chọn">
            ➕ Hàng trên
          </button>
          <button class="btn btn-secondary btn-sm" onclick="insertRow('below')" title="Thêm 1 hàng phía dưới ô đang chọn">
            ➕ Hàng dưới
          </button>
          <button class="btn btn-secondary btn-sm" style="color: #f87171;" onclick="deleteFocusedRow()" title="Xóa hàng đang chọn">
            🗑️ Xóa hàng
          </button>
          <span style="color: #475569;">|</span>
          <button class="btn btn-secondary btn-sm" onclick="insertCol('left')" title="Thêm 1 cột bên trái">
            ➕ Cột trái
          </button>
          <button class="btn btn-secondary btn-sm" onclick="insertCol('right')" title="Thêm 1 cột bên phải">
            ➕ Cột phải
          </button>
          <button class="btn btn-secondary btn-sm" style="color: #f87171;" onclick="deleteFocusedCol()" title="Xóa cột đang chọn">
            🗑️ Xóa cột
          </button>
        </div>

        <div class="toolbar-group">
          <button class="btn btn-secondary btn-sm" onclick="autoFormatNumbers()" title="Chuẩn hóa định dạng số và phân cách hàng nghìn">
            🔢 Format Số
          </button>
          <button class="btn btn-secondary btn-sm" onclick="resetCurrentTable()" title="Hoàn tác bảng này về bản OCR ban đầu">
            🔄 Khôi phục
          </button>
        </div>
      </div>

      <!-- Sheet Container -->
      <div class="grid-container" id="gridContainer">
        <table class="sheet-table" id="sheetTable">
          <!-- Render dynamically by JS -->
        </table>
      </div>
    </div>
  </div>

  <!-- Bottom Navigation -->
  <footer>
    <div class="table-nav">
      <button class="btn btn-secondary btn-sm" onclick="prevTable()" id="prevBtn">
        ◀ Bảng trước (Left Arrow)
      </button>
      <span style="font-weight: 600; font-size: 0.9rem;" id="navCounter">
        Bảng 1 / 1
      </span>
      <button class="btn btn-secondary btn-sm" onclick="nextTable()" id="nextBtn">
        Bảng tiếp theo (Right Arrow) ▶
      </button>
      <div style="display: flex; align-items: center; gap: 6px; margin-left: 8px;">
        <label for="tableJumpSelect" style="font-size: 0.78rem; color: #94a3b8; font-weight: 500;">Chuyển nhanh:</label>
        <select id="tableJumpSelect" class="btn btn-secondary btn-sm" onchange="jumpToTable(this.value)" style="max-width: 320px; font-size: 0.78rem; text-overflow: ellipsis; padding: 3px 8px;">
        </select>
      </div>
      <span class="status-badge badge-unmodified" id="currentTableStatusBadge">
        Chưa chỉnh sửa
      </span>
    </div>

    <div style="font-size: 0.8rem; color: #94a3b8;">
      Tổng tiến độ: <b id="progressSummary" style="color: #38bdf8;">Đã sửa 0 / 0 bảng</b>
    </div>
  </footer>

  <!-- Modal Xuất Lần Cuối -->
  <div class="modal-overlay" id="exportModal" onclick="closeModals(event)">
    <div class="modal-card" onclick="event.stopPropagation()">
      <h3 style="color: #60a5fa; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
        🚀 Xuất File Markdown Hoàn Chỉnh (Lần cuối)
      </h3>
      <p style="font-size: 0.88rem; color: #cbd5e1; line-height: 1.5; margin-bottom: 16px;">
        Toàn bộ tài liệu Markdown gốc cùng các bảng biểu đã được bạn rà soát & sửa sẽ được lưu lại, bảo toàn 100% từng câu từ và cấu trúc văn bản.
      </p>

      <div style="margin-bottom: 16px;">
        <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 6px; color: #94a3b8;">
          Đường dẫn file xuất ra (.md):
        </label>
        <input type="text" id="exportPathInput" style="width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid #475569; border-radius: 6px; color: #fff; font-family: 'JetBrains Mono', monospace; font-size: 0.88rem;" />
      </div>

      <div id="exportDiffStats" style="background: #0f172a; padding: 12px; border-radius: 6px; font-size: 0.82rem; color: #94a3b8; margin-bottom: 20px; line-height: 1.5;">
        Đang kiểm tra thay đổi...
      </div>

      <div style="display: flex; justify-content: flex-end; gap: 10px;">
        <button class="btn btn-secondary" onclick="document.getElementById('exportModal').style.display='none'">
          Hủy bỏ
        </button>
        <button class="btn btn-success" onclick="confirmExportFinal()">
          ✓ Xác nhận & Xuất File
        </button>
      </div>
    </div>
  </div>

  <!-- Modal Xem toàn văn MD -->
  <div class="modal-overlay" id="previewModal" onclick="closeModals(event)">
    <div class="modal-card" style="max-width: 800px; height: 80vh; display: flex; flex-direction: column;" onclick="event.stopPropagation()">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <h3 style="color: #60a5fa;">Toàn văn Markdown sau khi sửa</h3>
        <button class="btn btn-secondary btn-sm" onclick="document.getElementById('previewModal').style.display='none'">✕</button>
      </div>
      <textarea id="fullDocTextarea" class="raw-textarea" style="flex: 1;" readonly></textarea>
    </div>
  </div>

  <script>
    let currentDocument = null;
    let tables = [];
    let currentIndex = 0;
    let focusedCell = { r: 0, c: 0 };
    let editedTables = {};
    let isZoomed = false;
    let currentRotation = 0;

    async function init() {
      // Đọc query parameters từ URL (?company=...&year=...)
      const params = new URLSearchParams(window.location.search);
      const company = params.get('company') || '';
      const year = params.get('year') || '';
      const file = params.get('file') || '';
      
      let queryStr = '';
      if (company && year) {
        queryStr = `?company=${encodeURIComponent(company)}&year=${encodeURIComponent(year)}`;
      } else if (file) {
        queryStr = `?file=${encodeURIComponent(file)}`;
      }
      
      await loadDocument(queryStr);
    }

    async function loadDocument(queryStr) {
      const url = queryStr ? `/api/document${queryStr}` : '/api/document';
      try {
        const res = await fetch(url);
        currentDocument = await res.json();
        if (currentDocument.error) {
          alert("Lỗi tải tài liệu: " + currentDocument.error);
          return;
        }

        tables = currentDocument.tables || [];
        editedTables = {};
        
        // Cập nhật Badge trên Header (Không cần chọn nguồn)
        const comp = currentDocument.company || 'BCTC';
        const yr = currentDocument.year || '2025';
        document.getElementById('badgeCompanyText').innerText = `${comp} (${yr})`;
        document.getElementById('badgeTableCount').innerText = `${tables.length} Bảng Biểu`;
        
        const defaultExport = currentDocument.file_path 
          ? currentDocument.file_path.replace(/\.md$/i, '_final.md')
          : `outputs/${comp}_${yr}/${comp}_${yr}_financial_report_final.md`;
        document.getElementById('exportPathInput').value = defaultExport;

        // Khởi tạo danh sách chọn nhanh bảng
        const jumpSel = document.getElementById('tableJumpSelect');
        if (jumpSel) {
          jumpSel.innerHTML = '';
          tables.forEach((t, i) => {
            const opt = document.createElement('option');
            opt.value = i;
            const h = (t.heading || '').replace(/^[#*>\-\s]+/, '').trim();
            const shortH = h.length > 35 ? h.substring(0, 33) + '...' : h;
            opt.innerText = `Bảng ${i + 1} (Trang ${t.page}): ${shortH || 'Bảng ' + (i + 1)}`;
            jumpSel.appendChild(opt);
          });
        }

        currentIndex = 0;
        if (tables.length > 0) {
          renderCurrentTable();
        } else {
          document.getElementById('sheetTable').innerHTML = '<tr><td style="padding:20px; text-align:center;">Không tìm thấy bảng biểu nào trong cache của tài liệu này.</td></tr>';
        }
        updateGlobalStats();
      } catch (e) {
        alert("Lỗi kết nối máy chủ: " + e.message);
      }
    }

    function renderCurrentTable() {
      if (currentIndex < 0 || currentIndex >= tables.length) return;
      const t = getActiveTableData();

      // Đồng bộ thanh chọn nhanh
      const jumpSel = document.getElementById('tableJumpSelect');
      if (jumpSel) jumpSel.value = currentIndex;

      // Cập nhật thông tin tiêu đề và ngữ cảnh
      document.getElementById('tableHeadingText').innerText = t.heading || `Bảng ${t.table_id}`;
      document.getElementById('tablePreText').innerText = t.pre_text || '(Không có đoạn văn mở đầu)';
      
      const blockTag = t.block_id ? ` • ${t.block_id}` : '';
      document.getElementById('pageBadge').innerText = `Trang ${t.page || '--'}${blockTag}`;
      document.getElementById('navCounter').innerText = `Bảng ${currentIndex + 1} / ${tables.length}`;
      document.getElementById('gridDimensionsBadge').innerText = `${t.rows.length} rows × ${t.rows[0] ? t.rows[0].length : 0} cols`;
      document.getElementById('headerCountSelect').value = t.header_rows_count || 1;

      // Status badge
      const badge = document.getElementById('currentTableStatusBadge');
      if (editedTables[t.table_id]) {
        badge.className = 'status-badge badge-edited';
        badge.innerText = '✏️ Đã chỉnh sửa';
      } else {
        badge.className = 'status-badge badge-unmodified';
        badge.innerText = 'Chưa chỉnh sửa';
      }

      // CẬP NHẬT ẢNH CROP BẢNG TƯƠNG ỨNG TỪ CACHE CỦA ĐÚNG DOANH NGHIỆP NÀY
      const cropImg = document.getElementById('pdfCropImage');
      const comp = currentDocument.company || t.company || 'VIC';
      const yr = currentDocument.year || t.year || 2025;
      const cropUrl = `/api/table_crop?company=${encodeURIComponent(comp)}&year=${encodeURIComponent(yr)}&block_id=${encodeURIComponent(t.block_id || '')}&page=${t.page}`;
      cropImg.src = cropUrl;
      document.getElementById('cropInfoLabel').innerText = `Ảnh crop: Trang ${t.page} (Khối: ${t.block_id || 'table_' + t.table_id}) • ${comp} (${yr})`;
      
      // Reset zoom và rotation khi chuyển bảng
      isZoomed = false;
      currentRotation = 0;
      applyImageTransform();
      const zoomBtnEl = document.getElementById('zoomBtn');
      if (zoomBtnEl) zoomBtnEl.innerText = '🔍 Phóng to (135%)';

      // Cập nhật Raw Textarea
      updateRawArea(t);

      // Render Visual Grid
      renderSheetGrid(t);
    }


    function applyImageTransform() {
      const cropImg = document.getElementById('pdfCropImage');
      const wrapper = document.querySelector('.crop-image-wrapper');
      if (!cropImg) return;
      
      const isRotated90 = (currentRotation === 90 || currentRotation === 270);
      let transformStr = `rotate(${currentRotation}deg)`;
      if (isZoomed) {
        transformStr += ` scale(1.35)`;
      }
      cropImg.style.transform = transformStr;
      cropImg.style.transformOrigin = 'center center';
      cropImg.style.transition = 'transform 0.25s ease';

      if (wrapper) {
        wrapper.style.minHeight = isRotated90 ? '550px' : 'auto';
        wrapper.style.overflow = 'auto';
      }

      const rotBtn = document.getElementById('rotateBtn');
      if (rotBtn) {
        rotBtn.innerText = currentRotation > 0 ? `↻ (${currentRotation}°)` : '↻ Xoay +90°';
      }
    }

    function rotateImage(deg = 90) {
      currentRotation = (currentRotation + deg) % 360;
      if (currentRotation < 0) currentRotation += 360;
      applyImageTransform();
      showToast(`Đã xoay ảnh sang ${currentRotation}°. Bấm "⚡ OCR lại bảng" nếu muốn nhận diện lại dữ liệu!`, 'info');
    }

    function toggleZoom() {
      isZoomed = !isZoomed;
      applyImageTransform();
      const zoomBtn = document.getElementById('zoomBtn');
      if (zoomBtn) {
        zoomBtn.innerText = isZoomed ? '🔍 Thu nhỏ' : '🔍 Phóng to (135%)';
      }
    }

    function openImageNewTab() {
      const cropImg = document.getElementById('pdfCropImage');
      if (cropImg && cropImg.src) {
        window.open(cropImg.src, '_blank');
      }
    }

    async function reocrCurrentTable() {
      const t = tables[currentIndex];
      if (!t) return;
      const reocrBtn = document.getElementById('reocrBtn');
      const originalText = reocrBtn ? reocrBtn.innerText : '⚡ OCR lại bảng';
      if (reocrBtn) {
        reocrBtn.disabled = true;
        reocrBtn.innerText = '⏳ Đang OCR lại...';
      }

      try {
        const payload = {
          table_id: t.table_id,
          block_id: t.block_id,
          page: t.page,
          rotation: currentRotation,
          company: currentDocument.company || t.company,
          year: currentDocument.year || t.year,
        };

        const res = await fetch('/api/reocr_table', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (data.status === 'ok') {
          t.rows = data.rows;
          t.raw_markdown = data.raw_markdown;
          t.n_rows = data.n_rows;
          t.n_cols = data.n_cols;
          t.is_edited = true;
          editedTables[t.table_id] = JSON.parse(JSON.stringify(t));

          currentRotation = 0;
          applyImageTransform();

          const cropImg = document.getElementById('pdfCropImage');
          cropImg.src = cropImg.src.split('&_t=')[0] + '&_t=' + Date.now();

          renderSheetGrid(t);
          updateRawArea(t);

          const badge = document.getElementById('tableStatusBadge');
          if (badge) {
            badge.className = 'status-badge badge-modified';
            badge.innerText = 'Đã OCR lại';
          }

          showToast(`✅ Đã OCR lại bảng thành công! (${t.n_rows} hàng × ${t.n_cols} cột)`, 'success');
        } else {
          showToast(`⚠️ Lỗi OCR lại bảng: ${data.error || 'Thất bại'}`, 'error');
        }
      } catch (err) {
        showToast(`⚠️ Lỗi kết nối: ${err.message}`, 'error');
      } finally {
        if (reocrBtn) {
          reocrBtn.disabled = false;
          reocrBtn.innerText = originalText;
        }
      }
    }

    function getActiveTableData() {
      const orig = tables[currentIndex];
      if (editedTables[orig.table_id]) {
        return editedTables[orig.table_id];
      }
      return JSON.parse(JSON.stringify(orig));
    }

    function renderSheetGrid(t) {
      const tableEl = document.getElementById('sheetTable');
      tableEl.innerHTML = '';
      const rows = t.rows;
      if (!rows || rows.length === 0) return;

      const nCols = rows[0].length;
      const headerRowsCount = parseInt(t.header_rows_count) || 1;

      // Cột chữ cái A, B, C...
      const colHeaderTr = document.createElement('tr');
      const cornerTh = document.createElement('th');
      cornerTh.className = 'corner-th';
      cornerTh.innerText = '#';
      colHeaderTr.appendChild(cornerTh);

      for (let c = 0; c < nCols; c++) {
        const th = document.createElement('th');
        th.innerText = getColumnLetter(c);
        colHeaderTr.appendChild(th);
      }
      tableEl.appendChild(colHeaderTr);

      // Các hàng dữ liệu
      rows.forEach((row, rIdx) => {
        const tr = document.createElement('tr');
        if (rIdx < headerRowsCount) {
          tr.className = 'header-tier-row';
        }

        const rowTh = document.createElement('th');
        rowTh.className = 'row-header-th';
        rowTh.innerText = rIdx + 1;
        tr.appendChild(rowTh);

        row.forEach((cellVal, cIdx) => {
          const td = document.createElement('td');
          const input = document.createElement('input');
          input.type = 'text';
          input.className = 'cell-input';
          input.value = cellVal;
          input.dataset.row = rIdx;
          input.dataset.col = cIdx;

          input.addEventListener('focus', () => {
            focusedCell = { r: rIdx, c: cIdx };
          });

          input.addEventListener('input', (e) => {
            onCellInput(rIdx, cIdx, e.target.value);
          });

          input.addEventListener('keydown', (e) => {
            handleCellKeydown(e, rIdx, cIdx);
          });

          td.appendChild(input);
          tr.appendChild(td);
        });

        tableEl.appendChild(tr);
      });
    }

    function getColumnLetter(colIndex) {
      let letter = '';
      while (colIndex >= 0) {
        letter = String.fromCharCode((colIndex % 26) + 65) + letter;
        colIndex = Math.floor(colIndex / 26) - 1;
      }
      return letter;
    }

    function onCellInput(r, c, val) {
      markTableAsEdited();
      const t = editedTables[tables[currentIndex].table_id];
      t.rows[r][c] = val;
      updateRawArea(t);
    }

    function handleCellKeydown(e, r, c) {
      if (e.key === 'Enter') {
        e.preventDefault();
        focusCell(r + 1, c);
      } else if (e.key === 'ArrowUp' && e.ctrlKey) {
        e.preventDefault();
        focusCell(r - 1, c);
      } else if (e.key === 'ArrowDown' && e.ctrlKey) {
        e.preventDefault();
        focusCell(r + 1, c);
      }
    }

    function focusCell(r, c) {
      const el = document.querySelector(`input[data-row="${r}"][data-col="${c}"]`);
      if (el) {
        el.focus();
        el.select();
      }
    }

    function markTableAsEdited() {
      const orig = tables[currentIndex];
      if (!editedTables[orig.table_id]) {
        editedTables[orig.table_id] = JSON.parse(JSON.stringify(orig));
      }
      editedTables[orig.table_id].is_edited = true;
      document.getElementById('currentTableStatusBadge').className = 'status-badge badge-edited';
      document.getElementById('currentTableStatusBadge').innerText = '✏️ Đã chỉnh sửa';
      updateGlobalStats();
    }

    function insertRow(pos) {
      markTableAsEdited();
      const t = editedTables[tables[currentIndex].table_id];
      const nCols = t.rows[0] ? t.rows[0].length : 1;
      const emptyRow = new Array(nCols).fill('');
      const targetR = pos === 'above' ? focusedCell.r : focusedCell.r + 1;
      t.rows.splice(targetR, 0, emptyRow);
      renderSheetGrid(t);
      updateRawArea(t);
      document.getElementById('gridDimensionsBadge').innerText = `${t.rows.length} rows × ${nCols} cols`;
    }

    function deleteFocusedRow() {
      const t = getActiveTableData();
      if (t.rows.length <= 1) {
        alert("Bảng phải có ít nhất 1 hàng!");
        return;
      }
      markTableAsEdited();
      const cur = editedTables[tables[currentIndex].table_id];
      cur.rows.splice(focusedCell.r, 1);
      if (focusedCell.r >= cur.rows.length) focusedCell.r = cur.rows.length - 1;
      renderSheetGrid(cur);
      updateRawArea(cur);
      document.getElementById('gridDimensionsBadge').innerText = `${cur.rows.length} rows × ${cur.rows[0].length} cols`;
    }

    function insertCol(pos) {
      markTableAsEdited();
      const t = editedTables[tables[currentIndex].table_id];
      const targetC = pos === 'left' ? focusedCell.c : focusedCell.c + 1;
      t.rows.forEach(r => r.splice(targetC, 0, ''));
      renderSheetGrid(t);
      updateRawArea(t);
      document.getElementById('gridDimensionsBadge').innerText = `${t.rows.length} rows × ${t.rows[0].length} cols`;
    }

    function deleteFocusedCol() {
      const t = getActiveTableData();
      if (t.rows[0].length <= 1) {
        alert("Bảng phải có ít nhất 1 cột!");
        return;
      }
      markTableAsEdited();
      const cur = editedTables[tables[currentIndex].table_id];
      cur.rows.forEach(r => r.splice(focusedCell.c, 1));
      if (focusedCell.c >= cur.rows[0].length) focusedCell.c = cur.rows[0].length - 1;
      renderSheetGrid(cur);
      updateRawArea(cur);
      document.getElementById('gridDimensionsBadge').innerText = `${cur.rows.length} rows × ${cur.rows[0].length} cols`;
    }

    function changeHeaderCount(cnt) {
      markTableAsEdited();
      const t = editedTables[tables[currentIndex].table_id];
      t.header_rows_count = parseInt(cnt);
      renderSheetGrid(t);
      updateRawArea(t);
    }

    function autoFormatNumbers() {
      markTableAsEdited();
      const t = editedTables[tables[currentIndex].table_id];
      t.rows.forEach((row, rIdx) => {
        if (rIdx < (t.header_rows_count || 1)) return;
        row.forEach((cell, cIdx) => {
          let trimmed = cell.trim();
          if (/^\\d{10,}$/.test(trimmed)) {
            row[cIdx] = trimmed.replace(/\\B(?=(\\d{3})+(?!\\d))/g, ".");
          }
        });
      });
      renderSheetGrid(t);
      updateRawArea(t);
    }

    function resetCurrentTable() {
      const tid = tables[currentIndex].table_id;
      delete editedTables[tid];
      renderCurrentTable();
      updateGlobalStats();
    }

    function updateRawArea(t) {
      const lines = [];
      const nCols = t.rows[0] ? t.rows[0].length : 0;
      if (nCols === 0) return;

      const hdrCount = t.header_rows_count || 1;
      for (let h = 0; h < hdrCount; h++) {
        lines.push("| " + t.rows[h].join(" | ") + " |");
      }
      lines.push("| " + new Array(nCols).fill("---").join(" | ") + " |");
      for (let r = hdrCount; r < t.rows.length; r++) {
        lines.push("| " + t.rows[r].join(" | ") + " |");
      }
      document.getElementById('rawMarkdownArea').value = lines.join("\\n");
    }

    function applyRawMarkdownToGrid() {
      const raw = document.getElementById('rawMarkdownArea').value;
      const lines = raw.trim().split('\\n').map(l => l.trim()).filter(l => l.startsWith('|') && l.endsWith('|'));
      if (lines.length === 0) return;

      const newRows = [];
      let sepFound = false;
      let hdrCount = 1;

      lines.forEach((l, idx) => {
        const inner = l.slice(1, -1);
        const cells = inner.split('|').map(c => c.trim());
        const isSep = cells.every(c => /^:?-+:?$/.test(c));
        if (isSep && !sepFound) {
          sepFound = true;
          hdrCount = idx;
        } else {
          newRows.push(cells);
        }
      });

      markTableAsEdited();
      const t = editedTables[tables[currentIndex].table_id];
      t.rows = newRows;
      t.header_rows_count = hdrCount;
      renderSheetGrid(t);
    }

    function commitCurrentTableInMemory() {
      if (!tables || tables.length === 0 || currentIndex < 0 || currentIndex >= tables.length) return;
      const orig = tables[currentIndex];
      if (editedTables[orig.table_id]) {
        editedTables[orig.table_id] = getActiveTableData();
      }
    }

    function prevTable() {
      if (currentIndex > 0) {
        commitCurrentTableInMemory();
        currentIndex--;
        renderCurrentTable();
      }
    }

    function nextTable() {
      if (currentIndex < tables.length - 1) {
        commitCurrentTableInMemory();
        currentIndex++;
        renderCurrentTable();
      }
    }

    function jumpToTable(idx) {
      const target = parseInt(idx);
      if (!isNaN(target) && target >= 0 && target < tables.length) {
        commitCurrentTableInMemory();
        currentIndex = target;
        renderCurrentTable();
      }
    }

    function switchLeftTab(tab) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('contextView').style.display = 'none';
      document.getElementById('imageView').style.display = 'none';
      document.getElementById('rawView').style.display = 'none';

      if (tab === 'image') {
        document.getElementById('tabImageBtn').classList.add('active');
        document.getElementById('imageView').style.display = 'block';
      } else if (tab === 'context') {
        document.getElementById('tabContextBtn').classList.add('active');
        document.getElementById('contextView').style.display = 'block';
      } else if (tab === 'raw') {
        document.getElementById('tabRawBtn').classList.add('active');
        document.getElementById('rawView').style.display = 'block';
      }
    }

    function updateGlobalStats() {
      const count = Object.keys(editedTables).length;
      document.getElementById('progressSummary').innerText = `Đã sửa ${count} / ${tables.length} bảng`;
    }

    async function syncAllEditsToServer() {
      if (tables && tables.length > 0 && currentIndex >= 0 && currentIndex < tables.length) {
        const tid = tables[currentIndex].table_id;
        if (editedTables[tid]) {
          editedTables[tid] = getActiveTableData();
        }
      }
      updateGlobalStats();

      const comp = (currentDocument && currentDocument.company) || 'VNM';
      const yr = (currentDocument && currentDocument.year) || 2025;
      const fpath = (currentDocument && currentDocument.file_path) || '';

      try {
        const res = await fetch('/api/sync_all_edits', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            company: comp,
            year: yr,
            file_path: fpath,
            edited_tables: editedTables
          })
        });
        const data = await res.json();
        return data;
      } catch (err) {
        console.warn('Lỗi syncAllEditsToServer:', err);
        return { status: 'error', error: err.message };
      }
    }

    async function saveCurrentTable() {
      if (!tables || tables.length === 0 || currentIndex < 0 || currentIndex >= tables.length) return;
      const tid = tables[currentIndex].table_id;
      const t = getActiveTableData();
      editedTables[tid] = t;
      updateGlobalStats();
      
      const statusBadge = document.getElementById('currentTableStatusBadge');
      if (statusBadge) {
        statusBadge.className = 'status-badge badge-edited';
        statusBadge.innerText = '✏️ Đã chỉnh sửa';
      }

      const saveBtn = document.getElementById('saveBtn');
      if (saveBtn) {
        saveBtn.innerText = '⏳ Đang Lưu...';
        saveBtn.style.backgroundColor = '#f59e0b';
      }

      const syncResult = await syncAllEditsToServer();

      if (saveBtn) {
        const count = Object.keys(editedTables).length;
        saveBtn.innerText = `✓ Đã Lưu (${count} bảng)`;
        saveBtn.style.backgroundColor = '#10b981';
        setTimeout(() => { 
          saveBtn.innerText = '💾 Lưu Bảng (Ctrl+S)'; 
          saveBtn.style.backgroundColor = '';
        }, 1500);
      }

      showToast(`✅ Đã đồng bộ & lưu ${Object.keys(editedTables).length} bảng vào file Markdown hoàn thiện!`, 'success');
    }

    function openExportModal() {
      const editedCount = Object.keys(editedTables).length;
      document.getElementById('exportDiffStats').innerHTML = `
        • <b>Tổng số bảng trong tài liệu:</b> ${tables.length} bảng<br>
        • <b>Số bảng đã chỉnh sửa:</b> <b style="color:#34d399;">${editedCount} bảng</b><br>
        • <b>Trạng thái:</b> Sẵn sàng xuất văn bản Markdown chuẩn hóa cuối cùng.
      `;
      document.getElementById('exportModal').style.display = 'flex';
    }

    async function confirmExportFinal() {
      const targetPath = document.getElementById('exportPathInput').value.trim();
      if (!targetPath) {
        alert("Vui lòng nhập đường dẫn file xuất!");
        return;
      }

      try {
        const res = await fetch('/api/export_final', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            company: currentDocument.company,
            year: currentDocument.year,
            file_path: currentDocument.file_path,
            export_path: targetPath,
            edited_tables: editedTables
          })
        });

        const data = await res.json();
        if (data.status === 'ok') {
          alert(`🎉 XUẤT FILE HOÀN TẤT!\nFile đã lưu tại:\n${data.saved_path}`);
          document.getElementById('exportModal').style.display = 'none';
        } else {
          alert("Lỗi xuất file: " + data.error);
        }
      } catch (e) {
        alert("Lỗi kết nối máy chủ: " + e.message);
      }
    }

    async function openPreviewModal() {
      try {
        const res = await fetch('/api/preview_full', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            company: currentDocument.company,
            year: currentDocument.year,
            file_path: currentDocument.file_path,
            edited_tables: editedTables
          })
        });
        const data = await res.json();
        document.getElementById('fullDocTextarea').value = data.markdown;
        document.getElementById('previewModal').style.display = 'flex';
      } catch (e) {
        alert("Lỗi tạo preview: " + e.message);
      }
    }

    function closeModals(e) {
      document.getElementById('exportModal').style.display = 'none';
      document.getElementById('previewModal').style.display = 'none';
    }

    document.addEventListener('keydown', (e) => {
      if (e.ctrlKey && (e.key === 's' || e.key === 'S')) {
        e.preventDefault();
        e.stopPropagation();
        saveCurrentTable();
      } else if (e.key === 'ArrowLeft' && e.altKey) {
        e.preventDefault();
        prevTable();
      } else if (e.key === 'ArrowRight' && e.altKey) {
        e.preventDefault();
        nextTable();
      }
    });

    // Lắng nghe lệnh lưu / đồng bộ từ trang cha (nếu nhúng iframe)
    window.addEventListener('message', async (e) => {
      if (e.data && (e.data.action === 'save_table' || e.data.action === 'sync_all' || e.data.action === 'export_all')) {
        const res = await syncAllEditsToServer();
        try {
          if (window.parent && window.parent !== window) {
            window.parent.postMessage({ action: 'sync_complete', status: 'ok', detail: res }, '*');
          }
        } catch (_) {}
      }
    });

    window.onload = init;
  </script>
</body>
</html>
"""


# =====================================================================
# 4. HTTP SERVER & API HANDLER
# =====================================================================

class TableEditorHandler(BaseHTTPRequestHandler):
    active_company: str = "VIC"
    active_year: int = 2025
    active_file: Path = PROJECT_ROOT / "outputs" / "VIC_2025_financial_report.md"
    cached_tables: list[dict[str, Any]] = []

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(EDITOR_HTML_TEMPLATE.encode("utf-8"))
            return

        elif path == "/api/document":
            req_company = query.get("company", [None])[0]
            req_year = query.get("year", [None])[0]
            req_file = query.get("file", [None])[0]

            company = TableEditorHandler.active_company
            year = TableEditorHandler.active_year
            target_path = TableEditorHandler.active_file

            if req_file:
                target_path = Path(unquote(req_file)).resolve()
                stem = target_path.stem
                parts = stem.split("_")
                if len(parts) >= 2 and parts[1].isdigit():
                    company = parts[0].upper()
                    year = int(parts[1])
            elif req_company and req_year:
                company = req_company.upper()
                try:
                    year = int(req_year)
                except ValueError:
                    year = 2025
                cand1 = PROJECT_ROOT / "outputs" / f"{company}_{year}" / f"{company}_{year}_financial_report.md"
                cand2 = PROJECT_ROOT / "outputs" / f"{company}_{year}_financial_report.md"
                target_path = cand1 if cand1.exists() else (cand2 if cand2.exists() else cand1)
            else:
                # Tự động nhận diện doanh nghiệp mới nhất trong cache
                company, year = detect_latest_company_year()
                cand1 = PROJECT_ROOT / "outputs" / f"{company}_{year}" / f"{company}_{year}_financial_report.md"
                cand2 = PROJECT_ROOT / "outputs" / f"{company}_{year}_financial_report.md"
                target_path = cand1 if cand1.exists() else (cand2 if cand2.exists() else cand1)

            TableEditorHandler.active_company = company
            TableEditorHandler.active_year = year
            TableEditorHandler.active_file = target_path

            try:
                tables = load_all_tables_from_cache(company=company, year=year)
                if not tables:
                    # Kiểm tra xem có niên độ nào khác của doanh nghiệp này trong cache không
                    outputs_base = PROJECT_ROOT / "outputs"
                    if outputs_base.exists():
                        matched_dirs = [d for d in outputs_base.glob(f"{company}_*") if d.is_dir() and (d / "cache").exists()]
                        if matched_dirs:
                            matched_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                            fallback_year_str = matched_dirs[0].name.split("_")[-1]
                            if fallback_year_str.isdigit():
                                year = int(fallback_year_str)
                                tables = load_all_tables_from_cache(company=company, year=year)
                                TableEditorHandler.active_year = year

                    if not tables:
                        notes_base = PROJECT_ROOT / "data" / "cache" / "notes"
                        if notes_base.exists():
                            matched_dirs = list(notes_base.glob(f"{company}_*"))
                            if matched_dirs:
                                matched_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                                fallback_year_str = matched_dirs[0].name.split("_")[-1]
                                if fallback_year_str.isdigit():
                                    year = int(fallback_year_str)
                                    tables = load_all_tables_from_cache(company=company, year=year)
                                    TableEditorHandler.active_year = year

                TableEditorHandler.cached_tables = tables

                self._send_json({
                    "company": company,
                    "year": year,
                    "file_name": target_path.name if target_path.exists() else f"{company}_{year}_financial_report.md",
                    "file_path": str(target_path) if target_path.exists() else "",
                    "total_tables": len(tables),
                    "tables": tables
                })
            except Exception as e:
                logger.error("Lỗi đọc document: %s", e)
                self._send_json({"error": str(e)}, status=500)
            return

        # ENDPOINT PHỤC VỤ ẢNH CROP BẢNG CHÍNH XÁC (KHÔNG LẤY TỪ NGUỒN KHÁC)
        elif path == "/api/table_crop":
            block_id = query.get("block_id", [""])[0]
            page_str = query.get("page", ["1"])[0]
            company = query.get("company", [TableEditorHandler.active_company])[0].upper()
            try:
                year = int(query.get("year", [str(TableEditorHandler.active_year)])[0])
            except ValueError:
                year = TableEditorHandler.active_year

            try:
                page_num = max(1, int(page_str))
            except ValueError:
                page_num = 1

            # 1. ƯU TIÊN SỐ 1: Phục vụ trực tiếp ảnh đã crop của đúng {company}_{year} trong cache
            if block_id:
                crop_file = PROJECT_ROOT / "outputs" / f"{company}_{year}" / "cache" / "table_crops" / f"{block_id}.png"
                if not crop_file.exists():
                    crop_file = PROJECT_ROOT / "data" / "cache" / "table_crops" / f"{company}_{year}" / f"{block_id}.png"
                if not crop_file.exists():
                    # Thử tìm trong các thư mục outputs khác của cùng doanh nghiệp
                    outputs_base = PROJECT_ROOT / "outputs"
                    if outputs_base.exists():
                        for cdir in outputs_base.glob(f"{company}_*/cache/table_crops"):
                            cand = cdir / f"{block_id}.png"
                            if cand.exists():
                                crop_file = cand
                                break
                if not crop_file.exists():
                    # Thử tìm trong các niên độ khác của cùng doanh nghiệp ở data/cache
                    crops_base = PROJECT_ROOT / "data" / "cache" / "table_crops"
                    if crops_base.exists():
                        for cdir in crops_base.glob(f"{company}_*"):
                            cand = cdir / f"{block_id}.png"
                            if cand.exists():
                                crop_file = cand
                                break

                if crop_file.exists():
                    self._send_file(crop_file, "image/png")
                    return

            # 2. ƯU TIÊN SỐ 2: Render crop trực tiếp theo bbox từ PDF gốc của chính doanh nghiệp đó
            pdf_path = find_pdf_for_company(company, year)
            if HAS_PYMUPDF and pdf_path and pdf_path.exists():
                try:
                    doc = fitz.open(str(pdf_path))
                    if 1 <= page_num <= len(doc):
                        page = doc[page_num - 1]
                        pw = page.rect.width
                        ph = page.rect.height

                        # Tìm bbox từ cached_tables
                        matched = next((t for t in TableEditorHandler.cached_tables if t.get("block_id") == block_id), None)
                        bbox = matched.get("bbox") if matched else None

                        if bbox and len(bbox) == 4:
                            c1, c2, c3, c4 = bbox
                            xmin = min(c1, c3)
                            xmax = max(c1, c3)
                            ymin = min(c2, c4)
                            ymax = max(c2, c4)

                            pad = 12
                            rect = fitz.Rect(
                                max(0, xmin * pw - pad),
                                max(0, ymin * ph - pad),
                                min(pw, xmax * pw + pad),
                                min(ph, ymax * ph + pad)
                            )
                        else:
                            rect = fitz.Rect(0.08 * pw, 0.15 * ph, 0.92 * pw, 0.88 * ph)

                        pix = page.get_pixmap(clip=rect, dpi=200)
                        png_bytes = pix.tobytes("png")
                        
                        # Lưu vào cache table_crops để lần sau load tức thì (0ms)
                        if block_id:
                            save_dir = PROJECT_ROOT / "outputs" / f"{company}_{year}" / "cache" / "table_crops"
                            save_dir.mkdir(parents=True, exist_ok=True)
                            (save_dir / f"{block_id}.png").write_bytes(png_bytes)

                        try:
                            self.send_response(200)
                            self.send_header("Content-Type", "image/png")
                            self.send_header("Content-Length", str(len(png_bytes)))
                            self.end_headers()
                            self.wfile.write(png_bytes)
                        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                            # Client hủy kết nối khi chuyển trang nhanh
                            pass
                        return
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                    # Client hủy tải ảnh khi cuộn nhanh - bỏ qua bình thường
                    return
                except Exception as e:
                    logger.error("Lỗi dynamic crop: %s", e)
                    self._send_json({"error": str(e)}, status=500)
                    return

            # Chuỗi ASCII an toàn (tránh UnicodeEncodeError latin-1 trong send_error)
            self.send_error(404, f"Crop image not found for {company} block {block_id}")
            return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if path in ("/api/save_table", "/api/sync_all_edits"):
            company = (payload.get("company") or TableEditorHandler.active_company).upper()
            try:
                year = int(payload.get("year") or TableEditorHandler.active_year)
            except (ValueError, TypeError):
                year = 2025

            TableEditorHandler.active_company = company
            TableEditorHandler.active_year = year

            file_path_str = payload.get("file_path")
            if file_path_str and Path(file_path_str).exists():
                TableEditorHandler.active_file = Path(file_path_str).resolve()
            else:
                cand1 = PROJECT_ROOT / "outputs" / f"{company}_{year}" / f"{company}_{year}_financial_report.md"
                cand2 = PROJECT_ROOT / "outputs" / f"{company}_{year}_financial_report.md"
                TableEditorHandler.active_file = cand1 if cand1.exists() else (cand2 if cand2.exists() else cand1)

            # Đảm bảo danh sách bảng trong cache luôn sẵn sàng
            if not TableEditorHandler.cached_tables:
                TableEditorHandler.cached_tables = load_all_tables_from_cache(company=company, year=year)

            cache_dirs = [
                PROJECT_ROOT / "outputs" / f"{company}_{year}" / "cache" / "notes",
                PROJECT_ROOT / "outputs" / f"{company}_{year}" / "cache" / "ocr",
                PROJECT_ROOT / "data" / "cache" / "notes" / f"{company}_{year}",
                PROJECT_ROOT / "data" / "cache" / "ocr" / f"{company}_{year}",
            ]

            # 1. Thu thập tất cả các bảng cần cập nhật
            tables_to_update: dict[int, dict[str, Any]] = {}

            # Nếu là sync_all_edits: nhận toàn bộ map edited_tables
            raw_edited = payload.get("edited_tables", {})
            for k, v in raw_edited.items():
                try:
                    tables_to_update[int(k)] = v
                except (ValueError, TypeError):
                    pass

            # Nếu là save_table đơn lẻ
            single_tid = payload.get("table_id")
            if single_tid is not None:
                try:
                    s_tid = int(single_tid)
                    tables_to_update[s_tid] = {
                        "table_id": s_tid,
                        "rows": payload.get("rows"),
                        "raw_markdown": payload.get("raw_markdown"),
                        "page": payload.get("page"),
                        "block_id": payload.get("block_id"),
                        "header_rows_count": payload.get("header_rows_count", 1)
                    }
                except (ValueError, TypeError):
                    pass

            # 2. Cập nhật vào TableEditorHandler.cached_tables và ghi cache JSON trên đĩa
            for tid, ed in tables_to_update.items():
                target_tbl = next((t for t in TableEditorHandler.cached_tables if t.get("table_id") == tid), None)
                if not target_tbl:
                    continue

                if ed.get("rows"):
                    target_tbl["rows"] = ed["rows"]
                    target_tbl["n_rows"] = len(ed["rows"])
                    target_tbl["n_cols"] = len(ed["rows"][0]) if ed["rows"] else 0
                if ed.get("header_rows_count"):
                    target_tbl["header_rows_count"] = ed["header_rows_count"]
                if ed.get("raw_markdown"):
                    target_tbl["raw_markdown"] = ed["raw_markdown"]
                target_tbl["is_edited"] = True

                # Cập nhật cache JSON trên đĩa
                block_id = ed.get("block_id") or target_tbl.get("block_id")
                page_num = ed.get("page") or target_tbl.get("page")
                if block_id and page_num:
                    new_md_content = ed.get("raw_markdown") or "\n".join(format_grid_to_markdown(
                        rows=target_tbl["rows"],
                        header_rows_count=target_tbl.get("header_rows_count", 1)
                    ))
                    for cdir in cache_dirs:
                        if not cdir.exists():
                            continue
                        for json_f in cdir.glob(f"page_{page_num}.json"):
                            try:
                                jdata = json.loads(json_f.read_text(encoding="utf-8"))
                                for blk in jdata:
                                    if blk.get("block_id") == block_id:
                                        blk["content"] = new_md_content
                                json_f.write_text(json.dumps(jdata, ensure_ascii=False, indent=2), encoding="utf-8")
                            except Exception as ex:
                                logger.warning("Lỗi cập nhật cache JSON: %s", ex)

            # 3. Tự động ráp nối lại toàn bộ tài liệu và ghi ngay vào file _final.md
            final_path = None
            try:
                all_edited_map = {
                    t["table_id"]: t
                    for t in TableEditorHandler.cached_tables
                    if t.get("is_edited")
                }
                for tid, ed in tables_to_update.items():
                    all_edited_map[tid] = ed

                if all_edited_map:
                    final_doc = reconstruct_full_document(
                        original_md_path=TableEditorHandler.active_file,
                        edited_tables=all_edited_map,
                        all_tables=TableEditorHandler.cached_tables
                    )
                    clean_stem = TableEditorHandler.active_file.stem.replace("_final", "")
                    final_path = TableEditorHandler.active_file.parent / f"{clean_stem}_final.md"
                    final_path.write_text(final_doc, encoding="utf-8")
                    logger.info("✓ [Auto-Save] Đã cập nhật file Markdown hoàn thiện: %s (%d bảng)", final_path, len(all_edited_map))
            except Exception as ex:
                logger.error("Lỗi tự động cập nhật _final.md: %s", ex)

            self._send_json({
                "status": "ok",
                "message": f"Đã đồng bộ {len(tables_to_update)} bảng",
                "saved_path": str(final_path) if final_path else "",
                "file_name": final_path.name if final_path else "",
                "tables_count": len(tables_to_update)
            })
            return

        elif path == "/api/export_final":
            try:
                export_path_str = payload.get("export_path")
                raw_edited = payload.get("edited_tables", {})
                company = (payload.get("company") or TableEditorHandler.active_company).upper()
                year = int(payload.get("year") or TableEditorHandler.active_year)

                TableEditorHandler.active_company = company
                TableEditorHandler.active_year = year

                if not TableEditorHandler.cached_tables:
                    TableEditorHandler.cached_tables = load_all_tables_from_cache(company=company, year=year)

                edited_tables = {int(k): v for k, v in raw_edited.items()}

                if not export_path_str:
                    clean_stem = TableEditorHandler.active_file.stem.replace("_final", "")
                    export_path = TableEditorHandler.active_file.parent / f"{clean_stem}_final.md"
                else:
                    export_path = Path(export_path_str).resolve()

                export_path.parent.mkdir(parents=True, exist_ok=True)

                all_edited_map = {
                    t["table_id"]: t
                    for t in TableEditorHandler.cached_tables
                    if t.get("is_edited")
                }
                for tid, ed in edited_tables.items():
                    all_edited_map[tid] = ed

                final_markdown = reconstruct_full_document(
                    original_md_path=TableEditorHandler.active_file,
                    edited_tables=all_edited_map,
                    all_tables=TableEditorHandler.cached_tables
                )

                export_path.write_text(final_markdown, encoding="utf-8")
                logger.info("✓ Đã xuất file Markdown cuối cùng: %s", export_path)

                self._send_json({
                    "status": "ok",
                    "saved_path": str(export_path),
                    "file_name": export_path.name,
                    "total_tables_edited": len(all_edited_map)
                })
            except Exception as e:
                logger.error("Lỗi export_final: %s", e)
                self._send_json({"status": "error", "error": str(e)}, status=500)
            return

        elif path == "/api/preview_full":
            try:
                raw_edited = payload.get("edited_tables", {})
                edited_tables = {int(k): v for k, v in raw_edited.items()}
                preview_markdown = reconstruct_full_document(
                    original_md_path=TableEditorHandler.active_file,
                    edited_tables=edited_tables,
                    all_tables=TableEditorHandler.cached_tables
                )
                self._send_json({"markdown": preview_markdown})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        elif path == "/api/reocr_table":
            try:
                import io, base64
                from PIL import Image
                import numpy as np

                table_id = int(payload.get("table_id", 1))
                block_id = payload.get("block_id", "")
                page_num = int(payload.get("page", 1))
                rotation = int(payload.get("rotation", 90)) % 360
                company = (payload.get("company") or TableEditorHandler.active_company).upper()
                year = int(payload.get("year") or TableEditorHandler.active_year)

                crop_file = PROJECT_ROOT / "outputs" / f"{company}_{year}" / "cache" / "table_crops" / f"{block_id}.png"
                if not crop_file.exists():
                    crop_file = PROJECT_ROOT / "data" / "cache" / "table_crops" / f"{company}_{year}" / f"{block_id}.png"
                if not crop_file.exists():
                    outputs_base = PROJECT_ROOT / "outputs"
                    if outputs_base.exists():
                        for cdir in outputs_base.glob(f"{company}_*/cache/table_crops"):
                            cand = cdir / f"{block_id}.png"
                            if cand.exists():
                                crop_file = cand
                                break
                if not crop_file.exists():
                    crops_base = PROJECT_ROOT / "data" / "cache" / "table_crops"
                    if crops_base.exists():
                        for cdir in crops_base.glob(f"{company}_*"):
                            cand = cdir / f"{block_id}.png"
                            if cand.exists():
                                crop_file = cand
                                break

                if not crop_file.exists():
                    self._send_json({"status": "error", "error": f"Không tìm thấy ảnh crop {block_id}.png"}, status=404)
                    return

                # 1. Đọc và xoay ảnh crop theo góc yêu cầu
                im = Image.open(crop_file)
                if rotation != 0:
                    im_rotated = im.rotate(360 - rotation, expand=True)
                    im_rotated.save(crop_file)
                    im = im_rotated

                # 2. Chạy OCR trên ảnh đã xoay thẳng đứng
                from src.parser.ocr_pipeline import VisionOCRPipeline
                pipe = VisionOCRPipeline()
                buf = io.BytesIO()
                im.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")

                raw_md = pipe._call_vision_api(b64)
                if not raw_md or ("|" not in raw_md and "<table" not in raw_md.lower()):
                    # Fallback sang RapidOCR nếu Vision API không trả về bảng
                    from rapidocr_onnxruntime import RapidOCR
                    rocr = RapidOCR()
                    res, _ = rocr(np.array(im))
                    raw_md = "\n".join([f"| {r[1]} |" for r in res]) if res else "| Trống |"

                # 3. Chuyển Markdown thành grid 2D
                if "<table" in raw_md.lower():
                    grid = html_to_grid(raw_md)
                else:
                    grid = pipe_to_grid(raw_md)

                # 4. Cập nhật vào TableEditorHandler.cached_tables
                target_tbl = next((t for t in TableEditorHandler.cached_tables if t.get("table_id") == table_id), None)
                if target_tbl:
                    target_tbl["rows"] = grid
                    target_tbl["raw_markdown"] = raw_md
                    target_tbl["n_rows"] = len(grid)
                    target_tbl["n_cols"] = len(grid[0]) if grid else 0
                    target_tbl["is_edited"] = True

                # 5. Cập nhật cache JSON trên đĩa để bền vững
                cache_dirs = [
                    PROJECT_ROOT / "outputs" / f"{company}_{year}" / "cache" / "notes",
                    PROJECT_ROOT / "outputs" / f"{company}_{year}" / "cache" / "ocr",
                    PROJECT_ROOT / "data" / "cache" / "notes" / f"{company}_{year}",
                    PROJECT_ROOT / "data" / "cache" / "ocr" / f"{company}_{year}",
                ]
                for cdir in cache_dirs:
                    if not cdir.exists(): continue
                    for json_f in cdir.glob(f"page_{page_num}.json"):
                        try:
                            jdata = json.loads(json_f.read_text(encoding="utf-8"))
                            for blk in jdata:
                                if blk.get("block_id") == block_id:
                                    blk["content"] = raw_md
                            json_f.write_text(json.dumps(jdata, ensure_ascii=False, indent=2), encoding="utf-8")
                            logger.info("Đã cập nhật bảng %s vào %s", block_id, json_f)
                        except Exception as ex:
                            logger.warning("Lỗi cập nhật cache file %s: %s", json_f, ex)

                self._send_json({
                    "status": "ok",
                    "rows": grid,
                    "raw_markdown": raw_md,
                    "n_rows": len(grid),
                    "n_cols": len(grid[0]) if grid else 0,
                    "rotation_applied": rotation
                })
            except Exception as e:
                logger.error("Lỗi reocr_table: %s", e)
                self._send_json({"status": "error", "error": str(e)}, status=500)
            return

        self.send_error(404, "Not Found")

    def _send_file(self, file_path: Path, mime_type: str) -> None:
        try:
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(file_path.stat().st_size))
            self.end_headers()
            self.wfile.write(file_path.read_bytes())
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def _send_json(self, data: Any, status: int = 200) -> None:
        try:
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def log_message(self, format: str, *args: Any) -> None:
        return


def run_editor_server(
    file_path: Path | None = None,
    company: str = "",
    year: int = 0,
    port: int = DEFAULT_PORT,
    auto_open: bool = True
) -> None:
    if file_path:
        target = file_path.resolve()
        TableEditorHandler.active_file = target
        parts = target.stem.split("_")
        if len(parts) >= 2 and parts[1].isdigit():
            TableEditorHandler.active_company = parts[0].upper()
            try:
                TableEditorHandler.active_year = int(parts[1])
            except ValueError:
                pass
    if company:
        TableEditorHandler.active_company = company.upper()
    if year > 0:
        TableEditorHandler.active_year = year

    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, TableEditorHandler)
    url = f"http://localhost:{port}"

    print("\n" + "=" * 70)
    print(" 🚀 FINADULT AI — MARKDOWN TABLE REVIEWER & EDITOR ĐANG CHẠY:")
    print(f" 👉 Mở trình duyệt tại: {url}")
    print(f" 🏢 Doanh nghiệp: {TableEditorHandler.active_company} ({TableEditorHandler.active_year})")
    print(" 📄 Chế độ: TRÍCH XUẤT 100% BẢNG BIỂU TỪ CACHE & ẢNH CROP GỐC")
    print(" ⌨️  Nhấn Ctrl + C để dừng server.")
    print("=" * 70 + "\n")

    if auto_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Đã dừng Markdown Table Editor Server.")
        httpd.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy Web Editor chỉnh sửa bảng biểu Markdown sau khi OCR")
    parser.add_argument("--file", "-f", type=Path, default=None, help="Đường dẫn file .md cần review/chỉnh sửa")
    parser.add_argument("--company", "-c", type=str, default="", help="Mã doanh nghiệp (VIC, VNM, HPG...)")
    parser.add_argument("--year", "-y", type=int, default=0, help="Năm tài chính (ví dụ 2025)")
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PORT, help="Cổng chạy server Web (mặc định 8502)")
    parser.add_argument("--no-browser", action="store_true", help="Không tự động mở trình duyệt")
    args = parser.parse_args()

    run_editor_server(
        file_path=args.file,
        company=args.company,
        year=args.year,
        port=args.port,
        auto_open=not args.no_browser
    )


if __name__ == "__main__":
    main()
