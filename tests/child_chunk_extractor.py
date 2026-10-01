# -*- coding: utf-8 -*-
"""
child_chunk_extractor.py — Công cụ trích xuất Child Chunks độc lập từ Markdown BCTC phân cấp.

Module này hoạt động độc lập (không can thiệp vào core workflow), bóc tách các đề mục
H3, H4, H5 trong file Báo cáo tài chính đã qua phân cấp (ví dụ: outputs/vnm_2024_triaged.md).
Mỗi Child Chunk đại diện cho một đơn vị tìm kiếm ngữ nghĩa tinh gọn (Fine-grained Searchable Unit),
lưu trữ đầy đủ phả hệ (breadcrumb, parent_id), mã tham chiếu kế toán chuẩn hóa (reference_code),
đoạn trích văn xuôi mở đầu (text_snippet) phục vụ sửa lỗi chính tả mini-LLM, cùng metadata bảng biểu.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Optional
import unicodedata


def clean_vietnamese_text(text: str) -> str:
    """Làm sạch ký tự định dạng markdown thừa và khoảng trắng."""
    text = re.sub(r"[*_~`]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def slugify_vietnamese(text: str) -> str:
    """Chuyển chuỗi tiếng Việt thành slug ASCII an toàn cho định danh ID."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "d")
    text = re.sub(r"[^a-zA-Z0-9\s_-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text).strip("_").lower()
    return text[:60]


@dataclass
class ChildChunk:
    """Đơn vị tìm kiếm ngữ nghĩa con (Child Chunk) trong kiến trúc Parent-Child RAG."""

    chunk_id: str
    parent_id: str
    doc_id: str
    level: int  # 3: H3, 4: H4, 5: H5
    title: str  # Raw title
    clean_title: str
    reference_code: str  # e.g., 'V.19', 'VI.1', 'CORE_BALANCE_SHEET', 'I.4(a)'
    breadcrumb: str
    breadcrumb_path: list[str] = field(default_factory=list)
    page_hint: Optional[str] = None
    text_snippet: str = ""  # Đoạn văn xuôi mở đầu, dành cho mini-LLM sửa chính tả
    full_content: str = ""  # Nội dung toàn bộ section (Markdown)
    has_table: bool = False
    table_count: int = 0
    table_headers: list[str] = field(default_factory=list)
    char_count: int = 0
    word_count: int = 0
    search_payload: str = ""  # Chuỗi tối ưu cho BM25 & Dense Embedding
    needs_spellcheck: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Chuyển thành dict có thể tuần tự hóa JSON."""
        return asdict(self)


class ChildChunkExtractor:
    """Bộ bóc tách Child Chunks từ tệp Markdown báo cáo tài chính phân cấp."""

    # Regex nhận diện các BCTC cốt lõi
    CORE_STATEMENTS_MAP = {
        "bảng cân đối kế toán": "CORE_BALANCE_SHEET",
        "báo cáo tình hình tài chính": "CORE_BALANCE_SHEET",
        "báo cáo kết quả hoạt động kinh doanh": "CORE_INCOME_STATEMENT",
        "báo cáo kết quả kinh doanh": "CORE_INCOME_STATEMENT",
        "báo cáo lưu chuyển tiền tệ": "CORE_CASH_FLOW",
    }

    def __init__(self, doc_id: str = "vnm_2024") -> None:
        self.doc_id = doc_id

    def extract_from_file(self, md_path: Path | str) -> list[ChildChunk]:
        """Đọc tệp Markdown và trích xuất danh sách Child Chunks."""
        path = Path(md_path)
        if not path.is_file():
            raise FileNotFoundError(f"Không tìm thấy tệp Markdown: {path}")
        md_text = path.read_text(encoding="utf-8")
        return self.extract_from_markdown(md_text)

    def extract_from_markdown(self, md_text: str) -> list[ChildChunk]:
        """Thuật toán duyệt Heading State Machine trích xuất phân cấp Child Chunks."""
        lines = md_text.splitlines()

        # 1. Thu thập tiêu đề tài liệu gốc (H1)
        root_title = f"BÁO CÁO TÀI CHÍNH — {self.doc_id.upper()}"
        for line in lines[:10]:
            if line.strip().startswith("# "):
                root_title = clean_vietnamese_text(line.strip()[2:])
                break

        # 2. Quét các vị trí Heading H3, H4, H5
        heading_re = re.compile(r"^(#{3,5})\s+(.*)")
        entries: list[tuple[int, int, str]] = []  # (line_idx, level, raw_title)

        for i, line in enumerate(lines):
            line_str = line.strip()
            m = heading_re.match(line_str)
            if m:
                level = len(m.group(1))
                raw_title = m.group(2).strip()
                entries.append((i, level, raw_title))

        if not entries:
            return []

        # 3. Quản lý trạng thái phân cấp (Phả hệ)
        chunks: list[ChildChunk] = []

        # State tracking cho breadcrumb và parent_id
        current_h3_id: str = ""
        current_h3_title: str = ""
        current_h3_roman: str = ""

        current_h4_id: str = ""
        current_h4_title: str = ""
        current_h4_num: str = ""

        page_hint_re = re.compile(r"\*\((?:Trang|Trang\s+)?([0-9\u2013\-–]+)\)\*", re.IGNORECASE)

        for idx, (line_idx, level, raw_title) in enumerate(entries):
            # Biên dòng nội dung của section này
            content_start = line_idx + 1
            content_end = entries[idx + 1][0] if idx + 1 < len(entries) else len(lines)

            section_lines = lines[content_start:content_end]
            clean_title = self._clean_heading_title(raw_title, level)

            # Phân tích dải trang (nếu có ngay dưới heading)
            page_hint = None
            for s_line in section_lines[:4]:
                p_match = page_hint_re.search(s_line.strip())
                if p_match:
                    page_hint = f"Trang {p_match.group(1)}"
                    break

            # Phân tích bảng biểu Markdown
            tables: list[list[str]] = []
            current_tbl: list[str] = []
            for s_line in section_lines:
                strip_line = s_line.strip()
                if strip_line.startswith("|") and strip_line.endswith("|"):
                    current_tbl.append(strip_line)
                else:
                    if current_tbl:
                        tables.append(current_tbl)
                        current_tbl = []
            if current_tbl:
                tables.append(current_tbl)

            # Trích xuất danh sách cột chỉ tiêu từ các bảng
            table_headers: list[str] = []
            for tbl in tables:
                if len(tbl) >= 1:
                    headers = [c.strip() for c in tbl[0].split("|")[1:-1] if c.strip()]
                    table_headers.extend(headers)
            # Khử trùng lặp cột theo thứ tự xuất hiện
            table_headers = list(dict.fromkeys(table_headers))[:12]

            # Bóc tách đoạn văn xuôi thuần túy (loại bỏ bảng, page marker, dấu kẻ)
            narrative_lines: list[str] = []
            for s_line in section_lines:
                strip_line = s_line.strip()
                if not strip_line:
                    continue
                if strip_line.startswith("|") and strip_line.endswith("|"):
                    continue
                if strip_line.startswith("*(") and strip_line.endswith(")*"):
                    continue
                if strip_line.startswith("---") or strip_line.startswith("==="):
                    continue
                narrative_lines.append(strip_line)

            full_narrative = clean_vietnamese_text(" ".join(narrative_lines))
            text_snippet = full_narrative[:350] if full_narrative else ""

            # Nội dung Markdown đầy đủ của section
            full_content = "\n".join(section_lines).strip()

            # Xác định Reference Code & Breadcrumb theo cấp độ
            if level == 3:
                ref_code, roman = self._resolve_h3_code(clean_title)
                current_h3_roman = roman
                current_h3_title = clean_title
                current_h4_id = ""
                current_h4_title = ""
                current_h4_num = ""

                chunk_id = self._generate_chunk_id(self.doc_id, 3, ref_code, clean_title, idx + 1)
                parent_id = f"{self.doc_id}_root"
                current_h3_id = chunk_id

                breadcrumb_path = [root_title, clean_title]

            elif level == 4:
                ref_code, num = self._resolve_h4_code(clean_title, current_h3_roman)
                current_h4_num = num
                current_h4_title = clean_title

                chunk_id = self._generate_chunk_id(self.doc_id, 4, ref_code, clean_title, idx + 1)
                parent_id = current_h3_id or f"{self.doc_id}_root"
                current_h4_id = chunk_id

                breadcrumb_path = [root_title]
                if current_h3_title:
                    breadcrumb_path.append(current_h3_title)
                breadcrumb_path.append(clean_title)

            else:  # level == 5
                ref_code = self._resolve_h5_code(clean_title, current_h3_roman, current_h4_num)
                chunk_id = self._generate_chunk_id(self.doc_id, 5, ref_code, clean_title, idx + 1)
                parent_id = current_h4_id or current_h3_id or f"{self.doc_id}_root"

                breadcrumb_path = [root_title]
                if current_h3_title:
                    breadcrumb_path.append(current_h3_title)
                if current_h4_title:
                    breadcrumb_path.append(current_h4_title)
                breadcrumb_path.append(clean_title)

            breadcrumb_str = " > ".join(breadcrumb_path)

            # Tạo chuỗi Search Payload tối ưu cho Hybrid Search
            payload_parts = [f"[{ref_code}]" if ref_code else "", breadcrumb_str, clean_title]
            if table_headers:
                payload_parts.append(f"Chỉ tiêu bảng: {', '.join(table_headers[:6])}")
            if text_snippet:
                payload_parts.append(f"Mô tả: {text_snippet}")
            search_payload = " | ".join([p for p in payload_parts if p])

            needs_spellcheck = bool(text_snippet and len(text_snippet) > 15)

            chunk = ChildChunk(
                chunk_id=chunk_id,
                parent_id=parent_id,
                doc_id=self.doc_id,
                level=level,
                title=raw_title,
                clean_title=clean_title,
                reference_code=ref_code,
                breadcrumb=breadcrumb_str,
                breadcrumb_path=breadcrumb_path,
                page_hint=page_hint,
                text_snippet=text_snippet,
                full_content=full_content,
                has_table=len(tables) > 0,
                table_count=len(tables),
                table_headers=table_headers,
                char_count=len(full_content),
                word_count=len(full_content.split()),
                search_payload=search_payload,
                needs_spellcheck=needs_spellcheck,
            )
            chunks.append(chunk)

        return chunks

    def _clean_heading_title(self, raw_title: str, level: int) -> str:
        """Làm sạch tiêu đề, tách bỏ rác OCR hoặc header bảng dính kèm ở H5."""
        title = clean_vietnamese_text(raw_title)
        if level == 5:
            # Xử lý trường hợp H5 bị dính header bảng: (a) Các công ty con Tên Tru số Hoạt động...
            m = re.match(
                r"^(\([a-zA-Z0-9]+\)\s+[^:]+?)(?:\s+(?:Tên|Trụ sở|Tru so|Hoạt động|Lợi ích|31/12|1/1).*|$)",
                title,
                re.IGNORECASE,
            )
            if m:
                return m.group(1).strip()
        return title

    def _resolve_h3_code(self, title: str) -> tuple[str, str]:
        """Nhận diện mã chuẩn hóa cho H3 (Core Statements hoặc Thuyết minh La Mã)."""
        # 1. Ưu tiên nhận diện số La Mã ở đầu (xếp dài đến ngắn để tránh 'II' match 'I')
        m = re.match(r"^(VIII|VII|VI|IV|III|II|IX|I|V|X)\.?\s+", title, re.IGNORECASE)
        if m:
            roman = m.group(1).upper()
            return roman, roman

        # 2. Nếu không có số La Mã, kiểm tra 3 BCTC cốt lõi (loại trừ các phần thuyết minh bổ sung)
        lower_title = title.lower()
        if "thông tin bổ sung" not in lower_title and "thuyết minh" not in lower_title:
            for name, code in self.CORE_STATEMENTS_MAP.items():
                if name in lower_title:
                    return code, ""

        return "", ""

    def _resolve_h4_code(self, title: str, roman: str) -> tuple[str, str]:
        """Nhận diện mã chuẩn hóa cho H4 (ví dụ mục 19 dưới phần V -> V.19)."""
        m = re.match(r"^(\d+)\.?\s*", title)
        if m:
            num = m.group(1)
            ref_code = f"{roman}.{num}" if roman else num
            return ref_code, num
        return roman, ""

    def _resolve_h5_code(self, title: str, roman: str, num: str) -> str:
        """Nhận diện mã chuẩn hóa cho H5 (ví dụ tiểu mục (b) -> V.19(b))."""
        m = re.match(r"^\(?([a-zA-Z0-9]+)\)?\.?\s*", title)
        if m:
            sub = m.group(1).lower()
            base = f"{roman}.{num}" if (roman and num) else (roman or num)
            if base:
                return f"{base}({sub})"
            return f"({sub})"
        return f"{roman}.{num}" if (roman and num) else ""

    def _generate_chunk_id(
        self, doc_id: str, level: int, ref_code: str, clean_title: str, order: int
    ) -> str:
        """Sinh chunk_id duy nhất, có ý nghĩa ngữ nghĩa cao."""
        if ref_code:
            safe_code = re.sub(r"[^a-zA-Z0-9_]", "_", ref_code).lower().strip("_")
            return f"{doc_id}_c_h{level}_{safe_code}_{order:03d}"
        slug = slugify_vietnamese(clean_title)
        slug_short = slug[:30].rstrip("_")
        return f"{doc_id}_c_h{level}_{slug_short}_{order:03d}"

    def export_json(self, chunks: list[ChildChunk], output_path: Path | str, indent: int = 2) -> Path:
        """Xuất danh sách Child Chunks ra file JSON có cấu trúc."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "document_id": self.doc_id,
            "total_child_chunks": len(chunks),
            "hierarchy_breakdown": {
                "level_3_sections": len([c for c in chunks if c.level == 3]),
                "level_4_subsections": len([c for c in chunks if c.level == 4]),
                "level_5_subsubsections": len([c for c in chunks if c.level == 5]),
            },
            "tables_summary": {
                "chunks_with_tables": len([c for c in chunks if c.has_table]),
                "total_tables_detected": sum(c.table_count for c in chunks),
            },
            "spellcheck_candidates": len([c for c in chunks if c.needs_spellcheck]),
            "chunks": [c.to_dict() for c in chunks],
        }

        out.write_text(json.dumps(payload, ensure_ascii=False, indent=indent), encoding="utf-8")
        return out

    def get_summary_stats(self, chunks: list[ChildChunk]) -> dict[str, Any]:
        """Tạo từ điển thống kê tổng quan danh sách chunks."""
        return {
            "total_chunks": len(chunks),
            "h3_count": len([c for c in chunks if c.level == 3]),
            "h4_count": len([c for c in chunks if c.level == 4]),
            "h5_count": len([c for c in chunks if c.level == 5]),
            "chunks_with_tables": len([c for c in chunks if c.has_table]),
            "total_tables": sum(c.table_count for c in chunks),
            "spellcheck_candidates": len([c for c in chunks if c.needs_spellcheck]),
        }


def main() -> None:
    """CLI runner bóc tách trực tiếp file Markdown."""
    parser = argparse.ArgumentParser(
        description="Trích xuất Child Chunks độc lập từ Markdown BCTC phân cấp."
    )
    parser.add_argument(
        "--input",
        "-i",
        default="outputs/vnm_2024_triaged.md",
        help="Đường dẫn file Markdown đầu vào (mặc định: outputs/vnm_2024_triaged.md)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="outputs/vnm_2024_child_chunks.json",
        help="Đường dẫn file JSON kết quả (mặc định: outputs/vnm_2024_child_chunks.json)",
    )
    parser.add_argument(
        "--doc-id",
        "-d",
        default="vnm_2024",
        help="Định danh tài liệu (mặc định: vnm_2024)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    print("=" * 70)
    print("FINAUDIT AI — ĐỘC LẬP TRÍCH XUẤT CHILD CHUNKS CHO PARENT-CHILD RAG")
    print("=" * 70)
    print(f"File nguồn: {input_path}")
    print(f"File đích : {output_path}")

    extractor = ChildChunkExtractor(doc_id=args.doc_id)
    chunks = extractor.extract_from_file(input_path)
    out_file = extractor.export_json(chunks, output_path)

    stats = extractor.get_summary_stats(chunks)
    print("\n[+] KẾT QUẢ TRÍCH XUẤT:")
    print(f"  - Tổng số Child Chunks       : {stats['total_chunks']}")
    print(f"    + Cấp 3 (H3 Sections)      : {stats['h3_count']}")
    print(f"    + Cấp 4 (H4 Subsections)   : {stats['h4_count']}")
    print(f"    + Cấp 5 (H5 Sub-subsections): {stats['h5_count']}")
    print(f"  - Số chunk chứa Bảng biểu    : {stats['chunks_with_tables']} (Tổng {stats['total_tables']} bảng)")
    print(f"  - Đoạn cần Mini-LLM Spellcheck: {stats['spellcheck_candidates']}")
    print(f"\n[+] Đã lưu manifest JSON thành công tại: {out_file.resolve()}")

    print("\n--- MẪU 5 CHUNKS TIÊU BIỂU CHO HYBRID SEARCH ---")
    sample_codes = ["CORE_BALANCE_SHEET", "I.1", "V.19", "VI.1", "V.8"]
    sample_chunks = [c for c in chunks if any(code in c.reference_code for code in sample_codes)][:5]
    for c in sample_chunks:
        print(f"\n[ID: {c.chunk_id}] (Parent: {c.parent_id})")
        print(f"  Ref Code  : {c.reference_code}")
        print(f"  Breadcrumb: {c.breadcrumb}")
        print(f"  Tables    : {c.table_count} | Headers: {c.table_headers[:4]}")
        if c.text_snippet:
            print(f"  Snippet   : {c.text_snippet[:120]}...")


if __name__ == "__main__":
    main()
