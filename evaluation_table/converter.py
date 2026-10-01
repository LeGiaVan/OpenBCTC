"""
converter.py — Công cụ chuẩn hóa định dạng bảng tài chính cho Table Structure Evaluation.

Hỗ trợ chuyển đổi qua lại giữa:
1. HTML Table (<table>...</table>) với rowspan, colspan
2. Markdown Table (| col1 | col2 |)
3. Table Schema chuẩn (n_rows, n_cols, spans, header_rows)
"""

from __future__ import annotations

import re
from typing import Any
from bs4 import BeautifulSoup, Tag


def html_to_schema(html_str: str) -> dict[str, Any]:
    """
    Phân tích chuỗi HTML table thành Table Schema logic.
    Tự động tính toán ma trận lưới 2D để xác định chính xác tọa độ các ô gộp (spans).
    
    Returns:
        dict chứa:
            - n_rows: Tổng số hàng logic
            - n_cols: Tổng số cột logic
            - spans: Danh sách [r_start, c_start, r_end, c_end] cho các ô có rowspan/colspan > 1
            - header_rows: Danh sách chỉ số hàng là header (0-indexed)
    """
    soup = BeautifulSoup(html_str, "html.parser")
    table = soup.find("table")
    if not table:
        raise ValueError("Không tìm thấy thẻ <table> trong chuỗi HTML cung cấp.")

    # Tìm tất cả thẻ tr (cả trong thead, tbody hoặc trực tiếp)
    rows = table.find_all("tr")
    if not rows:
        return {"n_rows": 0, "n_cols": 0, "spans": [], "header_rows": []}

    grid: dict[tuple[int, int], str] = {}
    spans: list[list[int]] = []
    header_rows: set[int] = set()

    for r_idx, tr in enumerate(rows):
        # Kiểm tra xem dòng này có nằm trong thead hoặc chứa th không
        is_th_row = bool(tr.find_all("th", recursive=False))
        is_in_thead = bool(tr.find_parent("thead"))
        if is_th_row or is_in_thead:
            header_rows.add(r_idx)

        c_idx = 0
        cells = tr.find_all(["th", "td"], recursive=False)
        for cell in cells:
            # Bỏ qua các tọa độ ô đã bị ô ở hàng trên kéo xuống chiếm chỗ (rowspan)
            while (r_idx, c_idx) in grid:
                c_idx += 1

            rowspan = int(cell.get("rowspan", 1))
            colspan = int(cell.get("colspan", 1))

            if rowspan > 1 or colspan > 1:
                spans.append([r_idx, c_idx, r_idx + rowspan - 1, c_idx + colspan - 1])

            cell_text = cell.get_text(strip=True)
            for dr in range(rowspan):
                for dc in range(colspan):
                    grid[(r_idx + dr, c_idx + dc)] = cell_text

            c_idx += colspan

    max_r = max((r for r, c in grid.keys()), default=-1) + 1
    max_c = max((c for r, c in grid.keys()), default=-1) + 1

    # Nếu không có thẻ th hay thead, mặc định dòng 0 là header nếu có dữ liệu
    if not header_rows and max_r > 0:
        header_rows.add(0)

    # Sắp xếp spans theo thứ tự đọc (hàng trước, cột sau)
    spans.sort(key=lambda s: (s[0], s[1]))

    return {
        "n_rows": max_r,
        "n_cols": max_c,
        "spans": spans,
        "header_rows": sorted(list(header_rows)),
    }


def markdown_to_schema(md_str: str) -> dict[str, Any]:
    """
    Phân tích chuỗi Markdown Table (GFM pipe table) thành Table Schema.
    Vì Markdown không hỗ trợ gộp ô nên spans luôn là [].
    """
    lines = [l.strip() for l in md_str.strip().splitlines() if l.strip()]
    table_lines: list[str] = []

    for line in lines:
        if line.startswith("|") and line.endswith("|"):
            table_lines.append(line)

    if not table_lines:
        return {"n_rows": 0, "n_cols": 0, "spans": [], "header_rows": []}

    rows_data: list[list[str]] = []
    header_rows = [0] if len(table_lines) >= 2 else []

    for idx, line in enumerate(table_lines):
        # Bỏ qua dòng phân cách |---|---|
        inner = line.strip("|")
        cells = [c.strip() for c in inner.split("|")]
        if all(re.match(r"^:?-+:?$", c) for c in cells if c):
            continue
        rows_data.append(cells)

    n_rows = len(rows_data)
    n_cols = max((len(r) for r in rows_data), default=0)

    return {
        "n_rows": n_rows,
        "n_cols": n_cols,
        "spans": [],
        "header_rows": header_rows if n_rows > 0 else [],
    }


def schema_to_html(schema: dict[str, Any]) -> str:
    """
    Chuyển đổi Table Schema thành mã HTML tối giản để phục vụ tính TEDS-Struct.
    """
    n_rows = schema.get("n_rows", 0)
    n_cols = schema.get("n_cols", 0)
    spans = schema.get("spans", [])
    header_rows = set(schema.get("header_rows", []))

    if n_rows == 0 or n_cols == 0:
        return "<table></table>"

    # Map tọa độ bắt đầu của mỗi span
    span_map: dict[tuple[int, int], tuple[int, int]] = {}
    covered: set[tuple[int, int]] = set()

    for s in spans:
        r1, c1, r2, c2 = s
        span_map[(r1, c1)] = (r2 - r1 + 1, c2 - c1 + 1)
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                if (r, c) != (r1, c1):
                    covered.add((r, c))

    html_parts = ["<table>"]
    for r in range(n_rows):
        html_parts.append("<tr>")
        tag = "th" if r in header_rows else "td"
        for c in range(n_cols):
            if (r, c) in covered:
                continue
            if (r, c) in span_map:
                rowspan, colspan = span_map[(r, c)]
                attrs = []
                if rowspan > 1:
                    attrs.append(f'rowspan="{rowspan}"')
                if colspan > 1:
                    attrs.append(f'colspan="{colspan}"')
                attr_str = f" {' '.join(attrs)}" if attrs else ""
                html_parts.append(f"<{tag}{attr_str}></{tag}>")
            else:
                html_parts.append(f"<{tag}></{tag}>")
        html_parts.append("</tr>")
    html_parts.append("</table>")

    return "".join(html_parts)


def auto_to_schema(content: str | dict[str, Any]) -> dict[str, Any]:
    """
    Tự động nhận diện định dạng đầu vào (dict schema, chuỗi HTML hoặc chuỗi Markdown)
    và chuẩn hóa về Table Schema thống nhất.
    """
    if isinstance(content, dict):
        required = ("n_rows", "n_cols", "spans")
        if all(k in content for k in required):
            return {
                "n_rows": int(content["n_rows"]),
                "n_cols": int(content["n_cols"]),
                "spans": [list(map(int, s)) for s in content.get("spans", [])],
                "header_rows": list(map(int, content.get("header_rows", []))),
            }
        if "html" in content and content["html"]:
            return html_to_schema(str(content["html"]))
        if "markdown" in content and content["markdown"]:
            return markdown_to_schema(str(content["markdown"]))
        if "content" in content and content["content"]:
            return auto_to_schema(str(content["content"]))
        raise ValueError(f"Dict không đúng định dạng table_schema: {content}")

    text = str(content).strip()
    if "<table" in text.lower():
        return html_to_schema(text)
    if "|" in text and ("---" in text or text.startswith("|")):
        return markdown_to_schema(text)

    # Thử parse HTML trước, nếu lỗi thì thử Markdown
    try:
        return html_to_schema(text)
    except Exception:
        return markdown_to_schema(text)
