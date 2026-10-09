# 🤖 Hướng Dẫn Kỹ Thuật Dành Cho AI Agent: Dự Án OpenBCTC
## (Producer Agent: OCR Engine, Anti-GIGO Auditor & Data Syncer)

---

## 1. Vai Trò & Sứ Mệnh (Role & Mission)
Bạn là **Producer Agent** trong hệ sinh thái xử lý BCTC hai tầng:
- **Tầng 1 (Bạn - OpenBCTC):** Tiếp nhận PDF BCTC (native/scanned), thực hiện OCR thị giác, trích xuất cấu trúc bảng biểu theo Thông tư 200, kiểm toán số học tự động bằng **17 đẳng thức Anti-GIGO**, quản lý giao diện duyệt HITL (Human-In-The-Loop) và **đóng gói/đồng bộ dữ liệu** sang Tầng 2.
- **Tầng 2 (Đối tác - OpenBCTC Copilot):** Hệ thống trợ lý AI đàm thoại, SQL Fact Engine, Qdrant Hybrid RAG và Visual Grounding.

> **Mục tiêu tối thượng:** Đảm bảo mọi tệp đầu ra đều đạt độ chính xác số học 100%, đúng chuẩn khế ước dữ liệu (Data Contract), tự động đồng bộ sang MongoDB GridFS & Collections của Copilot mà **không làm gián đoạn** tiến trình cục bộ nếu Copilot chưa sẵn sàng.

---

## 2. Khế Ước Dữ Liệu Đầu Ra (Data Contract)

Mỗi lần OpenBCTC chạy bóc tách cho doanh nghiệp `<COMPANY>` và năm `<YEAR>` (Ví dụ: `VNM`, `2025`), bạn phải đảm bảo sinh ra đầy đủ các tài sản sau tại thư mục cục bộ `outputs/<COMPANY>_<YEAR>/` và đồng bộ sang MongoDB:

| Tài Sản Dữ Liệu | Đường Dẫn Thực Tế Tại OpenBCTC | Đích Đến Tại MongoDB Copilot | Mục Đích Sử Dụng |
| :--- | :--- | :--- | :--- |
| **PDF BCTC Gốc** | `pdf_files/{company}_{year}.pdf` hoặc `data/uploads/...` | **GridFS:** `{company_lower}_{year}.pdf` | Stream nhanh cho Web UI để vẽ khung highlight Bounding Box |
| **Markdown BCTC Final** | `outputs/{company}_{year}/{company}_{year}_financial_report_final.md` | **GridFS:** `{company_lower}_{year}_final.md` | Cung cấp toàn văn & cấu trúc TOC Tree cho LLM Reasoning |
| **SQLite Facts DB** | `outputs/{company}_{year}/benchmark_{company}_{year}.db` | **GridFS:** `benchmark_{company_lower}_{year}.db`<br>*(Mount qua Volume)* | Cung cấp dữ liệu cho **Deterministic SQL Fact Engine** |
| **Cache JSON Blocks** | `outputs/{company}_{year}/cache/notes/page_*.json` | **Collection:** `document_blocks` | Cung cấp toạ độ `bbox` cho Hybrid Qdrant Vector RAG |
| **Benchmark Metrics** | `outputs/{company}_{year}/{company}_{year}_ocr_benchmark_metrics.json` | **Collection:** `ocr_benchmarks` | Giám sát chất lượng kiểm toán số học Anti-GIGO (17 đẳng thức) |
| **Ảnh Crop Bảng Biểu** | `outputs/{company}_{year}/cache/table_crops/*.png` | Thư mục cục bộ / Mount Volume tĩnh | Đối chiếu kiểm toán thị giác độ phân giải cao 200 DPI |

---

## 3. Chi Tiết Cấu Trúc Dữ Liệu Thực Tế (Schema Specifications)

### 3.1. Cấu trúc JSON Block (`cache/notes/page_*.json`)
Mỗi tệp JSON trong `cache/notes/` đại diện cho một trang tài liệu, chứa mảng các khối đối tượng kế thừa chuẩn `ParsedBlock` / `JSONBlock`:

```json
[
  {
    "block_id": "p14_mineru_txt_1",
    "block_type": "text",
    "page": 14,
    "content": "Mẫu B09-DN (Ban hành theo Thông tư số 200/2014/TT-BTC ngày 22 tháng 12 năm 2014 của Bộ Tài chính)",
    "bbox": [0.552, 0.129, 0.908, 0.179],
    "source": "local_ocr",
    "metadata": {
      "company": "VNM",
      "year": 2025,
      "engine": "mineru_vietocr",
      "is_note": true
    }
  },
  {
    "block_id": "p14_mineru_tbl_1",
    "block_type": "table",
    "page": 14,
    "content": "| Khoản mục | Năm nay | Năm trước |\n| :--- | :--- | :--- |\n| Tiền mặt | 1.200 | 950 |",
    "bbox": [0.120, 0.210, 0.450, 0.890],
    "source": "local_ocr",
    "metadata": {
      "company": "VNM",
      "year": 2025,
      "headers": ["Khoản mục", "Năm nay", "Năm trước"],
      "num_rows": 2,
      "num_cols": 3
    }
  }
]
```
> **Quy tắc Bounding Box:** Toạ độ chuẩn hóa trong khoảng `[0.0, 1.0]` theo thứ tự `[ymin, xmin, ymax, xmax]`.

---

### 3.2. Cấu trúc SQLite Database (`benchmark_<COMPANY>_<YEAR>.db`)
Tuân thủ nghiêm ngặt DDL trong [`src/database/schema.py`](file:///d:/OpenBCTC/src/database/schema.py), gồm 4 bảng và 5 Index:

#### 1. Bảng `companies`:
```sql
CREATE TABLE IF NOT EXISTS companies (
    code TEXT PRIMARY KEY,
    name TEXT,
    industry TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 2. Bảng `financial_statements`:
```sql
CREATE TABLE IF NOT EXISTS financial_statements (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    year INTEGER NOT NULL,
    period TEXT NOT NULL,
    statement_type TEXT DEFAULT 'CONSOLIDATED',
    source_file TEXT,
    is_balanced INTEGER DEFAULT 1,
    total_checks INTEGER DEFAULT 0,
    passed_checks TEXT DEFAULT '[]',
    failed_checks TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company) REFERENCES companies(code)
);
```

#### 3. Bảng `financial_facts` (Chứa 224 chỉ tiêu tài chính nguyên tử):
```sql
CREATE TABLE IF NOT EXISTS financial_facts (
    id TEXT PRIMARY KEY,
    prov_id TEXT NOT NULL,
    company TEXT NOT NULL,
    year INTEGER NOT NULL,
    period TEXT NOT NULL,
    period_type TEXT NOT NULL,
    concept TEXT NOT NULL,
    standard_code TEXT,
    raw_label TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT DEFAULT 'VND',
    page INTEGER,
    table_id TEXT,
    source TEXT DEFAULT 'pdfplumber',
    confidence REAL DEFAULT 1.0,
    verification_status TEXT DEFAULT 'UNCHECKED',
    verification_detail TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company) REFERENCES companies(code)
);
```

#### 4. Bảng `financial_ratios` (Chứa 13 chỉ số tài chính tính sẵn):
```sql
CREATE TABLE IF NOT EXISTS financial_ratios (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    year INTEGER NOT NULL,
    ratio_name TEXT NOT NULL,
    ratio_category TEXT NOT NULL,
    value REAL NOT NULL,
    formula TEXT NOT NULL,
    input_prov_ids TEXT DEFAULT '[]',
    is_deterministic INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company) REFERENCES companies(code)
);
```

#### 5. Hệ thống Indexes tối ưu tốc độ đọc:
```sql
CREATE INDEX IF NOT EXISTS idx_facts_company_year ON financial_facts(company, year);
CREATE INDEX IF NOT EXISTS idx_facts_concept ON financial_facts(concept);
CREATE INDEX IF NOT EXISTS idx_facts_prov_id ON financial_facts(prov_id);
CREATE INDEX IF NOT EXISTS idx_ratios_company_year ON financial_ratios(company, year);
CREATE INDEX IF NOT EXISTS idx_ratios_name ON financial_ratios(ratio_name);
```

---

## 4. Module Đồng Bộ Chuyên Trách: `CopilotSyncer`

Vị trí tệp: [`src/uploader/copilot_syncer.py`](file:///d:/OpenBCTC/src/uploader/copilot_syncer.py)

### 4.1. Quy Trình Thực Thi 6 Bước Của Syncer
1. **Kiểm tra cờ kích hoạt:** `ENABLE_COPILOT_SYNC` (mặc định: `true`). Nếu `false` thì bỏ qua.
2. **Kiểm tra thư viện:** Thử import `pymongo` và `httpx`. Nếu thiếu, ghi log cảnh báo và tiếp tục lưu cục bộ.
3. **Kết nối MongoDB an toàn:** Thiết lập `serverSelectionTimeoutMS=3000` (3 giây). Nếu không phản hồi:
   - Ghi log: `⚠️ Không thể kết nối MongoDB. Dữ liệu vẫn an toàn tại thư mục local!`
   - Trả về status `WARNING` (Tuyệt đối không ném ngoại lệ làm gián đoạn pipeline).
4. **Nạp GridFS (File nhị phân & văn bản lớn):**
   - Xóa file cũ cùng tên nếu có.
   - Nạp PDF: filename `{company_lower}_{year}.pdf` kèm `metadata={"company": COMPANY, "year": YEAR, "type": "pdf"}`
   - Nạp Markdown: filename `{company_lower}_{year}_final.md` kèm `metadata={"company": COMPANY, "year": YEAR, "type": "markdown"}`
   - Nạp SQLite: filename `benchmark_{company_lower}_{year}.db` kèm `metadata={"company": COMPANY, "year": YEAR, "type": "sqlite"}`
5. **Nạp Collections MongoDB:**
   - Collection `document_blocks`: Làm mới toàn bộ blocks của `company` và `year`. Mỗi block gắn thêm `company`, `year`, `source_file`.
   - Collection `ocr_benchmarks`: Upsert tài liệu metrics kiểm toán Anti-GIGO: `{"company": COMPANY, "year": YEAR, "metrics": ...}`.
6. **Kích hoạt Webhook tự động (Auto Ingestion Trigger):**
   - Endpoint: `POST {COPILOT_API_URL}/api/v1/ingest`
   - Payload: `{"company": "<COMPANY>", "year": <YEAR>}`
   - Timeout: 5.0 giây. Bắt toàn bộ lỗi HTTP/kết nối nếu Copilot API chưa bật.

---

## 5. Điểm Gắn Hook Trong Codebase OpenBCTC

Khi bảo trì hoặc mở rộng pipeline, bạn phải đảm bảo hook đồng bộ được gọi tại 2 vị trí:

### Điểm 1: Cuối hàm bóc tách toàn trình trong [`interface.py`](file:///d:/OpenBCTC/interface.py)
Sau khi hoàn tất bóc tách và ghi file metrics JSON:
```python
try:
    from src.uploader.copilot_syncer import CopilotSyncer
    syncer = CopilotSyncer()
    sync_res = syncer.sync_company_run(
        company=company,
        year=year,
        output_dir=run_dir,
        pdf_path=pdf_file,
        trigger_ingest=True,
    )
    if sync_res.get("status") == "SUCCESS":
        logger.info("✓ Đã đồng bộ tài nguyên tức thì sang OpenBCTC Copilot!")
except Exception as e:
    logger.warning("Không thể kích hoạt CopilotSyncer: %s", e)
```

### Điểm 2: Khi người dùng bấm lưu hoàn tất trên HITL Reviewer ([`serve_md_editor.py`](file:///d:/OpenBCTC/serve_md_editor.py))
Trong endpoint xử lý `/api/export_final`:
```python
# Sau khi xuất export_path (file *_financial_report_final.md):
try:
    from src.uploader.copilot_syncer import CopilotSyncer
    syncer = CopilotSyncer()
    if syncer.enabled:
        syncer.sync_company_run(
            company=company,
            year=year,
            output_dir=export_path.parent,
            trigger_ingest=True,
        )
except Exception as ex_sync:
    logger.warning("CopilotSyncer warning trong export_final: %s", ex_sync)
```

---

## 6. Cấu Hình Hạ Tầng Docker & Mạng Chung

Mạng nội bộ thống nhất giữa 2 dự án là **`openbctc-net`**.

Cấu hình tệp [`docker-compose.yml`](file:///d:/OpenBCTC/docker-compose.yml) của OpenBCTC:
```yaml
version: '3.8'

networks:
  openbctc-net:
    external: true  # Dùng chung mạng với OpenBCTC Copilot

services:
  openbctc-ocr:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: openbctc_ocr_engine
    restart: unless-stopped
    ports:
      - "8501:8501"
      - "8502:8502"
    environment:
      - MONGO_URI=mongodb://mongodb:27017
      - MONGO_DB=openbctc
      - COPILOT_API_URL=http://copilot-api:8000
      - ENABLE_COPILOT_SYNC=true
    volumes:
      - ./data:/app/data
      - ./outputs:/app/outputs
      - ./pdf_files:/app/pdf_files
    networks:
      - openbctc-net
```

---

## 7. Triết Lý Thiết Kế Lean Architecture Cho OpenBCTC Agent

Áp dụng hướng dẫn từ [`docs/agent_lean_architecture_guide.md`](file:///d:/OpenBCTC/docs/agent_lean_architecture_guide.md):

1. **Separation of Concerns (Phân tách trách nhiệm):**
   - Tầng OCR / Extraction chỉ làm đúng việc trích xuất ký tự và bounding box.
   - Tầng Verification Anti-GIGO là code logic xác định thuần túy (Pure Python Deterministic), không trộn lẫn logic LLM.
   - Tầng Syncer độc lập, không xâm lấn vào logic nghiệp vụ của OCR.
2. **Thin Nodes trong LangGraph:**
   - Tránh biến các node thành "God Functions". Mỗi node chỉ thực hiện một nhiệm vụ duy nhất và trả về state delta.
3. **Graceful Degradation (Suy giảm an toàn):**
   - Mọi tương tác mạng (MongoDB, Webhook, Vision API) đều phải có Timeout xác định và cơ chế Fallback an toàn về Local File System.

---

## 8. Quy Tắc Bất Di Bất Dịch Cho OpenBCTC Agent (Do's & Don'ts)

### ✅ NÊN LÀM (DO):
1. **Luôn bảo toàn bản lưu cục bộ:** Thư mục `outputs/<COMPANY>_<YEAR>/` là nguồn chân lý (Source of Truth) cho người dùng cơ bản. Toàn bộ file `.pdf`, `.md`, `.db`, `.json` phải tồn tại đầy đủ tại đây trước khi đồng bộ.
2. **Kiểm toán Anti-GIGO trước khi xuất bản SQLite:** Bắt buộc chạy 17 đẳng thức kiểm toán số học. Bảng `financial_statements` phải ghi nhận chính xác trạng thái `is_balanced` (1 hoặc 0).
3. **Ưu tiên bản duyệt `_final.md`:** Sau khi kiểm toán viên chỉnh sửa qua Web Editor (Port 8502), bản final phải tự động ghi đè bản cũ trên GridFS.
4. **Chuẩn hóa chữ hoa / chữ thường:** Mã công ty dùng in hoa (`VNM`) cho folder và database; chữ thường (`vnm_2025.pdf`) cho filename trên GridFS.

### ❌ TUYỆT ĐỐI TRÁNH (DON'T):
1. **Không làm treo pipeline vì lỗi mạng:** Tuyệt đối không để việc mất kết nối MongoDB hay Copilot API làm dừng tiến trình OCR.
2. **Không tự ý đổi tên Collection:** Tên collection blocks bắt buộc là **`document_blocks`**, không đổi thành `documents_json` hay `notes_blocks`.
3. **Không phát sinh số liệu ảo:** Nếu một khoản mục OCR bị mờ hoặc không nhận diện được, ghi nhận `confidence < 1.0` hoặc `UNCHECKED`, không tự động bịa số liệu.
