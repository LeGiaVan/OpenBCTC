"""
scripts/query_db.py — Công cụ CLI trực quan để truy vấn toàn bộ dữ liệu trong CSDL SQLite.
Hỗ trợ:
  - Tự động nhận diện file CSDL (data/benchmark_vnm.db, data/finaudit.db...)
  - Query all các bảng: companies, financial_statements, financial_facts, financial_ratios
  - Xem thống kê tổng quan (Overview / Summary Stats)
  - Lọc theo bảng, mã công ty, năm tài chính
  - Chạy câu lệnh SQL tùy ý (--sql)
  - Xuất định dạng JSON (--json)
  - Giao diện bảng Rich Console đẹp mắt, có màu sắc trực quan
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

# Đảm bảo mã hóa UTF-8 trên Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Kiểm tra thư viện rich
try:
    from rich.box import ROUNDED
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    HAS_RICH = True
    console = Console()
except ImportError:
    HAS_RICH = False
    console = None


def find_default_db() -> Path:
    """Tự động tìm kiếm file CSDL phù hợp nhất trong thư mục data/."""
    candidates = [
        Path("data/benchmark_vnm.db"),
        Path("data/finaudit.db"),
    ]
    for c in candidates:
        if c.exists() and c.stat().st_size > 0:
            return c

    # Tìm file *.db bất kỳ trong data/
    data_dir = Path("data")
    if data_dir.exists():
        dbs = list(data_dir.glob("*.db"))
        if dbs:
            return dbs[0]

    return Path("data/finaudit.db")


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Tạo kết nối tới SQLite và trả về row dạng từ điển."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def get_all_tables(conn: sqlite3.Connection) -> list[str]:
    """Lấy danh sách tất cả các bảng người dùng trong CSDL."""
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
    )
    return [row[0] for row in cur.fetchall()]


def format_number(val: Any, col_name: str = "") -> str:
    """Định dạng số thực hoặc nguyên dễ đọc."""
    if val is None:
        return ""
    if col_name.lower() in ("year", "năm", "page", "trang"):
        return str(val)
    if isinstance(val, (int, float)):
        if isinstance(val, int) or (isinstance(val, float) and val.is_integer()):
            return f"{int(val):,}"
        return f"{val:,.4f}".rstrip("0").rstrip(".")
    return str(val)


def print_table_data(
    title: str,
    headers: list[str],
    rows: list[list[Any]],
    max_col_width: int = 40,
) -> None:
    """In bảng dữ liệu bằng rich Table hoặc fallback thuần ASCII."""
    if not rows:
        if HAS_RICH and console:
            console.print(f"[yellow]⚠️  Bảng {title} không có dữ liệu.[/yellow]")
        else:
            print(f"Bảng {title} không có dữ liệu.\n")
        return

    if HAS_RICH and console:
        table = Table(title=title, box=ROUNDED, header_style="bold cyan", title_style="bold green")
        for h in headers:
            justify = "right" if any(h.lower().endswith(k) for k in ["val", "value", "id", "page", "count", "year"]) else "left"
            table.add_column(h, justify=justify, overflow="fold")

        for row in rows:
            formatted_row = []
            for h, cell in zip(headers, row, strict=False):
                cell_str = format_number(cell, h) if isinstance(cell, (int, float)) else str(cell if cell is not None else "")
                
                # Cắt ngắn nếu quá dài
                if len(cell_str) > max_col_width and not h.lower() in ("concept", "raw_label", "formula"):
                    cell_str = cell_str[: max_col_width - 3] + "..."

                # Highlight trạng thái kiểm toán
                if h == "verification_status":
                    if cell_str == "VERIFIED":
                        cell_str = f"[bold green]{cell_str}[/bold green]"
                    elif cell_str == "DISCREPANCY":
                        cell_str = f"[bold red]{cell_str}[/bold red]"
                    elif cell_str == "UNCHECKED":
                        cell_str = f"[yellow]{cell_str}[/yellow]"

                formatted_row.append(cell_str)
            table.add_row(*formatted_row)

        console.print(table)
        console.print()
    else:
        # Fallback console ASCII
        print(f"=== {title} ({len(rows)} bản ghi) ===")
        header_str = " | ".join(headers)
        print(header_str)
        print("-" * len(header_str))
        for row in rows:
            print(" | ".join(str(c if c is not None else "") for c in row))
        print("\n")


def display_overview(conn: sqlite3.Connection, db_path: Path) -> None:
    """Hiển thị bảng thống kê tổng quan toàn bộ CSDL."""
    tables = get_all_tables(conn)
    cur = conn.cursor()

    stats_rows = []
    total_records = 0
    for t in tables:
        count = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        total_records += count
        stats_rows.append([t, count])

    if HAS_RICH and console:
        panel_content = (
            f"[bold cyan]Database Path:[/bold cyan] {db_path.resolve()}\n"
            f"[bold cyan]Dung lượng:[/bold cyan] {db_path.stat().st_size / 1024:.2f} KB\n"
            f"[bold cyan]Tổng số bảng:[/bold cyan] {len(tables)}\n"
            f"[bold cyan]Tổng số bản ghi:[/bold cyan] {total_records:,}"
        )
        console.print(Panel(panel_content, title="[bold magenta]📊 THÔNG TIN CƠ SỞ DỮ LIỆU[/bold magenta]", box=ROUNDED))

        overview_table = Table(title="Danh Sách Các Bảng", box=ROUNDED, header_style="bold yellow")
        overview_table.add_column("Tên Bảng", style="bold")
        overview_table.add_column("Số Lượng Bản Ghi", justify="right", style="green")

        for t_name, count in stats_rows:
            overview_table.add_row(t_name, f"{count:,}")

        console.print(overview_table)
        console.print()
    else:
        print(f"DATABASE: {db_path} ({total_records} records in {len(tables)} tables)")
        for t_name, count in stats_rows:
            print(f"  - {t_name}: {count} records")
        print()


def query_companies(conn: sqlite3.Connection, company_code: str | None = None) -> None:
    """Query và in bảng companies."""
    sql = "SELECT code, name, industry, created_at FROM companies"
    params = []
    if company_code:
        sql += " WHERE code = ?"
        params.append(company_code.upper())
    sql += " ORDER BY code;"

    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    headers = ["Code", "Tên Doanh Nghiệp", "Ngành", "Ngày Tạo"]
    print_table_data("Bảng: companies", headers, [list(r) for r in rows])


def query_financial_statements(
    conn: sqlite3.Connection,
    company_code: str | None = None,
    year: int | None = None,
) -> None:
    """Query và in bảng financial_statements."""
    sql = """
    SELECT id, company, year, period, statement_type, is_balanced,
           total_checks, source_file, created_at
    FROM financial_statements
    """
    conditions = []
    params = []
    if company_code:
        conditions.append("company = ?")
        params.append(company_code.upper())
    if year:
        conditions.append("year = ?")
        params.append(year)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY company, year DESC;"

    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    headers = [
        "Statement ID", "Công Ty", "Năm", "Kỳ", "Loại BC",
        "Cân Đối?", "Số Checks", "File Gốc", "Ngày Lưu"
    ]
    print_table_data("Bảng: financial_statements", headers, [list(r) for r in rows])


def query_financial_ratios(
    conn: sqlite3.Connection,
    company_code: str | None = None,
    year: int | None = None,
    limit: int | None = None,
) -> None:
    """Query và in bảng financial_ratios."""
    sql = """
    SELECT id, company, year, ratio_name, ratio_category, value, formula, is_deterministic
    FROM financial_ratios
    """
    conditions = []
    params = []
    if company_code:
        conditions.append("company = ?")
        params.append(company_code.upper())
    if year:
        conditions.append("year = ?")
        params.append(year)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY company, year, ratio_category, ratio_name"

    if limit and limit > 0:
        sql += f" LIMIT {limit}"

    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    headers = [
        "Ratio ID", "Công Ty", "Năm", "Tên Chỉ Số", "Phân Loại",
        "Giá Trị", "Công Thức", "Định Lượng?"
    ]
    title = "Bảng: financial_ratios"
    if limit and limit > 0 and len(rows) == limit:
        title += f" (Giới hạn hiển thị {limit} dòng)"
    print_table_data(title, headers, [list(r) for r in rows])


def query_financial_facts(
    conn: sqlite3.Connection,
    company_code: str | None = None,
    year: int | None = None,
    limit: int | None = None,
    verification_status: str | None = None,
) -> None:
    """Query và in bảng financial_facts."""
    sql = """
    SELECT id, company, year, period_type, standard_code, concept,
           value, unit, page, verification_status, confidence
    FROM financial_facts
    """
    conditions = []
    params = []
    if company_code:
        conditions.append("company = ?")
        params.append(company_code.upper())
    if year:
        conditions.append("year = ?")
        params.append(year)
    if verification_status:
        conditions.append("verification_status = ?")
        params.append(verification_status.upper())

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY company, year, page, id"

    if limit and limit > 0:
        sql += f" LIMIT {limit}"

    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()

    headers = [
        "Fact ID", "Công Ty", "Năm", "Loại Kỳ", "Mã Số", "Khoản Mục (Concept)",
        "Giá Trị", "Đơn Vị", "Trang", "Trạng Thái", "Độ Tin Cậy"
    ]
    title = "Bảng: financial_facts"
    if limit and limit > 0 and len(rows) == limit:
        title += f" (Giới hạn hiển thị {limit} dòng. Dùng --all hoặc --limit 0 để xem hết)"

    print_table_data(title, headers, [list(r) for r in rows])


def query_generic_table(
    conn: sqlite3.Connection,
    table_name: str,
    limit: int | None = None,
) -> None:
    """Query bất kỳ bảng nào chưa có hàm định dạng riêng."""
    cur = conn.cursor()
    sql = f"SELECT * FROM {table_name}"
    if limit and limit > 0:
        sql += f" LIMIT {limit}"

    cur.execute(sql)
    rows = cur.fetchall()
    headers = [desc[0] for desc in cur.description] if cur.description else []
    print_table_data(f"Bảng: {table_name}", headers, [list(r) for r in rows])


def run_custom_sql(conn: sqlite3.Connection, sql: str) -> None:
    """Chạy câu truy vấn SQL tùy ý."""
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    if cur.description:
        headers = [desc[0] for desc in cur.description]
        print_table_data(f"Kết Quả SQL: [italic]{sql}[/italic]", headers, [list(r) for r in rows])
    else:
        conn.commit()
        if HAS_RICH and console:
            console.print(f"[bold green]✓ Thực thi thành công. Số hàng ảnh hưởng: {cur.rowcount}[/bold green]")
        else:
            print(f"Thực thi thành công. Số hàng ảnh hưởng: {cur.rowcount}")


def export_all_to_json(conn: sqlite3.Connection) -> str:
    """Trích xuất toàn bộ dữ liệu CSDL thành JSON dictionary."""
    tables = get_all_tables(conn)
    cur = conn.cursor()
    db_dump: dict[str, list[dict[str, Any]]] = {}

    for t in tables:
        cur.execute(f"SELECT * FROM {t}")
        rows = cur.fetchall()
        db_dump[t] = [dict(r) for r in rows]

    return json.dumps(db_dump, ensure_ascii=False, indent=2, default=str)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FinAudit AI — Trình truy vấn và xem dữ liệu SQLite Database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ sử dụng:
  python scripts/query_db.py                          # Query all mọi bảng trong DB mặc định
  python scripts/query_db.py --all                    # Hiển thị toàn bộ dòng (không giới hạn facts)
  python scripts/query_db.py --stats                  # Chỉ hiển thị thống kê tổng quan
  python scripts/query_db.py --table financial_ratios # Chỉ xem bảng chỉ số tài chính
  python scripts/query_db.py --table financial_facts --limit 20 # Xem 20 facts
  python scripts/query_db.py --company VNM --year 2024          # Lọc theo công ty và năm
  python scripts/query_db.py --sql "SELECT concept, value, unit FROM financial_facts LIMIT 5"
  python scripts/query_db.py --db data/benchmark_vnm.db         # Chỉ định file DB khác
  python scripts/query_db.py --json > data/dump.json            # Xuất toàn bộ ra JSON
        """,
    )

    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Đường dẫn đến file SQLite DB (mặc định: tự động tìm trong data/)",
    )
    parser.add_argument(
        "-t", "--table",
        type=str,
        default=None,
        help="Chỉ query một bảng cụ thể (ví dụ: companies, financial_statements, financial_facts, financial_ratios)",
    )
    parser.add_argument(
        "-c", "--company",
        type=str,
        default=None,
        help="Lọc theo mã chứng khoán / doanh nghiệp (ví dụ: VNM)",
    )
    parser.add_argument(
        "-y", "--year",
        type=int,
        default=None,
        help="Lọc theo năm tài chính (ví dụ: 2024)",
    )
    parser.add_argument(
        "--status",
        type=str,
        default=None,
        choices=["VERIFIED", "DISCREPANCY", "UNCHECKED"],
        help="Lọc facts theo trạng thái kiểm toán",
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=100,
        help="Giới hạn số dòng hiển thị cho bảng facts (mặc định: 100, 0 = không giới hạn)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Hiển thị tất cả dòng dữ liệu không bị giới hạn limit",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Chỉ hiển thị tổng quan thống kê các bảng, không in chi tiết từng dòng",
    )
    parser.add_argument(
        "--sql",
        type=str,
        default=None,
        help="Thực thi một câu lệnh SQL tùy ý trực tiếp trên CSDL",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Xuất toàn bộ dữ liệu CSDL ra định dạng JSON",
    )

    args = parser.parse_args()

    # 1. Xác định file DB
    if args.db:
        db_path = Path(args.db)
    else:
        db_path = find_default_db()

    if not db_path.exists():
        print(f"❌ Lỗi: Không tìm thấy file CSDL tại '{db_path}'.", file=sys.stderr)
        print("Gợi ý: Kiểm tra thư mục data/ hoặc chỉ định bằng cờ --db <đường_dẫn>", file=sys.stderr)
        sys.exit(1)

    # 2. Kết nối
    conn = get_connection(db_path)

    # 3. Xuất JSON nếu được yêu cầu
    if args.json:
        print(export_all_to_json(conn))
        conn.close()
        return

    # 4. Chạy câu lệnh SQL tùy ý
    if args.sql:
        run_custom_sql(conn, args.sql)
        conn.close()
        return

    # 5. Hiển thị Overview
    display_overview(conn, db_path)

    if args.stats:
        conn.close()
        return

    # Xác định giới hạn dòng
    effective_limit = None if args.all or args.limit == 0 else args.limit

    # 6. Query theo bảng chỉ định hoặc query all
    tables = get_all_tables(conn)

    target_table = args.table.lower().strip() if args.table else None

    # Ánh xạ tên ngắn
    short_names = {
        "company": "companies",
        "companies": "companies",
        "statement": "financial_statements",
        "statements": "financial_statements",
        "fact": "financial_facts",
        "facts": "financial_facts",
        "ratio": "financial_ratios",
        "ratios": "financial_ratios",
    }
    if target_table in short_names:
        target_table = short_names[target_table]

    if target_table:
        if target_table not in tables:
            print(f"❌ Lỗi: Bảng '{target_table}' không tồn tại trong CSDL. Các bảng hiện có: {', '.join(tables)}")
            conn.close()
            sys.exit(1)

        if target_table == "companies":
            query_companies(conn, company_code=args.company)
        elif target_table == "financial_statements":
            query_financial_statements(conn, company_code=args.company, year=args.year)
        elif target_table == "financial_facts":
            query_financial_facts(
                conn,
                company_code=args.company,
                year=args.year,
                limit=effective_limit,
                verification_status=args.status,
            )
        elif target_table == "financial_ratios":
            query_financial_ratios(
                conn,
                company_code=args.company,
                year=args.year,
                limit=effective_limit,
            )
        else:
            query_generic_table(conn, target_table, limit=effective_limit)
    else:
        # QUERY ALL TẤT CẢ CÁC BẢNG THEO THỨ TỰ LOGIC
        if "companies" in tables:
            query_companies(conn, company_code=args.company)

        if "financial_statements" in tables:
            query_financial_statements(conn, company_code=args.company, year=args.year)

        if "financial_ratios" in tables:
            query_financial_ratios(
                conn,
                company_code=args.company,
                year=args.year,
                limit=effective_limit,
            )

        if "financial_facts" in tables:
            query_financial_facts(
                conn,
                company_code=args.company,
                year=args.year,
                limit=effective_limit,
                verification_status=args.status,
            )

        # Các bảng khác nếu có
        for t in tables:
            if t not in ["companies", "financial_statements", "financial_facts", "financial_ratios"]:
                query_generic_table(conn, t, limit=effective_limit)

    conn.close()


if __name__ == "__main__":
    main()
