"""
test_verifier.py — Unit tests cho AccountingVerifier (Tự kiểm toán số học Anti-GIGO).
Kiểm tra các phương trình kế toán:
  1. Mã 270 == Mã 440 (Tài sản == Nguồn vốn)
  2. Mã 270 == Mã 100 + Mã 200 (Tài sản ngắn hạn + Dài hạn)
  3. Mã 100 == 110 + 120 + 130 + 140 + 150
  4. Mã 440 == Mã 300 + Mã 400 (Nợ phải trả + Vốn CSH)
  5. Mã 20 == Mã 10 - Mã 11 (Lợi nhuận gộp)
"""


from src.models import FinancialFact, VerificationStatus
from src.verifier.accounting_verifier import AccountingVerifier


def test_accounting_verifier_balanced_equations():
    verifier = AccountingVerifier()
    facts = [
        FinancialFact(
            id="f_ta", prov_id="p1", concept="TOTAL_ASSETS", standard_code="270",
            raw_label="Tổng tài sản", value=1000.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_tr", prov_id="p2", concept="TOTAL_RESOURCES", standard_code="440",
            raw_label="Tổng nguồn vốn", value=1000.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_ca", prov_id="p3", concept="CURRENT_ASSETS", standard_code="100",
            raw_label="Tài sản ngắn hạn", value=600.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_nca", prov_id="p4", concept="NON_CURRENT_ASSETS", standard_code="200",
            raw_label="Tài sản dài hạn", value=400.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_liab", prov_id="p5", concept="LIABILITIES", standard_code="300",
            raw_label="Nợ phải trả", value=300.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_eq", prov_id="p6", concept="EQUITY", standard_code="400",
            raw_label="Vốn chủ sở hữu", value=700.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_rev", prov_id="p7", concept="NET_REVENUE", standard_code="10",
            raw_label="Doanh thu thuần", value=2000.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_cogs", prov_id="p8", concept="COGS", standard_code="11",
            raw_label="Giá vốn hàng bán", value=1400.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_gp", prov_id="p9", concept="GROSS_PROFIT", standard_code="20",
            raw_label="Lợi nhuận gộp", value=600.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
    ]

    report = verifier.verify_facts(facts, company="TEST", year=2024)

    assert report.is_balanced is True
    assert report.total_checks >= 4
    assert len(report.failed_checks) == 0
    assert len(report.discrepancies) == 0
    assert facts[0].verification_status == VerificationStatus.VERIFIED
    assert facts[1].verification_status == VerificationStatus.VERIFIED


def test_accounting_verifier_detects_discrepancy():
    verifier = AccountingVerifier()
    # Giả lập số liệu bị sai lệch (ví dụ: do OCR nhầm số hoặc ảo giác LLM)
    facts = [
        FinancialFact(
            id="f_ta", prov_id="p1", concept="TOTAL_ASSETS", standard_code="270",
            raw_label="Tổng tài sản", value=1000.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_tr", prov_id="p2", concept="TOTAL_RESOURCES", standard_code="440",
            raw_label="Tổng nguồn vốn", value=950.0,  # Sai lệch 50
            period="2024", period_type="current", company="TEST", year=2024,
        ),
    ]

    report = verifier.verify_facts(facts, company="TEST", year=2024)

    assert report.is_balanced is False
    assert len(report.failed_checks) == 1
    assert len(report.discrepancies) == 1
    assert report.discrepancies[0]["delta"] == 50.0
    assert facts[0].verification_status == VerificationStatus.DISCREPANCY
    assert facts[1].verification_status == VerificationStatus.DISCREPANCY


def test_accounting_verifier_current_assets_sum():
    verifier = AccountingVerifier()
    facts = [
        FinancialFact(
            id="f_ca", prov_id="p1", concept="CURRENT_ASSETS", standard_code="100",
            raw_label="Tài sản ngắn hạn", value=500.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_cash", prov_id="p2", concept="CASH_AND_EQUIVALENTS", standard_code="110",
            raw_label="Tiền", value=100.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_inv", prov_id="p3", concept="INVENTORIES", standard_code="140",
            raw_label="Hàng tồn kho", value=200.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_rec", prov_id="p4", concept="SHORT_TERM_RECEIVABLES", standard_code="130",
            raw_label="Phải thu", value=200.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
    ]

    report = verifier.verify_facts(facts, company="TEST", year=2024)

    assert report.is_balanced is True
    assert facts[0].verification_status == VerificationStatus.VERIFIED


def test_accounting_verifier_smart_priority_and_cash_flow_isolation():
    verifier = AccountingVerifier()
    # Giả lập danh sách fact có cả KQKD và LCTT (nơi mã số 10, 11, 20 bị trùng)
    # và khoản mục con CĐKT xuất hiện sau khoản mục cha
    facts = [
        # Bảng Cân đối kế toán
        FinancialFact(
            id="f_ca", prov_id="p5_1", concept="CURRENT_ASSETS", standard_code="100",
            raw_label="TÀI SẢN NGẮN HẠN", value=1000.0, period="2024", period_type="current",
            company="VNM", year=2024,
        ),
        FinancialFact(
            id="f_cash", prov_id="p5_2", concept="CASH_AND_EQUIVALENTS", standard_code="110",
            raw_label="Tiền và tương đương tiền", value=200.0, period="2024", period_type="current",
            company="VNM", year=2024,
        ),
        FinancialFact(
            id="f_st_inv", prov_id="p5_3", concept="SHORT_TERM_INVESTMENTS", standard_code="120",
            raw_label="Đầu tư tài chính ngắn hạn", value=300.0, period="2024", period_type="current",
            company="VNM", year=2024,
        ),
        FinancialFact(
            id="f_rec", prov_id="p5_4", concept="SHORT_TERM_RECEIVABLES", standard_code="130",
            raw_label="Các khoản phải thu ngắn hạn", value=250.0, period="2024", period_type="current",
            company="VNM", year=2024,
        ),
        FinancialFact(
            id="f_inv", prov_id="p5_5", concept="INVENTORIES", standard_code="140",
            raw_label="Hàng tồn kho", value=200.0, period="2024", period_type="current",
            company="VNM", year=2024,
        ),
        FinancialFact(
            id="f_other_ca", prov_id="p5_6", concept="OTHER_CURRENT_ASSETS", standard_code="150",
            raw_label="Tài sản ngắn hạn khác", value=50.0, period="2024", period_type="current",
            company="VNM", year=2024,
        ),
        # Khoản mục con xuất hiện sau (nếu bị gán nhầm hoặc cùng concept)
        FinancialFact(
            id="f_rec_other", prov_id="p5_7", concept="SHORT_TERM_RECEIVABLES", standard_code="136",
            raw_label="Phải thu ngắn hạn khác", value=40.0, period="2024", period_type="current",
            company="VNM", year=2024,
        ),
        # Báo cáo Kết quả kinh doanh (KQKD)
        FinancialFact(
            id="f_rev", prov_id="p10_1", concept="NET_REVENUE", standard_code="10",
            raw_label="3. Doanh thu thuần về bán hàng", value=5000.0, period="2024", period_type="current",
            company="VNM", year=2024,
        ),
        FinancialFact(
            id="f_cogs", prov_id="p10_2", concept="COGS", standard_code="11",
            raw_label="4. Giá vốn hàng bán", value=3000.0, period="2024", period_type="current",
            company="VNM", year=2024,
        ),
        FinancialFact(
            id="f_gp", prov_id="p10_3", concept="GROSS_PROFIT", standard_code="20",
            raw_label="5. Lợi nhuận gộp về bán hàng", value=2000.0, period="2024", period_type="current",
            company="VNM", year=2024,
        ),
        # Báo cáo Lưu chuyển tiền tệ (LCTT) xuất hiện ở các trang sau
        FinancialFact(
            id="f_cf_inv", prov_id="p11_1", concept="NET_REVENUE", standard_code="10",
            raw_label="Biến động hàng tồn kho", value=-100.0, period="2024", period_type="current",
            company="VNM", year=2024,
        ),
        FinancialFact(
            id="f_cf_pay", prov_id="p11_2", concept="COGS", standard_code="11",
            raw_label="Biến động các khoản phải trả", value=-50.0, period="2024", period_type="current",
            company="VNM", year=2024,
        ),
        FinancialFact(
            id="f_cf_net", prov_id="p11_3", concept="GROSS_PROFIT", standard_code="20",
            raw_label="Lưu chuyển tiền thuần từ hoạt động kinh doanh", value=800.0, period="2024", period_type="current",
            company="VNM", year=2024,
        ),
    ]

    report = verifier.verify_facts(facts, company="VNM", year=2024)

    # Cả kiểm tra CỘNG_DỌC_NGẮN_HẠN và CÂN_ĐỐI_LỢI_NHUẬN_GỘP đều phải PASSED
    assert "CỘNG_DỌC_NGẮN_HẠN: TS Ngắn hạn (100) == ∑(5 khoản mục con)" in report.passed_checks
    assert "CÂN_ĐỐI_LỢI_NHUẬN_GỘP: LN Gộp (20) == Doanh thu thuần (10) - Giá vốn (11)" in report.passed_checks
    assert len(report.failed_checks) == 0
    assert report.is_balanced is True


def test_accounting_verifier_cash_flow_and_cross_check():
    """Kiểm tra các bài kiểm tra Báo cáo LCTT và Đối chiếu chéo CĐKT vs LCTT."""
    verifier = AccountingVerifier()
    facts = [
        # Bảng CĐKT
        FinancialFact(
            id="f_bs_cash", prov_id="p7_1", concept="CASH_AND_EQUIVALENTS", standard_code="110",
            raw_label="Tiền và các khoản tương đương tiền", value=1500.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        # Báo cáo KQKD
        FinancialFact(
            id="f_gross_rev", prov_id="p9_1", concept="GROSS_REVENUE", standard_code="01",
            raw_label="Doanh thu bán hàng và cung cấp dịch vụ", value=2100.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_ded", prov_id="p9_2", concept="REVENUE_DEDUCTIONS", standard_code="02",
            raw_label="Các khoản giảm trừ doanh thu", value=100.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_net_rev", prov_id="p9_3", concept="NET_REVENUE", standard_code="10",
            raw_label="Doanh thu thuần", value=2000.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_op", prov_id="p9_4", concept="OPERATING_PROFIT", standard_code="30",
            raw_label="Lợi nhuận thuần từ HĐKD", value=800.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_oth", prov_id="p9_5", concept="OTHER_PROFIT", standard_code="40",
            raw_label="Lợi nhuận khác", value=50.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_pbt", prov_id="p9_6", concept="PROFIT_BEFORE_TAX", standard_code="50",
            raw_label="Tổng lợi nhuận kế toán trước thuế", value=850.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        # Báo cáo LCTT
        FinancialFact(
            id="f_cf_ope", prov_id="p11_1", concept="CF_NET_OPERATING", standard_code="20",
            raw_label="Lưu chuyển tiền thuần từ hoạt động kinh doanh", value=1200.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_cf_inv", prov_id="p11_2", concept="CF_NET_INVESTING", standard_code="30",
            raw_label="Lưu chuyển tiền thuần từ hoạt động đầu tư", value=-500.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_cf_fin", prov_id="p11_3", concept="CF_NET_FINANCING", standard_code="40",
            raw_label="Lưu chuyển tiền thuần từ hoạt động tài chính", value=-200.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_cf_net", prov_id="p11_4", concept="CF_NET_CHANGE", standard_code="50",
            raw_label="Lưu chuyển tiền thuần trong năm", value=500.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_cf_beg", prov_id="p11_5", concept="CF_BEGINNING_CASH", standard_code="60",
            raw_label="Tiền và tương đương tiền đầu năm", value=1000.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
        FinancialFact(
            id="f_cf_end", prov_id="p11_6", concept="CF_ENDING_CASH", standard_code="70",
            raw_label="Tiền và tương đương tiền cuối năm", value=1500.0, period="2024", period_type="current",
            company="TEST", year=2024,
        ),
    ]

    report = verifier.verify_facts(facts, company="TEST", year=2024)

    assert report.is_balanced is True
    passed_names = " ".join(report.passed_checks)
    assert "CÂN_ĐỐI_DOANH_THU" in passed_names
    assert "CỘNG_LN_TRƯỚC_THUẾ" in passed_names
    assert "CÂN_ĐỐI_LCTT_THUẦN" in passed_names
    assert "CÂN_ĐỐI_TIỀN_CUỐI_KỲ" in passed_names
    assert "ĐỐI_CHIẾU_CHÉO_TIỀN" in passed_names


def test_accounting_verifier_all_new_equations():
    """Kiểm tra toàn diện tất cả các bài kiểm tra số học mới theo Thông tư 200:
    - Bảng CĐKT: Dài hạn (200 == sum con), Nợ phải trả (300 == 310 + 330)
    - Báo cáo KQKD: LN thuần HĐKD (30 == 20+21-22-25-26), LN Khác (40 == 31-32), LN Sau thuế (60 == 50-51-52)
    - Báo cáo LCTT: HĐTC đủ 6 mã con (40 == 31-32+33-34-35-36), Tiền cuối kỳ kèm tỷ giá (70 == 60+50+61)
    - Đối chiếu chéo: LN trước thuế LCTT gián tiếp (01) == KQKD (50)
    """
    verifier = AccountingVerifier()
    facts = [
        # CĐKT
        FinancialFact(id="f1", prov_id="p1", concept="NON_CURRENT_ASSETS", standard_code="200", raw_label="TÀI SẢN DÀI HẠN", value=1500.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f2", prov_id="p2", concept="FIXED_ASSETS", standard_code="220", raw_label="Tài sản cố định", value=1000.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f3", prov_id="p3", concept="LONG_TERM_INVESTMENTS", standard_code="250", raw_label="Đầu tư tài chính dài hạn", value=500.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f4", prov_id="p4", concept="LIABILITIES", standard_code="300", raw_label="NỢ PHẢI TRẢ", value=800.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f5", prov_id="p5", concept="CURRENT_LIABILITIES", standard_code="310", raw_label="Nợ ngắn hạn", value=500.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f6", prov_id="p6", concept="NON_CURRENT_LIABILITIES", standard_code="330", raw_label="Nợ dài hạn", value=300.0, period="2024", period_type="current", company="DN", year=2024),

        # KQKD
        FinancialFact(id="f7", prov_id="p7", concept="GROSS_PROFIT", standard_code="20", raw_label="Lợi nhuận gộp", value=1000.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f8", prov_id="p8", concept="FINANCIAL_INCOME", standard_code="21", raw_label="Doanh thu tài chính", value=200.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f9", prov_id="p9", concept="FINANCIAL_EXPENSES", standard_code="22", raw_label="Chi phí tài chính", value=100.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f10", prov_id="p10", concept="SELLING_EXPENSES", standard_code="25", raw_label="Chi phí bán hàng", value=150.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f11", prov_id="p11", concept="ADMIN_EXPENSES", standard_code="26", raw_label="Chi phí quản lý DN", value=150.0, period="2024", period_type="current", company="DN", year=2024),
        # 1000 + 200 - 100 - 150 - 150 = 800
        FinancialFact(id="f12", prov_id="p12", concept="OPERATING_PROFIT", standard_code="30", raw_label="Lợi nhuận thuần từ HĐKD", value=800.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f13", prov_id="p13", concept="OTHER_INCOME", standard_code="31", raw_label="Thu nhập khác", value=80.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f14", prov_id="p14", concept="OTHER_EXPENSES", standard_code="32", raw_label="Chi phí khác", value=30.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f15", prov_id="p15", concept="OTHER_PROFIT", standard_code="40", raw_label="Lợi nhuận khác", value=50.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f16", prov_id="p16", concept="PROFIT_BEFORE_TAX", standard_code="50", raw_label="Tổng lợi nhuận trước thuế", value=850.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f17", prov_id="p17", concept="CURRENT_TAX_EXPENSE", standard_code="51", raw_label="Chi phí thuế TNDN hiện hành", value=150.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f18", prov_id="p18", concept="DEFERRED_TAX_EXPENSE", standard_code="52", raw_label="Chi phí thuế TNDN hoãn lại", value=20.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f19", prov_id="p19", concept="NET_PROFIT", standard_code="60", raw_label="Lợi nhuận sau thuế", value=680.0, period="2024", period_type="current", company="DN", year=2024),

        # LCTT đầy đủ 6 mã con HĐTC: 31 - 32 + 33 - 34 - 35 - 36
        # = 500 (31) - 100 (32) + 1000 (33) - 600 (34) - 50 (35) - 200 (36) = 550
        FinancialFact(id="f20", prov_id="p20", concept="CF_EQUITY_ISSUANCE", standard_code="31", raw_label="Tiền thu từ phát hành cổ phiếu", value=500.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f21", prov_id="p21", concept="CF_CAPITAL_REFUND", standard_code="32", raw_label="Tiền trả lại vốn góp", value=-100.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f22", prov_id="p22", concept="CF_BORROWINGS", standard_code="33", raw_label="Tiền thu từ đi vay", value=1000.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f23", prov_id="p23", concept="CF_REPAYMENTS", standard_code="34", raw_label="Tiền chi trả nợ gốc vay", value=-600.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f24", prov_id="p24", concept="CF_LEASE_REPAYMENTS", standard_code="35", raw_label="Tiền chi trả nợ thuê tài chính", value=-50.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f25", prov_id="p25", concept="CF_DIVIDENDS_PAID", standard_code="36", raw_label="Cổ tức đã trả", value=-200.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f26", prov_id="p26", concept="CF_NET_FINANCING", standard_code="40", raw_label="Lưu chuyển thuần từ HĐTC", value=550.0, period="2024", period_type="current", company="DN", year=2024),

        # Tiền cuối kỳ LCTT có tỷ giá (61): 1000 (60) + 500 (50) + (-20) (61) = 1480 (70)
        FinancialFact(id="f27", prov_id="p27", concept="CF_BEGINNING_CASH", standard_code="60", raw_label="Tiền đầu năm", value=1000.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f28", prov_id="p28", concept="CF_NET_CHANGE", standard_code="50", raw_label="Lưu chuyển thuần trong năm", value=500.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f29", prov_id="p29", concept="CF_EXCHANGE_RATE_DIFF", standard_code="61", raw_label="Ảnh hưởng của thay đổi tỷ giá", value=-20.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f30", prov_id="p30", concept="CF_ENDING_CASH", standard_code="70", raw_label="Tiền cuối năm", value=1480.0, period="2024", period_type="current", company="DN", year=2024),

        # Đối chiếu chéo LN trước thuế LCTT gián tiếp vs KQKD
        FinancialFact(id="f31", prov_id="p31", concept="CF_PROFIT_BEFORE_TAX", standard_code="01", raw_label="Lợi nhuận trước thuế", value=850.0, period="2024", period_type="current", company="DN", year=2024),
    ]

    report = verifier.verify_facts(facts, company="DN", year=2024)

    assert report.is_balanced is True
    passed_names = " ".join(report.passed_checks)
    assert "CỘNG_DỌC_DÀI_HẠN" in passed_names
    assert "CỘNG_NỢ_PHẢI_TRẢ" in passed_names
    assert "CÂN_ĐỐI_LN_THUẦN_HĐKD" in passed_names
    assert "CÂN_ĐỐI_LN_KHÁC" in passed_names
    assert "CÂN_ĐỐI_LN_SAU_THUẾ" in passed_names
    assert "CÂN_ĐỐI_LCTT_HĐTC" in passed_names
    assert "CÂN_ĐỐI_TIỀN_CUỐI_KỲ" in passed_names
    assert "ĐỐI_CHIẾU_CHÉO_LN_TRƯỚC_THUẾ" in passed_names


def test_accounting_verifier_cash_flow_financing_discrepancy():
    """Kiểm tra khi LCTT HĐTC bị sai lệch (ví dụ OCR đọc nhầm mã 40), hệ thống báo DISCREPANCY."""
    verifier = AccountingVerifier()
    facts = [
        FinancialFact(id="f1", prov_id="p1", concept="CF_BORROWINGS", standard_code="33", raw_label="Tiền thu từ đi vay", value=1000.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f2", prov_id="p2", concept="CF_REPAYMENTS", standard_code="34", raw_label="Tiền chi trả nợ gốc vay", value=-600.0, period="2024", period_type="current", company="DN", year=2024),
        FinancialFact(id="f3", prov_id="p3", concept="CF_NET_FINANCING", standard_code="40", raw_label="Lưu chuyển thuần HĐTC", value=500.0, period="2024", period_type="current", company="DN", year=2024), # Sai lệch: đúng ra phải là 400
    ]

    report = verifier.verify_facts(facts, company="DN", year=2024)

    assert report.is_balanced is False
    assert len(report.failed_checks) == 1
    assert "LỆCH_LCTT_HĐTC" in report.failed_checks[0]
    assert report.discrepancies[0]["delta"] == 100.0
    assert facts[2].verification_status == VerificationStatus.DISCREPANCY


def test_vision_zoom_multi_variable_residual_correction():
    """Kiểm tra phá vỡ bẫy Chicken-and-Egg khi phương trình có 2 biến cùng bị sai."""
    from unittest.mock import patch
    from src.verifier.vision_zoom_corrector import VisionZoomCorrector

    verifier = AccountingVerifier()
    corrector = VisionZoomCorrector(verifier=verifier)

    # 500 == 400 (OP) + 200 (INV) - 100 (FIN)
    fact_net = FinancialFact(id="f50", prov_id="p50", concept="CF_NET_CHANGE", standard_code="50", raw_label="Lưu chuyển thuần trong năm", value=500.0, period="2024", period_type="current", company="DN", year=2024, page=11)
    fact_fin = FinancialFact(id="f40", prov_id="p40", concept="CF_NET_FINANCING", standard_code="40", raw_label="Lưu chuyển thuần HĐTC", value=-100.0, period="2024", period_type="current", company="DN", year=2024, page=11)
    # 2 biến bị gán nhầm mã số:
    fact_op = FinancialFact(id="f20", prov_id="p20", concept="CF_NET_OPERATING", standard_code="20", raw_label="Lưu chuyển thuần HĐKD", value=20.0, period="2024", period_type="current", company="DN", year=2024, page=11)
    fact_inv = FinancialFact(id="f30", prov_id="p30", concept="CF_NET_INVESTING", standard_code="30", raw_label="Lưu chuyển thuần HĐĐT", value=30.0, period="2024", period_type="current", company="DN", year=2024, page=11)

    facts = [fact_net, fact_op, fact_inv, fact_fin]
    initial_report = verifier.verify_facts(facts, company="DN", year=2024)
    assert not initial_report.is_balanced

    # Mock locate_and_crop_row và inspect_row_image
    def mock_locate(pdf_path, fact, suspect_facts=None, save_debug_dir=None):
        return ("dummy_img", "dummy_b64", "current")

    def mock_inspect(img_b64, fact, target_column):
        if fact.concept == "CF_NET_OPERATING":
            return {"value_current": 400.0}
        elif fact.concept == "CF_NET_INVESTING":
            return {"value_current": 200.0}
        return {"value_current": fact.value}

    with patch.object(corrector, "locate_and_crop_row", side_effect=mock_locate), \
         patch.object(corrector, "inspect_row_image", side_effect=mock_inspect):
        corrected_facts, final_report, is_corrected = corrector.run_self_correction(
            pdf_path="dummy.pdf",
            facts=facts,
            report=initial_report,
            company="DN",
            year=2024,
        )

    # Khẳng định: Cả 2 biến đều được sửa và BCTC cân đối 100%
    assert is_corrected is True
    assert final_report.is_balanced is True
    op_val = next(f.value for f in corrected_facts if f.concept == "CF_NET_OPERATING")
    inv_val = next(f.value for f in corrected_facts if f.concept == "CF_NET_INVESTING")
    assert op_val == 400.0
    assert inv_val == 200.0




