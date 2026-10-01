# Kế Hoạch OCR Post-Processing — Sau Phản Biện
*(MinerU TSR + VietOCR Raw Text — Hierarchical RAG, 0 Token LLM)*

---

## PHẢN BIỆN PLAN CŨ

### Lỗi 1 — Ontology nhầm vị trí các phần La Mã
**Plan cũ viết sai:** `V = Thông tin bổ sung Bảng CĐKT (30 mục)`, `VI = KQKD`, `VII = LCTT`, `VIII = Những thông tin khác`.

**Thực tế trong `TMBCTC`** (đã đọc từ file xlsx):
```
I   → Đặc điểm hoạt động
II  → Kỳ kế toán & đơn vị tiền tệ
III → Chuẩn mực & chế độ kế toán
IV  → Các chính sách kế toán (26 mục)
V   → Chính sách kế toán khi không đáp ứng hoạt động liên tục (mục dự phòng - ít DN)
VI  → Thông tin bổ sung Bảng CĐKT (30 mục: 01-30)   ← plan cũ ghi là "V"
VII → Thông tin bổ sung KQKD (11 mục: 1-11)          ← plan cũ ghi là "VI"
VIII→ Thông tin bổ sung LCTT (4 mục: 1-4)             ← plan cũ ghi là "VII"
IX  → Những thông tin khác (7 mục: 1-7)               ← plan cũ ghi là "VIII"
```
> ⚠️ File TT200 mẫu có **9 phần (I → IX)**, không phải 8 (I → VIII). `section_detector.py` hiện tại đang thiếu Phần V (hoạt động liên tục) và lệch toàn bộ từ Phần VI trở đi.

### Lỗi 2 — `MAX_NOTES_MAP` trong plan cũ vẫn sai sau khi "sửa"
Plan cũ đề xuất:
```python
MAX_NOTES_MAP_TT200 = {1: 7, 2: 2, 3: 2, 4: 26, 5: 30, 6: 11, 7: 4, 8: 7}
```
Nhưng theo phân tích ở trên, `5` là Phần V (hoạt động liên tục, 3 mục), **30 mục** thuộc Roman `6` (Phần VI). Map đúng:
```python
MAX_NOTES_MAP_TT200 = {1: 7, 2: 2, 3: 2, 4: 26, 5: 3, 6: 30, 7: 11, 8: 4, 9: 7}
```

### Lỗi 3 — Plan đề xuất hàm skeleton, không nói rõ nên thêm vào file nào
- Plan cũ viết 4 hàm trống (`def align_markdown_table_columns...`) nhưng không nói thêm vào `table_utils.py` hay `local_ocr.py` hay tạo file mới.
- `table_utils.py` đã có sẵn `clean_cell_value`, `parse_financial_number`, `detect_currency_unit`, `compute_numeric_density` — plan cũ không tái dụng, sẽ gây code trùng.

### Lỗi 4 — Regex H4 cho mục số có `?:\.0` không cần thiết & dễ false-positive
```python
# Plan cũ:
r"^(\d{1,2})(?:\.0|[\.\-\:\s])\s*(...)"
```
Pattern `\.0` được thêm vì "OCR đọc nhầm dấu chấm thành .0" — tuy nhiên `?.0` sẽ bắt nhầm `20.0 Doanh thu...` thành Thuyết minh mục `20` khi nó thực ra là số liệu trong bảng. Cần thêm điều kiện: phần title phải bắt đầu bằng ký tự chữ (không phải số).

### Lỗi 5 — Không đề cập việc MinerU v4 dùng Python API, không dùng CLI
Plan cũ và plan trước đó nói về `mineru server start` và CLI. Thực tế từ test trước đó:
- Lệnh `mineru.exe server start` không ổn định (server crash ngay sau khi start theo log).
- `MinerUParser` Python API trực tiếp (`from mineru.parser.mineru_parser import MinerUParser`) hoạt động tốt và không cần server.

### Lỗi 6 — Bỏ qua cặp phân tích quan trọng nhất: Gạch đầu dòng leaf node là `- Tiền mặt`
Trong `TMBCTC`, các mục con **không có chữ số và không có chữ cái** (ví dụ `- Tiền mặt`, `- Tiền gửi ngân hàng`) xuất hiện sau H4 và cần được gom vào Section H4 như **nội dung (body)**, không phải tạo Section H5 riêng. Plan cũ đề xuất `Gạch đầu dòng (Leaf) → Level H5` là sai — sẽ phá vỡ cây phân cấp và làm rác RAG.

---

## PLAN ĐÃ ĐƯỢC SỬA & HOÀN CHỈNH

---

### 1. Ontology Chuẩn TT200 — Sửa Lại Hoàn Toàn

```python
# src/parser/section_detector.py — Thay thế ROMAN_CANONICAL
ROMAN_CANONICAL = {
    "I":    ("NOTE_SEC_GENERAL_INFO",        "I. ĐẶC ĐIỂM HOẠT ĐỘNG CỦA DOANH NGHIỆP",                                    1),
    "II":   ("NOTE_SEC_ACCOUNTING_PERIOD",   "II. KỲ KẾ TOÁN VÀ ĐƠN VỊ TIỀN TỆ SỬ DỤNG TRONG KẾ TOÁN",                  2),
    "III":  ("NOTE_SEC_ACCOUNTING_STANDARDS","III. CHUẨN MỰC VÀ CHẾ ĐỘ KẾ TOÁN ÁP DỤNG",                                 3),
    "IV":   ("NOTE_SEC_ACCOUNTING_POLICIES", "IV. CÁC CHÍNH SÁCH KẾ TOÁN ÁP DỤNG",                                        4),
    "V":    ("NOTE_SEC_GOING_CONCERN",       "V. CÁC CHÍNH SÁCH KẾ TOÁN ÁP DỤNG (KHÔNG ĐÁP ỨNG HOẠT ĐỘNG LIÊN TỤC)",     5),
    "VI":   ("NOTE_SEC_BALANCE_SHEET",       "VI. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BẢNG CÂN ĐỐI KẾ TOÁN", 6),
    "VII":  ("NOTE_SEC_INCOME_STATEMENT",    "VII. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH", 7),
    "VIII": ("NOTE_SEC_CASH_FLOW",           "VIII. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BÁO CÁO LƯU CHUYỂN TIỀN TỆ",           8),
    "IX":   ("NOTE_SEC_OTHER_INFO",          "IX. NHỮNG THÔNG TIN KHÁC",                                                   9),
}

# Sửa lại max_notes_map trong _match_numbered_note:
MAX_NOTES_MAP_TT200 = {
    1: 7,   # I: 7 mục đặc điểm (hình thức sở hữu, lĩnh vực, ngành nghề...)
    2: 2,   # II: 2 mục (kỳ kế toán, đơn vị tiền tệ)
    3: 2,   # III: 2 mục (chế độ kế toán, chuẩn mực)
    4: 26,  # IV: 26 mục chính sách kế toán (nguyên tắc tiền, đầu tư, HTK...)
    5: 3,   # V: 3 mục (tái phân loại TS, xác định giá trị, xử lý tài chính)
    6: 30,  # VI: 30 mục bổ sung Bảng CĐKT (01. Tiền → 30. Thông tin khác)
    7: 11,  # VII: 11 mục bổ sung KQKD (doanh thu, giá vốn, chi phí...)
    8: 4,   # VIII: 4 mục bổ sung LCTT (giao dịch không bằng tiền...)
    9: 7,   # IX: 7 mục thông tin khác (nợ tiềm tàng, sự kiện sau BS, bên liên quan...)
}
```

### 2. Danh Mục Mục Thuyết Minh Chuẩn TT200 (Phục Vụ Canonical Lookup)

Thêm vào `section_detector.py` để lookup nhanh khi cần gán `canonical_code`:

```python
# Tra cứu nhanh tiêu đề Thuyết minh Phần VI (CĐKT): key = số mục
TT200_VI_BALANCE_SHEET_NOTES: dict[int, str] = {
    1: "Tiền",
    2: "Các khoản đầu tư tài chính",
    3: "Phải thu của khách hàng",
    4: "Phải thu khác",
    5: "Tài sản thiếu chờ xử lý",
    6: "Nợ xấu",
    7: "Hàng tồn kho",
    8: "Tài sản dở dang dài hạn",
    9: "Tăng, giảm tài sản cố định hữu hình",
    10: "Tăng, giảm tài sản cố định vô hình",
    11: "Tăng, giảm tài sản cố định thuê tài chính",
    12: "Tăng, giảm bất động sản đầu tư",
    13: "Chi phí trả trước",
    14: "Tài sản khác",
    15: "Vay và nợ thuê tài chính",
    16: "Phải trả người bán",
    17: "Thuế và các khoản phải nộp nhà nước",
    18: "Chi phí phải trả",
    19: "Phải trả khác",
    20: "Doanh thu chưa thực hiện",
    21: "Trái phiếu phát hành",
    22: "Cổ phiếu ưu đãi phân loại là nợ phải trả",
    23: "Dự phòng phải trả",
    24: "Tài sản và thuế thu nhập hoãn lại phải trả",
    25: "Vốn chủ sở hữu",
    26: "Chênh lệch đánh giá lại tài sản",
    27: "Chênh lệch tỷ giá",
    28: "Nguồn kinh phí",
    29: "Các khoản mục ngoài Bảng cân đối kế toán",
    30: "Các thông tin khác do doanh nghiệp tự thuyết minh",
}

# Tra cứu Phần VII (KQKD):
TT200_VII_INCOME_STATEMENT_NOTES: dict[int, str] = {
    1: "Tổng doanh thu bán hàng và cung cấp dịch vụ",
    2: "Các khoản giảm trừ doanh thu",
    3: "Giá vốn hàng bán",
    4: "Doanh thu hoạt động tài chính",
    5: "Chi phí tài chính",
    6: "Thu nhập khác",
    7: "Chi phí khác",
    8: "Chi phí bán hàng và chi phí quản lý doanh nghiệp",
    9: "Chi phí sản xuất kinh doanh theo yếu tố",
    10: "Chi phí thuế thu nhập doanh nghiệp hiện hành",
    11: "Chi phí thuế thu nhập doanh nghiệp hoãn lại",
}
```

### 3. Regex Nhận Diện Tiêu Đề — Sửa Lại Chính Xác

| Cấp | Quy chuẩn TT200 (ví dụ thực tế từ TMBCTC) | Regex chính xác |
| :--- | :--- | :--- |
| **H3 — Roman** | `I- Đặc điểm...`, `VI. Thông tin bổ sung...`, `VII - Thông tin...` | `r"^(IX|VIII|VII|VI|IV|V|III|II|I)[\.\-\:\s]+(.+)$"` |
| **H4 — Mục số** | `01. Tiền`, `7. Hàng tồn kho`, `25. Vốn chủ sở hữu` — **phần title PHẢI bắt đầu bằng chữ cái (không phải số)** | `r"^(\d{1,2})[\.\-\:\s]+([A-ZÀ-Ỹa-zà-ỹ][A-ZÀ-Ỹa-zà-ỹ0-9\s,–—\-\/]{2,90})$"` |
| **H5 — Tiểu mục chữ** | `a) Chứng khoán kinh doanh`, `(b) Đầu tư nắm giữ...` — chỉ a-z, không phải số | `r"^\(?([a-zđ])\)[\.\-\:\s]+([A-ZÀ-Ỹa-zà-ỹ][^;,\n]{2,100})$"` |
| **Body dòng gạch** | `- Tiền mặt`, `- Tiền gửi ngân hàng` — **KHÔNG tạo H5**, gom vào body của H4 | — (không tạo Section, giữ làm body text) |

> **Lưu ý quan trọng**: Dấu gạch đầu dòng (`- Tiền mặt`) là **body content** của Section H4 cha, không phải heading Level 5.

### 4. Bảng Xử Lý Bảng Biểu — Thêm Vào `table_utils.py`

4 hàm mới, tái dụng `clean_cell_value` và `parse_financial_number` đã có:

```python
# === Thêm vào cuối table_utils.py ===

def extract_embedded_heading_from_table(table_md: str) -> tuple[str | None, str]:
    """
    Kiểm tra dòng đầu tiên của Markdown table xem có phải Tiêu đề mục TM không.
    Ví dụ: '| 13. Chi phí trả trước | | |' → bóc tách thành heading "13. Chi phí trả trước".
    Returns: (heading_text | None, table_md_without_heading_row)
    Pattern: Hàng đầu có 1 cell chứa nội dung, các cell còn lại rỗng.
    """
    HEADING_IN_TABLE_RE = re.compile(
        r"^\|\s*(\d{1,2}[\.\-\:\s]+[A-ZÀ-Ỹa-zà-ỹ][^|]{2,80}?)\s*\|(?:\s*\|)*\s*$"
    )
    lines = table_md.strip().splitlines()
    if not lines:
        return None, table_md
    first = lines[0]
    m = HEADING_IN_TABLE_RE.match(first)
    if m:
        heading = m.group(1).strip()
        remaining = "\n".join(lines[1:]).strip()
        return heading, remaining
    return None, table_md


def align_markdown_table_columns(table_md: str) -> str:
    """
    Đồng nhất số lượng cột trong Markdown table.
    Đếm số cột tối đa N, đệm thêm '| ' vào các hàng thiếu cột.
    Không thay đổi hàng separator (hàng chứa '---').
    """
    lines = table_md.strip().splitlines()
    if not lines:
        return table_md
    col_counts = [line.count("|") - 1 for line in lines if "|" in line and "---" not in line]
    if not col_counts:
        return table_md
    max_cols = max(col_counts)
    fixed = []
    for line in lines:
        if "|" not in line:
            fixed.append(line)
            continue
        if "---" in line:
            # Sửa luôn dòng separator
            parts = [p.strip() for p in line.split("|") if p.strip() or True][1:-1]
            while len(parts) < max_cols:
                parts.append("---")
            fixed.append("| " + " | ".join(parts) + " |")
        else:
            count = line.count("|") - 1
            if count < max_cols:
                line = line.rstrip()
                if not line.endswith("|"):
                    line += " |"
                line += " |" * (max_cols - count)
            fixed.append(line)
    return "\n".join(fixed)


def stitch_multiline_headers(table_md: str) -> str:
    """
    Phát hiện và nối 2 dòng header liên tiếp không chứa số liệu (cả 2 đều numeric_density=0).
    Ví dụ:
      Hàng 1: | Khoản mục | Số cuối năm |  | Số đầu năm |  |
      Hàng 2: |            | Giá gốc | Khả dụng | Giá gốc | Khả dụng |
    →   Nối: | Khoản mục | Số cuối năm - Giá gốc | Số cuối năm - Khả dụng | Số đầu năm - Giá gốc | Số đầu năm - Khả dụng |
    """
    lines = table_md.strip().splitlines()
    if len(lines) < 3:
        return table_md
    # Kiểm tra 2 dòng đầu đều không có số liệu tài chính
    def has_numeric(line: str) -> bool:
        cells = [c.strip() for c in line.split("|")[1:-1]]
        return any(re.search(r"\d{2,}", c) for c in cells)
    if has_numeric(lines[0]) or has_numeric(lines[1]):
        return table_md
    # Nối cell-by-cell
    h1 = [c.strip() for c in lines[0].split("|")[1:-1]]
    h2 = [c.strip() for c in lines[1].split("|")[1:-1]]
    # Forward-fill h1 với merge cells
    filled_h1 = []
    last = ""
    for c in h1:
        if c:
            last = c
        filled_h1.append(last)
    merged = []
    for a, b in zip(filled_h1, h2):
        if a and b and a != b:
            merged.append(f"{a} - {b}")
        elif b:
            merged.append(b)
        else:
            merged.append(a)
    new_header = "| " + " | ".join(merged) + " |"
    return "\n".join([new_header] + lines[2:])


def clean_numeric_cells(table_md: str) -> str:
    """
    Chuẩn hóa từng ô số trong Markdown table:
    - Xóa khoảng trắng thừa bên trong số: '1 234 567' → '1.234.567'
    - Chuẩn hóa dấu gạch ngang đơn độc → '-'
    - Bảo toàn ngoặc đơn số âm: '( 15.420.000 )' → '(15.420.000)'
    """
    SPACE_IN_NUM_RE = re.compile(r"(?<=\d)\s+(?=\d)")
    PAREN_SPACE_RE = re.compile(r"\(\s*([\d.,]+)\s*\)")
    DASH_ONLY_RE = re.compile(r"^[\-\–—‐]+$")

    def clean_cell(cell: str) -> str:
        c = cell.strip()
        if DASH_ONLY_RE.match(c):
            return "-"
        c = PAREN_SPACE_RE.sub(r"(\1)", c)
        c = SPACE_IN_NUM_RE.sub("", c)
        return c

    fixed_lines = []
    for line in table_md.splitlines():
        if "|" not in line or "---" in line:
            fixed_lines.append(line)
            continue
        cells = line.split("|")
        cleaned = [clean_cell(c) if i > 0 and i < len(cells) - 1 else c for i, c in enumerate(cells)]
        fixed_lines.append("|".join(cleaned))
    return "\n".join(fixed_lines)
```

### 5. MinerU — Cách Gọi Đúng (Python API, Không Dùng Server/CLI)

```python
# src/parser/local_ocr.py — Sửa _extract_with_mineru_and_vietocr
from mineru.parser.mineru_parser import MinerUParser

def _extract_with_mineru(self, pdf_path: str, page_number: int) -> list[dict]:
    """
    Gọi MinerU Python API trực tiếp (không qua CLI hay server).
    Dùng tier='basic' để tắt MFR (Math Formula Recognition),
    tiết kiệm 30-40% thời gian mà không ảnh hưởng BCTC (không có công thức toán).
    """
    try:
        parser = MinerUParser(tier="basic", image_analysis=True)
        result = parser.parse(pdf_path, page_range=str(page_number))
        parser.close()
        return result.structured_content or []
    except Exception as e:
        logger.warning("MinerU parse lỗi trang %d: %s", page_number, e)
        return []
```

> **Lý do dùng `tier="basic"`**: Tier `flash` bỏ qua Table Recognition. Tier `standard`/`advanced` kích hoạt UniMERNet (MFR nặng). Chỉ `basic` là cân bằng: có TSR table + không có MFR.

---

### 6. Lộ Trình Triển Khai — Thứ Tự Ưu Tiên

| # | Công việc | File | Ghi chú |
| :---: | :--- | :--- | :--- |
| **1** | Sửa `ROMAN_CANONICAL` từ 8 → 9 phần (thêm `IX`) | [section_detector.py](../src/parser/section_detector.py#L33-L42) | Ảnh hưởng toàn bộ matching và breadcrumb |
| **2** | Sửa `max_notes_map` → `MAX_NOTES_MAP_TT200` chính xác | [section_detector.py](../src/parser/section_detector.py#L501) | Fix mục 25-30 đang bị bỏ sót |
| **3** | Thêm `TT200_VI_BALANCE_SHEET_NOTES` + `TT200_VII_INCOME_STATEMENT_NOTES` | [section_detector.py](../src/parser/section_detector.py) | Dùng để verify + gán `reference_code` chuẩn |
| **4** | Sửa Regex H4 — bỏ `?:\.0`, title phải bắt đầu chữ cái | [section_detector.py](../src/parser/section_detector.py#L446) | Tránh false-positive bắt số liệu trong bảng |
| **5** | Thêm 4 hàm postprocess table vào `table_utils.py` | [table_utils.py](../src/parser/table_utils.py) | Gióng cột, nối header, tách heading từ table |
| **6** | Sửa `_extract_with_mineru_and_vietocr` dùng Python API | [local_ocr.py](../src/parser/local_ocr.py#L282) | Bỏ CLI subprocess, dùng `MinerUParser(tier="basic")` |
| **7** | Viết test trên `vnm.pdf` (trang thuyết minh mẫu) | `tests/test_notes_ocr.py` | Nghiệm thu breadcrumb + bảng không vỡ |
