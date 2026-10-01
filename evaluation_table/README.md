# FRAMEWORK ĐÁNH GIÁ CẤU TRÚC BẢNG TÀI CHÍNH (TABLE STRUCTURE EVALUATION)

> **Mục tiêu:** Đo lường độ chính xác và độ toàn vẹn của mô hình trích xuất bảng (MinerU Layout/Table Model) về mặt **hình học và cấu trúc logic** (số hàng, số cột, tọa độ ô gộp, cấp bậc header) — **tách biệt hoàn toàn khỏi việc nội dung OCR trong ô đọc đúng hay sai**.

---

## 1. Bản chất cấu trúc Bảng trong BCTC & Định dạng xuất của MinerU

Trong Báo cáo Tài chính (BCTC) Việt Nam (Thông tư 200), bảng số liệu kế toán thường chứa các cấu trúc phức tạp:
- **Header 2 tầng (Multi-level Header):** Ví dụ cột "Năm nay" gộp 2 cột con "Nguyên tệ" và "Tương đương VND" (`colspan="2"`).
- **Ô gộp dòng (Rowspan):** Tên nhóm chỉ tiêu gộp 2 dòng liên tiếp (`rowspan="2"`).
- **Dòng "Cộng / Tổng cộng":** Định dạng in đậm, viền khung khác biệt dễ bị hiểu nhầm thành bảng mới.
- **Bảng ngắt trang:** Một bảng thuyết minh dài 2-3 trang PDF liên tiếp.

### Tại sao MinerU lúc xuất Markdown, lúc lại xuất HTML?
- **Markdown chuẩn (GFM):** Là dạng lưới phẳng (`| Cột 1 | Cột 2 |`), **hoàn toàn không hỗ trợ gộp ô** (`colspan`/`rowspan`).
- **HTML Table (`<table>`):** Hỗ trợ đầy đủ các thuộc tính `rowspan` và `colspan`.

Bên trong MinerU (`docvortex/render/_internal/markdown/table.py`), hàm `_is_complex_table` sẽ kiểm tra:
1. **Bảng đơn giản (Simple Table):** Nếu bảng phẳng, không có ô gộp nào $\rightarrow$ Chuyển thành **Markdown pipe table (`| ... |`)**.
2. **Bảng phức tạp (Complex Table):** Nếu phát hiện có `rowspan` hoặc `colspan` $\rightarrow$ **Bắt buộc giữ nguyên HTML `<table>...</table>`** để bảo toàn cấu trúc logic không bị mất mát.

Toolkit này được thiết kế để **tự động tương thích và chuẩn hóa cả 2 định dạng (HTML và Markdown)** về một ma trận lưới thống nhất.

---

## 2. Cấu trúc Thư mục Tài nguyên (`evaluation_table/`)

```
evaluation_table/
├── README.md                           # Hướng dẫn chi tiết & đặc tả bộ chỉ số Benchmark
├── converter.py                        # Bộ chuyển đổi linh hoạt: HTML / Markdown <-> Table Schema
├── metrics.py                          # 4 metric cốt lõi: Count Acc, Span IoU, TEDS-Struct, Error Taxonomy
├── evaluator.py                        # Script CLI đánh giá toàn diện bộ dataset GT vs Predictions
├── serve_reviewer.py                   # Giao diện Web Reviewer đối chiếu ảnh crop & gán nhãn Ground Truth
├── manifest.json                       # Index JSON của 49 bảng thực tế kèm phân nhóm và siêu dữ liệu
├── ground_truth/                       # 49 file nhãn chuẩn ứng với 49 bảng thực tế (.json)
├── predictions/                        # 49 bảng trích xuất từ pipeline (.html, .md, .json)
├── images/                             # 49 ảnh crop 200 DPI của các bảng phục vụ đối chiếu
└── reports/                            # Báo cáo đánh giá xuất ra tự động
    ├── report_latest.json              # File JSON chi tiết mọi thông số kỹ thuật
    └── report_latest.md                # Báo cáo Markdown có bảng so sánh và phân tích lỗi
```

---

## 3. Định dạng Dữ liệu Chuẩn (`table_schema`)

Mọi bảng (dù là Ground Truth hay Prediction từ pipeline) đều được `converter.py` tự động ánh xạ về schema:

```json
{
  "table_id": "vnm_2024_p44_tbl_2",
  "description": "Thuyết minh Ngoại tệ (Header 2 tầng, ô gộp)",
  "n_rows": 4,
  "n_cols": 5,
  "header_rows": [0, 1],
  "spans": [
    [0, 0, 0, 2],
    [0, 3, 0, 4],
    [1, 0, 2, 0]
  ],
  "html": "<table>...</table>"
}
```

### Quy tắc tọa độ `spans`:
Mỗi phần tử trong `spans` là một mảng 4 số nguyên `[r_start, c_start, r_end, c_end]` (chỉ số 0-indexed):
- `[0, 0, 0, 2]`: Ô từ hàng 0 cột 0 kéo dài đến hàng 0 cột 2 (gộp 3 cột ngang → `colspan="3"`).
- `[1, 0, 2, 0]`: Ô từ hàng 1 cột 0 kéo dài đến hàng 2 cột 0 (gộp 2 hàng dọc → `rowspan="2"`).

---

## 4. Bốn Tầng Metrics Đo Lường

### 4.1. Row & Column Count Accuracy (Độ chính xác kích thước lưới)
- Đo xem số hàng (`n_rows`) và số cột (`n_cols`) logic có khớp tuyệt đối giữa Prediction và Ground Truth hay không.
- Nếu kích thước lưới lệch, bảng gần như chắc chắn đã bị vỡ cấu trúc hoặc gộp nhầm cột/hàng.

### 4.2. Span IoU (Độ chính xác ô gộp / Header 2 tầng)
- Với mỗi vùng ô gộp trong Prediction $S_{pred}$ và Ground Truth $S_{gt}$, tính diện tích giao trên diện tích hợp:
  $$\text{IoU}(S_{pred}, S_{gt}) = \frac{\text{Area}(S_{pred} \cap S_{gt})}{\text{Area}(S_{pred} \cup S_{gt})}$$
- Nếu $\text{IoU} \ge 0.5$, tính là **True Positive (TP)**.
- Trả về 3 chỉ số: **Precision**, **Recall**, và **Span F1**.
  - **Recall thấp:** Model bỏ sót các ô gộp thật (thường gặp khi header 2 tầng bị ép phẳng).
  - **Precision thấp:** Model tự bịa ra các ô gộp không có thực.

### 4.3. TEDS-Struct (Tree Edit Distance-based Similarity)
- Chuẩn học thuật của IBM (PubTabNet paper) chuyên dùng đánh giá Table Structure.
- Công thức:
  $$\text{TEDS}_{\text{struct}}(T_{pred}, T_{gt}) = 1 - \frac{\text{TreeEditDistance}(T_{pred}, T_{gt})}{\max(|T_{pred}|, |T_{gt}|)}$$
- Toolkit này triển khai **thuật toán Zhang-Shasha thuần Python (100% offline, zero-dependency)**, chỉ so sánh cấu trúc các node DOM (`table`, `thead`, `tr`, `th`, `td` kèm thuộc tính `rowspan`, `colspan`) và bỏ qua nội dung text.
- Thang điểm: `0.0` (sai lệch hoàn toàn) → `1.0` (cấu trúc trùng khớp tuyệt đối).

### 4.4. Error Taxonomy (Phân loại tự động nguyên nhân lỗi)
Framework tự động chẩn đoán và gắn nhãn các mã lỗi sau:
1. `MISSING_ROWS`: Thiếu dòng (bảng bị ngắt trang hoặc OCR nuốt mất dòng).
2. `EXTRA_ROWS`: Thừa dòng (khoảng trắng, footnote bị nhận diện nhầm thành dữ liệu).
3. `COLUMN_COUNT_MISMATCH`: Lệch số cột (thường do header 2 tầng bị hiểu sai).
4. `MISSED_MERGED_HEADER`: Bỏ sót ô gộp (đặc biệt là các cột "Năm nay / Năm trước").
5. `HALLUCINATED_MERGE`: Gộp ô ảo không có thực.
6. `HEADER_DEPTH_MISMATCH`: Lệch số dòng tiêu đề bảng.
7. `OK`: Khớp hoàn hảo.

---

## 5. Hướng Dẫn Chạy Đánh Giá Nhanh (Quickstart)

### Bước 1: Chạy đánh giá trên bộ 49 bảng Ground Truth
Từ thư mục gốc của dự án, chạy lệnh:

```bash
python evaluation_table/evaluator.py
# hoặc
python interface.py --eval-tables
```

Kết quả đo lường thực tế trên bộ dữ liệu 49 bảng:
```text
=================================================================
 KẾT QUẢ ĐÁNH GIÁ TABLE STRUCTURE:
 - Tổng số bảng: 49
 - Row Accuracy: 46.9%
 - Col Accuracy: 89.8%
 - Span F1 (Ô gộp): 71.8%
 - TEDS-Struct: 0.8604
 - Phân bố lỗi: {'MISSING_ROWS': 19, 'OK': 16, 'MISSED_MERGED_HEADER': 12, 'HALLUCINATED_MERGE': 10, 'HEADER_DEPTH_MISMATCH': 10, 'EXTRA_ROWS': 7, 'COLUMN_COUNT_MISMATCH': 5}
=================================================================
```

### Bước 2: Xem báo cáo chi tiết
Mở file [reports/report_latest.md](reports/report_latest.md) để xem phân tích chi tiết từng bảng trong 49 bảng kiểm thử.

---

## 6. Quy Trình Thu Thập & Đánh Giá Thực Chiến (40–55 Bảng BCTC)

Để xây dựng bộ benchmark đáng tin cậy cho toàn bộ dự án FinAudit AI:

1. **Lựa chọn phân bổ mẫu (Document-level diversity):**
   - 10 bảng cân đối / kết quả kinh doanh đơn giản (Baseline).
   - 15 bảng thuyết minh có header 2 tầng (Ngoại tệ, Phải thu, Biến động vốn chủ sở hữu).
   - 10 bảng có dòng "Cộng / Tổng cộng" viền đậm.
   - 10 bảng thuyết minh dài bị ngắt trang (Trang $N \rightarrow N+1$).
   - 5 bảng có ô trống, gạch ngang `-` hoặc số âm trong ngoặc `(120.000)`.

2. **Cách gán nhãn Ground Truth nhanh bằng công cụ có sẵn:**
   - Copy chuỗi HTML của bảng (từ file Excel/HTML công bố thông tin, hoặc lấy từ `data/cache/notes/.../page_xx.json`).
   - Dùng hàm `html_to_schema` trong `converter.py` để tự động tính `spans` và `n_rows, n_cols` nháp, sau đó chỉ cần rà soát lại bằng mắt:
   ```python
   from evaluation_table.converter import html_to_schema
   import json

   raw_html = "<table>...</table>"
   schema = html_to_schema(raw_html)
   print(json.dumps(schema, indent=2, ensure_ascii=False))
   ```
   - Lưu vào thư mục `evaluation_table/ground_truth/{tên_bảng}.json`.

3. **Thu thập Predictions từ Pipeline:**
   - Chạy pipeline trích xuất MinerU + VietOCR trên trang chứa bảng.
   - Lưu nội dung `cb.content` của block bảng vào `evaluation_table/predictions/{tên_bảng}.html` (hoặc `.md`).

4. **Chạy Evaluator và phân tích Error Taxonomy:**
   - Chạy `evaluator.py` để đo chỉ số.
   - Nếu lỗi `COLUMN_COUNT_MISMATCH` cao $\rightarrow$ Ưu tiên cải thiện prompt/rule xử lý header 2 tầng.
   - Nếu lỗi `MISSING_ROWS` cao $\rightarrow$ Cải thiện thuật toán ghép bảng ngắt trang (`table_stitcher`).
