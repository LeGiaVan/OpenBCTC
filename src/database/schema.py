"""
schema.py — Định nghĩa DDL SQLite cho lưu trữ Fact tài chính và Chỉ số tỷ số.
Thiết kế chuẩn hóa để truy vấn SQL tốc độ cao và phục vụ Deterministic Formula Engine.
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS companies (
    code TEXT PRIMARY KEY,
    name TEXT,
    industry TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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

-- Index tối ưu truy vấn theo doanh nghiệp, năm và mã khoản mục
CREATE INDEX IF NOT EXISTS idx_facts_company_year ON financial_facts(company, year);
CREATE INDEX IF NOT EXISTS idx_facts_concept ON financial_facts(concept);
CREATE INDEX IF NOT EXISTS idx_facts_prov_id ON financial_facts(prov_id);
CREATE INDEX IF NOT EXISTS idx_ratios_company_year ON financial_ratios(company, year);
CREATE INDEX IF NOT EXISTS idx_ratios_name ON financial_ratios(ratio_name);
"""
