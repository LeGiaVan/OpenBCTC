# BÁO CÁO ĐÁNH GIÁ CẤU TRÚC BẢNG (TABLE STRUCTURE EVALUATION)

- **Tổng số bảng kiểm thử:** `49`
- **Độ chính xác số Hàng (Row Acc):** `46.9%`
- **Độ chính xác số Cột (Col Acc):** `89.8%`
- **Độ khớp Ma trận Lưới (Grid Exact Match):** `44.9%`
- **Span F1 (Ô gộp / Header 2 tầng):** `71.8%`
- **TEDS-Struct (Tree Edit Distance):** `0.8604`

---

## 1. Phân bố các loại lỗi (Error Distribution)

| Phân loại lỗi | Số lượng bảng | Ý nghĩa & Hướng xử lý |
|---|---|---|
| `MISSING_ROWS` | **19** (38.8%) | Thiếu dòng — Có thể do bảng bị ngắt trang qua 2 trang PDF hoặc OCR gộp dòng. |
| `OK` | **16** (32.7%) | Cấu trúc hoàn hảo — Khớp 100% kích thước và vị trí ô gộp. |
| `MISSED_MERGED_HEADER` | **12** (24.5%) | Bỏ sót ô gộp — Model coi header đa tầng là các ô riêng rẽ độc lập. |
| `HALLUCINATED_MERGE` | **10** (20.4%) | Gộp ô ảo — Model tự động gộp các ô không có thật. |
| `HEADER_DEPTH_MISMATCH` | **10** (20.4%) | Lệch số tầng header — Số dòng tiêu đề bảng nhận diện sai. |
| `EXTRA_ROWS` | **7** (14.3%) | Thừa dòng — Dòng kẻ ngang, khoảng trắng hoặc ghi chú chân trang bị coi là dữ liệu. |
| `COLUMN_COUNT_MISMATCH` | **5** (10.2%) | Lệch số cột — Thường do Header 2 tầng bị gộp phẳng làm mất cột con. |

---

## 2. Chi tiết từng bảng kiểm thử

| Table ID | Hàng (Pred/GT) | Cột (Pred/GT) | Span F1 | TEDS-Struct | Lỗi ghi nhận |
|---|---|---|---|---|---|
| `p14_mineru_tbl_1` | 9/9 | 6/5 | 0.67 | **0.790** | `COLUMN_COUNT_MISMATCH`, `HALLUCINATED_MERGE`, `HEADER_DEPTH_MISMATCH` |
| `p15_mineru_tbl_1` | 8/7 | 5/5 | 0.12 | **0.429** | `EXTRA_ROWS`, `MISSED_MERGED_HEADER`, `HALLUCINATED_MERGE`, `HEADER_DEPTH_MISMATCH` |
| `p15_mineru_tbl_2` | 6/7 | 6/5 | 0.33 | **0.619** | `MISSING_ROWS`, `COLUMN_COUNT_MISMATCH`, `MISSED_MERGED_HEADER`, `HEADER_DEPTH_MISMATCH` |
| `p27_mineru_tbl_1` | 4/4 | 3/3 | 1.00 | **1.000** | `OK` |
| `p27_mineru_tbl_2` | 12/11 | 3/3 | 0.00 | **0.796** | `EXTRA_ROWS`, `MISSED_MERGED_HEADER` |
| `p27_mineru_tbl_3` | 5/6 | 3/3 | 1.00 | **0.840** | `MISSING_ROWS` |
| `p28_mineru_tbl_1` | 8/8 | 3/3 | 0.00 | **0.939** | `HALLUCINATED_MERGE` |
| `p28_mineru_tbl_2` | 3/4 | 2/2 | 1.00 | **0.769** | `MISSING_ROWS` |
| `p28_mineru_tbl_3` | 3/3 | 2/2 | 1.00 | **1.000** | `OK` |
| `p29_mineru_tbl_1` | 11/12 | 9/9 | 0.29 | **0.868** | `MISSING_ROWS`, `MISSED_MERGED_HEADER`, `HALLUCINATED_MERGE`, `HEADER_DEPTH_MISMATCH` |
| `p30_mineru_tbl_1` | 0/13 | 0/9 | 0.00 | **0.009** | `MISSING_ROWS`, `COLUMN_COUNT_MISMATCH`, `MISSED_MERGED_HEADER`, `HEADER_DEPTH_MISMATCH` |
| `p31_mineru_tbl_1` | 5/5 | 3/3 | 0.00 | **0.857** | `HALLUCINATED_MERGE` |
| `p31_mineru_tbl_2` | 11/10 | 4/5 | 0.00 | **0.690** | `EXTRA_ROWS`, `COLUMN_COUNT_MISMATCH`, `MISSED_MERGED_HEADER`, `HALLUCINATED_MERGE`, `HEADER_DEPTH_MISMATCH` |
| `p31_mineru_tbl_3` | 6/6 | 3/3 | 1.00 | **1.000** | `OK` |
| `p32_mineru_tbl_1` | 17/17 | 6/6 | 1.00 | **1.000** | `OK` |
| `p33_mineru_tbl_1` | 15/13 | 6/5 | 0.00 | **0.743** | `EXTRA_ROWS`, `COLUMN_COUNT_MISMATCH`, `HALLUCINATED_MERGE` |
| `p34_mineru_tbl_1` | 9/10 | 5/5 | 1.00 | **0.902** | `MISSING_ROWS` |
| `p35_mineru_tbl_1` | 9/10 | 3/3 | 1.00 | **0.902** | `MISSING_ROWS` |
| `p35_mineru_tbl_2` | 6/6 | 3/3 | 1.00 | **1.000** | `OK` |
| `p35_mineru_tbl_3` | 8/8 | 3/3 | 1.00 | **1.000** | `OK` |
| `p36_mineru_tbl_1` | 6/6 | 6/6 | 0.00 | **0.907** | `HALLUCINATED_MERGE` |
| `p37_mineru_tbl_1` | 9/10 | 3/3 | 1.00 | **0.902** | `MISSING_ROWS` |
| `p37_mineru_tbl_2` | 11/11 | 3/3 | 0.00 | **0.867** | `MISSED_MERGED_HEADER` |
| `p38_mineru_tbl_1` | 8/8 | 5/5 | 1.00 | **1.000** | `OK` |
| `p39_mineru_tbl_1` | 10/11 | 3/3 | 1.00 | **0.911** | `MISSING_ROWS` |
| `p39_mineru_tbl_2` | 5/6 | 3/3 | 1.00 | **0.840** | `MISSING_ROWS` |
| `p40_mineru_tbl_1` | 5/5 | 6/6 | 1.00 | **1.000** | `OK` |
| `p41_mineru_tbl_1` | 2/2 | 3/3 | 1.00 | **1.000** | `OK` |
| `p41_mineru_tbl_2` | 6/6 | 3/3 | 1.00 | **1.000** | `OK` |
| `p41_mineru_tbl_3` | 5/5 | 3/3 | 1.00 | **1.000** | `OK` |
| `p42_mineru_tbl_1` | 11/12 | 6/6 | 1.00 | **0.918** | `MISSING_ROWS` |
| `p43_mineru_tbl_1` | 6/7 | 3/3 | 0.40 | **0.625** | `MISSING_ROWS`, `MISSED_MERGED_HEADER`, `HEADER_DEPTH_MISMATCH` |
| `p43_mineru_tbl_2` | 5/5 | 3/3 | 1.00 | **0.895** | `HEADER_DEPTH_MISMATCH` |
| `p44_mineru_tbl_1` | 5/5 | 3/3 | 1.00 | **1.000** | `OK` |
| `p44_mineru_tbl_2` | 4/6 | 5/5 | 0.57 | **0.633** | `MISSING_ROWS`, `MISSED_MERGED_HEADER`, `HALLUCINATED_MERGE`, `HEADER_DEPTH_MISMATCH` |
| `p45_mineru_tbl_1` | 2/2 | 3/3 | 1.00 | **1.000** | `OK` |
| `p45_mineru_tbl_2` | 11/13 | 3/3 | 0.00 | **0.918** | `MISSING_ROWS`, `MISSED_MERGED_HEADER` |
| `p46_mineru_tbl_1` | 26/26 | 3/3 | 1.00 | **1.000** | `OK` |
| `p47_mineru_tbl_1` | 6/6 | 3/3 | 1.00 | **1.000** | `OK` |
| `p47_mineru_tbl_2` | 8/8 | 3/3 | 1.00 | **1.000** | `OK` |
| `p48_mineru_tbl_1` | 12/11 | 3/3 | 1.00 | **0.918** | `EXTRA_ROWS` |
| `p48_mineru_tbl_2` | 13/14 | 3/3 | 1.00 | **0.930** | `MISSING_ROWS` |
| `p49_mineru_tbl_1` | 21/19 | 3/3 | 1.00 | **0.906** | `EXTRA_ROWS` |
| `p50_mineru_tbl_1` | 18/17 | 3/3 | 1.00 | **0.945** | `EXTRA_ROWS` |
| `p51_mineru_tbl_1` | 16/20 | 5/5 | 0.80 | **0.726** | `MISSING_ROWS`, `MISSED_MERGED_HEADER` |
| `p52_mineru_tbl_1` | 11/12 | 5/5 | 0.00 | **0.667** | `MISSING_ROWS`, `MISSED_MERGED_HEADER`, `HALLUCINATED_MERGE` |
| `p53_mineru_tbl_1` | 14/15 | 3/3 | 1.00 | **0.934** | `MISSING_ROWS` |
| `p53_mineru_tbl_2` | 5/7 | 3/3 | 1.00 | **0.724** | `MISSING_ROWS` |
| `p54_mineru_tbl_1` | 5/5 | 7/7 | 1.00 | **0.838** | `HEADER_DEPTH_MISMATCH` |
