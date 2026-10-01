# DANH MỤC 49 BẢNG THUYẾT MINH THỰC TẾ (NOTES ONLY) — BCTC VNM 2024

> **Nguồn gốc dữ liệu:** 100% trích xuất từ cache Notes (`data/cache/notes/VNM_2024/page_13.json` -> `page_54.json`).
> **Tiêu chí kiểm thử:** Phân loại theo đúng 5 nhóm rủi ro cấu trúc bảng trong `evaluation_table/plan.md:L30`.
> **Trạng thái Ground Truth:** Thư mục `ground_truth/` đã được dọn sạch để người dùng tự gán nhãn chuẩn vàng.

- **Tổng số bảng Thuyết minh:** `49` bảng.

---

## 1. Thống kê theo 5 nhóm kiểm thử (Test Groups)

| Nhóm bảng | Số lượng | Đặc điểm kiểm thử & Nguy cơ lỗi |
|---|---|---|
| **1. Bảng đơn giản (1 tầng header)** | `16` | Baseline đơn giản, kỳ vọng điểm số TEDS-Struct tuyệt đối |
| **2. Bảng có header 2 tầng (gộp cột con / spans)** | `11` | Header 2 tầng (Năm nay/Năm trước gộp cột con), hay bị sai spans |
| **3. Bảng có dòng 'Cộng / Tổng cộng'** | `8` | Dòng Cộng/Tổng cộng kẻ khung đậm, dễ bị cắt nhầm thành 2 bảng |
| **4. Bảng bị ngắt trang (trải dài 2+ trang PDF)** | `8` | Bảng ngắt trang qua 2-3 trang PDF liên tiếp |
| **5. Bảng có ô trống / gạch ngang '-'** | `6` | Ô trống hoặc gạch ngang '-', dễ bị hiểu nhầm cấu trúc |

---

## 2. Danh mục chi tiết 49 bảng Thuyết minh

| STT | Table ID | Trang | Nhóm kiểm thử | Định dạng | Hàng x Cột | Ô gộp (Spans) | Thuyết minh / Nội dung |
|---|---|---|---|---|---|---|---|
| 01 | `p14_mineru_tbl_1` | Trang 14 | Bảng bị ngắt trang (trải dài 2+ trang PDF) | `HTML` | 9 x 6 | 2 | Thuyết minh Cấu trúc Tập đoàn (Công ty con P1) |
| 02 | `p15_mineru_tbl_1` | Trang 15 | Bảng bị ngắt trang (trải dài 2+ trang PDF) | `HTML` | 8 x 5 | 10 | Thuyết minh Cấu trúc Tập đoàn (Công ty con P2) |
| 03 | `p15_mineru_tbl_2` | Trang 15 | Bảng có header 2 tầng (gộp cột con / spans) | `HTML` | 6 x 6 | 1 | (b) Các công ty liên doanh, liên kết |
| 04 | `p27_mineru_tbl_1` | Trang 27 | Bảng đơn giản (1 tầng header) | `MD` | 4 x 3 | 0 | 1.1 Tiền và các khoản tương đương tiền |
| 05 | `p27_mineru_tbl_2` | Trang 27 | Bảng có ô trống / gạch ngang '-' | `MD` | 12 x 3 | 0 | (a) Phải thu khách hàng là các bên liên quan |
| 06 | `p27_mineru_tbl_3` | Trang 27 | Bảng đơn giản (1 tầng header) | `MD` | 5 x 3 | 0 | Biến động của dự phòng phải thu khó đòi trong năm như sau: |
| 07 | `p28_mineru_tbl_1` | Trang 28 | Bảng có header 2 tầng (gộp cột con / spans) | `HTML` | 8 x 3 | 1 | (a) Phải thu ngắn hạn khác |
| 08 | `p28_mineru_tbl_2` | Trang 28 | Bảng đơn giản (1 tầng header) | `MD` | 3 x 2 | 0 | Ký cược, ký quỹ dài hạn Phải thu khác |
| 09 | `p28_mineru_tbl_3` | Trang 28 | Bảng đơn giản (1 tầng header) | `MD` | 3 x 2 | 0 | Đầu tư nắm giữ đến ngày đáo hạn - dài hạn tiền gửi ngân hàng có kỳ hạn |
| 10 | `p29_mineru_tbl_1` | Trang 29 | Bảng có header 2 tầng (gộp cột con / spans) | `HTML` | 11 x 9 | 3 | (b) Các khoản đầu tư càí chính dài |
| 11 | `p30_mineru_tbl_1` | Trang 30 | Bảng có header 2 tầng (gộp cột con / spans) | `MD` | 0 x 0 (Pred lỗi) | 0 | Thuyết minh Các khoản đầu tư tài chính dài hạn (Trang 30) |
| 12 | `p31_mineru_tbl_1` | Trang 31 | Bảng có header 2 tầng (gộp cột con / spans) | `HTML` | 5 x 3 | 1 | Biến động dự phòng giảm giá đầu tư tài chính dài hạn trong năm như sau: |
| 13 | `p31_mineru_tbl_2` | Trang 31 | Bảng có header 2 tầng (gộp cột con / spans) | `HTML` | 11 x 4 | 2 | 5. Hàng tồn kho |
| 14 | `p31_mineru_tbl_3` | Trang 31 | Bảng đơn giản (1 tầng header) | `MD` | 6 x 3 | 0 | Biển động dự phòng giảm giá hàng tồn kho trong năm như sau: |
| 15 | `p32_mineru_tbl_1` | Trang 32 | Bảng có dòng 'Cộng / Tổng cộng' | `MD` | 17 x 6 | 0 | 6.0 Tài sản cố định hữu hình |
| 16 | `p33_mineru_tbl_1` | Trang 33 | Bảng có header 2 tầng (gộp cột con / spans) | `HTML` | 15 x 6 | 5 | 7.0 Tài sản cố định vô hình |
| 17 | `p34_mineru_tbl_1` | Trang 34 | Bảng có dòng 'Cộng / Tổng cộng' | `MD` | 9 x 5 | 0 | 8. Bất động sản đầu tư |
| 18 | `p35_mineru_tbl_1` | Trang 35 | Bảng đơn giản (1 tầng header) | `MD` | 9 x 3 | 0 | 9. Xây dựng cơ bản dở dang |
| 19 | `p35_mineru_tbl_2` | Trang 35 | Bảng đơn giản (1 tầng header) | `MD` | 6 x 3 | 0 | Các công trình xây dựng cơ bản dở dang lớn đang thực hiện như sau |
| 20 | `p35_mineru_tbl_3` | Trang 35 | Bảng đơn giản (1 tầng header) | `MD` | 8 x 3 | 0 | (a) Chi phí trả trước ngắn hạn |
| 21 | `p36_mineru_tbl_1` | Trang 36 | Bảng có header 2 tầng (gộp cột con / spans) | `HTML` | 6 x 6 | 2 | (b) Chi phí trả trước dài hạn |
| 22 | `p37_mineru_tbl_1` | Trang 37 | Bảng có dòng 'Cộng / Tổng cộng' | `MD` | 9 x 3 | 0 | 11. Tài sản thuế thu nhập hoãn lại và thuế thu nhập hoãn lại phải trá |
| 23 | `p37_mineru_tbl_2` | Trang 37 | Bảng có ô trống / gạch ngang '-' | `MD` | 11 x 3 | 0 | Phải trả người bán là các bên liên quan |
| 24 | `p38_mineru_tbl_1` | Trang 38 | Bảng có ô trống / gạch ngang '-' | `MD` | 8 x 5 | 0 | 13. Thuế phải nộân sách nước |
| 25 | `p39_mineru_tbl_1` | Trang 39 | Bảng đơn giản (1 tầng header) | `MD` | 10 x 3 | 0 | 14. Chi phí phải trả |
| 26 | `p39_mineru_tbl_2` | Trang 39 | Bảng đơn giản (1 tầng header) | `MD` | 5 x 3 | 0 | 15. Phải trả ngăn hạn khác |
| 27 | `p40_mineru_tbl_1` | Trang 40 | Bảng có ô trống / gạch ngang '-' | `MD` | 5 x 6 | 0 | 16. Vay ngắn hạn |
| 28 | `p41_mineru_tbl_1` | Trang 41 | Bảng đơn giản (1 tầng header) | `MD` | 2 x 3 | 0 | 17. Dự phòng phải trả ngắn hạn |
| 29 | `p41_mineru_tbl_2` | Trang 41 | Bảng đơn giản (1 tầng header) | `MD` | 6 x 3 | 0 | Biến động dự phòng trợ cấp thôi việc trong năm như sau: |
| 30 | `p41_mineru_tbl_3` | Trang 41 | Bảng có ô trống / gạch ngang '-' | `MD` | 5 x 3 | 0 | Biến động quỹ khen thưởng và phúc lợi trong năm như sau: |
| 31 | `p42_mineru_tbl_1` | Trang 42 | Bảng có dòng 'Cộng / Tổng cộng' | `MD` | 11 x 6 | 0 | 19.1 Thay đổi vốn chủ sở hữu |
| 32 | `p43_mineru_tbl_1` | Trang 43 | Bảng có header 2 tầng (gộp cột con / spans) | `HTML` | 6 x 3 | 1 | Vốn cổ phần được duyệt và đã phát hành của Công ty là: |
| 33 | `p43_mineru_tbl_2` | Trang 43 | Bảng có header 2 tầng (gộp cột con / spans) | `HTML` | 5 x 3 | 2 | Chi tiết vốn cổ phần |
| 34 | `p44_mineru_tbl_1` | Trang 44 | Bảng đơn giản (1 tầng header) | `MD` | 5 x 3 | 0 | Các khoản tiền thuê tối thiểu phải trả cho các hợp đồng thuê hoạt động không được hủy ngang như sau: |
| 35 | `p44_mineru_tbl_2` | Trang 44 | Bảng có header 2 tầng (gộp cột con / spans) | `HTML` | 4 x 5 | 3 | (b) Ngoại tệ các loại |
| 36 | `p45_mineru_tbl_1` | Trang 45 | Bảng đơn giản (1 tầng header) | `MD` | 2 x 3 | 0 | Tại ngày báo cáo, Công ty có các cam kết vốn sau đã được duyệt nhưng chưa được phản ánh trong báo cáo tình hình tài chính riêng: |
| 37 | `p45_mineru_tbl_2` | Trang 45 | Bảng có dòng 'Cộng / Tổng cộng' | `MD` | 11 x 3 | 0 | Doanh thu thuần bao gồm: |
| 38 | `p46_mineru_tbl_1` | Trang 46 | Bảng có dòng 'Cộng / Tổng cộng' | `MD` | 26 x 3 | 0 | Trong đó, doanh thu với khách hàng là các bên liên quan như sau: |
| 39 | `p47_mineru_tbl_1` | Trang 47 | Bảng đơn giản (1 tầng header) | `MD` | 6 x 3 | 0 | 3. Doanh thu hoạt động tài chính |
| 40 | `p47_mineru_tbl_2` | Trang 47 | Bảng bị ngắt trang (trải dài 2+ trang PDF) | `MD` | 8 x 3 | 0 | Thuyết minh Chi phí bán hàng (Phần 1 - Trang 47) |
| 41 | `p48_mineru_tbl_1` | Trang 48 | Bảng bị ngắt trang (trải dài 2+ trang PDF) | `MD` | 12 x 3 | 0 | Thuyết minh Chi phí bán hàng (Phần 2 - Trang 48) |
| 42 | `p48_mineru_tbl_2` | Trang 48 | Bảng bị ngắt trang (trải dài 2+ trang PDF) | `MD` | 13 x 3 | 0 | Thuyết minh Chi phí quản lý doanh nghiệp (Phần 1 - Trang 48) |
| 43 | `p49_mineru_tbl_1` | Trang 49 | Bảng bị ngắt trang (trải dài 2+ trang PDF) | `MD` | 21 x 3 | 0 | Thuyết minh Chi phí quản lý doanh nghiệp (Phần 2 - Trang 49) |
| 44 | `p50_mineru_tbl_1` | Trang 50 | Bảng có ô trống / gạch ngang '-' | `MD` | 18 x 3 | 0 | (a) Ghi nhận trong báo cáo kết quả hoạt động kinh doanh riêng |
| 45 | `p51_mineru_tbl_1` | Trang 51 | Bảng bị ngắt trang (trải dài 2+ trang PDF) | `HTML` | 16 x 5 | 8 | Giao dịch các bên liên quan (Doanh thu & Mua hàng) |
| 46 | `p52_mineru_tbl_1` | Trang 52 | Bảng bị ngắt trang (trải dài 2+ trang PDF) | `HTML` | 11 x 5 | 3 | Giao dịch các bên liên quan (Số dư công nợ) |
| 47 | `p53_mineru_tbl_1` | Trang 53 | Bảng có dòng 'Cộng / Tổng cộng' | `MD` | 14 x 3 | 0 | Thù lao và lương của thành viên quản lý chủ chốt thuy |
| 48 | `p53_mineru_tbl_2` | Trang 53 | Bảng có dòng 'Cộng / Tổng cộng' | `MD` | 5 x 3 | 0 | (ii) Thành viên Hội đồng quản trị kiêm Giám đốc Diều hành ? Tài chính |
| 49 | `p54_mineru_tbl_1` | Trang 54 | Bảng có header 2 tầng (gộp cột con / spans) | `HTML` | 5 x 7 | 4 | Khi trình bày thông tin bộ phận theo khu vực địa lý, daanh thu của bộ phận được trình bày dụa vào vị trí địa lý của khách hàng tạ ở các nước khác Việt Nam ( Nước ngoài") Tái sản bộ phận và chi phá vốn không đo vị trí của tài sản và cơ sở sản xuất chủ yếu là ở |
