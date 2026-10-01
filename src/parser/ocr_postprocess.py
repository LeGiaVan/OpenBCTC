"""
ocr_postprocess.py — Tầng hậu xử lý làm sạch số liệu và kiểm tra tính hợp lệ (Validation Layer).
Đây là bước cực kỳ quan trọng đối với tài liệu tài chính OCR:
- Sửa lỗi nhầm `0` ↔ `O`/`o` trong ngữ cảnh số liệu
- Sửa lỗi nhầm `1` ↔ `l`/`I`/`|`
- Chuẩn hóa số âm ngoặc đơn `(1,234)` -> `-1234.0`
- Chuẩn hóa dấu phân cách nghìn/thập phân kiểu Việt Nam và quốc tế
- Kiểm tra tính hợp lệ số học (Validation: tổng cột/dòng, kiểm tra tài sản/doanh thu âm)
"""

import logging
import re

logger = logging.getLogger(__name__)

# Pattern nhận diện số âm ngoặc đơn: (1,234), ( 1.234.567 ), (50.5)
_PAREN_NUM_RE = re.compile(r"^\s*\(\s*([^\)]+)\s*\)\s*$")

# Từ điển sửa lỗi OCR text tiếng Việt tài chính & kế toán phổ biến (Thông tư 200 / VAS)
# Issue #7: Tách thành 2 phần: _BASE_OCR_TEXT_FIXES (domain-agnostic chung) và
# _DOMAIN_OCR_TEXT_FIXES (cụ thể theo ngành/công ty). Dùng extend_ocr_text_fixes() để thêm custom.
_BASE_OCR_TEXT_FIXES: list[tuple[str, str]] = [
    (r"\bThong tur\b", "Thông tư"),
    (r"\bthong tu\b", "Thông tư"),
    (r"\bChedo\b", "Chế độ"),
    (r"\bKetoan\b", "Kế toán"),
    (r"\bbio ctiotai\b", "báo cáo tài"),
    (r"\bs0\b", "số"),
    (r"\bB6 Tai chinh\b", "Bộ Tài chính"),
    (r"\bBa Tai chinh\b", "Bộ Tài chính"),
    (r"\bBộ Tài chinh\b", "Bộ Tài chính"),
    (r"\bKiem TOAN\b", "Kiểm toán"),
    (r"\bDQC LAp\b", "Độc lập"),
    (r"\bkinh givi\b", "Kính gửi"),
    (r"\bthuyc\b", "thực"),
    (r"\bthyrc\b", "thực"),
    (r"\btrung thuyc\b", "trung thực"),
    (r"\bduroc\b", "được"),
    (r"\bdurgc\b", "được"),
    (r"\bdiurc\b", "được"),
    (r"\bluru\b", "lưu"),
    (r"\bChuan myc\b", "Chuẩn mực"),
    (r"\bchirng\b", "chứng"),
    (r"\bchju\b", "chịu"),
    (r"\btai cbinh\b", "tài chính"),
    (r"\btal chinh\b", "tài chính"),
    # Kế toán Thuyết minh & Báo cáo tài chính (TT 200)
    (r"\bVôn\b", "Vốn"),
    (r"\bvon\b", "vốn"),
    (r"\bThặng du vối\b", "Thặng dư vốn"),
    (r"\bThặng du vốn\b", "Thặng dư vốn"),
    (r"\bThang du von\b", "Thặng dư vốn"),
    (r"\bQuỹ dầu tư\b", "Quỹ đầu tư"),
    (r"\bQuy dau tu\b", "Quỹ đầu tư"),
    (r"\bCổ túc\b", "Cổ tức"),
    (r"\bco tuc\b", "Cổ tức"),
    (r"\bLoi nhuận\b", "Lợi nhuận"),
    (r"\bloi nhuan\b", "Lợi nhuận"),
    (r"\bYND\b", "VND"),
    (r"\bháo cáo\b", "báo cáo"),
    (r"\(+\s*1\s*huyết minh\b", "(Thuyết minh"),
    (r"\b1\s*huyết minh\b", "(Thuyết minh"),
    (r"\bhuyết minh\b", "Thuyết minh"),
    (r"\bchu so hua\b", "chủ sở hữu"),
    (r"\bvon chu so hua\b", "vốn chủ sở hữu"),
    (r"\bvon chu so huu\b", "vốn chủ sở hữu"),
    (r"\bphúc lại\b", "phúc lợi"),
    (r"\bphuc loi\b", "phúc lợi"),
    (r"\bkhen thuong\b", "khen thưởng"),
    (r"\bTrich quy thuoc\b", "Trích quỹ thuộc"),
    (r"\btrich quy thuoc\b", "trích quỹ thuộc"),
    (r"\bTrích quy\b", "Trích quỹ"),
    (r"\btrich quy\b", "trích quỹ"),
    (r"\bHoan nhap\b", "Hoàn nhập"),
    (r"\bhoan nhap\b", "hoàn nhập"),
    (r"\bchua phan phoi\b", "chưa phân phối"),
    (r"\bphat trien\b", "phát triển"),
    (r"\bSo du tai ngay\b", "Số dư tại ngày"),
    (r"\bSố du tại ngày\b", "Số dư tại ngày"),
    (r"\bBan hanh\b", "Ban hành"),
    (r"\bban hanh\b", "ban hành"),
    (r"\bkết tháng\b", "kết thúc ngày"),
    (r"\bMẫu B 19\b", "Mẫu B 09"),
    (r"\(\(+", "("),
    (r"\)\)+", ")"),
]

# Issue #7: Pattern theo domain/ngành cụ thể — tách riêng để dễ bật/tắt
# Các pattern này chủ yếu cho ngành thực phẩm/sữa (VNM, TH True Milk...)
_DOMAIN_OCR_TEXT_FIXES: list[tuple[str, str]] = [
    (r"\bS[it]ra\b", "Sữa"),
    (r"\bS[it]a\b", "Sữa"),
    (r"\bBuong\b", "Đường"),
]

# Active list — được dùng khi gọi clean_ocr_text_line()
_COMMON_OCR_TEXT_FIXES: list[tuple[str, str]] = _BASE_OCR_TEXT_FIXES + _DOMAIN_OCR_TEXT_FIXES


def extend_ocr_text_fixes(extra_patterns: list[tuple[str, str]]) -> None:
    """
    Mở rộng danh sách pattern fix OCR bằng các pattern tùy chỉnh theo domain/công ty.

    Issue #7 fix: Thay vì hardcode toàn bộ trong module, caller có thể cung cấp
    thêm patterns sau khi biết công ty/ngành đang xử lý. Pattern mới sẽ được
    thêm vào cuối danh sách active và áp dụng ngay cho mọi lần gọi clean_ocr_text_line() tiếp theo.

    Example:
        from src.parser.ocr_postprocess import extend_ocr_text_fixes
        # Thêm fix cho ngành ngân hàng
        extend_ocr_text_fixes([
            (r"\\bNo xau\\b", "Nợ xấu"),
            (r"\\btai khoan\\b", "tài khoản"),
        ])
    """
    global _COMMON_OCR_TEXT_FIXES  # noqa: PLW0603
    _COMMON_OCR_TEXT_FIXES = _COMMON_OCR_TEXT_FIXES + extra_patterns
    logger.debug("extend_ocr_text_fixes: Đã thêm %d patterns mới. Tổng: %d", len(extra_patterns), len(_COMMON_OCR_TEXT_FIXES))


def reset_ocr_text_fixes() -> None:
    """Restore danh sách OCR pattern về mặc định ban đầu (base + domain)."""
    global _COMMON_OCR_TEXT_FIXES  # noqa: PLW0603
    _COMMON_OCR_TEXT_FIXES = _BASE_OCR_TEXT_FIXES + _DOMAIN_OCR_TEXT_FIXES
    logger.debug("reset_ocr_text_fixes: Đã reset về %d patterns mặc định.", len(_COMMON_OCR_TEXT_FIXES))



def clean_ocr_number(text: str) -> float | None:
    """
    Làm sạch chuỗi số sau OCR và chuyển thành số thực float.

    Các bước sửa lỗi:
      1. Bóc tách số âm ngoặc đơn: `(1,234)` -> flag is_negative = True
      2. Sửa lỗi nhầm ký tự: `O`/`o` -> `0`, `l`/`I`/`|` -> `1`
      3. Bỏ khoảng trắng bên trong số (ví dụ: `1 234 567`)
      4. Loại bỏ các ký tự rác không thuộc định dạng số
      5. Chuẩn hóa dấu chấm/phẩy theo quy chuẩn tài chính

    Args:
        text: Chuỗi văn bản từ ô bảng hoặc text OCR

    Returns:
        float | None: Giá trị số chuẩn hóa (kèm dấu âm nếu có), hoặc None nếu không phải số
    """
    if text is None:
        return None
    cleaned = str(text).strip()
    # Chuẩn hóa ngoặc đơn full-width UTF-8 từ ảnh OCR scan
    cleaned = cleaned.replace("（", "(").replace("）", ")").replace("【", "[").replace("】", "]")
    if not cleaned or cleaned in ("-", "—", "–", "‐"):
        return 0.0 if cleaned in ("-", "—", "–", "‐") else None

    # 1. Phát hiện số âm ngoặc đơn
    is_negative = False
    paren_match = _PAREN_NUM_RE.match(cleaned)
    if paren_match:
        is_negative = True
        cleaned = paren_match.group(1).strip()
    elif cleaned.startswith("-"):
        is_negative = True
        cleaned = cleaned[1:].strip()

    # Bỏ qua ngay nếu chứa các chữ cái thông thường (không phải các ký tự nhầm lẫn số như o/O, l/I)
    if re.search(r"[a-km-np-zA-HJ-NP-Z\u00C0-\u1EF9]", cleaned):
        return None

    # 2. Sửa lỗi OCR ký tự phổ biến (O -> 0, l/I -> 1) trong ngữ cảnh số
    cleaned = cleaned.replace("O", "0").replace("o", "0")
    cleaned = cleaned.replace("l", "1").replace("I", "1").replace("|", "1")
    cleaned = cleaned.replace(" ", "")

    # Loại bỏ ký tự rác chỉ giữ số, dấu chấm, dấu phẩy, dấu trừ
    cleaned = re.sub(r"[^\d,.-]", "", cleaned)
    if not cleaned:
        return None

    # 3. Chuẩn hóa dấu phân cách
    dot_count = cleaned.count(".")
    comma_count = cleaned.count(",")

    try:
        if dot_count > 0 and comma_count > 0:
            last_dot = cleaned.rfind(".")
            last_comma = cleaned.rfind(",")
            if last_comma > last_dot:
                # Dạng VN: 1.234.567,89
                std_num = cleaned.replace(".", "").replace(",", ".")
            else:
                # Dạng EN: 1,234,567.89
                std_num = cleaned.replace(",", "")
        elif dot_count > 1:
            # Nhiều dấu chấm -> phân cách nghìn: 1.234.567
            std_num = cleaned.replace(".", "")
        elif comma_count > 1:
            # Nhiều dấu phẩy -> phân cách nghìn: 1,234,567
            std_num = cleaned.replace(",", "")
        elif dot_count == 1:
            parts = cleaned.split(".")
            # Nếu phần sau dấu chấm có 3 chữ số -> phân cách nghìn (trừ số bắt đầu '0.')
            if len(parts[1]) == 3 and not cleaned.startswith("0."):
                std_num = cleaned.replace(".", "")
            else:
                std_num = cleaned
        elif comma_count == 1:
            parts = cleaned.split(",")
            if len(parts[1]) == 3 and not cleaned.startswith("0,"):
                std_num = cleaned.replace(",", "")
            else:
                std_num = cleaned.replace(",", ".")
        else:
            std_num = cleaned

        val = float(std_num)
        return -abs(val) if is_negative else abs(val)
    except ValueError:
        return None


def clean_ocr_text_line(text: str) -> str:
    """Làm sạch và chỉnh sửa các lỗi OCR từ vựng tiếng Việt thường gặp."""
    if not text:
        return ""
    result = text.strip()
    for pattern, replacement in _COMMON_OCR_TEXT_FIXES:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    # Chuẩn hóa khoảng trắng
    result = re.sub(r"\s{2,}", " ", result)
    return result.strip()


def filter_noise_and_images(text: str) -> str:
    """Lọc bỏ toàn bộ nhiễu thị giác: con dấu (seal), hình ảnh nhúng base64, thẻ details XML/HTML."""
    if not text:
        return ""
    # 1. Khử các khối con dấu dạng <details><summary>seal</summary>...</details>
    cleaned = re.sub(r"<details>\s*<summary>\s*seal\s*</summary>.*?</details>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # 2. Khử các thẻ details/summary còn sót lại
    cleaned = re.sub(r"</?details>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</?summary[^>]*>", "", cleaned, flags=re.IGNORECASE)
    # 3. Khử ảnh Markdown nhúng base64: ![](data:image/...)
    cleaned = re.sub(r"!\[.*?\]\(data:image\/[^)]+\)", "", cleaned)
    # 4. Khử các ảnh Markdown thông thường: ![](...)
    cleaned = re.sub(r"!\[.*?\]\([^\)]+\)", "", cleaned)
    # 5. Khử các dòng chứa chuỗi base64 dài hoặc đường dẫn ảnh đơn độc
    filtered_lines = []
    for line in cleaned.splitlines():
        l_trim = line.strip()
        if not l_trim:
            continue
        if "data:image/" in l_trim or (len(l_trim) > 80 and re.match(r"^[A-Za-z0-9+/=]{60,}$", l_trim)):
            continue
        if l_trim.lower() in ("seal", "t.n.h.h", "liminh", "m.s.d.n:"):
            continue
        filtered_lines.append(line)
    return "\n".join(filtered_lines).strip()


def clean_accounting_text(text: str) -> str:
    """Làm sạch và chỉnh sửa các lỗi OCR từ vựng tiếng Việt kế toán (Thông tư 200) và lọc nhiễu."""
    cleaned = filter_noise_and_images(text)
    return clean_ocr_text_line(cleaned)


# Các mẫu regex nhận diện rác hành chính lặp lại (Boilerplate Header/Footer/Page numbers)
_BOILERPLATE_PATTERNS = [
    # Tiêu đề biểu mẫu & Thông tư (Mẫu B 09-DN, Mẫu B 01 – DN, Bo9 DN, B (9 DN, Thông tư 200...)
    re.compile(r"^(\*{0,2})M[ẫãa]u\s*B\s*[\(\[oO0-9\-\–\—\?\s]+\s*DN.*(\*{0,2})$", re.IGNORECASE),
    re.compile(r"^(\*{0,2})\(?Ban\s*h[àa]nh\s*(?:theo|then)\s*Th[oô]ng.*$", re.IGNORECASE),
    re.compile(r"^.*(?:200/2014/TT|200\s*/\s*2014|TT-B[IT]C).*$", re.IGNORECASE),
    re.compile(r"^.*(?:ng[àayuoô]+)\s*\d{1,2}\s*th[áaung]+\s*\d{1,2}\s*n[ăa]m\s*\d{4}.*B[ộo]\s*T[àa]i\s*ch[íi]nh.*$", re.IGNORECASE),
    re.compile(r"^.*B[ộo]\s*T[àa]i\s*ch[íi]nh\)?$", re.IGNORECASE),
    re.compile(r"^\(?M[ẫa]u\s*(?:s[ốo]\s*)?B\s*[0-9]{1,2}.*$", re.IGNORECASE),
    # Tiêu đề công ty lặp lại ở các trang tiếp theo (Cũng ty, Công ty Cổ/Cố/Cô phần...)
    re.compile(r"^(\*{0,2})(?:C[ôốồổoó]ng|C[ũu]ng)\s*ty\s*C[ổoóôốồơớợ]?[ -]?ph[ầaâ]n\s*S[ữửuraúùụũ]+[ -]?Vi[ệeê]t\s*Nam.*(\*{0,2})$", re.IGNORECASE),
    re.compile(r"^(\*{0,2})CONG\s*TY\s*CO\s*PHAN\s*SUA\s*VIET\s*NAM.*(\*{0,2})$", re.IGNORECASE),
    # Tiêu đề báo cáo lặp lại ở các trang thuyết minh tiếp theo
    re.compile(r"^(\*{0,2})Thuy[ếeê]t\s*minh\s*b[áa]o\s*c[áa][no]\s*[tl][àaá]+i?\s*ch[íi][no][bh]?.*$", re.IGNORECASE),
    re.compile(r"^(\*{0,2})Báo cáo tình hình tài chính riêng.*\(tiếp the[ou]\)(\*{0,2})$", re.IGNORECASE),
    re.compile(r"^(\*{0,2})Báo cáo lưu chuyển tiền tệ.*\(tiếp the[ou]\)(\*{0,2})$", re.IGNORECASE),
    re.compile(r"^(\*{0,2})Báo cáo kết quả hoạt động kinh doanh.*\(tiếp the[ou]\)(\*{0,2})$", re.IGNORECASE),
    re.compile(r"^\(?tiếp the[ou]\)?$", re.IGNORECASE),
    re.compile(r"^\(Phương pháp gián tiếp\s*-\s*tiếp the[ou]\)$", re.IGNORECASE),
    # Chú thích chân trang lặp lại
    re.compile(r"^\*?C[áa]c\s*thuy[ếe]t\s*minh\s*(?:n[àa]y|đ[íi]nh\s*k[èe]m|t[ừu]\s*trang).*l[àa]\s*b[ộo]\s*ph[ậa]n\s*h[ợo]p\s*th[àa]nh.*\*?$", re.IGNORECASE),
    re.compile(r"^k[èe]m\.?$", re.IGNORECASE),
    # Số trang đơn độc đứng một dòng (ví dụ: "7", "11", "12", "41")
    re.compile(r"^\s*\d{1,2}\s*$"),
    # Chuỗi số mã vạch / rác scan biên lề
    re.compile(r"^[0-9]{8,}$"),
    # Nhiễu lặp âm tiết OCR (hallucination chuỗi từ giống nhau)
    re.compile(r"^.*(\b\w+\b)(?:\s+\1){3,}.*$", re.IGNORECASE),
]


def strip_boilerplate_lines(text: str) -> str:
    """Lọc bỏ các dòng rác hành chính lặp lại (Boilerplate Header/Footer/Page numbers & OCR repetition noise) và con dấu/ảnh."""
    if not text:
        return ""
    # Trước tiên lọc các khối con dấu và ảnh nhúng
    text = filter_noise_and_images(text)
    cleaned_lines = []
    for line in text.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        # Bóc tiền tố markdown (#, *, -, >) để kiểm tra khớp boilerplate chính xác
        trimmed_unmd = re.sub(r"^[#*>\-\s]+", "", trimmed).strip()
        if any(pat.match(trimmed) or (trimmed_unmd and pat.match(trimmed_unmd)) for pat in _BOILERPLATE_PATTERNS):
            continue
        # Lọc các dòng nhiễu OCR có tỷ lệ lặp từ bất thường (>= 6 từ nhưng <= 30% từ độc nhất)
        tokens = [w for w in re.split(r"\s+", trimmed) if w]
        if len(tokens) >= 6 and (len(set(w.lower() for w in tokens)) / len(tokens)) <= 0.3:
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def validate_ocr_table(
    table_rows: list[list[str]],
    expected_total: float | None = None,
    value_col_indices: list[int] | None = None,
) -> dict:
    """
    Kiểm tra tính hợp lệ số học của bảng OCR:
      1. Kiểm tra tổng số cột có khớp với tổng mong đợi không (sai số < 1%).
      2. Cảnh báo các chỉ tiêu không thể âm (Tổng tài sản, Doanh thu thuần).

    Issue #3 fix:
      - Kiểm tra tất cả các cột số (kỳ này VÀ kỳ trước) thay vì chỉ cột cuối
      - value_col_indices: chỉ định cột nào chứa số tiền (None = tất cả cột từ 1 trở đi)
      - expected_total có thể được truyền vào từ caller (trước đây luôn là None)

    Returns:
        dict: {"issues": list[str], "is_valid": bool, "numeric_count": int}
    """
    issues: list[str] = []
    numeric_values: list[float] = []

    for row_idx, row in enumerate(table_rows):
        if not row:
            continue
        row_str = " ".join(row).lower()

        # Issue #3: Xác định các cột cần kiểm tra
        # Nếu không chỉ định → kiểm tra tất cả cột trừ cột đầu (thường là label)
        if value_col_indices is not None:
            cols_to_check = [row[idx] for idx in value_col_indices if idx < len(row)]
        elif len(row) > 1:
            cols_to_check = row[1:]  # Bỏ cột đầu (label), kiểm tra tất cả cột số
        else:
            cols_to_check = row  # Chỉ có 1 cột → kiểm tra luôn

        row_has_negative_warning = False
        for cell in cols_to_check:
            num = clean_ocr_number(cell)
            if num is not None:
                numeric_values.append(num)

                # Cảnh báo chỉ tiêu âm bất thường (chỉ cảnh báo 1 lần mỗi dòng)
                if not row_has_negative_warning and any(
                    kw in row_str for kw in ["tổng cộng tài sản", "tong tai san", "doanh thu thuần", "revenue"]
                ):
                    if num < 0:
                        issues.append(f"Dòng {row_idx + 1} ({row[0]}): Chỉ tiêu âm bất thường ({num})")
                        row_has_negative_warning = True

    if expected_total is not None and expected_total != 0.0:
        calculated = sum(numeric_values)
        if abs(calculated - expected_total) > 0.01 * abs(expected_total):
            issues.append(
                f"Tổng số không khớp: Tính được {calculated:,.0f} vs Mong đợi {expected_total:,.0f}"
            )

    is_valid = len(issues) == 0
    return {
        "issues": issues,
        "is_valid": is_valid,
        "numeric_count": len(numeric_values),
    }
