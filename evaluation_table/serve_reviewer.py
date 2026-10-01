"""
serve_reviewer.py — Giao diện Web cục bộ để review và gán nhãn Ground Truth cho Table Structure.

Chạy lệnh:
    .venv\\Scripts\\python.exe evaluation_table/serve_reviewer.py

Tự động mở trình duyệt tại: http://localhost:8501
- Màn hình chia đôi: Bên trái là ảnh crop từ PDF gốc, Bên phải là form gán nhãn cấu trúc.
- Lưu trực tiếp vào evaluation_table/ground_truth/{table_id}.json.
- Tích hợp nút "Chạy Đánh Giá" tính điểm trực tiếp theo thời gian thực.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import re
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from evaluation_table.converter import auto_to_schema, schema_to_html
from evaluation_table.evaluator import run_evaluation

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ReviewerServer")

PORT = 8501
PRED_DIR = current_dir / "predictions"
GT_DIR = current_dir / "ground_truth"
IMG_DIR = current_dir / "images"
MANIFEST_PATH = current_dir / "manifest.json"

GT_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FinAudit AI — Table Structure Ground Truth Reviewer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-border: #334155;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --text: #f8fafc;
      --text-muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', sans-serif;
      background-color: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }
    /* Header */
    header {
      background-color: #1e293b;
      border-bottom: 1px solid var(--card-border);
      padding: 10px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 15px;
      flex-shrink: 0;
    }
    .brand { font-size: 1.1rem; font-weight: 700; color: #60a5fa; display: flex; align-items: center; gap: 8px; }
    .progress-bar-container {
      flex: 1;
      max-width: 400px;
      background-color: #334155;
      border-radius: 9999px;
      height: 10px;
      overflow: hidden;
      position: relative;
    }
    .progress-bar {
      background: linear-gradient(90deg, #3b82f6, #10b981);
      height: 100%;
      width: 0%;
      transition: width 0.3s ease;
    }
    .progress-text { font-size: 0.85rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; }
    .header-actions { display: flex; gap: 10px; align-items: center; }
    .btn {
      padding: 8px 16px;
      font-size: 0.85rem;
      font-weight: 600;
      border-radius: 6px;
      border: none;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
    }
    .btn-primary { background-color: var(--primary); color: white; }
    .btn-primary:hover { background-color: var(--primary-hover); }
    .btn-success { background-color: var(--success); color: white; }
    .btn-success:hover { background-color: #059669; }
    .btn-secondary { background-color: #334155; color: var(--text); }
    .btn-secondary:hover { background-color: #475569; }
    .btn-danger { background-color: #dc2626; color: white; }

    /* Filter Bar */
    .filter-bar {
      background-color: #162032;
      border-bottom: 1px solid var(--card-border);
      padding: 8px 20px;
      display: flex;
      gap: 8px;
      overflow-x: auto;
      flex-shrink: 0;
    }
    .filter-btn {
      padding: 4px 12px;
      font-size: 0.8rem;
      border-radius: 9999px;
      border: 1px solid var(--card-border);
      background-color: transparent;
      color: var(--text-muted);
      cursor: pointer;
      white-space: nowrap;
    }
    .filter-btn.active {
      background-color: #2563eb;
      color: white;
      border-color: #3b82f6;
      font-weight: 600;
    }

    /* Main Container */
    main {
      flex: 1;
      display: flex;
      overflow: hidden;
      padding: 10px;
      gap: 12px;
    }
    .pane {
      flex: 1;
      background-color: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .pane-header {
      background-color: #273549;
      border-bottom: 1px solid var(--card-border);
      padding: 8px 14px;
      font-size: 0.9rem;
      font-weight: 600;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .pane-content {
      flex: 1;
      overflow: auto;
      padding: 16px;
    }

    /* Image Viewer */
    .img-container {
      display: flex;
      justify-content: center;
      align-items: flex-start;
      min-height: 100%;
      background-color: #0b1120;
      border-radius: 6px;
      padding: 12px;
    }
    .img-container img {
      max-width: 100%;
      height: auto;
      border-radius: 4px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.5);
      border: 1px solid #334155;
    }

    /* Ground Truth Form */
    .meta-card {
      background-color: #0f172a;
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 12px;
      margin-bottom: 16px;
    }
    .meta-title { font-size: 1rem; font-weight: 700; color: #38bdf8; margin-bottom: 4px; }
    .meta-sub { font-size: 0.8rem; color: var(--text-muted); display: flex; gap: 15px; }

    .form-group { margin-bottom: 14px; }
    .form-label {
      display: flex;
      justify-content: space-between;
      font-size: 0.85rem;
      font-weight: 600;
      margin-bottom: 6px;
      color: #cbd5e1;
    }
    .form-hint { font-size: 0.75rem; color: #64748b; font-weight: normal; }
    .grid-inputs {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .number-control {
      display: flex;
      align-items: center;
      background-color: #0f172a;
      border: 1px solid var(--card-border);
      border-radius: 6px;
      overflow: hidden;
    }
    .number-control button {
      padding: 8px 14px;
      background-color: #334155;
      color: white;
      border: none;
      cursor: pointer;
      font-weight: bold;
    }
    .number-control input {
      flex: 1;
      background: transparent;
      border: none;
      color: white;
      text-align: center;
      font-family: 'JetBrains Mono', monospace;
      font-size: 1.1rem;
      font-weight: 700;
      width: 50px;
    }

    /* Spans Editor */
    .spans-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 10px;
      min-height: 38px;
      padding: 8px;
      background-color: #0f172a;
      border: 1px solid var(--card-border);
      border-radius: 6px;
    }
    .span-chip {
      background-color: #1e3a8a;
      color: #93c5fd;
      border: 1px solid #3b82f6;
      border-radius: 4px;
      padding: 4px 8px;
      font-size: 0.8rem;
      font-family: 'JetBrains Mono', monospace;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .span-chip button {
      background: transparent;
      border: none;
      color: #ef4444;
      cursor: pointer;
      font-weight: bold;
    }
    .add-span-form {
      display: flex;
      gap: 6px;
      align-items: center;
      background-color: #1e293b;
      padding: 8px;
      border-radius: 6px;
      border: 1px dashed var(--card-border);
    }
    .add-span-form input {
      width: 48px;
      padding: 4px;
      background-color: #0f172a;
      border: 1px solid var(--card-border);
      color: white;
      border-radius: 4px;
      text-align: center;
      font-family: 'JetBrains Mono', monospace;
    }

    /* Grid Preview */
    .table-preview-container {
      margin-top: 15px;
      border-top: 1px solid var(--card-border);
      padding-top: 12px;
    }
    .table-preview {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.75rem;
      font-family: 'JetBrains Mono', monospace;
      text-align: center;
    }
    .table-preview td, .table-preview th {
      border: 1px solid #475569;
      padding: 4px;
      background-color: #1e293b;
      color: #cbd5e1;
    }
    .table-preview th { background-color: #334155; font-weight: bold; color: #93c5fd; }
    .table-preview td.merged { background-color: #1e3a8a; color: #bfdbfe; font-weight: bold; }

    /* Footer Nav */
    footer {
      background-color: #1e293b;
      border-top: 1px solid var(--card-border);
      padding: 10px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-shrink: 0;
    }
    .status-badge {
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 0.8rem;
      font-weight: 600;
    }
    .status-saved { background-color: #065f46; color: #6ee7b7; border: 1px solid #10b981; }
    .status-pending { background-color: #78350f; color: #fde68a; border: 1px solid #f59e0b; }

    /* Modal */
    .modal-overlay {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background-color: rgba(0,0,0,0.7);
      display: none;
      justify-content: center;
      align-items: center;
      z-index: 9999;
    }
    .modal-content {
      background-color: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      width: 650px;
      max-width: 90%;
      max-height: 85vh;
      overflow-y: auto;
      padding: 20px;
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <span>📊</span> FinAudit AI — Table Ground Truth Reviewer
    </div>
    <div class="progress-bar-container">
      <div class="progress-bar" id="progressBar"></div>
    </div>
    <div class="progress-text" id="progressText">0 / 49 (0%)</div>
    <div class="header-actions">
      <button class="btn btn-secondary" onclick="openEvalModal()">🚀 Chạy Đánh Giá Nhanh</button>
    </div>
  </header>

  <div class="filter-bar" id="filterBar">
    <button class="filter-btn active" onclick="setFilter('all')">Tất cả (49)</button>
    <button class="filter-btn" onclick="setFilter('group_1_simple_header')">1. Đơn giản (16)</button>
    <button class="filter-btn" onclick="setFilter('group_2_two_tier_header')">2. Header 2 tầng (11)</button>
    <button class="filter-btn" onclick="setFilter('group_3_has_subtotals')">3. Dòng Cộng (8)</button>
    <button class="filter-btn" onclick="setFilter('group_4_cross_page')">4. Ngắt trang (8)</button>
    <button class="filter-btn" onclick="setFilter('group_5_dashes_and_empty')">5. Ô gạch ngang (6)</button>
  </div>

  <main>
    <!-- Pane Trái: Ảnh PDF Gốc Crop -->
    <section class="pane">
      <div class="pane-header">
        <span>📸 ẢNH BẢNG GỐC TỪ PDF</span>
        <span id="imgPageTag" style="color: #94a3b8; font-size: 0.8rem;">Trang 0</span>
      </div>
      <div class="pane-content" style="padding: 6px;">
        <div class="img-container">
          <img id="tableImage" src="" alt="Ảnh bảng">
        </div>
      </div>
    </section>

    <!-- Pane Phải: Khung Gán Nhãn Ground Truth -->
    <section class="pane">
      <div class="pane-header">
        <span>✏️ KHUNG GÁN NHÃN GROUND TRUTH</span>
        <span id="statusBadge" class="status-badge status-pending">Chưa gán nhãn</span>
      </div>
      <div class="pane-content">
        <div class="meta-card">
          <div class="meta-title" id="tableId">pXX_mineru_tbl_Y</div>
          <div class="meta-sub">
            <span id="noteTitle">Thuyết minh</span>
            <span id="groupBadge" style="color: #60a5fa;">Nhóm 1</span>
          </div>
        </div>

        <div class="grid-inputs">
          <div class="form-group">
            <div class="form-label">
              <span>Số hàng (n_rows)</span>
              <span class="form-hint" id="predRowsHint">Pred: 0</span>
            </div>
            <div class="number-control">
              <button onclick="changeNum('n_rows', -1)">-</button>
              <input type="number" id="n_rows" min="1" max="100" value="4" onchange="renderGridPreview()">
              <button onclick="changeNum('n_rows', 1)">+</button>
            </div>
          </div>

          <div class="form-group">
            <div class="form-label">
              <span>Số cột (n_cols)</span>
              <span class="form-hint" id="predColsHint">Pred: 0</span>
            </div>
            <div class="number-control">
              <button onclick="changeNum('n_cols', -1)">-</button>
              <input type="number" id="n_cols" min="1" max="50" value="5" onchange="renderGridPreview()">
              <button onclick="changeNum('n_cols', 1)">+</button>
            </div>
          </div>
        </div>

        <div class="form-group">
          <div class="form-label">
            <span>Dòng Header (Header Rows)</span>
            <span class="form-hint">Chỉ định các dòng tiêu đề bảng (0-indexed)</span>
          </div>
          <div style="display: flex; gap: 15px; font-size: 0.85rem;">
            <label><input type="checkbox" id="hdr_0" checked onchange="renderGridPreview()"> Dòng 0 (Header chính)</label>
            <label><input type="checkbox" id="hdr_1" onchange="renderGridPreview()"> Dòng 1 (Header tầng 2)</label>
          </div>
        </div>

        <div class="form-group">
          <div class="form-label">
            <span>Danh sách Ô Gộp (Spans: colspan & rowspan)</span>
            <span class="form-hint" id="predSpansHint">Pred: 0 spans</span>
          </div>
          <div class="spans-list" id="spansList"></div>

          <div class="add-span-form">
            <span style="font-size: 0.75rem; color: #94a3b8;">Thêm ô gộp:</span>
            <span>Hàng:</span><input type="number" id="span_r1" min="0" value="0">
            <span>Cột:</span><input type="number" id="span_c1" min="0" value="0">
            <span>&rarr; Đến Hàng:</span><input type="number" id="span_r2" min="0" value="0">
            <span>Cột:</span><input type="number" id="span_c2" min="0" value="1">
            <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 0.75rem;" onclick="addSpanFromInputs()">➕ Thêm</button>
          </div>
        </div>

        <div class="table-preview-container">
          <div class="form-label">
            <span>Mô phỏng cấu trúc lưới logic (Grid Matrix):</span>
            <button class="btn btn-secondary" style="padding: 2px 8px; font-size: 0.7rem;" onclick="copyFromPred()">📋 Lấy gợi ý từ Pred</button>
          </div>
          <div style="overflow-x: auto; max-height: 200px;" id="gridPreviewBox"></div>
        </div>
      </div>
    </section>
  </main>

  <footer>
    <div style="display: flex; gap: 10px;">
      <button class="btn btn-secondary" onclick="prevTable()">⏮️ Trước (Left Arrow)</button>
      <button class="btn btn-secondary" onclick="nextTable()">Tiếp theo (Right Arrow) ⏭️</button>
    </div>
    <div>
      <span style="font-size: 0.8rem; color: var(--text-muted); margin-right: 15px;">Phím tắt: <code>Enter</code> hoặc <code>Ctrl + S</code> để Lưu & Chuyển</span>
      <button class="btn btn-success" style="font-size: 0.95rem; padding: 10px 24px;" onclick="saveGroundTruth()">💾 Lưu Ground Truth & Tiếp tục</button>
    </div>
  </footer>

  <!-- Modal Đánh Giá -->
  <div class="modal-overlay" id="evalModal" onclick="closeEvalModal(event)">
    <div class="modal-content" onclick="event.stopPropagation()">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
        <h3 style="color: #60a5fa;">Kết quả Đánh giá Table Structure</h3>
        <button class="btn btn-secondary" style="padding: 2px 8px;" onclick="document.getElementById('evalModal').style.display='none'">✕</button>
      </div>
      <div id="evalBody" style="font-size: 0.9rem; line-height: 1.6;">
        Đang chạy đánh giá...
      </div>
    </div>
  </div>

  <script>
    let allTables = [];
    let filteredTables = [];
    let currentIndex = 0;
    let currentFilter = 'all';
    let currentSpans = [];

    async function init() {
      const res = await fetch('/api/tables');
      allTables = await res.json();
      applyFilter();
      loadTable(0);
      updateProgress();
    }

    function setFilter(filter) {
      currentFilter = filter;
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      event.target.classList.add('active');
      applyFilter();
      loadTable(0);
    }

    function applyFilter() {
      if (currentFilter === 'all') {
        filteredTables = allTables;
      } else {
        filteredTables = allTables.filter(t => t.group_id === currentFilter);
      }
      currentIndex = 0;
    }

    function loadTable(index) {
      if (index < 0 || index >= filteredTables.length) return;
      currentIndex = index;
      const t = filteredTables[currentIndex];

      document.getElementById('tableId').innerText = t.table_id;
      document.getElementById('noteTitle').innerText = t.description || 'Thuyết minh BCTC';
      document.getElementById('groupBadge').innerText = t.group_name;
      document.getElementById('imgPageTag').innerText = `Trang ${t.page}`;
      document.getElementById('tableImage').src = `/images/${t.table_id}.png`;

      // Cập nhật trạng thái
      const badge = document.getElementById('statusBadge');
      if (t.is_reviewed) {
        badge.innerText = '✅ Đã gán nhãn';
        badge.className = 'status-badge status-saved';
      } else {
        badge.innerText = '⏳ Chưa gán nhãn';
        badge.className = 'status-badge status-pending';
      }

      // Hints
      document.getElementById('predRowsHint').innerText = `Pred: ${t.n_rows_pred}`;
      document.getElementById('predColsHint').innerText = `Pred: ${t.n_cols_pred}`;
      document.getElementById('predSpansHint').innerText = `Pred: ${t.spans_pred ? t.spans_pred.length : 0} spans`;

      // Giá trị: nếu đã review thì lấy GT, nếu chưa thì lấy draft từ Pred
      const initRows = t.gt_data ? t.gt_data.n_rows : t.n_rows_pred;
      const initCols = t.gt_data ? t.gt_data.n_cols : t.n_cols_pred;
      currentSpans = t.gt_data ? JSON.parse(JSON.stringify(t.gt_data.spans || [])) : JSON.parse(JSON.stringify(t.spans_pred || []));
      
      const hdrs = t.gt_data ? (t.gt_data.header_rows || [0]) : [0];
      document.getElementById('hdr_0').checked = hdrs.includes(0);
      document.getElementById('hdr_1').checked = hdrs.includes(1);

      document.getElementById('n_rows').value = initRows;
      document.getElementById('n_cols').value = initCols;

      renderSpansList();
      renderGridPreview();
    }

    function changeNum(id, delta) {
      const el = document.getElementById(id);
      let val = parseInt(el.value) + delta;
      if (val < 1) val = 1;
      el.value = val;
      renderGridPreview();
    }

    function renderSpansList() {
      const box = document.getElementById('spansList');
      box.innerHTML = '';
      if (currentSpans.length === 0) {
        box.innerHTML = '<span style="color:#64748b; font-size:0.8rem; font-style:italic;">Không có ô gộp nào (Bảng phẳng 100%)</span>';
        return;
      }
      currentSpans.forEach((s, idx) => {
        const chip = document.createElement('div');
        chip.className = 'span-chip';
        const r1 = s[0], c1 = s[1], r2 = s[2], c2 = s[3];
        let desc = `[${r1},${c1}]&rarr;[${r2},${c2}]`;
        if (r1 === r2) desc += ` (gộp ${c2 - c1 + 1} cột)`;
        if (c1 === c2) desc += ` (gộp ${r2 - r1 + 1} hàng)`;
        chip.innerHTML = `<span>${desc}</span><button onclick="removeSpan(${idx})">&times;</button>`;
        box.appendChild(chip);
      });
    }

    function addSpanFromInputs() {
      const r1 = parseInt(document.getElementById('span_r1').value);
      const c1 = parseInt(document.getElementById('span_c1').value);
      const r2 = parseInt(document.getElementById('span_r2').value);
      const c2 = parseInt(document.getElementById('span_c2').value);
      if (r2 < r1 || c2 < c1) {
        alert('Tọa độ kết thúc (r2, c2) phải lớn hơn hoặc bằng tọa độ bắt đầu (r1, c1)!');
        return;
      }
      currentSpans.push([r1, c1, r2, c2]);
      renderSpansList();
      renderGridPreview();
    }

    function removeSpan(idx) {
      currentSpans.splice(idx, 1);
      renderSpansList();
      renderGridPreview();
    }

    function copyFromPred() {
      const t = filteredTables[currentIndex];
      document.getElementById('n_rows').value = t.n_rows_pred;
      document.getElementById('n_cols').value = t.n_cols_pred;
      currentSpans = JSON.parse(JSON.stringify(t.spans_pred || []));
      renderSpansList();
      renderGridPreview();
    }

    function renderGridPreview() {
      const n_rows = parseInt(document.getElementById('n_rows').value) || 1;
      const n_cols = parseInt(document.getElementById('n_cols').value) || 1;
      const hdr0 = document.getElementById('hdr_0').checked;
      const hdr1 = document.getElementById('hdr_1').checked;

      const spanMap = {};
      const covered = new Set();
      currentSpans.forEach(s => {
        const r1 = s[0], c1 = s[1], r2 = s[2], c2 = s[3];
        spanMap[`${r1},${c1}`] = [r2 - r1 + 1, c2 - c1 + 1];
        for (let r = r1; r <= r2; r++) {
          for (let c = c1; c <= c2; c++) {
            if (r !== r1 || c !== c1) covered.add(`${r},${c}`);
          }
        }
      });

      let html = '<table class="table-preview">';
      for (let r = 0; r < n_rows; r++) {
        html += '<tr>';
        const isHeader = (r === 0 && hdr0) || (r === 1 && hdr1);
        const tag = isHeader ? 'th' : 'td';
        for (let c = 0; c < n_cols; c++) {
          if (covered.has(`${r},${c}`)) continue;
          if (spanMap[`${r},${c}`]) {
            const [rowspan, colspan] = spanMap[`${r},${c}`];
            html += `<${tag} class="merged" rowspan="${rowspan}" colspan="${colspan}">r${r}c${c} (${rowspan}x${colspan})</${tag}>`;
          } else {
            html += `<${tag}>r${r}c${c}</${tag}>`;
          }
        }
        html += '</tr>';
      }
      html += '</table>';
      document.getElementById('gridPreviewBox').innerHTML = html;
    }

    async function saveGroundTruth() {
      const t = filteredTables[currentIndex];
      const n_rows = parseInt(document.getElementById('n_rows').value);
      const n_cols = parseInt(document.getElementById('n_cols').value);
      const header_rows = [];
      if (document.getElementById('hdr_0').checked) header_rows.push(0);
      if (document.getElementById('hdr_1').checked) header_rows.push(1);

      const payload = {
        table_id: t.table_id,
        n_rows: n_rows,
        n_cols: n_cols,
        spans: currentSpans,
        header_rows: header_rows,
        description: t.description,
        page: t.page,
        test_group: t.group_id,
        group_name: t.group_name
      };

      const res = await fetch('/api/save_gt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.status === 'ok') {
        t.is_reviewed = true;
        t.gt_data = payload;
        updateProgress();
        nextTable();
      } else {
        alert('Lỗi lưu GT: ' + data.error);
      }
    }

    function prevTable() {
      if (currentIndex > 0) loadTable(currentIndex - 1);
    }

    function nextTable() {
      if (currentIndex < filteredTables.length - 1) {
        loadTable(currentIndex + 1);
      } else {
        alert('🎉 Bạn đã đi hết danh sách bảng trong bộ lọc hiện tại!');
      }
    }

    function updateProgress() {
      const total = allTables.length;
      const done = allTables.filter(t => t.is_reviewed).length;
      const pct = total ? Math.round((done / total) * 100) : 0;
      document.getElementById('progressBar').style.width = pct + '%';
      document.getElementById('progressText').innerText = `${done} / ${total} (${pct}%)`;
    }

    async function openEvalModal() {
      document.getElementById('evalModal').style.display = 'flex';
      document.getElementById('evalBody').innerHTML = '<p>⏳ Đang tính toán ma trận TEDS-Struct và độ chính xác...</p>';
      const res = await fetch('/api/run_eval', { method: 'POST' });
      const data = await res.json();

      if (data.error) {
        document.getElementById('evalBody').innerHTML = `<p style="color:#ef4444;">⚠️ ${data.error}</p>`;
        return;
      }

      let errHtml = '';
      for (const [k, v] of Object.entries(data.error_distribution || {})) {
        errHtml += `<li><b>${k}</b>: ${v} bảng</li>`;
      }

      document.getElementById('evalBody').innerHTML = `
        <div style="background:#0f172a; padding:15px; border-radius:6px; margin-bottom:15px; border:1px solid #334155;">
          <h4 style="color:#10b981; margin-bottom:8px;">Tổng quan kết quả (${data.total_tables} bảng đã có GT):</h4>
          <p>• <b>Độ chính xác số Hàng (Row Acc):</b> ${(data.row_accuracy * 100).toFixed(1)}%</p>
          <p>• <b>Độ chính xác số Cột (Col Acc):</b> ${(data.col_accuracy * 100).toFixed(1)}%</p>
          <p>• <b>Độ khớp Lưới (Grid Exact Match):</b> ${(data.exact_grid_accuracy * 100).toFixed(1)}%</p>
          <p>• <b>Span F1 (Ô gộp / Header 2 tầng):</b> ${(data.avg_span_f1 * 100).toFixed(1)}%</p>
          <p>• <b>TEDS-Struct:</b> <b style="color:#60a5fa;">${data.avg_teds_struct.toFixed(4)}</b></p>
        </div>
        <h4 style="margin-bottom:6px;">Phân bố lỗi phát hiện:</h4>
        <ul style="padding-left:20px;">${errHtml || '<li>Không ghi nhận lỗi</li>'}</ul>
      `;
    }

    function closeEvalModal(e) {
      document.getElementById('evalModal').style.display = 'none';
    }

    // Phím tắt
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey && e.key === 's') || (e.key === 'Enter' && e.target.tagName !== 'INPUT')) {
        e.preventDefault();
        saveGroundTruth();
      } else if (e.key === 'ArrowLeft' && e.target.tagName !== 'INPUT') {
        prevTable();
      } else if (e.key === 'ArrowRight' && e.target.tagName !== 'INPUT') {
        nextTable();
      }
    });

    window.onload = init;
  </script>
</body>
</html>
"""


class ReviewerHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            return

        elif path == "/api/tables":
            tables_data = self._get_tables_data()
            self._send_json(tables_data)
            return

        elif path.startswith("/images/"):
            img_name = path.replace("/images/", "")
            img_path = IMG_DIR / img_name
            if img_path.exists():
                self.send_response(200)
                mime = mimetypes.guess_type(str(img_path))[0] or "image/png"
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(img_path.stat().st_size))
                self.end_headers()
                self.wfile.write(img_path.read_bytes())
                return
            else:
                self.send_error(404, f"Image not found: {img_name}")
                return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/save_gt":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                data = json.loads(body)
                bid = data["table_id"]
                out_gt_file = GT_DIR / f"{bid}.json"
                out_gt_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.info("Đã lưu Ground Truth: %s", out_gt_file.name)
                self._send_json({"status": "ok", "saved": bid})
            except Exception as e:
                logger.error("Lỗi lưu GT: %s", e)
                self._send_json({"status": "error", "error": str(e)}, status=500)
            return

        elif path == "/api/run_eval":
            try:
                res = run_evaluation(GT_DIR, PRED_DIR)
                self._send_json(res)
            except Exception as e:
                logger.error("Lỗi chạy eval: %s", e)
                self._send_json({"error": str(e)}, status=500)
            return

        self.send_error(404, "Not Found")

    def _get_tables_data(self) -> list[dict[str, Any]]:
        if not MANIFEST_PATH.exists():
            return []
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        data = []
        for item in manifest:
            bid = item["table_id"]
            pred_meta_file = PRED_DIR / f"{bid}.json"
            pred_meta = {}
            if pred_meta_file.exists():
                try:
                    pred_meta = json.loads(pred_meta_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

            gt_file = GT_DIR / f"{bid}.json"
            is_reviewed = gt_file.exists()
            gt_data = None
            if is_reviewed:
                try:
                    gt_data = json.loads(gt_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

            data.append({
                "table_id": bid,
                "page": item["page"],
                "group_id": item["group_id"],
                "group_name": item["group_name"],
                "description": item["description"],
                "format": item["format"],
                "n_rows_pred": pred_meta.get("n_rows_pred", item.get("n_rows", 0)),
                "n_cols_pred": pred_meta.get("n_cols_pred", item.get("n_cols", 0)),
                "spans_pred": pred_meta.get("spans_pred", []),
                "is_reviewed": is_reviewed,
                "gt_data": gt_data,
            })
        return data

    def _send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        # Giảm ồn console log
        return


def run_server(port: int = PORT) -> None:
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, ReviewerHandler)
    url = f"http://localhost:{port}"
    print("\n" + "=" * 65)
    print(" 🚀 LOCAL TABLE REVIEWER SERVER ĐANG CHẠY:")
    print(f" 👉 Mở trình duyệt tại: {url}")
    print(" 💾 Ground Truth sẽ tự động lưu vào: evaluation_table/ground_truth/")
    print(" ⌨️  Nhấn Ctrl + C để dừng server.")
    print("=" * 65 + "\n")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng server.")


if __name__ == "__main__":
    run_server()
