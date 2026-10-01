"""
ontology.py — Financial Ontology và Canonical Concept Mapping theo Chuẩn mực Kế toán Việt Nam (Thông tư 200/2014/TT-BTC).
Định nghĩa ánh xạ từ mã số BCTC (100, 110, 270, 300, 440...) và tên chỉ tiêu tiếng Việt sang Canonical Concept.
Hỗ trợ phân định rành mạch 3 báo cáo: Bảng Cân đối kế toán (BS), Kết quả kinh doanh (IS), Lưu chuyển tiền tệ (CF).
"""

import re
from typing import NamedTuple


class ConceptDefinition(NamedTuple):
    concept: str
    code: str
    standard_name: str
    aliases: list[str]
    statement_type: str  # "BALANCE_SHEET" | "INCOME_STATEMENT" | "CASH_FLOW"


# Danh mục các khoản mục tài chính trọng yếu theo Thông tư 200
ONTOLOGY_DEFINITIONS: list[ConceptDefinition] = [
    # ── BẢNG CÂN ĐỐI KẾ TOÁN (TÀI SẢN - CÁC KHOẢN MỤC CHÍNH) ───────────────────
    ConceptDefinition(
        concept="TOTAL_ASSETS",
        code="270",
        standard_name="TỔNG CỘNG TÀI SẢN",
        aliases=[
            r"tổng cộng tài sản",
            r"tong cong tai san",
            r"tổng tài sản",
            r"tong tai san",
            r"^tài sản$",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="CURRENT_ASSETS",
        code="100",
        standard_name="TÀI SẢN NGẮN HẠN",
        aliases=[
            r"tài sản ngắn hạn",
            r"tai san ngan han",
            r"a\s*[-–]\s*tài sản ngắn hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="CASH_AND_EQUIVALENTS",
        code="110",
        standard_name="Tiền và các khoản tương đương tiền",
        aliases=[
            r"tiền và các khoản tương đương tiền",
            r"tiền và tương đương tiền",
            r"tien va tuong duong tien",
            r"i\.\s*tiền và các khoản tương đương tiền",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_INVESTMENTS",
        code="120",
        standard_name="Đầu tư tài chính ngắn hạn",
        aliases=[
            r"đầu tư tài chính ngắn hạn",
            r"dau tu tai chinh ngan han",
            r"các khoản đầu tư tài chính ngắn hạn",
            r"ii\.\s*đầu tư tài chính ngắn hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_RECEIVABLES",
        code="130",
        standard_name="Các khoản phải thu ngắn hạn",
        aliases=[
            r"^(?:iii\.\s*)?(?:các\s+khoản\s+)?phải\s+thu\s+ngắn\s+hạn(?:\s*\(.*\))?$",
            r"các khoản phải thu ngắn hạn",
            r"phải thu ngắn hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="INVENTORIES",
        code="140",
        standard_name="Hàng tồn kho",
        aliases=[
            r"^(?:iv\.\s*)?hàng\s+tồn\s+kho$",
            r"hàng tồn kho",
            r"hang ton kho",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="OTHER_CURRENT_ASSETS",
        code="150",
        standard_name="Tài sản ngắn hạn khác",
        aliases=[
            r"tài sản ngắn hạn khác",
            r"tai san ngan han khac",
            r"v\.\s*tài sản ngắn hạn khác",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="NON_CURRENT_ASSETS",
        code="200",
        standard_name="TÀI SẢN DÀI HẠN",
        aliases=[
            r"tài sản dài hạn",
            r"tai san dai han",
            r"b\s*[-–]\s*tài sản dài hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_RECEIVABLES",
        code="210",
        standard_name="Các khoản phải thu dài hạn",
        aliases=[
            r"^(?:i\.\s*)?(?:các\s+khoản\s+)?phải\s+thu\s+dài\s+hạn(?:\s*\(.*\))?$",
            r"các khoản phải thu dài hạn",
            r"phải thu dài hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="FIXED_ASSETS",
        code="220",
        standard_name="Tài sản cố định",
        aliases=[
            r"^(?:ii\.\s*)?tài\s+sản\s+cố\s+định(?:\s*\(.*\))?$",
            r"tài sản cố định",
            r"tai san co dinh",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="INVESTMENT_PROPERTIES",
        code="230",
        standard_name="Bất động sản đầu tư",
        aliases=[
            r"bất động sản đầu tư",
            r"bat dong san dau tu",
            r"iii\.\s*bất động sản đầu tư",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_ASSETS_IN_PROGRESS",
        code="240",
        standard_name="Tài sản dở dang dài hạn",
        aliases=[
            r"tài sản dở dang dài hạn",
            r"iv\.\s*tài sản dở dang dài hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_INVESTMENTS",
        code="250",
        standard_name="Đầu tư tài chính dài hạn",
        aliases=[
            r"đầu tư tài chính dài hạn",
            r"các khoản đầu tư tài chính dài hạn",
            r"v\.\s*đầu tư tài chính dài hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="OTHER_NON_CURRENT_ASSETS",
        code="260",
        standard_name="Tài sản dài hạn khác",
        aliases=[
            r"tài sản dài hạn khác",
            r"vi\.\s*tài sản dài hạn khác",
        ],
        statement_type="BALANCE_SHEET",
    ),

    # ── BẢNG CÂN ĐỐI KẾ TOÁN (CÁC KHOẢN MỤC CON CHI TIẾT) ─────────────────────
    ConceptDefinition(
        concept="SHORT_TERM_TRADE_RECEIVABLES",
        code="131",
        standard_name="Phải thu khách hàng",
        aliases=[r"phải thu khách hàng", r"phải thu của khách hàng"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_PREPAYMENTS",
        code="132",
        standard_name="Trả trước cho người bán",
        aliases=[r"trả trước cho người bán"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_OTHER_RECEIVABLES",
        code="136",
        standard_name="Phải thu ngắn hạn khác",
        aliases=[r"phải thu ngắn hạn khác"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_BAD_DEBT_PROVISION",
        code="137",
        standard_name="Dự phòng phải thu khó đòi",
        aliases=[r"dự phòng phải thu khó đòi", r"dự phòng phải thu ngắn hạn khó đòi"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="INVENTORY_GROSS",
        code="141",
        standard_name="Hàng tồn kho (nguyên giá)",
        aliases=[r"hàng tồn kho\s*\(nguyên giá\)"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="INVENTORY_PROVISION",
        code="149",
        standard_name="Dự phòng giảm giá hàng tồn kho",
        aliases=[r"dự phòng giảm giá hàng tồn kho"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_OTHER_RECEIVABLES",
        code="216",
        standard_name="Phải thu dài hạn khác",
        aliases=[r"phải thu dài hạn khác"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="TANGIBLE_FIXED_ASSETS",
        code="221",
        standard_name="Tài sản cố định hữu hình",
        aliases=[r"tài sản cố định hữu hình"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="INTANGIBLE_FIXED_ASSETS",
        code="227",
        standard_name="Tài sản cố định vô hình",
        aliases=[r"tài sản cố định vô hình"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="CONSTRUCTION_IN_PROGRESS",
        code="242",
        standard_name="Xây dựng cơ bản dở dang",
        aliases=[r"xây dựng cơ bản dở dang"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="CASH",
        code="111",
        standard_name="Tiền",
        aliases=[r"^1\.\s*tiền$", r"^tiền$"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="CASH_EQUIVALENTS",
        code="112",
        standard_name="Các khoản tương đương tiền",
        aliases=[r"tương đương tiền", r"2\.\s*các khoản tương đương tiền"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="TRADING_SECURITIES",
        code="121",
        standard_name="Chứng khoán kinh doanh",
        aliases=[r"chứng khoán kinh doanh"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="TRADING_SECURITIES_PROVISION",
        code="122",
        standard_name="Dự phòng giảm giá chứng khoán kinh doanh",
        aliases=[r"dự phòng giảm giá chứng khoán kinh doanh"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="HELD_TO_MATURITY_INVESTMENTS_SHORT",
        code="123",
        standard_name="Đầu tư nắm giữ đến ngày đáo hạn ngắn hạn",
        aliases=[r"đầu tư nắm giữ đến ngày đáo hạn", r"nắm giữ đến ngày đáo hạn"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_INTERNAL_RECEIVABLES",
        code="133",
        standard_name="Phải thu nội bộ ngắn hạn",
        aliases=[r"phải thu nội bộ ngắn hạn", r"phải thu nội bộ"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_CONSTRUCTION_RECEIVABLES",
        code="134",
        standard_name="Phải thu theo tiến độ kế hoạch hợp đồng xây dựng",
        aliases=[r"phải thu theo tiến độ", r"hợp đồng xây dựng"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_LOAN_RECEIVABLES",
        code="135",
        standard_name="Phải thu về cho vay ngắn hạn",
        aliases=[r"phải thu về cho vay ngắn hạn", r"phải thu về cho vay"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="ASSETS_AWAITING_RESOLUTION",
        code="139",
        standard_name="Tài sản thiếu chờ xử lý",
        aliases=[r"tài sản thiếu chờ xử lý"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_PREPAID_EXPENSES",
        code="151",
        standard_name="Chi phí trả trước ngắn hạn",
        aliases=[r"chi phí trả trước ngắn hạn"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="DEDUCTIBLE_VAT",
        code="152",
        standard_name="Thuế giá trị gia tăng được khấu trừ",
        aliases=[r"thuế giá trị gia tăng được khấu trừ", r"thuế gtgt được khấu trừ"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="TAXES_RECEIVABLE_FROM_STATE",
        code="153",
        standard_name="Thuế và các khoản khác phải thu Nhà nước",
        aliases=[r"thuế và các khoản khác phải thu nhà nước"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="GOVERNMENT_BOND_REPURCHASE",
        code="154",
        standard_name="Giao dịch mua bán lại trái phiếu Chính phủ",
        aliases=[r"giao dịch mua bán lại trái phiếu chính phủ"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="OTHER_SHORT_TERM_ASSETS_SUB",
        code="155",
        standard_name="Tài sản ngắn hạn khác",
        aliases=[r"tài sản ngắn hạn khác"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_TRADE_RECEIVABLES",
        code="211",
        standard_name="Phải thu dài hạn của khách hàng",
        aliases=[r"phải thu dài hạn của khách hàng", r"phải thu dài hạn khách hàng"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_PREPAYMENTS",
        code="212",
        standard_name="Trả trước cho người bán dài hạn",
        aliases=[r"trả trước cho người bán dài hạn"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_INTERNAL_CAPITAL",
        code="213",
        standard_name="Vốn kinh doanh ở đơn vị trực thuộc",
        aliases=[r"vốn kinh doanh ở đơn vị trực thuộc"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_INTERNAL_RECEIVABLES",
        code="214",
        standard_name="Phải thu nội bộ dài hạn",
        aliases=[r"phải thu nội bộ dài hạn"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_LOAN_RECEIVABLES",
        code="215",
        standard_name="Phải thu về cho vay dài hạn",
        aliases=[r"phải thu về cho vay dài hạn"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_BAD_DEBT_PROVISION",
        code="219",
        standard_name="Dự phòng phải thu dài hạn khó đòi",
        aliases=[r"dự phòng phải thu dài hạn khó đòi"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="TANGIBLE_FIXED_ASSETS_COST",
        code="222",
        standard_name="Nguyên giá TSCĐ hữu hình",
        aliases=[r"nguyên giá\s*\(tscđ hữu hình\)", r"nguyên giá tscđ hữu hình"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="TANGIBLE_FIXED_ASSETS_ACCUM_DEP",
        code="223",
        standard_name="Giá trị hao mòn lũy kế TSCĐ hữu hình",
        aliases=[r"giá trị hao mòn lũy kế.*hữu hình", r"hao mòn lũy kế.*hữu hình"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="FINANCE_LEASE_FIXED_ASSETS",
        code="224",
        standard_name="Tài sản cố định thuê tài chính",
        aliases=[r"tài sản cố định thuê tài chính", r"tscđ thuê tài chính"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="FINANCE_LEASE_COST",
        code="225",
        standard_name="Nguyên giá TSCĐ thuê tài chính",
        aliases=[r"nguyên giá.*thuê tài chính"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="FINANCE_LEASE_ACCUM_DEP",
        code="226",
        standard_name="Giá trị hao mòn lũy kế TSCĐ thuê tài chính",
        aliases=[r"hao mòn lũy kế.*thuê tài chính"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="INTANGIBLE_FIXED_ASSETS_COST",
        code="228",
        standard_name="Nguyên giá TSCĐ vô hình",
        aliases=[r"nguyên giá.*vô hình"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="INTANGIBLE_FIXED_ASSETS_ACCUM_DEP",
        code="229",
        standard_name="Giá trị hao mòn lũy kế TSCĐ vô hình",
        aliases=[r"hao mòn lũy kế.*vô hình"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="INVESTMENT_PROPERTIES_COST",
        code="231",
        standard_name="Nguyên giá bất động sản đầu tư",
        aliases=[r"nguyên giá.*bất động sản đầu tư"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="INVESTMENT_PROPERTIES_ACCUM_DEP",
        code="232",
        standard_name="Hao mòn lũy kế bất động sản đầu tư",
        aliases=[r"hao mòn lũy kế.*bất động sản đầu tư"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_WIP",
        code="241",
        standard_name="Chi phí sản xuất, kinh doanh dở dang dài hạn",
        aliases=[r"chi phí sản xuất,?\s*kinh doanh dở dang dài hạn"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="INVESTMENTS_IN_SUBSIDIARIES",
        code="251",
        standard_name="Đầu tư vào công ty con",
        aliases=[r"đầu tư vào công ty con"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="INVESTMENTS_IN_ASSOCIATES",
        code="252",
        standard_name="Đầu tư vào công ty liên doanh, liên kết",
        aliases=[r"đầu tư vào công ty liên doanh,?\s*liên kết", r"đầu tư vào công ty liên kết"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="OTHER_EQUITY_INVESTMENTS",
        code="253",
        standard_name="Đầu tư góp vốn vào đơn vị khác",
        aliases=[r"đầu tư góp vốn vào đơn vị khác"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_INVESTMENT_PROVISION",
        code="254",
        standard_name="Dự phòng đầu tư tài chính dài hạn",
        aliases=[r"dự phòng đầu tư tài chính dài hạn"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="HELD_TO_MATURITY_INVESTMENTS_LONG",
        code="255",
        standard_name="Đầu tư nắm giữ đến ngày đáo hạn dài hạn",
        aliases=[r"đầu tư nắm giữ đến ngày đáo hạn dài hạn"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_PREPAID_EXPENSES",
        code="261",
        standard_name="Chi phí trả trước dài hạn",
        aliases=[r"chi phí trả trước dài hạn"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="DEFERRED_TAX_ASSETS",
        code="262",
        standard_name="Tài sản thuế thu nhập hoãn lại",
        aliases=[r"tài sản thuế thu nhập hoãn lại", r"tài sản thuế tndn hoãn lại"],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="OTHER_LONG_TERM_ASSETS_SUB",
        code="268",
        standard_name="Tài sản dài hạn khác",
        aliases=[r"tài sản dài hạn khác"],
        statement_type="BALANCE_SHEET",
    ),

    # ── BẢNG CÂN ĐỐI KẾ TOÁN (NGUỒN VỐN) ─────────────────────────────────────────
    ConceptDefinition(
        concept="TOTAL_RESOURCES",
        code="440",
        standard_name="TỔNG CỘNG NGUỒN VỐN",
        aliases=[
            r"tổng cộng nguồn vốn",
            r"tong cong nguon von",
            r"tổng nguồn vốn",
            r"^nguồn vốn$",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LIABILITIES",
        code="300",
        standard_name="NỢ PHẢI TRẢ",
        aliases=[
            r"nợ phải trả",
            r"no phai tra",
            r"c\s*[-–]\s*nợ phải trả",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="CURRENT_LIABILITIES",
        code="310",
        standard_name="Nợ ngắn hạn",
        aliases=[
            r"nợ ngắn hạn",
            r"no ngan han",
            r"i\.\s*nợ ngắn hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="NON_CURRENT_LIABILITIES",
        code="330",
        standard_name="Nợ dài hạn",
        aliases=[
            r"nợ dài hạn",
            r"no dai han",
            r"ii\.\s*nợ dài hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="EQUITY",
        code="400",
        standard_name="VỐN CHỦ SỞ HỮU",
        aliases=[
            r"vốn chủ sở hữu",
            r"von chu so huu",
            r"d\s*[-–]\s*vốn chủ sở hữu",
        ],
        statement_type="BALANCE_SHEET",
    ),

    # ── BẢNG CÂN ĐỐI KẾ TOÁN (CHI TIẾT NỢ PHẢI TRẢ & VỐN CSH) ────────────────
    ConceptDefinition(
        concept="SHORT_TERM_TRADE_PAYABLES",
        code="311",
        standard_name="Phải trả người bán ngắn hạn",
        aliases=[
            r"phải trả người bán ngắn hạn",
            r"phải trả cho người bán ngắn hạn",
            r"phải trả người bán",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_ADVANCES_FROM_CUSTOMERS",
        code="312",
        standard_name="Người mua trả tiền trước ngắn hạn",
        aliases=[
            r"người mua trả tiền trước ngắn hạn",
            r"người mua trả tiền trước",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="TAXES_PAYABLE_TO_STATE",
        code="313",
        standard_name="Thuế và các khoản phải nộp nhà nước",
        aliases=[
            r"thuế và các khoản phải nộp nhà nước",
            r"thuế và các khoản.*phải nộp nhà nước",
            r"thuế và các khoản phải nộp",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="PAYABLES_TO_EMPLOYEES",
        code="314",
        standard_name="Phải trả người lao động",
        aliases=[
            r"phải trả người lao động",
            r"phải trả công nhân viên",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_ACCRUED_EXPENSES",
        code="315",
        standard_name="Chi phí phải trả ngắn hạn",
        aliases=[
            r"chi phí phải trả ngắn hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_INTERNAL_PAYABLES",
        code="316",
        standard_name="Phải trả nội bộ ngắn hạn",
        aliases=[
            r"phải trả nội bộ ngắn hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_CONSTRUCTION_PAYABLES",
        code="317",
        standard_name="Phải trả theo tiến độ kế hoạch hợp đồng xây dựng",
        aliases=[
            r"phải trả theo tiến độ.*xây dựng",
            r"hợp đồng xây dựng",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_UNEARNED_REVENUE",
        code="318",
        standard_name="Doanh thu chưa thực hiện ngắn hạn",
        aliases=[
            r"doanh thu chưa thực hiện ngắn hạn",
            r"doanh thu chưa thực hiện",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_OTHER_PAYABLES",
        code="319",
        standard_name="Phải trả ngắn hạn khác",
        aliases=[
            r"phải trả ngắn hạn khác",
            r"phải trả khác ngắn hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_BORROWINGS",
        code="320",
        standard_name="Vay và nợ thuê tài chính ngắn hạn",
        aliases=[
            r"vay và nợ thuê tài chính ngắn hạn",
            r"vay ngắn hạn",
            r"vay và nợ ngắn hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHORT_TERM_PROVISIONS",
        code="321",
        standard_name="Dự phòng phải trả ngắn hạn",
        aliases=[
            r"dự phòng phải trả ngắn hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="BONUS_AND_WELFARE_FUND",
        code="322",
        standard_name="Quỹ khen thưởng, phúc lợi",
        aliases=[
            r"quỹ khen thưởng,?\s*phúc lợi",
            r"quỹ khen thưởng và phúc lợi",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="PRICE_STABILIZATION_FUND",
        code="323",
        standard_name="Quỹ bình ổn giá",
        aliases=[
            r"quỹ bình ổn giá",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="GOVERNMENT_BOND_REPURCHASE_PAYABLE",
        code="324",
        standard_name="Giao dịch mua bán lại trái phiếu Chính phủ",
        aliases=[
            r"giao dịch mua bán lại trái phiếu chính phủ",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_TRADE_PAYABLES",
        code="331",
        standard_name="Phải trả người bán dài hạn",
        aliases=[
            r"phải trả người bán dài hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_ADVANCES_FROM_CUSTOMERS",
        code="332",
        standard_name="Người mua trả tiền trước dài hạn",
        aliases=[
            r"người mua trả tiền trước dài hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_ACCRUED_EXPENSES",
        code="333",
        standard_name="Chi phí phải trả dài hạn",
        aliases=[
            r"chi phí phải trả dài hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_INTERNAL_PAYABLES_CAPITAL",
        code="334",
        standard_name="Phải trả nội bộ về vốn kinh doanh",
        aliases=[
            r"phải trả nội bộ về vốn kinh doanh",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_INTERNAL_PAYABLES",
        code="335",
        standard_name="Phải trả nội bộ dài hạn",
        aliases=[
            r"phải trả nội bộ dài hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_UNEARNED_REVENUE",
        code="336",
        standard_name="Doanh thu chưa thực hiện dài hạn",
        aliases=[
            r"doanh thu chưa thực hiện dài hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_OTHER_PAYABLES",
        code="337",
        standard_name="Phải trả dài hạn khác",
        aliases=[
            r"phải trả dài hạn khác",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_BORROWINGS",
        code="338",
        standard_name="Vay và nợ thuê tài chính dài hạn",
        aliases=[
            r"vay và nợ thuê tài chính dài hạn",
            r"vay dài hạn",
            r"vay và nợ dài hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="CONVERTIBLE_BONDS",
        code="339",
        standard_name="Trái phiếu chuyển đổi",
        aliases=[
            r"trái phiếu chuyển đổi",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="PREFERRED_SHARES_DEBT",
        code="340",
        standard_name="Cổ phiếu ưu đãi",
        aliases=[
            r"cổ phiếu ưu đãi\s*\(nợ\)",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="DEFERRED_TAX_LIABILITIES",
        code="341",
        standard_name="Thuế thu nhập hoãn lại phải trả",
        aliases=[
            r"thuế thu nhập hoãn lại phải trả",
            r"thuế tndn hoãn lại phải trả",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="LONG_TERM_PROVISIONS",
        code="342",
        standard_name="Dự phòng phải trả dài hạn",
        aliases=[
            r"dự phòng phải trả dài hạn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SCIENCE_AND_TECHNOLOGY_FUND",
        code="343",
        standard_name="Quỹ phát triển khoa học và công nghệ",
        aliases=[
            r"quỹ phát triển khoa học,?\s*công nghệ",
            r"quỹ phát triển khoa học và công nghệ",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="OWNERS_EQUITY_TOTAL",
        code="410",
        standard_name="Vốn chủ sở hữu",
        aliases=[
            r"^i\.\s*vốn chủ sở hữu",
            r"^vốn chủ sở hữu\s*\(410\)",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="CONTRIBUTED_CAPITAL",
        code="411",
        standard_name="Vốn góp của chủ sở hữu",
        aliases=[
            r"vốn góp của chủ sở hữu",
            r"vốn đầu tư của chủ sở hữu",
            r"vốn cổ phần",
            r"vốn điều lệ",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="ORDINARY_SHARES",
        code="411a",
        standard_name="Cổ phiếu phổ thông có quyền biểu quyết",
        aliases=[
            r"cổ phiếu phổ thông có quyền biểu quyết",
            r"cổ phiếu phổ thông",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="PREFERRED_SHARES",
        code="411b",
        standard_name="Cổ phiếu ưu đãi",
        aliases=[
            r"cổ phiếu ưu đãi",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="SHARE_PREMIUM",
        code="412",
        standard_name="Thặng dư vốn cổ phần",
        aliases=[
            r"thặng dư vốn cổ phần",
            r"thặng dư vốn",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="CONVERTIBLE_BOND_OPTIONS",
        code="413",
        standard_name="Quyền chọn chuyển đổi trái phiếu",
        aliases=[
            r"quyền chọn chuyển đổi trái phiếu",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="OTHER_OWNERS_CAPITAL",
        code="414",
        standard_name="Vốn khác của chủ sở hữu",
        aliases=[
            r"vốn khác của chủ sở hữu",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="TREASURY_SHARES",
        code="415",
        standard_name="Cổ phiếu quỹ",
        aliases=[
            r"cổ phiếu quỹ",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="ASSET_REVALUATION_RESERVE",
        code="416",
        standard_name="Chênh lệch đánh giá lại tài sản",
        aliases=[
            r"chênh lệch đánh giá lại tài sản",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="FOREIGN_EXCHANGE_RESERVE",
        code="417",
        standard_name="Chênh lệch tỷ giá hối đoái",
        aliases=[
            r"chênh lệch tỷ giá hối đoái",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="DEVELOPMENT_INVESTMENT_FUND",
        code="418",
        standard_name="Quỹ đầu tư phát triển",
        aliases=[
            r"quỹ đầu tư phát triển",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="ENTERPRISE_REORGANIZATION_FUND",
        code="419",
        standard_name="Quỹ hỗ trợ sắp xếp doanh nghiệp",
        aliases=[
            r"quỹ hỗ trợ sắp xếp doanh nghiệp",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="OTHER_EQUITY_FUNDS",
        code="420",
        standard_name="Quỹ khác thuộc vốn chủ sở hữu",
        aliases=[
            r"quỹ khác thuộc vốn chủ sở hữu",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="RETAINED_EARNINGS",
        code="421",
        standard_name="Lợi nhuận sau thuế chưa phân phối",
        aliases=[
            r"lợi nhuận sau thuế chưa phân phối",
            r"lợi nhuận chưa phân phối",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="RETAINED_EARNINGS_PREV",
        code="421a",
        standard_name="LNST chưa phân phối lũy kế đến cuối kỳ trước",
        aliases=[
            r"lnst chưa phân phối lũy kế đến cuối kỳ trước",
            r"lợi nhuận sau thuế chưa phân phối lũy kế đến cuối kỳ trước",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="RETAINED_EARNINGS_CURR",
        code="421b",
        standard_name="LNST chưa phân phối kỳ này",
        aliases=[
            r"lnst chưa phân phối kỳ này",
            r"lợi nhuận sau thuế chưa phân phối kỳ này",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="CONSTRUCTION_INVESTMENT_SOURCE",
        code="422",
        standard_name="Nguồn vốn đầu tư XDCB",
        aliases=[
            r"nguồn vốn đầu tư xdcb",
            r"nguồn vốn đầu tư xây dựng cơ bản",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="BUDGET_SOURCES_AND_OTHER_FUNDS",
        code="430",
        standard_name="Nguồn kinh phí và quỹ khác",
        aliases=[
            r"nguồn kinh phí và quỹ khác",
            r"^ii\.\s*nguồn kinh phí và quỹ khác",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="BUDGET_SOURCES",
        code="431",
        standard_name="Nguồn kinh phí",
        aliases=[
            r"^1\.\s*nguồn kinh phí$",
            r"^nguồn kinh phí$",
        ],
        statement_type="BALANCE_SHEET",
    ),
    ConceptDefinition(
        concept="BUDGET_SOURCES_FIXED_ASSETS",
        code="432",
        standard_name="Nguồn kinh phí đã hình thành TSCĐ",
        aliases=[
            r"nguồn kinh phí đã hình thành tscđ",
        ],
        statement_type="BALANCE_SHEET",
    ),

    # ── BÁO CÁO KẾT QUẢ KINH DOANH (KQKD) ──────────────────────────────────────
    ConceptDefinition(
        concept="GROSS_REVENUE",
        code="01",
        standard_name="Doanh thu bán hàng và cung cấp dịch vụ",
        aliases=[
            r"doanh thu bán hàng và cung cấp dịch vụ",
            r"doanh thu bán hàng",
            r"tổng doanh thu",
            r"1\.\s*doanh thu bán hàng",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="REVENUE_DEDUCTIONS",
        code="02",
        standard_name="Các khoản giảm trừ doanh thu",
        aliases=[
            r"các khoản giảm trừ doanh thu",
            r"giảm trừ doanh thu",
            r"2\.\s*các khoản giảm trừ",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="NET_REVENUE",
        code="10",
        standard_name="Doanh thu thuần về bán hàng và cung cấp dịch vụ",
        aliases=[
            r"doanh thu thuần",
            r"doanh thu thuan",
            r"doanh thu thuần về bán hàng",
            r"3\.\s*doanh thu thuần",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="COGS",
        code="11",
        standard_name="Giá vốn hàng bán",
        aliases=[
            r"giá vốn hàng bán",
            r"gia von hang ban",
            r"4\.\s*giá vốn hàng bán",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="GROSS_PROFIT",
        code="20",
        standard_name="Lợi nhuận gộp về bán hàng và cung cấp dịch vụ",
        aliases=[
            r"lợi nhuận gộp",
            r"loi nhuan gop",
            r"5\.\s*lợi nhuận gộp",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="FINANCIAL_INCOME",
        code="21",
        standard_name="Doanh thu hoạt động tài chính",
        aliases=[
            r"doanh thu hoạt động tài chính",
            r"doanh thu tài chính",
            r"6\.\s*doanh thu hoạt động tài chính",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="FINANCIAL_EXPENSES",
        code="22",
        standard_name="Chi phí tài chính",
        aliases=[
            r"chi phí tài chính",
            r"chi phi tai chinh",
            r"7\.\s*chi phí tài chính",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="INTEREST_EXPENSE",
        code="23",
        standard_name="Trong đó: Chi phí lãi vay",
        aliases=[
            r"chi phí lãi vay",
            r"trong đó: chi phí lãi vay",
            r"lãi tiền vay",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="SELLING_EXPENSES",
        code="25",
        standard_name="Chi phí bán hàng",
        aliases=[
            r"chi phí bán hàng",
            r"chi phi ban hang",
            r"8\.\s*chi phí bán hàng",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="ADMIN_EXPENSES",
        code="26",
        standard_name="Chi phí quản lý doanh nghiệp",
        aliases=[
            r"chi phí quản lý doanh nghiệp",
            r"chi phí quản lý",
            r"9\.\s*chi phí quản lý doanh nghiệp",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="OPERATING_PROFIT",
        code="30",
        standard_name="Lợi nhuận thuần từ hoạt động kinh doanh",
        aliases=[
            r"lợi nhuận thuần từ hoạt động kinh doanh",
            r"lợi nhuận kinh doanh",
            r"10\.\s*lợi nhuận thuần từ hoạt động kinh doanh",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="OTHER_INCOME",
        code="31",
        standard_name="Thu nhập khác",
        aliases=[
            r"thu nhập khác",
            r"11\.\s*thu nhập khác",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="OTHER_EXPENSES",
        code="32",
        standard_name="Chi phí khác",
        aliases=[
            r"chi phí khác",
            r"12\.\s*chi phí khác",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="OTHER_PROFIT",
        code="40",
        standard_name="Kết quả từ hoạt động khác",
        aliases=[
            r"kết quả từ hoạt động khác",
            r"lợi nhuận khác",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="PROFIT_BEFORE_TAX",
        code="50",
        standard_name="Tổng lợi nhuận kế toán trước thuế",
        aliases=[
            r"tổng lợi nhuận kế toán trước thuế",
            r"lợi nhuận trước thuế",
            r"15\.\s*tổng lợi nhuận kế toán trước thuế",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="NET_PROFIT",
        code="60",
        standard_name="Lợi nhuận sau thuế thu nhập doanh nghiệp",
        aliases=[
            r"lợi nhuận sau thuế",
            r"loi nhuan sau thue",
            r"lợi nhuận sau thuế thu nhập doanh nghiệp",
            r"17\.\s*lợi nhuận sau thuế",
            r"lợi nhuận thuần sau thuế",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="CURRENT_TAX_EXPENSE",
        code="51",
        standard_name="Chi phí thuế TNDN hiện hành",
        aliases=[
            r"chi phí thuế thu nhập doanh nghiệp hiện hành",
            r"chi phí thuế tndn hiện hành",
            r"thuế tndn hiện hành",
            r"chi phí thuế hiện hành",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="DEFERRED_TAX_EXPENSE",
        code="52",
        standard_name="Chi phí thuế TNDN hoãn lại",
        aliases=[
            r"chi phí thuế thu nhập doanh nghiệp hoãn lại",
            r"chi phí thuế tndn hoãn lại",
            r"thuế tndn hoãn lại",
            r"chi phí thuế hoãn lại",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="BASIC_EPS",
        code="70",
        standard_name="Lãi cơ bản trên cổ phiếu",
        aliases=[
            r"lãi cơ bản trên cổ phiếu",
            r"lãi trên một cổ phiếu",
            r"lãi cơ bản trên mỗi cổ phiếu",
            r"eps cơ bản",
        ],
        statement_type="INCOME_STATEMENT",
    ),
    ConceptDefinition(
        concept="DILUTED_EPS",
        code="71",
        standard_name="Lãi suy giảm trên cổ phiếu",
        aliases=[
            r"lãi suy giảm trên cổ phiếu",
            r"lãi suy giảm trên mỗi cổ phiếu",
            r"eps pha loãng",
            r"eps suy giảm",
        ],
        statement_type="INCOME_STATEMENT",
    ),

    # ── BÁO CÁO LƯU CHUYỂN TIỀN TỆ (LCTT) THEO THÔNG TƯ 200 ─────────────────────
    # 1. Phương pháp trực tiếp (Mẫu B03a - DN)
    ConceptDefinition(
        concept="CF_DIRECT_SALES_PROCEEDS",
        code="01",
        standard_name="Tiền thu từ bán hàng, cung cấp dịch vụ và doanh thu khác",
        aliases=[
            r"tiền thu từ bán hàng,?\s*cung cấp dịch vụ",
            r"tiền thu từ bán hàng",
            r"^1\.\s*tiền thu từ bán hàng",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_DIRECT_SUPPLIER_PAYMENTS",
        code="02",
        standard_name="Tiền chi trả cho người cung cấp hàng hóa và dịch vụ",
        aliases=[
            r"tiền chi trả cho người cung cấp",
            r"chi trả cho người cung cấp hàng hóa",
            r"^2\.\s*tiền chi trả cho người cung cấp",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_DIRECT_EMPLOYEE_PAYMENTS",
        code="03",
        standard_name="Tiền chi trả cho người lao động",
        aliases=[
            r"tiền chi trả cho người lao động",
            r"chi trả cho người lao động",
            r"^3\.\s*tiền chi trả cho người lao động",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_DIRECT_INTEREST_PAID",
        code="04",
        standard_name="Tiền lãi vay đã trả (Trực tiếp)",
        aliases=[
            r"^4\.\s*tiền lãi vay đã trả",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_DIRECT_TAX_PAID",
        code="05",
        standard_name="Thuế thu nhập doanh nghiệp đã nộp (Trực tiếp)",
        aliases=[
            r"^5\.\s*thuế thu nhập doanh nghiệp đã nộp",
            r"^5\.\s*thuế tndn đã nộp",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_DIRECT_OTHER_PROCEEDS",
        code="06",
        standard_name="Tiền thu khác từ hoạt động kinh doanh (Trực tiếp)",
        aliases=[
            r"^6\.\s*tiền thu khác từ hoạt động kinh doanh",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_DIRECT_OTHER_PAYMENTS",
        code="07",
        standard_name="Tiền chi khác cho hoạt động kinh doanh (Trực tiếp)",
        aliases=[
            r"^7\.\s*tiền chi khác cho hoạt động kinh doanh",
        ],
        statement_type="CASH_FLOW",
    ),

    # 2. Phương pháp gián tiếp (Mẫu B03b - DN)
    ConceptDefinition(
        concept="CF_PROFIT_BEFORE_TAX",
        code="01",
        standard_name="Lợi nhuận trước thuế (Lưu chuyển tiền tệ gián tiếp)",
        aliases=[
            r"^lợi nhuận trước thuế$",
            r"1\.\s*lợi nhuận trước thuế",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_DEPRECIATION",
        code="02",
        standard_name="Khấu hao TSCĐ và BĐSĐT",
        aliases=[
            r"khấu hao tscđ",
            r"khấu hao tài sản cố định",
            r"chi phí khấu hao",
            r"khấu hao tscđ và bđsđt",
            r"^2\.\s*khấu hao",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_PROVISIONS",
        code="03",
        standard_name="Các khoản dự phòng",
        aliases=[
            r"các khoản dự phòng",
            r"^3\.\s*các khoản dự phòng",
            r"tăng,?\s*giảm các khoản dự phòng",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_UNREALIZED_FX",
        code="04",
        standard_name="Lãi, lỗ chênh lệch tỷ giá hối đoái do đánh giá lại",
        aliases=[
            r"chênh lệch tỷ giá hối đoái do đánh giá lại",
            r"lãi,?\s*lỗ chênh lệch tỷ giá",
            r"^4\.\s*lãi,?\s*lỗ chênh lệch tỷ giá",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_INVESTING_PL",
        code="05",
        standard_name="Lãi, lỗ từ hoạt động đầu tư",
        aliases=[
            r"lãi,?\s*lỗ từ hoạt động đầu tư",
            r"^5\.\s*lãi,?\s*lỗ từ hoạt động đầu tư",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_INTEREST_EXPENSE",
        code="06",
        standard_name="Chi phí lãi vay",
        aliases=[
            r"chi phí lãi vay",
            r"^6\.\s*chi phí lãi vay",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_OTHER_ADJUSTMENTS",
        code="07",
        standard_name="Các khoản điều chỉnh khác",
        aliases=[
            r"các khoản điều chỉnh khác",
            r"^7\.\s*các khoản điều chỉnh khác",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_OPERATING_PROFIT_BEFORE_WC",
        code="08",
        standard_name="Lợi nhuận từ HĐKD trước thay đổi vốn lưu động",
        aliases=[
            r"lợi nhuận từ hoạt động kinh doanh trước những thay đổi",
            r"trước những thay đổi vốn lưu động",
            r"^8\.\s*lợi nhuận từ hoạt động kinh doanh",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_RECEIVABLES_CHANGE",
        code="09",
        standard_name="Tăng, giảm các khoản phải thu",
        aliases=[
            r"tăng,?\s*giảm các khoản phải thu",
            r"biến động các khoản phải thu",
            r"^9\.\s*tăng,?\s*giảm các khoản phải thu",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_INVENTORY_CHANGE",
        code="10",
        standard_name="Biến động hàng tồn kho",
        aliases=[
            r"biến động hàng tồn kho",
            r"tăng,?\s*giảm hàng tồn kho",
            r"^10\.\s*tăng,?\s*giảm hàng tồn kho",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_PAYABLES_CHANGE",
        code="11",
        standard_name="Biến động các khoản phải trả",
        aliases=[
            r"biến động các khoản phải trả",
            r"tăng,?\s*giảm các khoản phải trả",
            r"^11\.\s*tăng,?\s*giảm các khoản phải trả",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_PREPAID_EXPENSES_CHANGE",
        code="12",
        standard_name="Biến động chi phí trả trước",
        aliases=[
            r"biến động chi phí trả trước",
            r"tăng,?\s*giảm chi phí trả trước",
            r"^12\.\s*tăng,?\s*giảm chi phí trả trước",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_TRADING_SECURITIES_CHANGE",
        code="13",
        standard_name="Tăng, giảm chứng khoán kinh doanh",
        aliases=[
            r"tăng,?\s*giảm chứng khoán kinh doanh",
            r"biến động chứng khoán kinh doanh",
            r"^13\.\s*tăng,?\s*giảm chứng khoán kinh doanh",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_INTEREST_PAID",
        code="14",
        standard_name="Tiền lãi vay đã trả",
        aliases=[
            r"tiền lãi vay đã trả",
            r"^14\.\s*tiền lãi vay đã trả",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_TAX_PAID",
        code="15",
        standard_name="Thuế TNDN đã nộp",
        aliases=[
            r"thuế thu nhập doanh nghiệp đã nộp",
            r"thuế tndn đã nộp",
            r"^15\.\s*thuế thu nhập doanh nghiệp đã nộp",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_OTHER_OPERATING_PROCEEDS",
        code="16",
        standard_name="Tiền thu khác từ hoạt động kinh doanh",
        aliases=[
            r"tiền thu khác từ hoạt động kinh doanh",
            r"^16\.\s*tiền thu khác",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_OTHER_OPERATING_PAYMENTS",
        code="17",
        standard_name="Tiền chi khác cho hoạt động kinh doanh",
        aliases=[
            r"tiền chi khác cho hoạt động kinh doanh",
            r"^17\.\s*tiền chi khác",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_NET_OPERATING",
        code="20",
        standard_name="Lưu chuyển tiền thuần từ hoạt động kinh doanh",
        aliases=[
            r"lưu chuyển tiền thuần từ hoạt động kinh doanh",
            r"^20\.\s*lưu chuyển tiền thuần",
        ],
        statement_type="CASH_FLOW",
    ),

    # 3. Hoạt động đầu tư (chung cho cả Trực tiếp và Gián tiếp)
    ConceptDefinition(
        concept="CF_CAPEX",
        code="21",
        standard_name="Tiền chi mua sắm tài sản cố định và tài sản dài hạn khác",
        aliases=[
            r"tiền chi mua tài sản cố định",
            r"tiền chi mua sắm,?\s*xây dựng tscđ",
            r"tiền chi để mua sắm,?\s*xây dựng tscđ",
            r"^21\.\s*tiền chi",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_PROCEEDS_DISPOSAL_ASSETS",
        code="22",
        standard_name="Tiền thu từ thanh lý tài sản cố định",
        aliases=[
            r"tiền thu từ thanh lý tài sản cố định",
            r"tiền thu từ thanh lý,?\s*nhượng bán tscđ",
            r"^22\.\s*tiền thu từ thanh lý",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_LOANS_GIVEN",
        code="23",
        standard_name="Tiền chi cho vay, mua các công cụ nợ của đơn vị khác",
        aliases=[
            r"tiền chi cho vay,?\s*mua các công cụ nợ",
            r"tiền chi cho vay",
            r"mua các công cụ nợ",
            r"^23\.\s*tiền chi cho vay",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_LOANS_COLLECTED",
        code="24",
        standard_name="Tiền thu hồi cho vay, bán lại các công cụ nợ của đơn vị khác",
        aliases=[
            r"tiền thu hồi cho vay",
            r"thu hồi cho vay,?\s*bán lại các công cụ nợ",
            r"^24\.\s*tiền thu hồi cho vay",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_EQUITY_INVESTMENTS_PAID",
        code="25",
        standard_name="Tiền chi đầu tư góp vốn vào đơn vị khác",
        aliases=[
            r"tiền chi đầu tư góp vốn vào đơn vị khác",
            r"chi đầu tư góp vốn",
            r"^25\.\s*tiền chi đầu tư góp vốn",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_EQUITY_INVESTMENTS_COLLECTED",
        code="26",
        standard_name="Tiền thu hồi đầu tư góp vốn vào đơn vị khác",
        aliases=[
            r"tiền thu hồi đầu tư góp vốn vào đơn vị khác",
            r"thu hồi đầu tư góp vốn",
            r"^26\.\s*tiền thu hồi đầu tư góp vốn",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_INTEREST_AND_DIVIDENDS_RECEIVED",
        code="27",
        standard_name="Tiền thu lãi cho vay, cổ tức và lợi nhuận được chia",
        aliases=[
            r"tiền thu lãi cho vay,?\s*cổ tức",
            r"tiền thu lãi và cổ tức",
            r"cổ tức và lợi nhuận được chia",
            r"^27\.\s*tiền thu lãi",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_NET_INVESTING",
        code="30",
        standard_name="Lưu chuyển tiền thuần từ hoạt động đầu tư",
        aliases=[
            r"lưu chuyển tiền thuần từ hoạt động đầu tư",
            r"^30\.\s*lưu chuyển tiền thuần từ hoạt động đầu tư",
        ],
        statement_type="CASH_FLOW",
    ),

    # 4. Hoạt động tài chính
    ConceptDefinition(
        concept="CF_EQUITY_ISSUANCE",
        code="31",
        standard_name="Tiền thu từ phát hành cổ phiếu, nhận vốn góp của chủ sở hữu",
        aliases=[
            r"tiền thu từ phát hành cổ phiếu",
            r"nhận vốn góp của chủ sở hữu",
            r"tiền thu từ phát hành cp",
            r"^31\.\s*tiền thu từ phát hành cổ phiếu",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_CAPITAL_REFUND",
        code="32",
        standard_name="Tiền trả lại vốn góp cho các chủ sở hữu, mua lại cổ phiếu của doanh nghiệp đã phát hành",
        aliases=[
            r"tiền trả lại vốn góp",
            r"mua lại cổ phiếu đã phát hành",
            r"trả lại vốn góp cho các chủ sở hữu",
            r"^32\.\s*tiền trả lại vốn góp",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_BORROWINGS",
        code="33",
        standard_name="Tiền thu từ đi vay",
        aliases=[
            r"tiền thu từ đi vay",
            r"^33\.\s*tiền thu từ đi vay",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_REPAYMENTS",
        code="34",
        standard_name="Tiền chi trả nợ gốc vay",
        aliases=[
            r"tiền chi trả nợ gốc vay",
            r"^34\.\s*tiền chi trả nợ gốc vay",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_LEASE_REPAYMENTS",
        code="35",
        standard_name="Tiền chi trả nợ thuê tài chính",
        aliases=[
            r"tiền chi trả nợ thuê tài chính",
            r"chi trả nợ thuê tài chính",
            r"tiền trả nợ gốc thuê tài chính",
            r"^35\.\s*tiền chi trả nợ thuê tài chính",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_DIVIDENDS_PAID",
        code="36",
        standard_name="Tiền chi trả cổ tức",
        aliases=[
            r"tiền chi trả cổ tức",
            r"cổ tức, lợi nhuận đã trả",
            r"^36\.\s*cổ tức",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_NET_FINANCING",
        code="40",
        standard_name="Lưu chuyển thuần từ hoạt động tài chính",
        aliases=[
            r"lưu chuyển thuần từ hoạt động tài chính",
            r"lưu chuyển tiền thuần từ hoạt động tài chính",
            r"^40\.\s*lưu chuyển",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_NET_CHANGE",
        code="50",
        standard_name="Lưu chuyển tiền thuần trong năm",
        aliases=[
            r"lưu chuyển tiền thuần trong năm",
            r"lưu chuyển tiền thuần trong kỳ",
            r"^50\.\s*lưu chuyển tiền thuần",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_BEGINNING_CASH",
        code="60",
        standard_name="Tiền và các khoản tương đương tiền đầu năm",
        aliases=[
            r"tiền và các khoản tương đương tiền đầu năm",
            r"tiền và tương đương tiền đầu kỳ",
            r"^60\.\s*tiền và tương đương tiền đầu kỳ",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_EXCHANGE_RATE_DIFF",
        code="61",
        standard_name="Ảnh hưởng của thay đổi tỷ giá hối đoái quy đổi ngoại tệ",
        aliases=[
            r"ảnh hưởng của thay đổi tỷ giá",
            r"ảnh hưởng tỷ giá",
            r"chênh lệch tỷ giá hối đoái quy đổi ngoại tệ",
            r"^61\.\s*ảnh hưởng",
        ],
        statement_type="CASH_FLOW",
    ),
    ConceptDefinition(
        concept="CF_ENDING_CASH",
        code="70",
        standard_name="Tiền và các khoản tương đương tiền cuối năm",
        aliases=[
            r"tiền và các khoản tương đương tiền cuối năm",
            r"tiền và tương đương tiền cuối kỳ",
            r"^70\.\s*tiền và tương đương tiền cuối kỳ",
        ],
        statement_type="CASH_FLOW",
    ),
]

# Từ điển tra cứu nhanh theo concept
CONCEPT_TO_DEF: dict[str, ConceptDefinition] = {d.concept: d for d in ONTOLOGY_DEFINITIONS}
CONCEPT_TO_CODE: dict[str, str] = {d.concept: d.code for d in ONTOLOGY_DEFINITIONS}

# Từ điển tra cứu theo mã số chuẩn (ưu tiên CĐKT và KQKD trước LCTT)
CODE_TO_CONCEPT: dict[str, str] = {}
for d in ONTOLOGY_DEFINITIONS:
    if d.code not in CODE_TO_CONCEPT or d.statement_type in ("BALANCE_SHEET", "INCOME_STATEMENT"):
        CODE_TO_CONCEPT[d.code] = d.concept


def match_concept_from_label_and_code(
    raw_label: str,
    raw_code: str = "",
    statement_type_hint: str | None = None,
) -> tuple[str | None, str]:
    """
    Ánh xạ tên khoản mục và mã số trên báo cáo sang Canonical Concept.

    Ưu tiên:
      1. Tự động suy luận statement_type nếu chưa có hint từ ngữ cảnh nhãn khoản mục.
      2. Khớp theo mã số chuẩn Thông tư 200 có kiểm tra phù hợp loại báo cáo và ngữ nghĩa nhãn.
      3. Khớp theo regex alias tên khoản mục (loại trừ các khoản mục con đè khoản mục cha).

    Returns:
        tuple[concept, standard_code]
    """
    clean_label = raw_label.strip().lower()
    # Hỗ trợ cả mã số dạng chữ cái phụ như 411a, 411b, 421a, 421b
    clean_code = re.sub(r"[^0-9a-zA-Z]", "", str(raw_code).strip()).lower()

    # Tự động suy luận loại báo cáo nếu không có hint
    inferred_type = statement_type_hint
    if not inferred_type:
        # Nếu nhãn chứa các từ ngữ đặc thù của Bảng Cân đối kế toán
        # (Đặt trước để tránh nhầm "Doanh thu chưa thực hiện ngắn hạn" sang INCOME_STATEMENT)
        if any(k in clean_label for k in [
            "chưa thực hiện", "ngắn hạn", "dài hạn", "tài sản", "nguồn vốn", "nợ phải trả", "vốn chủ sở hữu"
        ]):
            inferred_type = "BALANCE_SHEET"
        elif any(k in clean_label for k in [
            "lưu chuyển", "tiền thuần", "tiền chi", "tiền thu", "biến động",
            "thanh lý", "cổ tức", "tiền gửi có kì hạn", "tiền gửi có kỳ hạn"
        ]):
            inferred_type = "CASH_FLOW"
        elif any(k in clean_label for k in [
            "doanh thu", "giá vốn", "lợi nhuận gộp", "chi phí bán hàng",
            "chi phí quản lý", "kết quả từ hoạt động khác", "thu nhập khác"
        ]):
            inferred_type = "INCOME_STATEMENT"

    # 1. Khớp theo mã số chuẩn Thông tư 200
    if clean_code:
        # Hỗ trợ cả trường hợp OCR làm rớt số 0 ở đầu (ví dụ: '01' vs '1', '08' vs '8')
        matching_defs = [
            d for d in ONTOLOGY_DEFINITIONS
            if d.code.lower() == clean_code or (
                clean_code.isdigit()
                and d.code.isdigit()
                and len(clean_code) <= 2
                and d.code.lstrip("0") == clean_code.lstrip("0")
            )
        ]
        if inferred_type:
            filtered = [d for d in matching_defs if d.statement_type == inferred_type]
            if filtered:
                matching_defs = filtered

        for candidate in matching_defs:
            # Kiểm tra semantic compatibility
            if candidate.statement_type == "INCOME_STATEMENT":
                # Không gán chỉ tiêu KQKD nếu nhãn mang nghĩa LCTT
                if any(k in clean_label for k in ["lưu chuyển", "tiền thuần", "biến động", "tiền chi", "tiền thu"]):
                    continue
            elif candidate.statement_type == "CASH_FLOW":
                # Không gán chỉ tiêu LCTT nếu nhãn mang nghĩa KQKD rõ rệt
                if any(k in clean_label for k in ["giá vốn", "doanh thu thuần"]):
                    continue
                # Phân biệt Lưu chuyển tiền tệ Trực tiếp vs Gián tiếp cho các mã 01 - 07
                if candidate.concept == "CF_DIRECT_SALES_PROCEEDS" and any(k in clean_label for k in ["lợi nhuận", "trước thuế"]):
                    continue
                if candidate.concept == "CF_PROFIT_BEFORE_TAX" and any(k in clean_label for k in ["bán hàng", "cung cấp dịch vụ"]):
                    continue
                if candidate.concept == "CF_DIRECT_SUPPLIER_PAYMENTS" and any(k in clean_label for k in ["khấu hao", "bđsđt", "tscđ"]):
                    continue
                if candidate.concept == "CF_DEPRECIATION" and any(k in clean_label for k in ["cung cấp", "hàng hóa", "dịch vụ", "nhà cung cấp"]):
                    continue
                if candidate.concept == "CF_DIRECT_EMPLOYEE_PAYMENTS" and "dự phòng" in clean_label:
                    continue
                if candidate.concept == "CF_PROVISIONS" and any(k in clean_label for k in ["người lao động", "nhân viên", "lương"]):
                    continue
                if candidate.concept == "CF_DIRECT_INTEREST_PAID" and any(k in clean_label for k in ["tỷ giá", "ngoại tệ"]):
                    continue
                if candidate.concept == "CF_UNREALIZED_FX" and any(k in clean_label for k in ["lãi vay", "đã trả"]):
                    continue
                if candidate.concept == "CF_DIRECT_TAX_PAID" and "hoạt động đầu tư" in clean_label:
                    continue
                if candidate.concept == "CF_INVESTING_PL" and any(k in clean_label for k in ["thuế", "đã nộp"]):
                    continue
                if candidate.concept == "CF_DIRECT_OTHER_PROCEEDS" and any(k in clean_label for k in ["chi phí lãi", "lãi vay"]):
                    continue
                if candidate.concept == "CF_INTEREST_EXPENSE" and "tiền thu" in clean_label:
                    continue
                if candidate.concept == "CF_DIRECT_OTHER_PAYMENTS" and "điều chỉnh" in clean_label:
                    continue
                if candidate.concept == "CF_OTHER_ADJUSTMENTS" and "tiền chi" in clean_label:
                    continue
            elif candidate.statement_type == "BALANCE_SHEET":
                # Kiểm tra các khoản mục cha không bị con chiếm
                if candidate.concept == "SHORT_TERM_RECEIVABLES" and any(k in clean_label for k in ["khác", "khách hàng", "dự phòng"]):
                    continue
                if candidate.concept == "INVENTORIES" and any(k in clean_label for k in ["dự phòng", "giảm giá"]):
                    continue
                if candidate.concept == "FIXED_ASSETS" and any(k in clean_label for k in ["hữu hình", "vô hình"]):
                    continue
                if candidate.concept == "LIABILITIES" and any(k in clean_label for k in ["ngắn hạn", "dài hạn"]):
                    continue
                if candidate.concept == "CURRENT_LIABILITIES" and any(k in clean_label for k in ["người bán", "trả trước", "vay", "thuê tài chính", "khác", "chưa thực hiện", "thuế", "lao động", "chi phí phải trả"]):
                    continue
                if candidate.concept == "NON_CURRENT_LIABILITIES" and any(k in clean_label for k in ["vay", "thuê tài chính", "khác", "chưa thực hiện", "người bán", "trả trước", "chi phí phải trả", "dự phòng"]):
                    continue
                if candidate.concept == "EQUITY" and any(k in clean_label for k in ["góp", "cổ phần", "chưa phân phối", "thặng dư", "quỹ"]):
                    continue
                if candidate.concept == "OWNERS_EQUITY_TOTAL" and any(k in clean_label for k in ["góp", "cổ phần", "chưa phân phối", "thặng dư", "quỹ"]):
                    continue
                if candidate.concept == "CONTRIBUTED_CAPITAL" and any(k in clean_label for k in ["phổ thông", "ưu đãi"]):
                    continue
                if candidate.concept == "RETAINED_EARNINGS" and any(k in clean_label for k in ["kỳ trước", "lũy kế", "kỳ này", "năm nay"]):
                    continue

            return candidate.concept, clean_code

    # 2. Khớp theo regex alias tên khoản mục
    for cdef in ONTOLOGY_DEFINITIONS:
        if inferred_type and cdef.statement_type != inferred_type:
            continue

        # Nếu có mã số rõ ràng mà mã số đó khác với cdef.code (ví dụ mã 136 vs 130),
        # KHÔNG cho phép alias lỏng khớp sai mã
        if clean_code and clean_code != cdef.code.lower() and len(clean_code) >= 2:
            continue

        # Kiểm tra loại trừ ngữ nghĩa khoản mục con
        if cdef.concept == "SHORT_TERM_RECEIVABLES" and any(k in clean_label for k in ["khác", "khách hàng", "người bán", "dự phòng"]):
            continue
        if cdef.concept == "INVENTORIES" and any(k in clean_label for k in ["dự phòng", "giảm giá"]):
            continue
        if cdef.concept == "LONG_TERM_RECEIVABLES" and "khác" in clean_label:
            continue
        if cdef.concept == "FIXED_ASSETS" and any(k in clean_label for k in ["hữu hình", "vô hình"]):
            continue
        if cdef.concept == "LONG_TERM_ASSETS_IN_PROGRESS" and "xây dựng cơ bản" in clean_label:
            continue
        if cdef.concept == "LIABILITIES" and any(k in clean_label for k in ["ngắn hạn", "dài hạn"]):
            continue
        if cdef.concept == "CURRENT_LIABILITIES" and any(k in clean_label for k in ["người bán", "trả trước", "vay", "thuê tài chính", "khác", "chưa thực hiện", "thuế", "lao động", "chi phí phải trả"]):
            continue
        if cdef.concept == "NON_CURRENT_LIABILITIES" and any(k in clean_label for k in ["vay", "thuê tài chính", "khác", "chưa thực hiện", "người bán", "trả trước", "chi phí phải trả", "dự phòng"]):
            continue
        if cdef.concept == "EQUITY" and any(k in clean_label for k in ["góp", "cổ phần", "chưa phân phối", "thặng dư", "quỹ"]):
            continue
        if cdef.concept == "OWNERS_EQUITY_TOTAL" and any(k in clean_label for k in ["góp", "cổ phần", "chưa phân phối", "thặng dư", "quỹ"]):
            continue
        if cdef.concept == "CONTRIBUTED_CAPITAL" and any(k in clean_label for k in ["phổ thông", "ưu đãi"]):
            continue
        if cdef.concept == "RETAINED_EARNINGS" and any(k in clean_label for k in ["kỳ trước", "lũy kế", "kỳ này", "năm nay"]):
            continue

        for alias in cdef.aliases:
            if re.search(alias, clean_label, flags=re.IGNORECASE):
                return cdef.concept, cdef.code

    return None, clean_code
