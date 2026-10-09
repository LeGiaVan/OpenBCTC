# ⚡ OpenBCTC AI — Bóc Tách Scan PDF Báo Cáo Tài Chính Việt Nam (PDF → Markdown)

<div align="center">

<p align="center">
  <img src="https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/Python-Dark.svg" width="45" height="45" alt="Python" />
  <img src="https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/PyTorch-Dark.svg" width="45" height="45" alt="PyTorch" />
  <img src="https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/Markdown-Dark.svg" width="45" height="45" alt="Markdown" />
  <img src="https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/FastAPI.svg" width="45" height="45" alt="FastAPI" />
  <img src="https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/SQLite.svg" width="45" height="45" alt="SQLite" />
</p>

### Chuyển đổi PDF BCTC quét sang Markdown chuẩn mực • Tốc độ < 5 Phút • 0 Đồng API Thuyết Minh
**Dual-Branch Ingestion • 100% Offline Local OCR • Anti-GIGO 17 Đẳng Thức Kế Toán • Kính Lúp Vision Zoom Tự Sửa Sai • Web HITL Editor 200 DPI**

<br/>

[![Status](https://img.shields.io/badge/Status-Production--Ready-10b981?style=for-the-badge&logo=checkmarx&logoColor=white)](#)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)](#)
[![CUDA](https://img.shields.io/badge/CUDA-GPU%20Accelerated-76b900?style=for-the-badge&logo=nvidia&logoColor=white)](#)
[![Google Gemini](https://img.shields.io/badge/Gemini-2.0%20Flash%20Vision-4285f4?style=for-the-badge&logo=google&logoColor=white)](#)
[![Local OCR](https://img.shields.io/badge/Notes%20OCR-0%20API%20Tokens-8b5cf6?style=for-the-badge&logo=gnubash&logoColor=white)](#)
[![License](https://img.shields.io/badge/License-MIT-f59e0b?style=for-the-badge)](#)

<br/>

[🚀 Trải Nghiệm Web App](#52-khởi-chạy-giao-diện-web-app-trực-quan-interfacepy) • [💻 Tech Stack](#23-ngăn-xếp-công-nghệ-technology-stack) • [📖 Hướng Dẫn Giao Diện](docs/guide_interface.md) • [⚡ Cài Đặt Nhanh](#51-cài-đặt-môi-trường) • [🏗️ Sơ Đồ Kiến Trúc](#21-sơ-đồ-luồng-bóc-tách-toàn-trình-end-to-end-flow) • [🛡️ 17 Đẳng Thức Anti-GIGO](#43-bộ-kiểm-toán-số-học-anti-gigo--kính-lúp-vision-zoom-sửa-sai) • [📊 Benchmark](#61-bảng-hiệu-năng-đo-lường-trên-bctc-vinamilk-2024-54-trang) • [🔗 Tích Hợp Copilot & Docker](#7-tích-hợp-hệ-sinh-thái-openbctc-copilot--docker-dual-storage)

---

</div>

> [!TIP]
> 🚀 **Bỏ qua kiến trúc, chạy thử ngay (3 phút):** [**Hướng Dẫn Cài Đặt & Sử Dụng Giao Diện Web App** ➔](docs/guide_interface.md)

## 🌟 Điểm Nổi Bật Cốt Lõi (Key Highlights)

<table align="center" width="100%">
<tr>
<td width="50%" valign="top">

### ⚡ Siêu Tốc & 0 Đồng Thuyết Minh
* **100% Local Vietnamese OCR**: RapidOCR + VietOCR GPU batch processing chạy hoàn toàn offline.
* **Tốc độ bóc tách 1.2s – 2.0s / trang**: Xử lý trọn vẹn tập tài liệu 54 trang dưới 5 phút.
* **0 Tokens Thuyết Minh**: Tiết kiệm 100% chi phí API đám mây, bảo mật tuyệt đối dữ liệu nội bộ.

</td>
<td width="50%" valign="top">

### 🛡️ Độc Quyền Anti-GIGO (17 Invariants)
* **17 Phương trình Kế toán Bất biến**: Tự động kiểm toán đối chiếu CĐKT, KQKD, LCTT theo TT 200/2014/TT-BTC.
* **Kính lúp Vision Zoom**: Tự động suy luận dòng lỗi, crop ảnh độ nét cao 200 DPI sửa số tại chỗ.
* **Zero Hallucination**: Cam kết số liệu tài chính cân khớp 100% trước khi xuất bản.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🎯 Trinh Sát Mục Lục (TOC Inspector)
* **Khắc phục lệch trang vật lý (`page_offset`)**: Tự động giải quyết triệt để vấn đề số trang in không khớp với file PDF scan.
* **Dual-Branch Ingestion**: Tự động phân luồng riêng cho BCTC Cốt lõi (Vision LLM) và Thuyết minh (Offline OCR).
* **Nối Bảng Đa Trang (Spanning Tables)**: Tự động ghép nối bảng dài liên tục, khử triệt để bảng rác 1 cột.

</td>
<td width="50%" valign="top">

### 🖥️ Dual Web UI & HITL Spreadsheet Review
* **Web Dashboard All-in-One (`Port 8501`)**: Kéo thả nạp PDF, tự nhận diện mã CK, theo dõi luồng log LangGraph thời gian thực.
* **Zero-Latency Table Editor (`Port 8502`)**: Cắt sẵn 39 ảnh crop bảng 200 DPI, đối chiếu song song và sửa số tức thì.
* **Xuất bản Markdown Chuẩn Hóa**: Cung cấp dữ liệu sạch cho FinTech RAG, LLM Agent và Data Warehouse.

</td>
</tr>
</table>

---

## ⚖️ Bảng So Sánh Giải Pháp (Why OpenBCTC?)

| Tiêu Chí Kỹ Thuật | Phương Pháp OCR Truyền Thống / pdfplumber | Cloud Vision Chung (LlamaParse, Unstructured) | 🌟 OpenBCTC AI |
| :--- | :---: | :---: | :---: |
| **Chi phí API Thuyết minh** | 0 VNĐ (nhưng vỡ bảng, dính chữ) | Hàng trăm ngàn tokens / file ($$$) | **0 VNĐ (100% Offline Local GPU)** |
| **Nhận diện số âm kế toán `(xxx)`** | Thường mất dấu ngoặc → Sai số dương | Dễ lẫn lộn dấu hoặc xé số qua dòng | **✅ 100% Chuẩn xác (Anti-GIGO Gate)** |
| **Bảo đảm Cân đối Kế toán** | ❌ Không kiểm tra | ❌ Ảo giác LLM (Hallucination) | **✅ 17 Đẳng thức TT200 tự kiểm toán** |
| **Cơ chế Tự Sửa Sai Số Học** | Thủ công bằng tay | Phải gửi lại cả trang (Full Re-OCR) | **🔍 Kính lúp Vision Zoom crop dòng cục bộ** |
| **Đối Chiếu Kiểm Tra Bảng Biểu** | Lật tìm thủ công trong PDF gốc | Xem Markdown thô không kèm ảnh gốc | **🖥️ Web Spreadsheet đối chiếu ảnh 200 DPI (0s delay)** |
| **Bảo mật Dữ liệu Tài chính** | Nội bộ | Tải dữ liệu nhạy cảm lên Cloud | **100% An toàn nội bộ cho Thuyết minh** |

---

## 📑 Mục Lục

- [1. Tổng Quan & Vấn Đề Nghiệp Vụ](#1-tổng-quan--vấn-đề-nghiệp-vụ)
- [2. Quy Trình Chuyển Đổi PDF → Markdown (Pipeline Architecture)](#2-quy-trình-chuyển-đổi-pdf--markdown-pipeline-architecture)
  - [2.1. Sơ đồ Luồng Bóc Tách Toàn Trình (End-to-End Flow)](#21-sơ-đồ-luồng-bóc-tách-toàn-trình-end-to-end-flow)
  - [2.2. Phân Tầng Trách Nhiệm Kỹ Thuật](#22-phân-tầng-trách-nhiệm-kỹ-thuật)
  - [2.3. Technology Stack](#23-ngăn-xếp-công-nghệ-technology-stack)
- [3. Cấu Trúc Thư Mục Dự Án (Project Structure)](#3-cấu-trúc-thư-mục-dự-án-project-structure)
- [4. Các Công Nghệ & Kỹ Thuật Trọng Tâm](#4-các-công-nghệ--kỹ-thuật-trọng-tâm)
  - [4.1. TOC Inspector: Trinh Sát Mục Lục & Căn Chỉnh Lệch Trang Vật Lý](#41-toc-inspector-trinh-sát-mục-lục--căn-chỉnh-lệch-trang-vật-lý)
  - [4.2. Dual-Branch Ingestion: Bóc Tách Song Song Cốt Lõi & Thuyết Minh](#42-dual-branch-ingestion-bóc-tách-song-song-cốt-lõi--thuyết-minh)
  - [4.3. Bộ Kiểm Toán Số Học Anti-GIGO & Kính Lúp Vision Zoom Sửa Sai](#43-bộ-kiểm-toán-số-học-anti-gigo--kính-lúp-vision-zoom-sửa-sai)
  - [4.4. Local Vietnamese OCR Thuyết Minh (100% Offline, 0 API Tokens)](#44-local-vietnamese-ocr-thuyết-minh-100-offline-0-api-tokens)
  - [4.5. Kiểm Toán Cấu Trúc Bảng & Giao Diện Web Editor (Human-in-the-Loop)](#45-kiểm-toán-cấu-trúc-bảng--giao-diện-web-editor-human-in-the-loop)
- [5. Hướng Dẫn Vận Hành & Khởi Chạy Nhanh (Quick Start)](#5-hướng-dẫn-vận-hành--khởi-chạy-nhanh-quick-start)
  - [5.1. Cài Đặt Môi Trường](#51-cài-đặt-môi-trường)
  - [5.2. Khởi Chạy Giao Diện Web App Trực Quan (`interface.py`)](#52-khởi-chạy-giao-diện-web-app-trực-quan-interfacepy)
  - [5.3. Quy Trình Vận Hành 4 Bước Khép Kín (Ai Cũng Có Thể Dùng)](#53-quy-trình-vận-hành-4-bước-khép-kín-ai-cũng-có-thể-dùng)
  - [5.4. Các Chế Độ Chạy Dòng Lệnh Nâng Cao (CLI Options)](#54-các-chế-độ-chạy-dòng-lệnh-nâng-cao-cli-options)
- [6. Kết Quả Đo Lường Thực Tế & Benchmark](#6-kết-quả-đo-lường-thực-tế--benchmark)
  - [6.1. Bảng Hiệu Năng Đo Lường Trên BCTC Vinamilk 2024 (54 Trang)](#61-bảng-hiệu-năng-đo-lường-trên-bctc-vinamilk-2024-54-trang)
  - [6.2. Đánh Giá Độ Chính Xác Cấu Trúc Bảng (49 Bảng Thuyết Minh Ground Truth)](#62-đánh-giá-độ-chính-xác-cấu-trúc-bảng-49-bảng-thuyết-minh-ground-truth)
  - [6.3. Các Tệp Đầu Ra Trọng Yếu](#63-các-tệp-đầu-ra-trọng-yếu)
- [7. Tích Hợp Hệ Sinh Thái OpenBCTC Copilot & Docker (Dual-Storage)](#7-tích-hợp-hệ-sinh-thái-openbctc-copilot--docker-dual-storage)
  - [7.1. Triết Lý Dual-Storage (Lưu Trữ Song Song)](#71-triết-lý-dual-storage-lưu-trữ-song-song)
  - [7.2. Khế Ước Dữ Liệu Đồng Bộ](#72-khế-ước-dữ-liệu-đồng-bộ)
  - [7.3. Hướng Dẫn Cấu Hình & Tự Động Kích Hoạt](#73-hướng-dẫn-cấu-hình--tự-động-kích-hoạt)
  - [7.4. Đóng Gói Docker & Kết Nối Chung Mạng Nội Bộ](#74-đóng-gói-docker--kết-nối-chung-mạng-nội-bộ)
- [8. Lộ Trình Phát Triển (Roadmap)](#8-lộ-trình-phát-triển-roadmap)

---

## 1. Tổng Quan & Vấn Đề Nghiệp Vụ

Dự án này được xây dựng với mục tiêu **Chuyển đổi các tập tin Báo cáo Tài chính (BCTC) định dạng PDF (scan hoặc digital) sang định dạng Markdown (`.md`) có cấu trúc chuẩn mực, sạch rác và số liệu cân đối 100%**.

### Thách Thức Khi Parse PDF Báo Cáo Tài Chính
1. **Dữ liệu phân mảnh & ranh giới phức tạp:** Tài liệu BCTC gồm trang bìa, báo cáo kiểm toán, 4 bảng số liệu cốt lõi (CĐKT, KQKD, LCTT) và hàng chục trang thuyết minh chi tiết. Số in trên mục lục không bao giờ khớp với số trang vật lý của file PDF.
2. **Lỗi OCR làm sai lệch số học:** Bỏ sót dấu ngoặc đơn số âm `(15.000.000)` → `+15.000.000`, nhầm lẫn ký tự số tương đồng (`8` ↔ `0`, `3` ↔ `8`), hoặc xé số qua dòng khiến bảng số mất hoàn toàn giá trị sử dụng.
3. **Bảng biểu vỡ khung & dính chữ:** Bảng thuyết minh đa cột, tiêu đề 2 tầng thường bị biến dạng thành bảng giả 1 cột hoặc tràn dòng khi parse thô.
4. **Chi phí & Độ trễ:** Việc gửi 50–60 trang ảnh scan lên Vision API tốn kém chi phí, dễ bị nghẽn quota (Rate limit) và tiềm ẩn rủi ro lộ bí mật thông tin tài chính doanh nghiệp.

### Giải Pháp Của OpenBCTC
Hệ thống cung cấp một luồng bóc tách khép kín:
* **Tự động phân luồng (Triage):** Dùng trinh sát mục lục để tách riêng các trang BCTC cốt lõi và các trang Thuyết minh.
* **Xử lý song song:** Dùng Vision-LLM cho các trang bảng cốt lõi và Local OCR Engine cục bộ (RapidOCR + VietOCR GPU) cho các trang thuyết minh (0 API tokens).
* **Kiểm toán số học toán học (Anti-Garbage In Garbage Out):** Áp dụng 17 phương trình kế toán bất biến Thông tư 200. Nếu phát hiện sai số, kích hoạt kính lúp Vision Zoom cắt ảnh dòng sửa lỗi tại chỗ.
* **Kiểm toán bảng biểu & Human-in-the-Loop Web Editor:** Tự động cắt trước ảnh crop 200 DPI của từng bảng và cung cấp giao diện Web Spreadsheet (Port 8502) để người dùng đối chiếu ảnh gốc - sửa bảng trực tiếp - xuất file Markdown cuối cùng.

---

## 2. Quy Trình Chuyển Đổi PDF → Markdown (Pipeline Architecture)

### 2.1. Sơ đồ Luồng Bóc Tách Toàn Trình (End-to-End Flow)

#### Phần 1: Phân Luồng & Trích Xuất Dữ Liệu (Input & Extraction Phase)

```mermaid
flowchart TD
    subgraph INGEST["1. TIẾP NHẬN & PHÂN LOẠI PDF (Triage Phase)"]
        PDF["📄 Tập tin BCTC PDF\n(Scan hoặc Digital Text)"] --> DETECT["PDF Type Detector\n(Đếm ký tự, bảng biểu & phân loại trang)"]
        DETECT --> TOC["TOC Inspector\n(Trinh sát mục lục & tính page_offset)"]
        TOC --> SPLIT{"Phân Luồng Ranh Giới\n(Dual-Branch Routing)"}
    end

    subgraph BRANCH1["2A. NHÁNH BCTC CỐT LÕI (Core Statements)"]
        SPLIT -->|"Trang 7 → 12\n(CĐKT, KQKD, LCTT)"| VISION_PREP["Trích xuất ảnh 150 DPI\n(PIL / pypdfium2)"]
        VISION_PREP --> VISION_LLM["Vision-LLM Engine\n(Gemini 2.0 Flash / Groq Fast-Failover)"]
        VISION_LLM --> TABLE_VAL["Table Validator & Number Cleaner\n(Bảo toàn header 2 tầng & số âm ngoặc đơn)"]
        TABLE_VAL --> CORE_BLOCKS["Danh sách ParsedBlock\n(Bảng cốt lõi chuẩn Markdown)"]
    end

    subgraph BRANCH2["2B. NHÁNH THUYẾT MINH BCTC (Notes - 100% Offline)"]
        SPLIT -->|"Trang 13 → 54\n(Thuyết minh chi tiết)"| DB_NET["RapidOCR DBNet Detection\n(Quét bounding boxes vùng văn bản & số)"]
        DB_NET --> TRIAGE_LINE{"Line Triage\nPhân loại dòng"}
        TRIAGE_LINE -->|"Dòng Số / Bảng"| RAPID_NUM["RapidOCR CPU/ONNX\n(Bảo toàn dấu chấm, phẩy & ngoặc)"]
        TRIAGE_LINE -->|"Dòng Tiếng Việt"| VIET_GPU["VietOCR Seq2Seq (Batch GPU N=16)\n(Nhận diện tiếng Việt chuẩn có dấu)"]
        RAPID_NUM & VIET_GPU --> POST_CLEAN["Tái tạo bảng & Làm sạch rác:\n• Number Stitcher (Hàn số xé ngang)\n• Column Projection (Căn mép phải x_max)\n• Anti-Pseudo-Table (Khử bảng giả 1 cột)\n• Boilerplate Stripper (Lọc mẫu B09-DN)"]
        POST_CLEAN --> NOTE_BLOCKS["Danh sách ParsedBlock\n(Văn bản & bảng thuyết minh sạch rác)"]
    end

    subgraph NORMALIZE["3. HỢP NHẤT & CHUẨN HÓA BẢN THẢO (Normalizer Phase)"]
        CORE_BLOCKS & NOTE_BLOCKS --> MERGE_SPAN["Nối Bảng Đa Trang (Spanning Tables)\n(Ghép liền mạch bảng trải dài nhiều trang)"]
        MERGE_SPAN --> SEC_DETECT["Section Detector (Monotonic State Machine)\n(Dựng cây tiêu đề phân cấp H2 → H3 → H4 → H5)"]
        SEC_DETECT --> INTERMEDIATE_MD["📝 Bản Thảo Markdown Toàn Văn Hợp Nhất\n(Sẵn sàng cho kiểm toán số học Anti-GIGO)"]
    end

    style INGEST fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#fff
    style BRANCH1 fill:#1e293b,stroke:#f59e0b,stroke-width:2px,color:#fff
    style BRANCH2 fill:#1e293b,stroke:#8b5cf6,stroke-width:2px,color:#fff
    style NORMALIZE fill:#1e293b,stroke:#10b981,stroke-width:2px,color:#fff
```

<details>
<summary>🔍 <b>Nhấp để xem sơ đồ ảnh gốc độ phân giải cao (Phase 1 Image)</b></summary>
<br>
<p align="center">
  <a href="images/readme_images_1.png" target="_blank">
    <img src="images/readme_images_1.png" alt="Sơ đồ Phân Luồng & Trích Xuất Dữ Liệu" width="100%" style="border-radius: 10px; border: 1px solid #30363d;" />
  </a>
</p>
</details>

---

#### Phần 2: Kiểm Toán Toán Học, Hậu Kiểm & Xuất Bản (Audit, Review & Export Phase)

```mermaid
flowchart TD
    subgraph PHASE3["PHASE 3: KIỂM TOÁN SỐ HỌC ANTI-GIGO & SỬA SAI"]
        INPUT_MD["📝 Bản Thảo Markdown Toàn Văn"] --> FACT_EXT["Fact Extractor\n(Ánh xạ 69 chỉ tiêu chuẩn Thông tư 200)"]
        FACT_EXT --> VERIFIER["AccountingVerifier\n(Kiểm tra 17 Đẳng Thức Kế Toán Bất Biến)"]
        
        VERIFIER --> CHECK_BALANCED{"Báo cáo cân đối?\n(is_balanced == True?)"}
        
        CHECK_BALANCED -->|"✅ ĐẠT (100% Cân khớp)"| RATIO_ENG["Formula Engine (Deterministic)\n(Tính 13 chỉ số: Thanh khoản, Đòn bẩy, Sinh lời, Z-Score)"]
        RATIO_ENG --> DB_SAVE[("SQLite Storage: finaudit.db\n(Lưu Facts, Ratios & Báo cáo kiểm toán)")]
        
        CHECK_BALANCED -->|"❌ LỆCH (Sai số OCR)"| ZOOM_GATE["Kích Hoạt Kính Lúp Vision Zoom"]
        
        subgraph ZOOM_LOOP["Cơ chế Vòng Lặp Đóng (Closed-Loop Correction)"]
            ZOOM_GATE --> DEDUCT["1. Suy Luận Loại Trừ (Deductive Elimination)\n(Trừ điểm phương trình con cân, khoanh vùng 1 dòng sai)"]
            DEDUCT --> CROP_4["2. Structured Table Cropper (4-Strategy)\n(Cắt dải ảnh dòng hẹp 200 DPI kèm header)"]
            CROP_4 --> VISION_READ["3. Vision-LLM Targeted Inspection\n(Đọc tập trung số âm, ngoặc đơn, số lem)"]
            VISION_READ --> HOT_PATCH["4. Hot-Patch tạm thời & Re-verify\n(Chỉ chấp nhận khi phương trình kế toán cân đối)"]
            HOT_PATCH --> CHECK_BALANCED
        end
    end

    subgraph PHASE4["PHASE 4: KIỂM TOÁN BẢNG & HUMAN-IN-THE-LOOP (HITL)"]
        DB_SAVE --> INSPECTOR["Table Inspector & Zero-Latency Cropper\n(Quét 39 bảng, cắt sẵn ảnh 200 DPI vào cache)"]
        INSPECTOR --> HITL_WEB["🌐 Human-in-the-Loop Web Editor (Port 8502)\n• Bên trái: Ảnh crop bảng gốc 200 DPI tức thì\n• Bên phải: Bảng Spreadsheet trực quan cho phép sửa số"]
        HITL_WEB --> FINAL_CONFIRM["Xác Nhận & Xuất Bản Markdown Hoàn Chỉnh"]
    end

    subgraph OUTPUTS["PHASE 5: TÀI LIỆU XUẤT BẢN & PHỤC VỤ HẠ TẦNG"]
        FINAL_CONFIRM --> OUT_MD["📄 vnm_financial_report_final.md (Toàn văn BCTC chuẩn mực)"]
        FINAL_CONFIRM --> OUT_REP["📊 vnm_ocr_benchmark_report.md (Báo cáo đo lường chi tiết)"]
        FINAL_CONFIRM --> DOWNSTREAM["🚀 Sẵn sàng cho Financial RAG / LLM Agent / Data Warehouse"]
    end

    style PHASE3 fill:#1e293b,stroke:#f59e0b,stroke-width:2px,color:#fff
    style ZOOM_LOOP fill:#0f172a,stroke:#ef4444,stroke-width:1px,stroke-dasharray: 5 5,color:#fff
    style PHASE4 fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#fff
    style OUTPUTS fill:#1e293b,stroke:#10b981,stroke-width:2px,color:#fff
```

<details>
<summary>🔍 <b>Nhấp để xem sơ đồ ảnh gốc độ phân giải cao (Phase 2 Image)</b></summary>
<br>
<p align="center">
  <a href="images/readme_images_2.png" target="_blank">
    <img src="images/readme_images_2.png" alt="Sơ đồ Kiểm Toán Toán Học, Hậu Kiểm & Xuất Bản" width="100%" style="border-radius: 10px; border: 1px solid #30363d;" />
  </a>
</p>
</details>

> [!NOTE]
> **Quy trình trọng tâm trong Phần 2:**
> * **Phase 3 (Audit & Compile):** Số liệu các bảng cốt lõi được rà soát qua **17 đẳng thức kế toán Thông tư 200** (`AccountingVerifier`). Nếu có sai số OCR, hệ thống kích hoạt kính lúp `VisionZoomCorrector` cắt dải ảnh dòng và kích hoạt Vision LLM sửa lỗi trực tiếp.
> * **Phase 4 (Review & Export):** Tự động rà soát cấu trúc 39 bảng và cắt sẵn ảnh crop 200 DPI (`TableInspector`), hỗ trợ chế độ **Human-in-the-Loop Web Editor** (Cổng 8502) trước khi xuất bản bản Markdown hoàn chỉnh.

---

### 2.2. Phân Tầng Trách Nhiệm Kỹ Thuật

| Phân Tầng | Modules Chính | Trách Nhiệm Trong Quá Trình Parse PDF → Markdown |
| :--- | :--- | :--- |
| **1. Trinh Sát & Phân Luồng** | [`toc_inspector.py`](src/agents/toc_inspector.py)<br>[`pdf_type_detector.py`](src/parser/pdf_type_detector.py) | Nhận diện PDF scan/text; trinh sát trang mục lục; tính toán độ lệch trang vật lý (`page_offset`) để phân định chính xác ranh giới các bảng BCTC cốt lõi và Thuyết minh. |
| **2. Bóc Tách Đa Nhánh** | [`ocr_pipeline.py`](src/parser/ocr_pipeline.py)<br>[`local_ocr.py`](src/parser/local_ocr.py)<br>[`text_parser.py`](src/parser/text_parser.py) | **BCTC Cốt lõi:** Gemini Flash Vision đọc bảng đa cột chính xác tuyệt đối.<br>**Thuyết minh:** RapidOCR phát hiện vùng text + VietOCR nhận diện tiếng Việt chạy GPU theo batch, hoàn toàn offline (0 tokens). |
| **3. Kiểm Toán & Sửa Sai** | [`accounting_verifier.py`](src/verifier/accounting_verifier.py)<br>[`vision_zoom_corrector.py`](src/verifier/vision_zoom_corrector.py) | Kiểm tra 17 đẳng thức số học kế toán bất biến. Khi có sai số, tự động suy luận loại trừ dòng nghi vấn, cắt ảnh độ phân giải cao và kích hoạt Vision LLM sửa lỗi cục bộ. |
| **4. Chuẩn Hóa Cấu Trúc Markdown** | [`normalizer.py`](src/parser/normalizer.py)<br>[`section_detector.py`](src/parser/section_detector.py)<br>[`ocr_postprocess.py`](src/parser/ocr_postprocess.py) | Ghép nối bảng đa trang (Spanning Tables), dựng cây tiêu đề Heading Markdown phân cấp (`#`, `##`, `###`), lọc bỏ các dòng rác hành chính lặp lại và khử bảng giả 1 cột. |
| **5. Kiểm Toán Bảng & HITL Review** | [`serve_md_editor.py`](serve_md_editor.py)<br>[`ingestion_graph.py`](src/agents/ingestion_graph.py) | Cắt sẵn toàn bộ ảnh crop bảng biểu 200 DPI. Cung cấp giao diện Web Spreadsheet để người dùng rà soát, đối chiếu song song ảnh gốc và chỉnh sửa bảng trước khi xuất bản bản Markdown cuối cùng. |

---

### 2.3. Ngăn Xếp Công Nghệ (Technology Stack)

Hệ thống được thiết kế theo kiến trúc hybrid kết hợp giữa **Orchestration Agentic Workflow**, **Vision-Language Models**, **Mô hình OCR Deep Learning Nội Bộ** và **Giao diện Web phi phụ thuộc** (Zero external web framework dependencies):

| Phân Tầng Kỹ Thuật | Công Nghệ / Thư Viện Cốt Lõi | Vai Trò & Nhiệm Vụ Trong Pipeline |
| :--- | :--- | :--- |
| **🤖 Agent Orchestration** | • **LangGraph** (`^0.2`)<br>• **LangChain Core** (`^0.3`) | Điều phối đồ thị trạng thái (`StateGraph`), phân luồng song song 2 nhánh, quản lý checkpoint bộ nhớ và vòng lặp tự sửa sai (Vision Zoom Loop). |
| **👁️ Vision LLM Core** | • **Google Gemini 2.0 Flash Vision**<br>• **Groq Llama 3.2 Vision** (Fallback) | Bóc tách 6 trang BCTC cốt lõi; tái tạo cấu trúc bảng biểu đa cột, header nhiều tầng; Fast-Failover tự động khi chạm rate-limit. |
| **⚡ Local Vietnamese OCR** | • **RapidOCR (DBNet)**<br>• **VietOCR (Transformer Seq2Seq)** | **100% Offline, 0 tokens API**: Phát hiện vùng text và nhận diện tiếng Việt có dấu chuẩn xác cho toàn bộ ~40 trang Thuyết minh. |
| **🔥 Deep Learning Acceleration** | • **PyTorch** (`^2.1`)<br>• **NVIDIA CUDA** (`cu121`) | Tăng tốc GPU cho VietOCR xử lý theo lô (Batch $N=16$), tối ưu hóa VRAM và tự động giải phóng bộ nhớ rác (Active Eviction). |
| **📑 PDF & Vision Processing** | • **PyMuPDF (fitz)**<br>• **pdfplumber** (`^0.11`)<br>• **pdf2image / Poppler** (200 DPI) | Render PDF sang ảnh raster độ phân giải cao 200 DPI, trích xuất text/vector metadata native, cắt dải ảnh dòng phục vụ kính lúp Vision Zoom. |
| **🛡️ Schema & Validation** | • **Pydantic v2** (`^2.0`)<br>• **Pydantic-Settings** | Định nghĩa cấu trúc dữ liệu nghiêm ngặt: `ParsedBlock`, `Section`, `FinancialFact`, tự động đọc cấu hình an toàn từ `.env`. |
| **💾 Relational Storage** | • **SQLite 3** (Python Native)<br>• **DDL Kế toán chuẩn hóa** | Lưu trữ quan hệ facts tài chính, 13 chỉ số tài chính deterministic và toàn bộ báo cáo lịch sử kiểm toán 17 đẳng thức Thông tư 200. |
| **🌐 Web HITL Interface** | • **Vanilla HTML5 & Modern CSS3**<br>• **Native JavaScript (ES6+)**<br>• **Marked.js** (Client Markdown Preview) | Giao diện Web App tương tác (Port 8501) và Table Spreadsheet Reviewer (Port 8502) siêu nhẹ, zero framework bloat, stream log thời gian thực. |
| **📊 Benchmark & Metrics** | • **TEDS-Struct Algorithm**<br>• **Custom Tree AST Parser** | Đo lường độ tương đồng cấu trúc bảng theo chuẩn quốc tế Document AI, tính toán Span F1, Col/Row Accuracy trên 49 bảng Ground Truth. |
| **🧪 Testing & Code Quality** | • **Pytest / Pytest-asyncio**<br>• **Ruff** (`^0.4`) | Bộ kiểm thử tự động toàn diện bao phủ 100% logic kế toán; linter & formatter mã nguồn chuẩn mực. |

> [!NOTE]
> **Khả năng tương thích phần cứng (Hardware Agnostic):**
> * **Có GPU NVIDIA (CUDA):** Kích hoạt VietOCR Batch GPU Acceleration ($N=16$), tốc độ bóc tách đạt **1.2s – 2.0s / trang**.
> * **Chỉ có CPU (Intel, AMD, Apple Silicon):** Hệ thống tự động chuyển sang CPU Fallback, tốc độ bóc tách đạt **3.5s – 5.0s / trang**, vẫn bảo đảm 100% độ chính xác và 0 tốn phí API token.

---

## 3. Cấu Trúc Thư Mục Dự Án (Project Structure)

<details open>
<summary><b>📂 Nhấp để xem sơ đồ cấu trúc thư mục toàn diện</b></summary>

```text
OpenBCTC_AI/
├── interface.html                        # 🌐 GIAO DIỆN WEB TRỰC QUAN: Nạp PDF, giám sát tiến trình, review bảng & xuất file MD
├── interface.py                          # 🚀 ĐIỂM VÀO DUY NHẤT: Web Server (Port 8501) & CLI Engine điều khiển toàn bộ pipeline
├── serve_md_editor.py                    # 🌐 Máy chủ Web Table Editor (HITL) đối chiếu ảnh crop 200 DPI (Port 8502)
├── docs/                                 # Tài liệu đặc tả kiến trúc kỹ thuật chuyên sâu
│   ├── guide_interface.md                # 📖 Hướng dẫn cài đặt nhanh & vận hành giao diện Web App
│   ├── fact_verifier_logic.md            # Đặc tả chi tiết 17 đẳng thức kế toán & ma trận suy luận
│   ├── notes_ocr_performance_optimization.md # Kỹ thuật tối ưu hóa batch GPU & giải phóng RAM
│   ├── section_detector_architecture.md  # Cây phân cấp ngữ nghĩa & State machine nhận diện Heading
│   ├── self_correction_mechanism.md      # Đặc tả cơ chế kính lúp tự sửa sai Agentic Vision Zoom
│   └── vision_zoom.md                    # Thuật toán cắt ảnh dòng 4 tầng Waterfall
├── evaluation_table/                     # Bộ công cụ Benchmark cấu trúc 49 bảng Ground Truth
│   ├── evaluator.py                      # Động cơ benchmark chính (TEDS-Struct, Col/Row Acc, Span F1)
│   ├── metrics.py                        # Triển khai thuật toán TEDS-Struct & Span F1
│   ├── converter.py                      # Trích xuất Markdown sang HTML AST phục vụ TEDS
│   ├── serve_reviewer.py                 # Giao diện gán nhãn và đối chiếu Ground Truth (Port 8503)
│   ├── manifest.json                     # Metadata định danh 49 bảng (bbox, số hàng/cột, trang)
│   ├── ground_truth/                     # 49 tệp bảng biểu chuẩn hóa đối chứng (.md)
│   ├── predictions/                      # 49 tệp bảng biểu dự đoán từ pipeline OCR (.md)
│   ├── images/                           # 49 ảnh crop bảng đối chứng 200 DPI (.png)
│   └── reports/                          # Báo cáo đo lường chi tiết (report_latest.md, report.json)
├── images/                               # Biểu đồ kiến trúc & hình ảnh kiểm chuẩn
│   ├── interface/                        # 8 ảnh chụp giao diện Web App 4 bước vận hành
│   ├── 17_checks.png                     # Minh họa 17 bài kiểm tra kế toán Thông tư 200
│   ├── local_ocr.png                     # Sơ đồ luồng bóc tách Thuyết minh Local OCR
│   ├── logic_check.png                   # Sơ đồ suy luận loại trừ nghi vấn (Deductive Localization)
│   ├── section_workflow.png              # Quy trình trích xuất phân đoạn cây ngữ nghĩa
│   └── vision_zoom_corrector.png         # Sơ đồ vòng lặp đóng kính lúp sửa sai cục bộ
├── src/                                  # Mã nguồn nghiệp vụ cốt lõi
│   ├── config.py                         # Cấu hình tập trung bằng Pydantic-settings
│   ├── models.py                         # Khung dữ liệu Pydantic v2 (ParsedBlock, Section, FinancialFact...)
│   ├── agents/                           # Tầng tác nhân điều phối (LangGraph Orchestration)
│   │   ├── ingestion_graph.py            # LangGraph StateGraph tích hợp phân luồng 2 nhánh, zoom & HITL review
│   │   ├── ingestion_state.py            # Định nghĩa State Schema cho tiến trình Ingestion
│   │   └── toc_inspector.py              # Trinh sát Mục lục & Tính toán vật lý Page Offset
│   ├── database/                         # Tầng lưu trữ CSDL quan hệ
│   │   ├── db_manager.py                 # Quản lý kết nối, upsert Facts, Ratios và Verification Reports
│   │   └── schema.py                     # DDL SQLite chuẩn hóa cho lưu trữ BCTC
│   ├── engine/                           # Tầng tính toán chỉ số định lượng
│   │   └── formula_engine.py             # 13 chỉ số tài chính tính bằng Python thuần (Deterministic)
│   ├── extractor/                        # Tầng bóc tách & ánh xạ bản thể học kế toán
│   │   ├── fact_extractor.py             # Trích xuất FinancialFacts từ khối bảng Markdown
│   │   └── ontology.py                   # Bản đồ Ontology 69 chỉ tiêu chuẩn Thông tư 200/2014/TT-BTC
│   ├── parser/                           # Tầng trích xuất & chuyển đổi tài liệu PDF -> Markdown
│   │   ├── block_classifier.py           # Phân loại khối dữ liệu (Rule-based 80% + LLM fallback 20%)
│   │   ├── local_ocr.py                  # Local Offline OCR Engine (RapidOCR + VietOCR Batch GPU)
│   │   ├── normalizer.py                 # Hợp nhất khối và nối bảng biểu đa trang (Spanning Tables)
│   │   ├── ocr_pipeline.py               # VisionOCRPipeline (Gemini Fast-Failover & Checkpoint Cache)
│   │   ├── ocr_postprocess.py            # Khử nhiễu số, lọc boilerplate hành chính và bảng rác
│   │   ├── pdf_parser.py                 # Bộ điều phối facade trích xuất PDF cấp cao
│   │   ├── pdf_type_detector.py          # Phân loại trang: Native Text vs Scanned Image
│   │   ├── section_detector.py           # Bộ dựng cây phả hệ ngữ nghĩa (H2 -> H5) kèm Monotonicity Guards
│   │   └── table_utils.py                # Xử lý định dạng bảng số tài chính, header 2 tầng
│   └── verifier/                         # Tầng tự kiểm toán & sửa sai thông minh
│       ├── accounting_verifier.py        # Động cơ kiểm toán số học 17 Đẳng thức Kế toán TT200
│       └── vision_zoom_corrector.py      # Kính lúp cục bộ: StructuredTableCropper + Vision-LLM Hot-patch
├── tests/                                # Bộ kiểm thử tự động toàn diện
├── outputs/                              # TÀI LIỆU MARKDOWN XUẤT BẢN & CƠ SỞ DỮ LIỆU
│   └── <mã_ck>_<năm>/                   # Thư mục gói tài sản theo từng doanh nghiệp & kỳ báo cáo
│       ├── <mã>_<năm>_financial_report_final.md # Toàn văn BCTC Markdown hoàn thiện sau HITL
│       ├── benchmark_<mã>_<năm>.db       # CSDL SQLite Facts (224 facts) & Ratios (13 chỉ số)
│       ├── <mã>_<năm>_ocr_benchmark_report.md  # Báo cáo đo lường & kiểm toán 17 đẳng thức Anti-GIGO
│       ├── <mã>_<năm>_ocr_benchmark_metrics.json # Dữ liệu Benchmark JSON máy đọc
│       └── cache/                        # Cache JSON blocks có toạ độ bbox & ảnh crop bảng 200 DPI
├── Intergration_w_Copilot.md             # 🚀 Kế hoạch & Hướng dẫn tích hợp Dual-Storage sang OpenBCTC Copilot
└── scripts/                              # Các công cụ script chuyên biệt
```

</details>

---

## 4. Các Công Nghệ & Kỹ Thuật Trọng Tâm

### 4.1. TOC Inspector: Trinh Sát Mục Lục & Căn Chỉnh Lệch Trang Vật Lý

Trong hầu hết các tệp PDF BCTC, **số trang in trên mục lục không trùng với số thứ tự trang vật lý của file PDF** (do các trang bìa trước, trang mục lục hoặc thư ngỏ không đánh số).

[`TOCInspector`](src/agents/toc_inspector.py) giải quyết vấn đề này qua 3 bước:
1. **Phát hiện Mục lục:** Quét 3–5 trang đầu tìm bảng mục lục bằng từ khóa `MỤC LỤC`, `BÁO CÁO TÌNH HÌNH TÀI CHÍNH` kết hợp `THUYẾT MINH`.
2. **Khôi phục số trang dính OCR:** Tự động tách các số trang bị dính do OCR: `'68'` → `(6, 8)`; `'1253'` → `(12, 53)`.
3. **Thuật toán Anchor Search:** Tìm kiếm mục neo thực tế trong các trang kế tiếp để tính độ lệch trang vật lý:
   $$\Delta_{\text{page}} = P_{\text{actual}} - P_{\text{printed}}$$
   > 💡 **Quy tắc code:** `page_offset = p_num_thực_tế - first_printed_page`

Nhờ đó, hệ thống phân luồng ranh giới chính xác 100%:
* **Core Statements (BCTC Cốt lõi):** Trang 7 → 12.
* **Notes (Thuyết minh BCTC):** Trang 13 → 54.

---

### 4.2. Dual-Branch Ingestion: Bóc Tách Song Song Cốt Lõi & Thuyết Minh

Để tối ưu chi phí và độ chính xác, hệ thống phân chia tài liệu thành 2 nhánh xử lý chuyên biệt:

* **Nhánh 1: BCTC Cốt Lõi (Vision-LLM Pipeline):**
  * Xử lý 6 trang bảng số cốt lõi (Bảng cân đối kế toán, Kết quả kinh doanh, Lưu chuyển tiền tệ).
  * Sử dụng Gemini Flash Vision hoặc Groq Vision với cơ chế Fast-Failover.
  * Tái tạo hoàn hảo các bảng đa cột, header nhiều tầng phức tạp sang định dạng Markdown table.
* **Nhánh 2: Thuyết Minh BCTC (Local Offline OCR):**
  * Xử lý toàn bộ ~40 trang thuyết minh còn lại.
  * Chạy **100% Offline cục bộ** bằng RapidOCR (Text Detection DBNet) kết hợp VietOCR (Text Recognition) tăng tốc trên GPU CUDA.
  * **Chi phí API: 0 Tokens (Hoàn toàn miễn phí & bảo mật tuyệt đối).**

---

### 4.3. Bộ Kiểm Toán Số Học Anti-GIGO & Kính Lúp Vision Zoom Sửa Sai

Để đảm bảo số liệu trên bảng Markdown chính xác tuyệt đối (Zero Hallucination), OpenBCTC tích hợp **Bộ kiểm toán 17 đẳng thức kế toán bất biến** ([`accounting_verifier.py`](src/verifier/accounting_verifier.py)) theo Thông tư 200/2014/TT-BTC:

```mermaid
flowchart TD
    subgraph BS["1. BẢNG CÂN ĐỐI KẾ TOÁN (B01-DN)"]
        direction TB
        C1["Check 1: Mã 270 (Tổng tài sản) == Mã 440 (Tổng nguồn vốn)"]
        C2["Check 2: Mã 270 == Mã 100 (TS Ngắn hạn) + Mã 200 (TS Dài hạn)"]
        C3["Check 3: Mã 100 == ∑ Mã 110..150 (Tiền + ĐT ngắn + Phải thu + Tồn kho + TS khác)"]
        C4["Check 4: Mã 200 == ∑ Mã 210..260 (Phải thu dài + TSCĐ + BĐS + Dở dang + ĐT dài + khác)"]
        C5["Check 5: Mã 440 == Mã 300 (Nợ phải trả) + Mã 400 (Vốn chủ sở hữu)"]
        C6["Check 6: Mã 300 == Mã 310 (Nợ ngắn hạn) + Mã 330 (Nợ dài hạn)"]
        C1 --- C2 --- C3 --- C4 --- C5 --- C6
    end

    subgraph IS["2. KẾT QUẢ KINH DOANH (B02-DN)"]
        direction TB
        C7["Check 7: Mã 10 (Doanh thu thuần) == Mã 01 (Doanh thu gộp) - Mã 02 (Giảm trừ)"]
        C8["Check 8: Mã 20 (Lợi nhuận gộp) == Mã 10 - Mã 11 (Giá vốn hàng bán)"]
        C9["Check 9: Mã 30 (LN thuần HĐKD) == Mã 20 + 21 - 22 - 25 - 26"]
        C10["Check 10: Mã 40 (Lợi nhuận khác) == Mã 31 (Thu nhập khác) - Mã 32 (Chi phí khác)"]
        C11["Check 11: Mã 50 (Tổng LN trước thuế) == Mã 30 + Mã 40"]
        C12["Check 12: Mã 60 (LN sau thuế) == Mã 50 - Mã 51 (Thuế hiện hành) - Mã 52 (Thuế hoãn lại)"]
        C7 --- C8 --- C9 --- C10 --- C11 --- C12
    end

    subgraph CF["3. LƯU CHUYỂN TIỀN TỆ (B03-DN)"]
        direction TB
        C13["Check 13: Mã 50 (LCTT Thuần) == Mã 20 (HĐKD) + Mã 30 (HĐĐT) + Mã 40 (HĐTC)"]
        C14["Check 14: Mã 70 (Tiền cuối kỳ) == Mã 60 (Tiền đầu kỳ) + Mã 50 + Mã 61 (Ảnh hưởng tỷ giá)"]
        C15["Check 15: Mã 40 (LCTT HĐTC) == 31 - 32 + 33 - 34 - 35 - 36 (6 mục con tài chính)"]
        C13 --- C14 --- C15
    end

    subgraph CROSS["4. ĐỐI CHIẾU CHÉO LIÊN BẢNG (Cross-Statement Checks)"]
        direction TB
        C16["Check 16: LCTT Mã 70 (Tiền cuối kỳ) == CĐKT Mã 110 (Tiền & Tương đương tiền)"]
        C17["Check 17: LCTT Mã 01 (LN Trước Thuế Gián Tiếp) == KQKD Mã 50"]
    end

    BS -.->|"Mã 110"| C16
    CF -.->|"Mã 70"| C16

    IS -.->|"Mã 50"| C17
    CF -.->|"Mã 01"| C17

    style BS fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#fff
    style IS fill:#1e293b,stroke:#10b981,stroke-width:2px,color:#fff
    style CF fill:#1e293b,stroke:#f59e0b,stroke-width:2px,color:#fff
    style CROSS fill:#1e293b,stroke:#ec4899,stroke-width:2px,color:#fff
```

<details>
<summary>🔍 <b>Nhấp để xem sơ đồ ảnh 17 Đẳng Thức gốc (17 Checks Image)</b></summary>
<br>
<p align="center">
  <a href="images/17_checks.png" target="_blank">
    <img src="images/17_checks.png" alt="17 Đẳng Thức Kế Toán Thông tư 200" width="85%" style="border-radius: 8px; border: 1px solid #30363d;" />
  </a>
</p>
</details>

* `Doanh thu thuần (10) = Doanh thu gộp (01) - Các khoản giảm trừ (02)`
* `Lợi nhuận gộp (20) = Doanh thu thuần (10) - Giá vốn hàng bán (11)`
* `Tổng tài sản (270) = Tài sản ngắn hạn (100) + Tài sản dài hạn (200)`
* `Tổng nguồn vốn (440) = Nợ phải trả (300) + Vốn chủ sở hữu (400)`
* `Tổng tài sản (270) == Tổng nguồn vốn (440)`
* *(và 12 đẳng thức số học khác cho Lợi nhuận trước/sau thuế và Lưu chuyển tiền tệ)*

#### Cơ Chế Kính Lúp Vision Zoom Tự Sửa Sai (Closed-Loop Correction)
Khi một phương trình không cân, hệ thống kích hoạt [`VisionZoomCorrector`](src/verifier/vision_zoom_corrector.py):
1. **Deductive Localization:** Suy luận loại trừ để xác định chính xác dòng bảng bị OCR đọc sai (không OCR lại cả trang).
2. **Structured Table Cropper:** Cắt riêng dải ảnh dòng số liệu đó ở độ phân giải 200 DPI bằng thuật toán 4-Strategy Waterfall.
3. **Targeted Inspection:** Gọi Vision LLM đọc lại dải ảnh cắt nhỏ với prompt chuyên biệt cho dấu ngoặc đơn số âm.
4. **Hot-patch & Re-verify:** Thay thế số vào bảng Markdown và kiểm toán lại. Chỉ chấp nhận thay đổi khi phương trình kế toán cân khớp 100%.

```mermaid
flowchart TD
    Start(["🚨 AccountingVerifier: Phát Hiện Sai Số (is_balanced == False)"]) --> Step1["1. Suy Luận Loại Trừ (Deductive Elimination)\nidentify_suspect_facts()"]

    subgraph S1 ["Giai Đoạn 1: Khoanh Vùng Thủ Phạm Số Học"]
        Step1 --> Penalty["Cộng điểm phạt các bài kiểm tra thất bại (+10 điểm)"]
        Penalty --> Deduct["Trừ điểm minh oan phương trình con đạt chuẩn (-15 điểm)"]
        Deduct --> CrossDeduct["Phân xử đối chiếu chéo liên bảng BS vs CF (+15 điểm vào dòng lệch)"]
        CrossDeduct --> Rank["Xếp hạng và chọn Top 1-2 Fact có điểm nghi ngờ cao nhất"]
    end

    Rank --> Loop{"Lặp từng Fact nghi vấn\n(Tối đa 2 lần thử)"}

    subgraph S2 ["Giai Đoạn 2: Định Vị Dòng & Cắt Ảnh 4-Strategy Waterfall"]
        Loop -->|"Fact nghi vấn"| Cropper["StructuredTableCropper (locate_and_crop_row)"]
        Cropper --> Strategy{"4 Chiến Lược Định Vị:\n1. Bounding Box Table gốc\n2. Cột Mã Số Thông tư 200 (X: 28%-52%)\n3. Khớp Fuzzy Tên Khoản Mục (X < 42%)\n4. OpenCV Horizontal Lines + Local OCR"}
        Strategy --> CropImage["Cắt dải ảnh dòng hẹp 200 DPI\n(Tạo ảnh Composite kèm Header bảng)"]
        CropImage --> QualityGate{"Quality Gate:\nKiểm tra ảnh trắng / rác?"}
        QualityGate -->|"Không đạt"| Loop
        QualityGate -->|"Đạt chuẩn"| Step3["3. Targeted Inspection: Gửi dải ảnh cho Vision LLM\n(Prompt chuyên biệt: Bắt số âm ngoặc đơn, số lem)"]
    end

    subgraph S3 ["Giai Đoạn 3: Hot-Patch Tạm Thời & Re-Verify"]
        Step3 --> ExtractVal["Trích xuất giá trị số mới (value_new)"]
        ExtractVal --> CheckDiff{"Khác số cũ\n> tolerance?"}
        CheckDiff -->|"Không"| Loop
        CheckDiff -->|"Có số mới"| HotPatch["Hot-patch tạm thời: fact.value = value_new"]
        HotPatch --> ReVerify["AccountingVerifier.verify_facts() lại toàn bộ"]
        ReVerify --> CheckBalanced{"BCTC Đã Cân Đối 100%?"}
        CheckBalanced -->|"✅ CÂN ĐỐI"| Success["✅ Chấp nhận sửa đổi\nGhi correction_history & Lưu SQLite DB"]
        CheckBalanced -->|"❌ VẪN LỆCH"| Rollback["⚠️ Rollback an toàn: fact.value = value_old"]
        Rollback --> Loop
    end

    Loop -->|"Hết lượt thử"| Warn(["⚠️ Cảnh Báo: Chuyển sang Web HITL Reviewer (Port 8502)"])
    Success --> End(["🎉 BCTC ĐẠT CÂN ĐỐI 100% KHÔNG CÒN GIGO"])

    style Start fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#fff
    style S1 fill:#1e293b,stroke:#3b82f6,stroke-width:1px,color:#fff
    style S2 fill:#1e293b,stroke:#f59e0b,stroke-width:1px,color:#fff
    style S3 fill:#1e293b,stroke:#10b981,stroke-width:1px,color:#fff
    style End fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#fff
    style Warn fill:#78350f,stroke:#f59e0b,stroke-width:2px,color:#fff
```

<details>
<summary>🔍 <b>Nhấp để xem sơ đồ ảnh Vision Zoom gốc (Vision Zoom Image)</b></summary>
<br>
<p align="center">
  <a href="images/vision_zoom_corrector.png" target="_blank">
    <img src="images/vision_zoom_corrector.png" alt="Cơ chế Kính lúp Vision Zoom Sửa Sai" width="60%" style="border-radius: 8px; border: 1px solid #30363d;" />
  </a>
</p>
</details>

---

### 4.4. Local Vietnamese OCR Thuyết Minh (100% Offline, 0 API Tokens)

Xử lý thuyết minh BCTC đạt tốc độ cao và ổn định nhờ 4 kỹ thuật tối ưu hóa độc quyền ([`local_ocr.py`](src/parser/local_ocr.py)):

```mermaid
flowchart LR
    SCAN_PAGE["📄 Trang Thuyết Minh Scan\n(PIL Image 180 DPI)"] --> DBNET["RapidOCR DBNet\nText Detection\n(Tách bounding boxes)"]
    
    DBNET --> TRIAGE{"Triage Phân Loại\nDòng Thông Minh"}
    
    TRIAGE -->|"Dòng Số / Tiền tệ / Ngoặc âm\n(\\d+, VND, USD, -)"| RAPID_ONNX["RapidOCR ONNX (CPU)\n(Bảo toàn 100% dấu chấm,\ndấu phẩy & ngoặc đơn)"]
    
    TRIAGE -->|"Dòng Chữ Tiếng Việt"| BATCH_CROPS["Gom dải ảnh dòng\nvào batch_crops"]
    BATCH_CROPS --> VIET_GPU["VietOCR Batch Inference\n(CUDA GPU, BATCH_SIZE=16)\n1 Forward Pass trên Tensor Cores"]
    
    RAPID_ONNX & VIET_GPU --> TABLE_RECON["Tái Tạo Bảng Biểu & Gom Cụm Bbox"]
    
    subgraph CLEANUP["HẬU XỬ LÝ & LÀM SẠCH CẤU TRÚC TOÀN DIỆN"]
        TABLE_RECON --> STITCHER["Number Stitcher\n(Hàn gắn số bị xé ngang qua dòng:\n'23.225' + '734.296' → '23.225.734.296')"]
        STITCHER --> PROJECTION["Right-Aligned Column Projection\n(Căn chỉnh mép phải x_max theo chuẩn kế toán)"]
        PROJECTION --> ANTI_PSEUDO["Anti-Pseudo-Table Guard\n(Khử 100% bảng giả 1 cột do OCR nhầm văn xuôi)"]
        ANTI_PSEUDO --> STRIPPER["Boilerplate Stripper\n(Lọc bỏ > 400 dòng rác hành chính, Thông tư 200, Mẫu B)"]
    end
    
    STRIPPER --> MEM_EVICT["Active Memory Eviction\n(torch.cuda.empty_cache() & gc.collect)\nGiữ RAM ổn định ~1.2 GB"]
    MEM_EVICT --> OUTPUT_BLOCKS["✅ Danh Sách ParsedBlock Chuẩn Hóa\n(Phục vụ ghép nối Spanning Tables & RAG)"]

    style SCAN_PAGE fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#fff
    style TRIAGE fill:#1e293b,stroke:#f59e0b,stroke-width:2px,color:#fff
    style CLEANUP fill:#1e293b,stroke:#8b5cf6,stroke-width:2px,color:#fff
    style MEM_EVICT fill:#1e293b,stroke:#10b981,stroke-width:2px,color:#fff
    style OUTPUT_BLOCKS fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#fff
```

<details>
<summary>🔍 <b>Nhấp để xem sơ đồ ảnh Local OCR gốc (Local OCR Image)</b></summary>
<br>
<p align="center">
  <a href="images/local_ocr.png" target="_blank">
    <img src="images/local_ocr.png" alt="Local OCR Pipeline Architecture" width="100%" style="border-radius: 8px; border: 1px solid #30363d;" />
  </a>
</p>
</details>

1. **Intelligent Line Triage:** Dòng thuần số/mã hiệu được nhận diện nhanh bằng RapidOCR CPU/ONNX; chỉ những dòng văn bản tiếng Việt phức tạp mới chuyển sang VietOCR GPU.
2. **VietOCR Batch GPU Acceleration:** Xử lý theo lô ($N = 16$ dòng ảnh) trên CUDA GPU, rút ngắn thời gian bóc tách từ ~8.5s xuống còn **1.2s – 2.0s / trang**.
3. **Active Memory Eviction:** Tự động gọi `torch.cuda.empty_cache()` và thu gom rác sau mỗi trang, duy trì dung lượng RAM ổn định ở mức **~1.2 GB**, triệt tiêu hoàn toàn nguy cơ tràn bộ nhớ (OOM).
4. **Anti-Pseudo-Table Guard & Number Stitcher:** Lọc sạch các bảng giả 1 cột do OCR bắt nhầm đoạn văn; tự động nối các số bị xé dòng (`23.225` + `734.296` → `23.225.734.296`).

---

### 4.5. Kiểm Toán Cấu Trúc Bảng & Giao Diện Web Editor (Human-in-the-Loop)

Sau khi tổng hợp tài liệu Markdown toàn văn, OpenBCTC cung cấp một bước kiểm định chất lượng bảng biểu toàn diện:

1. **Table Inspector & Zero-Latency Cropper:**
   * Tự động quét toàn bộ 39 bảng Markdown được tạo ra.
   * Cắt trước ảnh crop độ phân giải cao (200 DPI) của từng bảng từ tệp PDF gốc và lưu vào cache (`data/cache/table_crops/`).
   * Khi người dùng mở giao diện, ảnh bảng gốc hiển thị tức thì với **độ trễ 0 giây**.
2. **Human-in-the-Loop Web Editor (Port 8502):**
   * Được triển khai trong [`serve_md_editor.py`](serve_md_editor.py).
   * Giao diện hai cột trực quan: Bên trái là ảnh crop thực tế của bảng từ PDF gốc; Bên phải là bảng Markdown hiển thị dạng Spreadsheet tương tác.
   * Hỗ trợ chỉnh sửa trực tiếp từng ô số liệu, thêm/xóa dòng, thêm/xóa cột.
   * Nút **"Lưu & Xuất Markdown Hoàn Thiện"** tự động cập nhật lại toàn văn tài liệu và xuất ra [`outputs/vnm_financial_report_final.md`](outputs/vnm_financial_report_final.md).

---

## 5. Hướng Dẫn Vận Hành & Khởi Chạy Nhanh (Quick Start)

### 5.1. Cài Đặt Môi Trường

> [!TIP]
> **Yêu cầu hệ thống:** Python 3.11+, Windows / Linux / macOS. Khuyến nghị máy có GPU NVIDIA (VRAM ≥ 4 GB) để đạt tốc độ tối đa 1.2s/trang cho Local OCR.

```powershell
# 1. Khởi tạo và kích hoạt môi trường ảo
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # Trên Linux/macOS dùng: source .venv/bin/activate

# 2. Cài đặt các gói phụ thuộc
pip install -e .
```

Tạo tệp `.env` tại thư mục gốc từ bản mẫu `.env.example`:
```ini
# Vision OCR Provider (Miễn phí từ Google AI Studio)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_VISION_MODEL=gemini-2.0-flash

# Groq Vision Provider (Fallback dự phòng)
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_VISION_MODEL=llama-3.2-11b-vision-preview

# Cấu hình OCR Cục bộ
ENABLE_OCR_FALLBACK=true
OCR_PROVIDER=auto
```

---

### 5.2. Khởi Chạy Giao Diện Web App Trực Quan (`interface.py`)

Hệ thống cung cấp giao diện Web tương tác trọn gói thông qua [`interface.html`](interface.html). Khởi chạy chỉ với **một câu lệnh duy nhất**:

```powershell
python interface.py
```

Hệ thống sẽ tự động kích hoạt máy chủ Web nội bộ và tự động mở trình duyệt tại:
👉 **`http://localhost:8501`**

```text
================================================================================
  🚀 OpenBCTC AI — GIAO DIỆN WEB TRỰC QUAN ĐANG HOẠT ĐỘNG
================================================================================
  👉 Truy cập Web App tại:   http://localhost:8501
  📄 File giao diện:         interface.html
  🌐 Port Rà Soát Bảng HITL: http://localhost:8502 (Tự động kích hoạt)
  ⌨️  Nhấn Ctrl + C trong Terminal để dừng máy chủ.
================================================================================
```

---

### 5.3. Quy Trình Vận Hành 4 Bước Khép Kín (Ai Cũng Có Thể Dùng)

```mermaid
flowchart LR
    Step1["1️⃣ Nạp PDF & Cấu Hình\n(Kéo thả / File mẫu)"] --> Step2["2️⃣ Xử Lý Toàn Trình\n(LangGraph + Live Logs)"]
    Step2 --> Step3["3️⃣ Rà Soát Bảng (Port 8502)\n(Đối chiếu ảnh crop 200 DPI)"]
    Step3 --> Step4["4️⃣ Xác Nhận & Xuất File\n(Tải / Copy Markdown .md)"]

    style Step1 fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#fff
    style Step2 fill:#1e293b,stroke:#10b981,stroke-width:2px,color:#fff
    style Step3 fill:#1e293b,stroke:#f59e0b,stroke-width:2px,color:#fff
    style Step4 fill:#1e293b,stroke:#8b5cf6,stroke-width:2px,color:#fff
```

#### Bước 1: Nạp Tài Liệu PDF & Cấu Hình Đa Doanh Nghiệp
* **Kéo & thả tập tin PDF BCTC bất kỳ** (scan hoặc text gốc của HPG, FPT, MWG, VNM, Vietcombank...) vào khung tải lên hoặc nhấp để duyệt file từ máy tính.
* **Tự động nhận diện thông minh (Metadata Auto-Detection):** Tự động đếm tổng số trang, phân tích trang bìa và tự động điền **Mã Doanh Nghiệp (Ticker)** và **Năm Tài Chính**.
* **Tiện ích kiểm thử nhanh:** Có sẵn nút *"🥛 Sử dụng file mẫu chuẩn: Vinamilk 2024 (vnm.pdf - 54 trang)"* để chạy thử nghiệm tức thì.

#### Bước 2: Bắt Đầu Xử Lý & Theo Dõi Tiến Trình Thời Gian Thực
* Nhấp nút **"🚀 Bắt Đầu Bóc Tách BCTC"**.
* Giao diện trực quan hóa trạng thái hoạt động của 6 node xử lý thời gian thực:
  1. `Phân Loại PDF` → 2. `Trinh Sát Mục Lục` → 3. `Vision LLM BCTC Cốt Lõi` → 4. `Local OCR Thuyết Minh` → 5. `Anti-GIGO 17 Đẳng Thức Kế Toán` → 6. `Table Inspector & Crop Ảnh Bảng 200 DPI`.
* Thanh tiến trình động `%` cùng cửa sổ **Terminal Live Stream** hiển thị chi tiết từng thông điệp log từ LangGraph.

#### Bước 3: Rà Soát Bảng Biểu Đối Chiếu Ảnh Crop 200 DPI (Port 8502)
* Xem ngay bảng tóm tắt chất lượng: Trạng thái cân đối kế toán (✅ 100% Cân đối), số bảng biểu kiểm toán hợp lệ, số lượng facts tài chính trích xuất.
* Nhấp **"Mở Tab Mới (Port 8502)"** hoặc **"Nhúng Trực Tiếp Tại Đây"** để đối chiếu song song:
  * Bên trái: Ảnh crop độ nét cao 200 DPI của riêng từng bảng (không hiển thị cả trang giấy).
  * Bên phải: Bảng tính tương tác (Spreadsheet) cho phép sửa số, chèn cột, sửa lỗi OCR trực tiếp.

#### Bước 4: Xác Nhận & Xuất File Markdown Hoàn Thiện
* Nhấp **"✅ Xác Nhận Đạt Chuẩn & Xuất Markdown"**.
* Giao diện cung cấp:
  * **Trình xem trước Markdown (Live Preview):** Chuyển đổi linh hoạt giữa giao diện BCTC đã render đẹp mắt và mã nguồn Markdown thô.
  * **Tải xuống tệp `.md` hoàn thiện:** Nhấp nút **"📥 Tải File .md Xuống"** (tự động đặt tên chuẩn theo mã CK và niên độ).
  * **Sao chép một chạm:** Nhấp **"📋 Sao Chép Markdown"** để copy toàn bộ nội dung vào Clipboard.
  * **Tải Báo cáo Benchmark:** Tải tệp đo lường hiệu năng xử lý (`outputs/<mã_ck>_<năm>_ocr_benchmark_report.md`).

---

### 5.4. Các Chế Độ Chạy Dòng Lệnh Nâng Cao (CLI Options)

Dành cho lập trình viên, tích hợp hệ thống backend hoặc chạy kiểm thử tự động trong CI/CD pipeline:

```powershell
# Chạy giao diện Menu văn bản tương tác trong Terminal
python interface.py --cli

# Bóc tách toàn trình chạy nền (Headless Mode)
python interface.py --pipeline

# Bóc tách toàn trình kèm tự động mở Web Reviewer (Port 8502)
python interface.py --pipeline --review

# Đo lường hiệu năng tải thực (Xóa sạch cache đĩa, ép chạy mới hoàn toàn)
python interface.py --pipeline --fresh

# Bóc tách nhanh 1 trang PDF cụ thể (Ví dụ trang Thuyết minh số 42)
python interface.py --page 42

# Đánh giá chất lượng bóc tách bảng trên 49 Bảng Ground Truth (TEDS-Struct & F1)
python interface.py --eval-tables

# Khởi chạy riêng máy chủ Web Table Reviewer độc lập (Port 8502)
python interface.py --serve-editor

# Tra cứu các Facts tài chính đã chuẩn hóa trong SQLite
python interface.py --query-db

# Chạy bộ kiểm thử tự động pytest
python interface.py --pytest

# Dọn dẹp toàn bộ cache đĩa
python interface.py --clear-cache
```

---

## 6. Kết Quả Đo Lường Thực Tế & Benchmark

### 6.1. Bảng Hiệu Năng Đo Lường Trên BCTC Vinamilk 2024 (54 Trang)

| Tiêu Chí Đo Lường | Phương Pháp Truyền Thống / Baseline | OpenBCTC (Sau Tối Ưu Hóa & Tích Hợp) | Ý Nghĩa Kỹ Thuật |
| :--- | :---: | :---: | :---: |
| **Độ tin cậy số liệu** | Dễ ảo giác do OCR thô, rớt số âm | **✅ 100% Cân đối (10/10 Invariants Pass)** | Triệt tiêu hoàn toàn lỗi GIGO |
| **Chất lượng bảng biểu** | Bảng dính chữ, lệch cột, rác OCR | **✅ 39/39 bảng chuẩn cấu trúc (100% Valid)** | Tự động kiểm toán cấu trúc bảng |
| **Ảnh Crop đối chiếu (HITL)** | Phải cuộn tìm trong file PDF gốc | **⚡ 39/39 ảnh crop 200 DPI (0s delay)** | Đối chiếu song song tức thì tại port 8502 |
| **Chi phí API Thuyết minh** | Hàng trăm ngàn tokens / Lỗi 503 | **💰 0 Tokens (100% Offline Local OCR)** | Miễn phí 100%, bảo mật dữ liệu tuyệt đối |
| **Tốc độ bóc tách Thuyết minh** | 6.0 – 8.5 giây / trang | **⚡ 1.2 – 2.0 giây / trang (427 trang/phút cached)** | **Nhanh hơn 3x – 4x** |
| **Mức chiếm dụng RAM** | 5.74 GB (tăng ròng liên tục) | **🎯 ~1.2 GB (Peak RSS ổn định)** | **Tiết kiệm > 75% RAM** (Active Eviction) |
| **Nguy cơ lỗi tràn bộ nhớ (OOM)** | Rất cao trên máy tính 16 GB | **✅ Triệt tiêu hoàn toàn** | Vận hành an toàn liên tục 54 trang |
| **Bảng giả vỡ cấu trúc** | Hàng chục bảng rác 1 cột | **✅ 0 bảng giả (Khử sạch 100%)** | Markdown chuẩn hóa, sạch rác |
| **Khả năng tự sửa sai số học** | Full-Page Re-OCR (Dễ phát sinh lỗi mới) | **🔍 Kính lúp Zoom cục bộ (Rollback an toàn)** | Giảm 92% token, chính xác 100% dòng số |

---

### 6.2. Đánh Giá Độ Chính Xác Cấu Trúc Bảng (49 Bảng Thuyết Minh Ground Truth)

Để đánh giá khoa học và khách quan chất lượng nhận diện bảng biểu trong phần Thuyết minh BCTC, OpenBCTC xây dựng bộ **Ground Truth gồm 49 bảng số liệu thực tế** (thu thập từ BCTC Vinamilk 2024) lưu tại [`evaluation_table/`](evaluation_table/).

Bộ công cụ đánh giá sử dụng các độ đo chuẩn quốc tế trong bài toán Document AI / Table Extraction:
* **TEDS-Struct (Tree Edit Distance based Similarity):** Đo lường khoảng cách chỉnh sửa giữa cây HTML AST dự đoán và cây HTML chuẩn (loại trừ nội dung chữ, chỉ đánh giá cấu trúc cây).
* **Span F1 (Merged Cells & Multi-tier Headers):** Đánh giá độ chính xác nhận diện các ô gộp đa cột / đa hàng và tiêu đề phân tầng.
* **Col & Row Accuracy:** Tỷ lệ số bảng khớp chính xác 100% số cột và số hàng.
* **Grid Exact Match:** Tỷ lệ bảng khớp tuyệt đối cả số hàng và số cột.

#### 📊 Tổng Hợp Chỉ Số Benchmark Cấu Trúc (Overall Metrics)

| Chỉ Số Đánh Giá | Điểm Số Đạt Được | Mục Tiêu / Ý Nghĩa Kỹ Thuật |
| :--- | :---: | :--- |
| **TEDS-Struct** | **`0.8604`** | Độ tương đồng cấu trúc cây AST đạt mức **Rất Tốt** (> 0.85) |
| **Độ chính xác Cột (Col Accuracy)** | **`89.8%`** (44/49 bảng) | Cực kỳ vững chắc, bảo toàn nguyên vẹn số lượng cột dữ liệu tài chính |
| **Span F1 (Header 2 tầng & Ô gộp)** | **`71.8%`** | Nhận diện và gộp chính xác phần lớn các tiêu đề phân cấp phức tạp |
| **Độ chính xác Hàng (Row Accuracy)** | **`46.9%`** (23/49 bảng) | Thách thức chủ yếu do bảng kéo dài qua nhiều trang PDF hoặc gộp dòng |
| **Khớp Ma Trận Tuyệt Đối (Grid Exact Match)** | **`44.9%`** (22/49 bảng) | Gần 1 nửa số bảng đạt độ chính xác lưới tuyệt đối ngay lần đầu trích xuất |

---

#### 🔍 Phân Bố Lỗi Cấu Trúc & Biện Pháp Xử Lý (Error Taxonomy)

Phân loại 7 dạng lỗi cấu trúc ghi nhận qua 49 bảng kiểm chuẩn:

| Phân Loại Lỗi | Số Lượng Bảng | Tỷ Lệ | Nguyên Nhân Kỹ Thuật & Giải Pháp Pipeline |
| :--- | :---: | :---: | :--- |
| `OK` | **16** | 32.7% | **Cấu trúc hoàn hảo 100%:** Khớp trọn vẹn số hàng, số cột và toàn bộ tọa độ ô gộp. |
| `MISSING_ROWS` | **19** | 38.8% | **Thiếu dòng:** Thường xuất hiện ở các bảng dài bị ngắt trang vật lý qua 2 trang PDF hoặc OCR gộp 2 dòng liên tiếp. Đã được khắc phục qua cơ chế `Spanning Tables` của [`normalizer.py`](src/parser/normalizer.py). |
| `MISSED_MERGED_HEADER` | **12** | 24.5% | **Bỏ sót ô gộp tiêu đề:** Engine nhận diện tiêu đề đa tầng thành các ô riêng rẽ. Được giải quyết qua bộ nhận diện header 2 tầng trong [`table_utils.py`](src/parser/table_utils.py). |
| `HALLUCINATED_MERGE` | **10** | 20.4% | **Gộp ô ảo:** OCR hiểu nhầm khoảng trắng của ô trống thành ô gộp mở rộng. |
| `HEADER_DEPTH_MISMATCH` | **10** | 20.4% | **Lệch số tầng Header:** Nhầm lẫn giữa dòng tiêu đề con và dòng số liệu đầu tiên. |
| `EXTRA_ROWS` | **7** | 14.3% | **Thừa dòng:** Đường kẻ phân cách, khoảng trắng hoặc ghi chú footnote dưới chân bảng bị nhận diện nhầm thành một hàng dữ liệu. Được lọc bởi [`ocr_postprocess.py`](src/parser/ocr_postprocess.py). |
| `COLUMN_COUNT_MISMATCH` | **5** | 10.2% | **Lệch số cột:** Header 2 tầng bị ép phẳng (flatten) làm rớt các cột con. Chỉ xuất hiện ở 5/49 bảng. |

---

#### 📋 Bảng Chi Tiết Kết Quả 49 Bảng Ground Truth

<details>
<summary>👉 <b>Nhấp để mở rộng danh sách chi tiết toàn bộ 49 bảng kiểm thử (Click to expand)</b></summary>
<br>

> Toàn bộ dữ liệu được trích xuất từ [`evaluation_table/reports/report_latest.md`](evaluation_table/reports/report_latest.md):

| Table ID | Hàng (Pred / GT) | Cột (Pred / GT) | Span F1 | TEDS-Struct | Phân Loại Lỗi Ghi Nhận |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `p14_mineru_tbl_1` | 9 / 9 | 6 / 5 | 0.67 | **0.790** | `COLUMN_COUNT_MISMATCH`, `HALLUCINATED_MERGE`, `HEADER_DEPTH_MISMATCH` |
| `p15_mineru_tbl_1` | 8 / 7 | 5 / 5 | 0.12 | **0.429** | `EXTRA_ROWS`, `MISSED_MERGED_HEADER`, `HALLUCINATED_MERGE`, `HEADER_DEPTH_MISMATCH` |
| `p15_mineru_tbl_2` | 6 / 7 | 6 / 5 | 0.33 | **0.619** | `MISSING_ROWS`, `COLUMN_COUNT_MISMATCH`, `MISSED_MERGED_HEADER`, `HEADER_DEPTH_MISMATCH` |
| `p27_mineru_tbl_1` | 4 / 4 | 3 / 3 | 1.00 | **1.000** | `OK` |
| `p27_mineru_tbl_2` | 12 / 11 | 3 / 3 | 0.00 | **0.796** | `EXTRA_ROWS`, `MISSED_MERGED_HEADER` |
| `p27_mineru_tbl_3` | 5 / 6 | 3 / 3 | 1.00 | **0.840** | `MISSING_ROWS` |
| `p28_mineru_tbl_1` | 8 / 8 | 3 / 3 | 0.00 | **0.939** | `HALLUCINATED_MERGE` |
| `p28_mineru_tbl_2` | 3 / 4 | 2 / 2 | 1.00 | **0.769** | `MISSING_ROWS` |
| `p28_mineru_tbl_3` | 3 / 3 | 2 / 2 | 1.00 | **1.000** | `OK` |
| `p29_mineru_tbl_1` | 11 / 12 | 9 / 9 | 0.29 | **0.868** | `MISSING_ROWS`, `MISSED_MERGED_HEADER`, `HALLUCINATED_MERGE`, `HEADER_DEPTH_MISMATCH` |
| `p30_mineru_tbl_1` | 0 / 13 | 0 / 9 | 0.00 | **0.009** | `MISSING_ROWS`, `COLUMN_COUNT_MISMATCH`, `MISSED_MERGED_HEADER`, `HEADER_DEPTH_MISMATCH` |
| `p31_mineru_tbl_1` | 5 / 5 | 3 / 3 | 0.00 | **0.857** | `HALLUCINATED_MERGE` |
| `p31_mineru_tbl_2` | 11 / 10 | 4 / 5 | 0.00 | **0.690** | `EXTRA_ROWS`, `COLUMN_COUNT_MISMATCH`, `MISSED_MERGED_HEADER`, `HALLUCINATED_MERGE`, `HEADER_DEPTH_MISMATCH` |
| `p31_mineru_tbl_3` | 6 / 6 | 3 / 3 | 1.00 | **1.000** | `OK` |
| `p32_mineru_tbl_1` | 17 / 17 | 6 / 6 | 1.00 | **1.000** | `OK` |
| `p33_mineru_tbl_1` | 15 / 13 | 6 / 5 | 0.00 | **0.743** | `EXTRA_ROWS`, `COLUMN_COUNT_MISMATCH`, `HALLUCINATED_MERGE` |
| `p34_mineru_tbl_1` | 9 / 10 | 5 / 5 | 1.00 | **0.902** | `MISSING_ROWS` |
| `p35_mineru_tbl_1` | 9 / 10 | 3 / 3 | 1.00 | **0.902** | `MISSING_ROWS` |
| `p35_mineru_tbl_2` | 6 / 6 | 3 / 3 | 1.00 | **1.000** | `OK` |
| `p35_mineru_tbl_3` | 8 / 8 | 3 / 3 | 1.00 | **1.000** | `OK` |
| `p36_mineru_tbl_1` | 6 / 6 | 6 / 6 | 0.00 | **0.907** | `HALLUCINATED_MERGE` |
| `p37_mineru_tbl_1` | 9 / 10 | 3 / 3 | 1.00 | **0.902** | `MISSING_ROWS` |
| `p37_mineru_tbl_2` | 11 / 11 | 3 / 3 | 0.00 | **0.867** | `MISSED_MERGED_HEADER` |
| `p38_mineru_tbl_1` | 8 / 8 | 5 / 5 | 1.00 | **1.000** | `OK` |
| `p39_mineru_tbl_1` | 10 / 11 | 3 / 3 | 1.00 | **0.911** | `MISSING_ROWS` |
| `p39_mineru_tbl_2` | 5 / 6 | 3 / 3 | 1.00 | **0.840** | `MISSING_ROWS` |
| `p40_mineru_tbl_1` | 5 / 5 | 6 / 6 | 1.00 | **1.000** | `OK` |
| `p41_mineru_tbl_1` | 2 / 2 | 3 / 3 | 1.00 | **1.000** | `OK` |
| `p41_mineru_tbl_2` | 6 / 6 | 3 / 3 | 1.00 | **1.000** | `OK` |
| `p41_mineru_tbl_3` | 5 / 5 | 3 / 3 | 1.00 | **1.000** | `OK` |
| `p42_mineru_tbl_1` | 11 / 12 | 6 / 6 | 1.00 | **0.918** | `MISSING_ROWS` |
| `p43_mineru_tbl_1` | 6 / 7 | 3 / 3 | 0.40 | **0.625** | `MISSING_ROWS`, `MISSED_MERGED_HEADER`, `HEADER_DEPTH_MISMATCH` |
| `p43_mineru_tbl_2` | 5 / 5 | 3 / 3 | 1.00 | **0.895** | `HEADER_DEPTH_MISMATCH` |
| `p44_mineru_tbl_1` | 5 / 5 | 3 / 3 | 1.00 | **1.000** | `OK` |
| `p44_mineru_tbl_2` | 4 / 6 | 5 / 5 | 0.57 | **0.633** | `MISSING_ROWS`, `MISSED_MERGED_HEADER`, `HALLUCINATED_MERGE`, `HEADER_DEPTH_MISMATCH` |
| `p45_mineru_tbl_1` | 2 / 2 | 3 / 3 | 1.00 | **1.000** | `OK` |
| `p45_mineru_tbl_2` | 11 / 13 | 3 / 3 | 0.00 | **0.918** | `MISSING_ROWS`, `MISSED_MERGED_HEADER` |
| `p46_mineru_tbl_1` | 26 / 26 | 3 / 3 | 1.00 | **1.000** | `OK` |
| `p47_mineru_tbl_1` | 6 / 6 | 3 / 3 | 1.00 | **1.000** | `OK` |
| `p47_mineru_tbl_2` | 8 / 8 | 3 / 3 | 1.00 | **1.000** | `OK` |
| `p48_mineru_tbl_1` | 12 / 11 | 3 / 3 | 1.00 | **0.918** | `EXTRA_ROWS` |
| `p48_mineru_tbl_2` | 13 / 14 | 3 / 3 | 1.00 | **0.930** | `MISSING_ROWS` |
| `p49_mineru_tbl_1` | 21 / 19 | 3 / 3 | 1.00 | **0.906** | `EXTRA_ROWS` |
| `p50_mineru_tbl_1` | 18 / 17 | 3 / 3 | 1.00 | **0.945** | `EXTRA_ROWS` |
| `p51_mineru_tbl_1` | 16 / 20 | 5 / 5 | 0.80 | **0.726** | `MISSING_ROWS`, `MISSED_MERGED_HEADER` |
| `p52_mineru_tbl_1` | 11 / 12 | 5 / 5 | 0.00 | **0.667** | `MISSING_ROWS`, `MISSED_MERGED_HEADER`, `HALLUCINATED_MERGE` |
| `p53_mineru_tbl_1` | 14 / 15 | 3 / 3 | 1.00 | **0.934** | `MISSING_ROWS` |
| `p53_mineru_tbl_2` | 5 / 7 | 3 / 3 | 1.00 | **0.724** | `MISSING_ROWS` |
| `p54_mineru_tbl_1` | 5 / 5 | 7 / 7 | 1.00 | **0.838** | `HEADER_DEPTH_MISMATCH` |

</details>

---

#### ⚙️ Khởi Chạy Lại Bộ Benchmark (Reproduction)

Kiểm toán viên và nhà phát triển có thể tái hiện lại toàn bộ kết quả đo lường trên qua dòng lệnh:

```bash
# Cách 1: Thông qua interface runner điều phối
python interface.py --eval-tables

# Cách 2: Chạy trực tiếp từ module đánh giá
python evaluation_table/evaluator.py
```

---

### 6.3. Các Tệp Đầu Ra Trọng Yếu

Sau khi chạy pipeline, hệ thống tự động xuất bản và tổ chức toàn bộ gói tài sản tại thư mục `outputs/<mã_ck>_<năm>/` (ví dụ: `outputs/VNM_2025/`):

* 📄 **`outputs/<mã>_<năm>/<mã>_<năm>_financial_report.md`**: Toàn văn BCTC định dạng Markdown bóc tách tự động hoàn chỉnh.
* 📝 **`outputs/<mã>_<năm>/<mã>_<năm>_financial_report_final.md`**: Bản Markdown hoàn thiện cuối cùng sau khi kiểm toán viên rà soát qua HITL Web Reviewer (Port 8502).
* 💾 **`outputs/<mã>_<năm>/benchmark_<mã>_<năm>.db`**: Cơ sở dữ liệu SQLite lưu trữ cấu trúc 224 chỉ tiêu tài chính TT200 (`financial_facts`) và 13 chỉ số tài chính (`financial_ratios`) phục vụ SQL Fact Engine.
* 📊 **`outputs/<mã>_<năm>/<mã>_<năm>_ocr_benchmark_report.md`**: Báo cáo kỹ thuật chi tiết về cấu hình phần cứng, hiệu năng đo lường, kiểm toán Anti-GIGO và kiểm toán bảng biểu.
* ⚙️ **`outputs/<mã>_<năm>/<mã>_<năm>_ocr_benchmark_metrics.json`**: Tập hợp các chỉ số đo lường định dạng máy đọc JSON phục vụ CI/CD.
* 🧩 **`outputs/<mã>_<năm>/cache/notes/page_*.json`**: Tập hợp các khối nội dung nguyên tử chứa số trang `page` và toạ độ `bbox` phục vụ trích dẫn trực quan (Visual Grounding).
* 🖼️ **`outputs/<mã>_<năm>/cache/table_crops/*.png`**: Bộ sưu tập ảnh crop độ phân giải 200 DPI của từng bảng biểu dùng cho đối chiếu và kiểm toán số học.

---

## 7. Tích Hợp Hệ Sinh Thái OpenBCTC Copilot & Docker (Dual-Storage)

> 💡 **Tài Liệu Hướng Dẫn Kỹ Thuật Cho AI Agent & Vận Hành:**
> - 📘 **[Agent Guide: OpenBCTC (Producer Agent)](docs/AGENT_GUIDE_OPENBCTC.md)**: Đặc tả Data Contract, DDL SQLite 4 bảng, Schema JSON Blocks và CopilotSyncer.
> - 📙 **[Agent Guide: OpenBCTC Copilot (Consumer Agent)](docs/AGENT_GUIDE_COPILOT.md)**: Đặc tả Ingestion Webhook, Dynamic Fact Resolver, Qdrant Hybrid RAG và LangGraph Multi-Agent.
> - 📖 **[Hướng Dẫn Giao Diện & Quy Trình 5 Bước](docs/guide_interface.md)**: Hướng dẫn trải nghiệm người dùng từ nạp PDF đến chat đàm thoại.
> - 📄 **[Tài Liệu Kế Hoạch Tích Hợp](docs/Intergration_w_Copilot.md)**: Bản đặc tả chi tiết kiến trúc Dual-Storage ban đầu.

### 7.1. Triết Lý Dual-Storage (Lưu Trữ Song Song)
Nhằm kết nối hoàn hảo với trợ lý AI đàm thoại **OpenBCTC Copilot** (chạy Docker stack gồm FastAPI, MongoDB GridFS, Qdrant Hybrid RAG và Nginx) mà vẫn giữ nguyên trải nghiệm đơn giản, không phụ thuộc của người dùng truyền thống:

* **Nhánh 1: Cục Bộ (Local Standalone):** Vẫn lưu đầy đủ tệp PDF, Markdown, SQLite `.db` và JSON blocks ra thư mục `outputs/<mã_ck>_<năm>/`. Người dùng độc lập không cần cài đặt Docker hay MongoDB, có thể mở file trực tiếp trên ổ cứng.
* **Nhánh 2: Đám Mây / Docker (Copilot Ecosystem):** Mỗi khi OpenBCTC chạy xong OCR (hoặc sau khi kiểm toán viên bấm xác nhận trên HITL Web Editor), hệ thống tự động kích hoạt module `CopilotSyncer` đẩy dữ liệu vào MongoDB của Copilot và gửi webhook kích hoạt Copilot tự động nạp vector chunks vào Qdrant.

```mermaid
flowchart LR
    A["OpenBCTC (OCR Engine)"] -->|Nhánh 1: Local| B["outputs/<mã>_<năm>/<br/>(MD, SQLite DB, JSON, PDF)"]
    A -->|Nhánh 2: CopilotSyncer| C[("MongoDB GridFS :27017<br/>PDF, MD, SQLite DB")]
    A -->|Nhánh 2: CopilotSyncer| D[("MongoDB Collections<br/>JSON Blocks (BBox)")]
    A -.->|Trigger Webhook| E["Copilot API (:8000)<br/>Auto Ingest -> Qdrant :6333"]
    E --> F["Copilot Web UI (:5500)<br/>Chat & Visual Grounding"]
```

### 7.2. Khế Ước Dữ Liệu Đồng Bộ (Data Contract)
| Dữ Liệu OpenBCTC | Đích Đến Tại MongoDB Copilot | Vai Trò Trong Hệ Thống Copilot |
| :--- | :--- | :--- |
| **PDF BCTC gốc** | GridFS: `{company_lower}_{year}.pdf` | Stream nhanh cho Web UI để vẽ khung highlight BBox |
| **Markdown BCTC final** | GridFS: `{company_lower}_{year}_final.md` | Cung cấp toàn văn & TOC Tree cho LLM Reasoning |
| **SQLite DB (`benchmark_*.db`)** | GridFS: `benchmark_{company_lower}_{year}.db` | Cung cấp dữ liệu cho Deterministic SQL Fact Engine |
| **Cache JSON (`page_*.json`)** | Collection: `document_blocks` | Cung cấp toạ độ `bbox` cho Hybrid Qdrant Vector RAG |
| **Benchmark Metrics JSON** | Collection: `ocr_benchmarks` | Giám sát chất lượng kiểm toán số học Anti-GIGO |

### 7.3. Hướng Dẫn Cấu Hình & Tự Động Kích Hoạt

#### 1. Cài đặt thư viện kết nối:
```bash
pip install pymongo motor httpx
```

#### 2. Cấu hình biến môi trường (`.env`):
```dotenv
ENABLE_COPILOT_SYNC=true
MONGO_URI=mongodb://localhost:27017
MONGO_DB=openbctc
COPILOT_API_URL=http://localhost:8000
```

> **🛡️ Cơ Chế Graceful Degradation (Chống Treo):** Nếu Docker của Copilot chưa khởi động, module `CopilotSyncer` sẽ tự động phát hiện với timeout 3s, chỉ ghi cảnh báo nhẹ và **tuyệt đối không làm gián đoạn** tiến trình OCR cục bộ.

### 7.4. Đóng Gói Docker & Kết Nối Chung Mạng Nội Bộ

Hai dự án kết nối mượt mà qua mạng nội bộ Docker **`openbctc-net`**:

#### 1. Cấu hình tại OpenBCTC (`docker-compose.yml` — Tham gia mạng external):

```yaml
version: '3.8'

networks:
  openbctc-net:
    external: true  # Dùng chung mạng với OpenBCTC Copilot

services:
  openbctc-ocr:
    build: .
    container_name: openbctc_ocr_engine
    ports:
      - "8501:8501"
      - "8502:8502"
    environment:
      - MONGO_URI=mongodb://mongodb:27017
      - COPILOT_API_URL=http://copilot-api:8000
      - ENABLE_COPILOT_SYNC=true
    volumes:
      - ./outputs:/app/outputs
      - ./pdf_files:/app/pdf_files
    networks:
      - openbctc-net
```

#### 2. Cấu hình tại OpenBCTC Copilot (`docker-compose.yml` — Khởi tạo mạng bridge):
```yaml
version: '3.8'

networks:
  openbctc-net:
    name: openbctc-net
    driver: bridge

services:
  # Backend FastAPI
  copilot-api:
    build: .
    ports:
      - 8000:8000
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}
      - QDRANT_URL=http://qdrant:6333
      - MONGO_URI=mongodb://mongodb:27017
      - MONGO_DB=openbctc
    depends_on:
      - qdrant
      - mongodb
    volumes:
      - ./data:/app/data
      - ../OpenBCTC/outputs:/app/outputs:ro  # Mount thư mục đầu ra của OpenBCTC làm nguồn facts
    networks:
      - openbctc-net

  # Frontend Web UI + Static Storage (Nginx)
  copilot-ui:
    image: nginx:alpine
    ports:
      - 5500:80
    volumes:
      - ./frontend:/usr/share/nginx/html
      - ./data:/usr/share/nginx/html/data:ro
    networks:
      - openbctc-net

  # Vector Database cho Hybrid RAG
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - 6333:6333
      - 6334:6334
    volumes:
      - qdrant_data:/qdrant/storage
    networks:
      - openbctc-net

  # Document & Metadata Storage
  mongodb:
    image: mongo:latest
    ports:
      - 27017:27017
    volumes:
      - mongodb_data:/data/db
    networks:
      - openbctc-net

volumes:
  qdrant_data:
  mongodb_data:
```

---

### 7.5. Quy Trình Vận Hành Toàn Trình Zero-Touch (End-to-End Workflow)

```mermaid
sequenceDiagram
    autonumber
    actor User as Chuyên Viên Phân Tích
    participant OpenBCTC as OpenBCTC (OCR Engine :8501)
    participant Mongo as MongoDB (:27017)
    participant CopilotAPI as Copilot Backend (:8000)
    participant Qdrant as Qdrant Vector DB (:6333)
    participant CopilotUI as Copilot Web UI (:5500)

    User->>OpenBCTC: Tải lên PDF BCTC & Bấm "Bắt Đầu Bóc Tách"
    OpenBCTC->>OpenBCTC: Vision LLM Core + Local OCR Notes
    OpenBCTC->>OpenBCTC: Kiểm toán số học Anti-GIGO (17 đẳng thức)
    OpenBCTC->>OpenBCTC: Ghi ra đĩa cục bộ: outputs/VNM_2025/ (Nhánh 1)
    
    rect rgb(235, 248, 255)
        Note over OpenBCTC, Mongo: Tự Động Bơm Dữ Liệu Sang Copilot (Nhánh 2)
        OpenBCTC->>Mongo: Đẩy PDF gốc, Markdown final, SQLite .db vào GridFS
        OpenBCTC->>Mongo: Đẩy toàn bộ JSON Blocks có BBox vào 'document_blocks'
        OpenBCTC->>CopilotAPI: Webhook POST /api/v1/ingest {"company": "VNM", "year": 2025}
    end

    rect rgb(240, 255, 240)
        Note over CopilotAPI, Qdrant: Tự Động Xây Dựng RAG & Vector Index
        CopilotAPI->>Mongo: Đọc JSON Blocks từ 'document_blocks'
        CopilotAPI->>Qdrant: Layout-Aware Chunker -> Index Dense (BGE-M3) + Sparse (BM25)
    end

    User->>CopilotUI: Mở giao diện chat (:5500) & Đặt câu hỏi
    CopilotUI->>CopilotAPI: Gửi câu hỏi đàm thoại
    CopilotAPI->>CopilotAPI: SQL Fact Engine (Số liệu xác thực) + RAG Thuyết minh
    CopilotAPI-->>CopilotUI: Trả lời kèm trích dẫn số trang & Highlight Bounding Box trên PDF!
```

Quy trình vận hành trở thành một vòng tuần hoàn **Zero-Touch 100%**: Thả file PDF vào OpenBCTC → OCR xong tự động đẩy dữ liệu sang Docker → Mở Copilot UI lên chat và phân tích dữ liệu ngay lập tức!


---

## 8. Lộ Trình Phát Triển (Roadmap)

- [x] **Dual-Branch Ingestion Pipeline**: Phân luồng BCTC Cốt lõi (Vision LLM) và Thuyết minh (Offline OCR).
- [x] **TOC Inspector & Physical Offset**: Tự động giải quyết lệch trang vật lý PDF scan.
- [x] **Anti-GIGO 17 Đẳng Thức Kế Toán**: Tự động kiểm toán theo Thông tư 200/2014/TT-BTC.
- [x] **Kính Lúp Vision Zoom**: Tự động crop dòng nghi vấn và sửa sai số học khép kín.
- [x] **Tối Ưu Hóa Local OCR**: VietOCR Batch GPU Acceleration (Batch N = 16) & Active Memory Eviction.
- [x] **Zero-Latency Table Cropper & Web HITL Editor**: Giao diện Spreadsheet đối chiếu ảnh 200 DPI (Port 8502).
- [x] **Web App All-in-One (`interface.py`)**: Kéo thả nạp PDF đa doanh nghiệp & Live stream log (Port 8501).
- [x] **Tích Hợp OpenBCTC Copilot (Dual-Storage & Docker)**: Đồng bộ tự động sang MongoDB GridFS & Qdrant RAG Ingestion phục vụ Chatbot tài chính trực quan.
- [ ] **Xuất dữ liệu Đa định dạng**: Xuất trực tiếp sang Microsoft Excel (`.xlsx`), JSON Schema và XBRL chuẩn quốc tế.
- [ ] **Multi-turn Financial QA Agent**: Tích hợp trợ lý hỏi đáp BCTC chuyên sâu kết hợp Hybrid RAG (SQL + Vector).

---

## 📜 Giấy Phép & Đóng Góp

Dự án được phát hành theo giấy phép [MIT License](LICENSE). Mọi đóng góp, báo cáo lỗi (Issues) và Pull Requests đều được chào đón!

<div align="center">

**OpenBCTC AI** — *Giải pháp bóc tách Báo cáo Tài chính PDF sang Markdown chuẩn mực, tin cậy và tự kiểm toán số học.*

Made with ❤️ by [LeGiaVan](https://github.com/LeGiaVan)

</div>
