# Hệ thống Agent đọc báo cáo tài chính (BCTC) — Mô tả kiến trúc

## 1. Bối cảnh và mục tiêu

Hệ thống xử lý báo cáo tài chính doanh nghiệp niêm yết tại Việt Nam nhằm phục vụ agent AI trả lời câu hỏi qua RAG. Bài toán có 3 đặc điểm ràng buộc thiết kế:

- **Đa số BCTC ở Việt Nam là bản scan**, không phải PDF native — do yêu cầu chữ ký/con dấu của kế toán trưởng, giám đốc và đơn vị kiểm toán. Việt Nam chưa có chuẩn nộp báo cáo dạng machine-readable (khác với XBRL của SEC Mỹ), nên không có nguồn nào — kể cả các nhà cung cấp dữ liệu trả phí (FiinGroup, Vietstock, WiChart) — cung cấp sẵn dữ liệu đã cấu trúc cho phần thuyết minh.
- Báo cáo gồm 2 phần có đặc điểm khác nhau rõ rệt: **báo cáo tài chính chính** (Bảng cân đối kế toán, KQKD, LCTT — ngắn, cấu trúc chuẩn hóa cao theo VAS) và **thuyết minh báo cáo tài chính** (thường ~40 trang, văn bản dài xen kẽ nhiều bảng biểu phức tạp, cấu trúc khác nhau giữa các công ty).
- Sai số liệu tài chính có chi phí cao hơn nhiều so với lỗi văn bản thông thường, nên hệ thống cần cơ chế tự kiểm chứng (validate) ở nhiều lớp thay vì tin tưởng tuyệt đối vào một model duy nhất.

## 2. Kiến trúc tổng thể

```
                    Báo cáo tài chính (PDF)
                              │
                              ▼
                 ┌─────────────────────────┐
                 │   Agent 1: định tuyến   │
                 │  (LLM đọc 5 trang đầu   │
                 │   chứa mục lục / TOC)   │
                 └────────────┬────────────┘
                    ┌──────────┴──────────┐
                    ▼                     ▼
          ┌───────────────────┐ ┌───────────────────┐
          │   Node LLM / VLM  │ │  Node OCR nội bộ  │
          │  (báo cáo chính)  │ │   (thuyết minh)   │
          └─────────┬─────────┘ └─────────┬─────────┘
                    ▼                     ▼
          ┌───────────────────┐ ┌───────────────────┐
          │ Validate kế toán  │ │  Sanity-check      │
          │ kép (TS = NV)     │ │  bảng biểu         │
          └─────────┬─────────┘ └─────────┬─────────┘
                    └──────────┬──────────┘
                               ▼
                  ┌─────────────────────────┐
                  │   Đối chiếu chéo 2      │
                  │   nguồn số liệu         │
                  │  (escalate LLM nếu lệch)│
                  └────────────┬────────────┘
                               ▼
                  ┌─────────────────────────┐
                  │  Merge + index cho RAG  │
                  └─────────────────────────┘
```

## 3. Chi tiết từng thành phần

### 3.1 Agent 1 — Định tuyến (routing)

**Nhiệm vụ:** xác định trong file PDF, khoảng trang nào là báo cáo tài chính chính (→ Edge 1) và khoảng trang nào là thuyết minh (→ Edge 2).

**Cách hoạt động:**
1. Cắt 5 trang đầu tài liệu (nơi mục lục/TOC thường xuất hiện), đưa cho LLM/VLM đọc trực tiếp — không cần OCR riêng cho bước này.
2. LLM đọc mục lục, đồng thời đối chiếu với số trang in ở đầu/chân trang của 1–2 trang neo để tính **độ lệch offset** giữa số trang in trong TOC và index trang thực tế của file PDF.
3. Output có cấu trúc (JSON), ví dụ:
   ```json
   {
     "toc_found": true,
     "confidence": "high",
     "page_offset": 2,
     "edge1_range": [3, 10],
     "edge2_range": [9, 48]
   }
   ```
4. Khoảng trang xuất ra có **overlap nhẹ ở ranh giới** (ví dụ trang 9–10 thuộc cả 2 khoảng) để tránh mất dữ liệu do sai lệch offset; phần trùng được lọc ở bước merge.

**Cơ chế dự phòng (fallback):**
- Nếu không tìm thấy TOC trong 5 trang đầu → mở rộng thử với 10 trang đầu.
- Nếu vẫn không có TOC (một số báo cáo nhỏ không có mục lục) → quét toàn văn bản tìm các tiêu đề chuẩn hóa theo quy định (`BẢNG CÂN ĐỐI KẾ TOÁN`, `THUYẾT MINH BÁO CÁO TÀI CHÍNH`...) bằng keyword/regex matching, dùng làm phương án cuối.

**Validate Agent 1 (bằng code, không cần LLM):**
- Tổng các khoảng trang được route ra phải phủ hết tổng số trang file gốc — phát hiện sớm nếu bỏ sót đoạn giữa.
- Các khoảng trang phải tuần tự, không chồng lấn bất thường ngoài phần overlap chủ đích.

### 3.2 Node LLM/VLM — Báo cáo tài chính chính (Edge 1)

**Lý do dùng LLM/VLM thay vì OCR truyền thống:** phần này ngắn (thường 3–4 trang) và có cấu trúc chuẩn hóa cao theo VAS across các công ty, nên đáng để dùng model mạnh hơn (đắt hơn nhưng khối lượng nhỏ) để đọc trực tiếp từ ảnh và xuất ra Markdown có cấu trúc.

**Output:** Markdown/JSON các khoản mục và số liệu của Bảng cân đối kế toán, KQKD, LCTT.

**Validate bằng code (chặn GIGO):**
- Nguyên tắc kế toán kép: **Tổng tài sản = Tổng nguồn vốn**.
- Kiểm tra tổng con của từng nhóm khoản mục khớp với dòng tổng tương ứng.
- Nếu validate fail → có thể yêu cầu LLM đọc lại hoặc đánh dấu cần review.

### 3.3 Node OCR nội bộ — Thuyết minh (Edge 2)

**Bước xử lý:**
1. **Kiểm tra native vs. scan** cho từng trang (dùng PyMuPDF `get_text()` với ngưỡng ký tự, hoặc `pdffonts`/`pdftotext` dòng lệnh) — trang có text layer thì trích xuất trực tiếp, không cần OCR.
2. **Parse/OCR bằng MinerU** (pipeline backend, license AGPLv3, mạnh về giữ cấu trúc bảng phức tạp) — thử trước với cờ `--lang latin` (nhóm ngôn ngữ Latin có dấu, gần với đặc điểm tiếng Việt hơn model mặc định).
3. Nếu tỷ lệ lỗi tiếng Việt (đặc biệt dấu thanh) còn cao sau khi đo trên mẫu thật: cân nhắc thay engine nhận diện text bằng **VietOCR** (chuyên tiếng Việt) cho các block văn bản thường, giữ MinerU cho phần layout/bảng — bằng cách lấy bounding box từ output trung gian của MinerU, crop ảnh vùng đó từ trang PDF render lại, rồi đưa qua VietOCR đọc lại.
4. **Sanity-check bảng biểu:** tổng các dòng con phải khớp dòng tổng; bảng lệch được đánh dấu (flag) độ tin cậy thấp.
5. **Chunking cho RAG:**
   - Chunk theo mục ngữ nghĩa (dựa vào đánh số mục có sẵn trong thuyết minh, VD "5.7. Tài sản cố định hữu hình"), không chunk theo số ký tự cố định.
   - Mỗi bảng là một chunk nguyên vẹn, kèm câu diễn giải/tiêu đề đứng trước.
   - Gắn metadata: tên công ty, kỳ báo cáo, số mục, số trang gốc — phục vụ truy vết ngược lại nguồn khi RAG trả lời.

### 3.4 Đối chiếu chéo 2 nguồn (cross-validation)

**Ý tưởng cốt lõi:** số liệu ở thuyết minh không độc lập với báo cáo chính — ví dụ "Tiền và tương đương tiền" ở thuyết minh phải khớp với dòng cùng tên trên Bảng cân đối kế toán. Vì Edge 1 đã qua validate kế toán kép (độ tin cậy cao hơn), dùng nó làm **ground truth** để đối chiếu ngược với số liệu Edge 2 đọc được từ OCR.

**Lưu ý triển khai:** tên khoản mục ở 2 nguồn có thể không viết y hệt nhau (khác cách viết tắt, thứ tự từ) — cần một lớp chuẩn hóa/fuzzy-match tên khoản mục trước khi so số.

**Cơ chế escalate:** khi phát hiện lệch, bảng/đoạn liên quan được đẩy ngược lại cho Node LLM/VLM đọc lại (chỉ phần bị lỗi, không phải toàn bộ tài liệu) — vừa tiết kiệm chi phí LLM, vừa giữ được khả năng tự phục hồi mà không cần dừng chờ người review.

### 3.5 Merge & Index cho RAG

Kết hợp output đã validate của cả 2 edge thành một bộ dữ liệu thống nhất, dùng chung schema metadata (mã công ty, kỳ báo cáo) để có thể liên kết ngữ cảnh giữa số liệu chính và phần thuyết minh giải thích nó khi truy vấn.

**Embedding & retrieval:**
- Ưu tiên model embedding đã fine-tune riêng cho tiếng Việt (`AITeamVN/Vietnamese_Embedding`, `bkai-foundation-models/vietnamese-bi-encoder`) thay vì model đa ngôn ngữ tổng quát — model đa ngôn ngữ tổng quát được ghi nhận cho điểm thấp hơn cả BM25 trên văn bản chuyên ngành tiếng Việt trong một benchmark gần đây.
- Dùng **hybrid search (BM25 + dense vector)** vì thuyết minh chứa nhiều số liệu/tên khoản mục cần khớp chính xác theo từ khóa, không chỉ theo ngữ nghĩa.
- Khi truy vấn liên quan một bảng, trả về nguyên cả bảng thay vì chỉ vài dòng khớp, để giữ ngữ cảnh số liệu không bị hiểu sai.

## 4. Công nghệ đề xuất

| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| Kiểm tra native/scan | PyMuPDF, `pdffonts`, `pdftotext` | Miễn phí, dùng lọc trước khi đưa vào OCR |
| Bảng trong PDF native | Camelot, pdfplumber | Không cần OCR nếu có text layer |
| Parse/OCR chính (thuyết minh) | MinerU (pipeline backend) | Mạnh về giữ cấu trúc bảng; license AGPLv3 |
| OCR chuyên tiếng Việt (nếu cần) | VietOCR | Dùng khi MinerU/PaddleOCR lỗi nhiều ở phần chữ có dấu |
| LLM/VLM đọc báo cáo chính | Tùy chọn theo hạ tầng sẵn có | Cần kèm code validate kế toán kép |
| Embedding tiếng Việt | AITeamVN/Vietnamese_Embedding, BKAI vietnamese-bi-encoder | Vượt trội BGE-M3 gốc trên benchmark tiếng Việt |
| Retrieval | Hybrid BM25 + dense vector | Phù hợp dữ liệu nhiều số liệu/tên khoản mục chính xác |

## 5. Rủi ro và biện pháp giảm thiểu

| Rủi ro | Biện pháp |
|---|---|
| Agent 1 route sai do TOC không chuẩn/không có | Fallback mở rộng phạm vi đọc, sau đó fallback heuristic quét tiêu đề; validate tổng khoảng trang phủ hết file |
| Offset trang giữa TOC và index PDF thực tế | Tính offset qua trang neo; thêm overlap ở ranh giới khoảng trang |
| OCR sai dấu thanh tiếng Việt | Test đo tỷ lệ lỗi trên mẫu thật trước khi tin tưởng; thử `--lang latin`; swap sang VietOCR nếu cần |
| Số liệu bảng OCR sai | Sanity-check tổng dòng = tổng con; đối chiếu chéo với Edge 1 |
| LLM ở Edge 1 hallucinate số liệu (GIGO) | Validate bằng nguyên tắc kế toán kép (TS = NV) |
| Không có nguồn dữ liệu cấu trúc sẵn cho thuyết minh | Chấp nhận, tập trung công sức OCR/validate vào đúng phần này; dùng dữ liệu trả phí (nếu có) chỉ cho báo cáo chính để giảm tải |

## 6. Việc cần làm tiếp

- Đo thử tỷ lệ lỗi thực tế của MinerU trên mẫu thuyết minh thật (3–5 báo cáo) trước khi scale.
- Xây dựng lớp fuzzy-match tên khoản mục cho bước đối chiếu chéo.
- Xác định ngưỡng confidence cụ thể để quyết định khi nào escalate từ Edge 2 sang Edge 1/LLM.
- Thiết kế schema metadata thống nhất cho bước merge (mã công ty, kỳ báo cáo, nguồn edge, số trang gốc).