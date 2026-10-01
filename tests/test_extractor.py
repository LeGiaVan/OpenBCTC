"""
test_extractor.py — Unit tests cho FinancialFactExtractor và Financial Ontology mapping.
"""


from src.extractor.fact_extractor import FinancialFactExtractor
from src.extractor.ontology import match_concept_from_label_and_code
from src.models import ClassifiedBlock, ParsedBlock, StorageTarget


def test_ontology_matching():
    # Khớp qua mã số
    concept, code = match_concept_from_label_and_code("TỔNG CỘNG TÀI SẢN", raw_code="270")
    assert concept == "TOTAL_ASSETS"
    assert code == "270"

    # Khớp qua regex label tiếng Việt
    concept, code = match_concept_from_label_and_code("Tiền và các khoản tương đương tiền")
    assert concept == "CASH_AND_EQUIVALENTS"
    assert code == "110"

    # Khớp qua Doanh thu thuần
    concept, code = match_concept_from_label_and_code("Doanh thu thuần về bán hàng và cung cấp dịch vụ", raw_code="10")
    assert concept == "NET_REVENUE"
    assert code == "10"

    # Phân biệt Lưu chuyển tiền tệ (mã 10, 20 LCTT không nhầm với KQKD)
    cf_concept, cf_code = match_concept_from_label_and_code("Biến động hàng tồn kho", raw_code="10")
    assert cf_concept == "CF_INVENTORY_CHANGE"
    assert cf_concept != "NET_REVENUE"

    cf_gp_concept, _ = match_concept_from_label_and_code("Lưu chuyển tiền thuần từ hoạt động kinh doanh", raw_code="20")
    assert cf_gp_concept == "CF_NET_OPERATING"
    assert cf_gp_concept != "GROSS_PROFIT"

    # Phân biệt khoản mục con CĐKT không đè khoản mục mẹ (136 vs 130, 149 vs 140)
    rec_other_concept, rec_other_code = match_concept_from_label_and_code("Phải thu ngắn hạn khác", raw_code="136")
    assert rec_other_concept == "SHORT_TERM_OTHER_RECEIVABLES"
    assert rec_other_concept != "SHORT_TERM_RECEIVABLES"

    inv_prov_concept, _ = match_concept_from_label_and_code("Dự phòng giảm giá hàng tồn kho", raw_code="149")
    assert inv_prov_concept == "INVENTORY_PROVISION"
    assert inv_prov_concept != "INVENTORIES"

    # Kiểm tra nợ vay và vốn chủ sở hữu mới bổ sung (320, 338, 411, 421)
    st_borrow, _ = match_concept_from_label_and_code("Vay và nợ thuê tài chính ngắn hạn", raw_code="320")
    assert st_borrow == "SHORT_TERM_BORROWINGS"

    lt_borrow, _ = match_concept_from_label_and_code("Vay và nợ thuê tài chính dài hạn", raw_code="338")
    assert lt_borrow == "LONG_TERM_BORROWINGS"

    contrib_cap, _ = match_concept_from_label_and_code("Vốn góp của chủ sở hữu", raw_code="411")
    assert contrib_cap == "CONTRIBUTED_CAPITAL"

    ret_earn, _ = match_concept_from_label_and_code("Lợi nhuận sau thuế chưa phân phối", raw_code="421")
    assert ret_earn == "RETAINED_EARNINGS"

    # Kiểm tra Doanh thu gộp (01) và Giảm trừ (02)
    gross_rev, _ = match_concept_from_label_and_code("Doanh thu bán hàng và cung cấp dịch vụ", raw_code="01")
    assert gross_rev == "GROSS_REVENUE"

    rev_deduct, _ = match_concept_from_label_and_code("Các khoản giảm trừ doanh thu", raw_code="02")
    assert rev_deduct == "REVENUE_DEDUCTIONS"

    # Kiểm tra khả năng chịu lỗi OCR rớt số 0 ở đầu (Leading zero tolerance: '1' -> '01', '8' -> '08')
    gross_rev_ocr, _ = match_concept_from_label_and_code("Doanh thu bán hàng và cung cấp dịch vụ", raw_code="1")
    assert gross_rev_ocr == "GROSS_REVENUE"

    cf_wc_ocr, _ = match_concept_from_label_and_code("Lợi nhuận từ hoạt động kinh doanh trước những thay đổi vốn lưu động", raw_code="8")
    assert cf_wc_ocr == "CF_OPERATING_PROFIT_BEFORE_WC"

    # Kiểm tra không nhầm "Doanh thu chưa thực hiện ngắn hạn" sang INCOME_STATEMENT
    unearned_rev, code_318 = match_concept_from_label_and_code("Doanh thu chưa thực hiện ngắn hạn", raw_code="318")
    assert unearned_rev == "SHORT_TERM_UNEARNED_REVENUE"
    assert code_318 == "318"


def test_fact_extractor_from_table_block():
    extractor = FinancialFactExtractor()

    table_content = """
| CHỈ TIÊU | Mã số | Thuyết minh | 31/12/2024 VND | 1/1/2024 VND |
| --- | --- | --- | --- | --- |
| Tài sản ngắn hạn | 100 |  | 30,000,000,000 | 25,000,000,000 |
| Tiền và tương đương tiền | 110 | V.01 | 5,000,000,000 | 4,000,000,000 |
| Hàng tồn kho | 140 | V.04 | 10,000,000,000 | 8,000,000,000 |
"""
    parsed_block = ParsedBlock(
        block_id="p5_b1",
        block_type="table",
        page=5,
        content=table_content.strip(),
        metadata={"unit": "VND"},
    )
    classified_block = ClassifiedBlock(
        block=parsed_block,
        block_type="FINANCIAL_STATEMENT",
        target=[StorageTarget.SQL],
        confidence=0.95,
        classification_method="rule_based",
    )

    facts, report = extractor.extract_from_blocks([classified_block], company="VNM", year=2024)

    assert len(facts) >= 3
    concepts = {f.concept for f in facts}
    assert "CURRENT_ASSETS" in concepts
    assert "CASH_AND_EQUIVALENTS" in concepts
    assert "INVENTORIES" in concepts

    # Kiểm tra giá trị đã làm sạch dấu phẩy
    ca_fact = next(f for f in facts if f.concept == "CURRENT_ASSETS" and f.period_type == "current")
    assert ca_fact.value == 30000000000.0
    assert ca_fact.prov_id.startswith("VNM_2024_p5_")


def test_tt200_comprehensive_ontology():
    # 1. Kiểm tra các tiểu mục Tài sản mới bổ sung
    c, code = match_concept_from_label_and_code("Tiền", raw_code="111")
    assert c == "CASH" and code == "111"

    c, code = match_concept_from_label_and_code("Các khoản tương đương tiền", raw_code="112")
    assert c == "CASH_EQUIVALENTS" and code == "112"

    c, code = match_concept_from_label_and_code("Chứng khoán kinh doanh", raw_code="121")
    assert c == "TRADING_SECURITIES" and code == "121"

    c, code = match_concept_from_label_and_code("Phải thu về cho vay ngắn hạn", raw_code="135")
    assert c == "SHORT_TERM_LOAN_RECEIVABLES" and code == "135"

    c, code = match_concept_from_label_and_code("Tài sản thiếu chờ xử lý", raw_code="139")
    assert c == "ASSETS_AWAITING_RESOLUTION" and code == "139"

    c, code = match_concept_from_label_and_code("Thuế giá trị gia tăng được khấu trừ", raw_code="152")
    assert c == "DEDUCTIBLE_VAT" and code == "152"

    c, code = match_concept_from_label_and_code("Nguyên giá TSCĐ hữu hình", raw_code="222")
    assert c == "TANGIBLE_FIXED_ASSETS_COST" and code == "222"

    c, code = match_concept_from_label_and_code("Giá trị hao mòn lũy kế TSCĐ hữu hình", raw_code="223")
    assert c == "TANGIBLE_FIXED_ASSETS_ACCUM_DEP" and code == "223"

    c, code = match_concept_from_label_and_code("Đầu tư vào công ty con", raw_code="251")
    assert c == "INVESTMENTS_IN_SUBSIDIARIES" and code == "251"

    c, code = match_concept_from_label_and_code("Tài sản thuế thu nhập hoãn lại", raw_code="262")
    assert c == "DEFERRED_TAX_ASSETS" and code == "262"

    # 2. Kiểm tra các tiểu mục Nợ phải trả mới bổ sung
    c, code = match_concept_from_label_and_code("Thuế và các khoản phải nộp nhà nước", raw_code="313")
    assert c == "TAXES_PAYABLE_TO_STATE" and code == "313"

    c, code = match_concept_from_label_and_code("Phải trả người lao động", raw_code="314")
    assert c == "PAYABLES_TO_EMPLOYEES" and code == "314"

    c, code = match_concept_from_label_and_code("Chi phí phải trả ngắn hạn", raw_code="315")
    assert c == "SHORT_TERM_ACCRUED_EXPENSES" and code == "315"

    c, code = match_concept_from_label_and_code("Dự phòng phải trả ngắn hạn", raw_code="321")
    assert c == "SHORT_TERM_PROVISIONS" and code == "321"

    c, code = match_concept_from_label_and_code("Quỹ khen thưởng, phúc lợi", raw_code="322")
    assert c == "BONUS_AND_WELFARE_FUND" and code == "322"

    c, code = match_concept_from_label_and_code("Phải trả người bán dài hạn", raw_code="331")
    assert c == "LONG_TERM_TRADE_PAYABLES" and code == "331"

    c, code = match_concept_from_label_and_code("Thuế thu nhập hoãn lại phải trả", raw_code="341")
    assert c == "DEFERRED_TAX_LIABILITIES" and code == "341"

    c, code = match_concept_from_label_and_code("Quỹ phát triển khoa học và công nghệ", raw_code="343")
    assert c == "SCIENCE_AND_TECHNOLOGY_FUND" and code == "343"

    # 3. Kiểm tra Vốn chủ sở hữu & mã dạng chữ cái phụ (411a, 411b, 421a, 421b)
    c, code = match_concept_from_label_and_code("Cổ phiếu phổ thông có quyền biểu quyết", raw_code="411a")
    assert c == "ORDINARY_SHARES" and code == "411a"

    c, code = match_concept_from_label_and_code("Cổ phiếu ưu đãi", raw_code="411b")
    assert c == "PREFERRED_SHARES" and code == "411b"

    c, code = match_concept_from_label_and_code("LNST chưa phân phối lũy kế đến cuối kỳ trước", raw_code="421a")
    assert c == "RETAINED_EARNINGS_PREV" and code == "421a"

    c, code = match_concept_from_label_and_code("LNST chưa phân phối kỳ này", raw_code="421b")
    assert c == "RETAINED_EARNINGS_CURR" and code == "421b"

    c, code = match_concept_from_label_and_code("Cổ phiếu quỹ", raw_code="415")
    assert c == "TREASURY_SHARES" and code == "415"

    c, code = match_concept_from_label_and_code("Quỹ đầu tư phát triển", raw_code="418")
    assert c == "DEVELOPMENT_INVESTMENT_FUND" and code == "418"

    c, code = match_concept_from_label_and_code("Nguồn kinh phí", raw_code="431")
    assert c == "BUDGET_SOURCES" and code == "431"

    # 4. Kiểm tra Lưu chuyển tiền tệ Trực tiếp vs Gián tiếp
    # Mã 01 Trực tiếp: Tiền thu từ bán hàng
    c_direct_01, _ = match_concept_from_label_and_code(
        "Tiền thu từ bán hàng, cung cấp dịch vụ và doanh thu khác",
        raw_code="01",
        statement_type_hint="CASH_FLOW",
    )
    assert c_direct_01 == "CF_DIRECT_SALES_PROCEEDS"

    # Mã 01 Gián tiếp: Lợi nhuận trước thuế
    c_indirect_01, _ = match_concept_from_label_and_code(
        "Lợi nhuận trước thuế",
        raw_code="01",
        statement_type_hint="CASH_FLOW",
    )
    assert c_indirect_01 == "CF_PROFIT_BEFORE_TAX"

    # Mã 02 Trực tiếp: Tiền chi trả người cung cấp
    c_direct_02, _ = match_concept_from_label_and_code(
        "Tiền chi trả cho người cung cấp hàng hóa và dịch vụ",
        raw_code="02",
        statement_type_hint="CASH_FLOW",
    )
    assert c_direct_02 == "CF_DIRECT_SUPPLIER_PAYMENTS"

    # Mã 02 Gián tiếp: Khấu hao TSCĐ
    c_indirect_02, _ = match_concept_from_label_and_code(
        "Khấu hao TSCĐ và BĐSĐT",
        raw_code="02",
        statement_type_hint="CASH_FLOW",
    )
    assert c_indirect_02 == "CF_DEPRECIATION"

    # Hoạt động đầu tư: 23, 24, 27
    c_loan, _ = match_concept_from_label_and_code(
        "Tiền chi cho vay, mua các công cụ nợ của đơn vị khác",
        raw_code="23",
        statement_type_hint="CASH_FLOW",
    )
    assert c_loan == "CF_LOANS_GIVEN"

    c_interest, _ = match_concept_from_label_and_code(
        "Tiền thu lãi cho vay, cổ tức và lợi nhuận được chia",
        raw_code="27",
        statement_type_hint="CASH_FLOW",
    )
    assert c_interest == "CF_INTEREST_AND_DIVIDENDS_RECEIVED"


def test_fact_extractor_headless_table_columns():
    """Kiểm tra bóc tách bảng thiếu header tường minh (headless table), không bị nhầm cột mã số sang giá trị tiền."""
    extractor = FinancialFactExtractor()

    # Bảng 5 cột chuẩn TT200 không có header 'Chỉ tiêu | Mã số...'
    headless_content = """
| Lợi nhuận kế toán trước thuế | 01 | | 11,466,794,698,617 | 11,243,489,707,213 |
| --- | --- | --- | --- | --- |
| Lưu chuyển tiền thuần từ hoạt động kinh doanh | 20 | | 7,690,701,645,261 | 8,845,818,265,750 |
| Lưu chuyển tiền thuần từ hoạt động đầu tư | 30 | | 2,608,662,395,779 | 1,232,840,887,367 |
"""
    parsed_block = ParsedBlock(
        block_id="p11_b6",
        block_type="table",
        page=11,
        content=headless_content.strip(),
        metadata={"unit": "VND"},
    )
    classified_block = ClassifiedBlock(
        block=parsed_block,
        block_type="FINANCIAL_STATEMENT",
        target=[StorageTarget.SQL],
        confidence=0.95,
        classification_method="rule_based",
    )

    facts, _ = extractor.extract_from_blocks([classified_block], company="VNM", year=2024)

    fact_op = next(f for f in facts if f.concept == "CF_NET_OPERATING" and f.period_type == "current")
    fact_inv = next(f for f in facts if f.concept == "CF_NET_INVESTING" and f.period_type == "current")

    # Phải lấy đúng giá trị tiền tệ ở cột 3, KHÔNG ĐƯỢC lấy mã số 20, 30
    assert fact_op.value == 7690701645261.0
    assert fact_op.standard_code == "20"
    assert fact_inv.value == 2608662395779.0
    assert fact_inv.standard_code == "30"


