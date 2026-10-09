# Sử dụng Python 3.11 Slim làm base image
FROM python:3.11-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Thiết lập biến môi trường tránh buffer log và UTF-8
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8

# Cài đặt các thư viện hệ thống cần thiết cho OpenCV, PyMuPDF và OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libspatialindex-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy cấu hình dependencies
COPY pyproject.toml .

# Cài đặt dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    pdfplumber PyMuPDF opencv-python-headless \
    pydantic pydantic-settings python-dotenv \
    langgraph langchain-core \
    pymongo motor httpx psutil

# Copy toàn bộ mã nguồn
COPY . /app

# Tạo các thư mục lưu trữ dữ liệu
RUN mkdir -p /app/data /app/outputs /app/pdf_files

# Mở các cổng: 8501 (Main Web App) và 8502 (HITL Editor)
EXPOSE 8501 8502

# Lệnh khởi chạy mặc định: Web Interface
CMD ["python", "interface.py", "--port", "8501", "--no-browser"]
