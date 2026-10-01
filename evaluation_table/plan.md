Được, tập trung toàn bộ vào đánh giá **Table Structure** — đây là framework chấm điểm riêng cho tầng này, chi tiết và có thể chạy độc lập.

## Mục tiêu của framework

Đo xem MinerU (hoặc bất kỳ model table structure nào bạn dùng) có tái tạo đúng **hình dạng logic của bảng** hay không — bao nhiêu hàng, bao nhiêu cột, ô nào gộp với ô nào — **hoàn toàn tách biệt khỏi việc nội dung trong ô đọc đúng hay sai**. Đây là bài toán cấu trúc thuần túy.

---

## Bước 1 — Chuẩn hóa định dạng biểu diễn bảng

Trước khi so sánh, cần một format thống nhất để biểu diễn "cấu trúc bảng" — dùng dạng **ma trận ô + danh sách vùng gộp (span)**:

```python
table_schema = {
    "n_rows": 8,
    "n_cols": 5,
    "spans": [
        # (row_start, col_start, row_end, col_end) — vùng bị gộp (merged cell)
        (0, 3, 0, 4),   # header "Năm nay" gộp 2 cột con
        (0, 5, 0, 6),   # header "Năm trước" gộp 2 cột con
    ],
    "header_rows": [0, 1],   # dòng nào là header (có thể nhiều tầng)
}
```

Cả **ground truth** (bạn tự gán nhãn tay) và **prediction** (MinerU trả ra) đều phải được chuẩn hóa về đúng format này trước khi so sánh.

---

## Bước 2 — Chuẩn bị test set (ground truth)

Chọn mẫu đại diện đủ các dạng bảng tài chính thường gặp, không chọn ngẫu nhiên — vì mỗi dạng có nguy cơ lỗi khác nhau:

| Nhóm bảng | Số lượng | Đặc điểm cần test |
|---|---|---|
| Bảng đơn giản (1 tầng header) | 10 | Baseline dễ, kỳ vọng score gần như tuyệt đối |
| Bảng có header 2 tầng ("Năm nay"/"Năm trước" gộp cột con) | 10-15 | Hay bị sai spans nhất |
| Bảng có dòng "Cộng/Tổng cộng" kẻ khung đậm khác | 10 | Dễ bị tách nhầm thành 2 bảng |
| Bảng bị ngắt trang (1 bảng trải dài 2 trang PDF) | 5-10 | MinerU có xu hướng coi là 2 bảng riêng |
| Bảng có ô trống/gạch ngang "-" thay vì số | 5-10 | Dễ bị hiểu nhầm cấu trúc do thiếu nội dung neo |

Tổng ~40-55 bảng là đủ để có bộ test đáng tin cậy cho mục đích đánh giá nội bộ.

**Công cụ gán nhãn**: dùng Label Studio (có template sẵn cho table annotation) hoặc đơn giản hơn — mở file HTML/Excel gốc của báo cáo (nếu có bản HTML/Excel song song với PDF) để lấy chính xác cấu trúc, nhanh hơn nhiều so với tự đếm ô bằng mắt trên ảnh scan.

---

## Bước 3 — Các metric đo

### 3.1. Row/Column Count Accuracy (thô, dễ tính, làm trước tiên)

```python
def count_accuracy(pred, gt):
    row_match = pred["n_rows"] == gt["n_rows"]
    col_match = pred["n_cols"] == gt["n_cols"]
    row_diff = abs(pred["n_rows"] - gt["n_rows"])
    col_diff = abs(pred["n_cols"] - gt["n_cols"])
    return {
        "row_exact_match": row_match,
        "col_exact_match": col_match,
        "row_diff": row_diff,
        "col_diff": col_diff
    }
```

Đây là bộ lọc nhanh đầu tiên: nếu số hàng/cột đã sai thì không cần đo sâu hơn nữa, bảng đó coi như hỏng cấu trúc rồi.

### 3.2. Span (merged cell) IoU

```python
def span_iou(pred_spans, gt_spans):
    """So khớp từng vùng gộp — vùng nào trong pred có match với gt không"""
    def area(span):
        r1, c1, r2, c2 = span
        return (r2 - r1 + 1) * (c2 - c1 + 1)
    
    def overlap(s1, s2):
        r1 = max(s1[0], s2[0]); c1 = max(s1[1], s2[1])
        r2 = min(s1[2], s2[2]); c2 = min(s1[3], s2[3])
        if r1 > r2 or c1 > c2:
            return 0
        return (r2 - r1 + 1) * (c2 - c1 + 1)
    
    matched_gt = set()
    tp = 0
    for p in pred_spans:
        for i, g in enumerate(gt_spans):
            if i in matched_gt:
                continue
            inter = overlap(p, g)
            union = area(p) + area(g) - inter
            if union > 0 and inter / union >= 0.5:
                tp += 1
                matched_gt.add(i)
                break
    
    precision = tp / len(pred_spans) if pred_spans else 1.0
    recall = tp / len(gt_spans) if gt_spans else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    return {"precision": precision, "recall": recall, "f1": f1}
```

Metric này quan trọng riêng cho lỗi header 2 tầng — nếu `recall` thấp nghĩa là model bỏ sót các vùng gộp thật (coi bảng có header phẳng trong khi thực tế header 2 tầng), nếu `precision` thấp nghĩa là model "bịa" ra vùng gộp không có thật.

### 3.3. TEDS-Struct (Tree Edit Distance — chỉ tính cấu trúc, bỏ qua nội dung)

Đây là metric chuẩn academic cho table structure recognition, cho điểm tổng hợp đáng tin cậy hơn 2 metric thô ở trên vì nó phạt đúng mức độ nghiêm trọng của từng loại lỗi (lệch 1 ô nhẹ hơn nhiều so với lệch cả cấu trúc bảng):

```bash
pip install teds  # hoặc dùng package table-recognition-metric
```

```python
from teds import TEDS

teds_scorer = TEDS(structure_only=True)  # QUAN TRỌNG: bật structure_only để bỏ qua nội dung ô

def compute_teds_struct(pred_html, gt_html):
    """
    pred_html, gt_html: bảng dạng HTML <table>...</table>
    (nếu nội dung ô khác nhau không sao — structure_only=True sẽ bỏ qua phần text trong <td>)
    """
    score = teds_scorer.evaluate(pred_html, gt_html)
    return score  # 0.0 - 1.0, càng cao càng tốt
```

Nếu bạn chưa có bảng dưới dạng HTML, cần viết hàm chuyển từ `table_schema` (ma trận + spans) sang HTML tối giản chỉ để phục vụ tính TEDS:

```python
def schema_to_html(schema):
    html = "<table>"
    covered = set()  # đánh dấu ô đã bị 1 span khác chiếm
    for r in range(schema["n_rows"]):
        html += "<tr>"
        for c in range(schema["n_cols"]):
            if (r, c) in covered:
                continue
            span = next((s for s in schema["spans"] if s[0]==r and s[1]==c), None)
            if span:
                rowspan = span[2] - span[0] + 1
                colspan = span[3] - span[1] + 1
                html += f'<td rowspan="{rowspan}" colspan="{colspan}"></td>'
                for rr in range(span[0], span[2]+1):
                    for cc in range(span[1], span[3]+1):
                        covered.add((rr, cc))
            else:
                html += "<td></td>"
        html += "</tr>"
    html += "</table>"
    return html
```

---

## Bước 4 — Phân loại lỗi theo nguyên nhân (error taxonomy)

Ngoài điểm số, framework nên tự động gắn nhãn **loại lỗi** cho mỗi bảng sai, để bạn biết nên ưu tiên sửa gì trước:

```python
def classify_table_error(pred, gt):
    errors = []
    
    if pred["n_rows"] < gt["n_rows"]:
        errors.append("MISSING_ROWS")  # có thể do bảng bị ngắt trang, hoặc dòng bị gộp nhầm
    if pred["n_rows"] > gt["n_rows"]:
        errors.append("EXTRA_ROWS")     # dòng trắng bị hiểu nhầm thành dòng dữ liệu
    if pred["n_cols"] != gt["n_cols"]:
        errors.append("COLUMN_COUNT_MISMATCH")  # thường do header 2 tầng bị hiểu sai
    
    span_result = span_iou(pred["spans"], gt["spans"])
    if span_result["recall"] < 0.7:
        errors.append("MISSED_MERGED_HEADER")
    if span_result["precision"] < 0.7:
        errors.append("HALLUCINATED_MERGE")
    
    if len(pred.get("header_rows", [])) != len(gt.get("header_rows", [])):
        errors.append("HEADER_DEPTH_MISMATCH")  # không nhận ra header nhiều tầng
    
    return errors if errors else ["OK"]
```

Chạy hàm này trên toàn bộ test set rồi thống kê tần suất từng loại lỗi:

```python
from collections import Counter

def error_distribution(all_results):
    all_errors = []
    for r in all_results:
        all_errors.extend(r["errors"])
    return Counter(all_errors)

# Output ví dụ:
# Counter({'COLUMN_COUNT_MISMATCH': 12, 'MISSING_ROWS': 8, 
#          'HALLUCINATED_MERGE': 5, 'OK': 25})
```

Bảng thống kê này chính là thứ quyết định bạn nên đầu tư công sức xử lý gì tiếp theo — nếu `COLUMN_COUNT_MISMATCH` chiếm đa số, vấn đề tập trung ở header 2 tầng; nếu `MISSING_ROWS` chiếm đa số, khả năng cao là lỗi bảng bị ngắt trang.

---

## Bước 5 — Report tổng hợp

```python
def generate_table_structure_report(all_pred, all_gt):
    results = []
    for pred, gt in zip(all_pred, all_gt):
        count_acc = count_accuracy(pred, gt)
        span_result = span_iou(pred["spans"], gt["spans"])
        teds = compute_teds_struct(schema_to_html(pred), schema_to_html(gt))
        errors = classify_table_error(pred, gt)
        results.append({
            "row_exact_match": count_acc["row_exact_match"],
            "col_exact_match": count_acc["col_exact_match"],
            "span_f1": span_result["f1"],
            "teds_struct": teds,
            "errors": errors
        })
    
    n = len(results)
    summary = {
        "n_tables": n,
        "row_accuracy": sum(r["row_exact_match"] for r in results) / n,
        "col_accuracy": sum(r["col_exact_match"] for r in results) / n,
        "avg_span_f1": sum(r["span_f1"] for r in results) / n,
        "avg_teds_struct": sum(r["teds_struct"] for r in results) / n,
        "error_distribution": error_distribution(results),
    }
    return summary, results
```

**Output mẫu để đọc kết quả:**
```
n_tables: 48
row_accuracy: 0.83
col_accuracy: 0.71        ← thấp nhất, cần chú ý
avg_span_f1: 0.65          ← thấp, khả năng do header 2 tầng
avg_teds_struct: 0.79
error_distribution: {
  'COLUMN_COUNT_MISMATCH': 14,
  'HALLUCINATED_MERGE': 6,
  'MISSED_MERGED_HEADER': 9,
  'OK': 27
}
```

Với kết quả ví dụ trên, kết luận rút ra ngay được: **vấn đề chính nằm ở việc nhận diện header 2 tầng** (col_accuracy thấp + MISSED_MERGED_HEADER cao) — đây là hướng cần xử lý ưu tiên, thay vì dàn trải công sức vào mọi loại lỗi.

---

## Cách dùng framework này để theo dõi tiến độ cải thiện

Chạy lại đúng report này mỗi khi bạn thay đổi bất kỳ thứ gì trong xử lý bảng (đổi model table structure, thêm tiền xử lý ảnh, viết rule hậu xử lý ghép bảng bị ngắt trang...) — trên **cùng test set 40-55 bảng** đã gán nhãn, để so sánh trước/sau một cách nhất quán, tránh tình trạng "cảm thấy tốt hơn" nhưng không có số liệu chứng minh.

Bạn đã có sẵn bảng ground truth (cấu trúc gán tay) chưa, hay cần mình viết thêm script hỗ trợ gán nhãn nhanh (ví dụ tool đơn giản để bạn click chọn vùng gộp trên ảnh bảng) để bắt đầu bước 2?