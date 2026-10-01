"""
test_formula_engine.py — Unit tests cho FormulaEngine (13 chỉ số tài chính tính deterministic).
"""


from src.engine.formula_engine import FormulaEngine
from src.models import FinancialFact


def test_formula_engine_all_ratios():
    engine = FormulaEngine()

    facts = [
        # Bảng cân đối kế toán
        FinancialFact(id="f1", prov_id="p1", concept="CURRENT_ASSETS", raw_label="TSNH", value=100.0, period="2024", company="TEST", year=2024),
        FinancialFact(id="f2", prov_id="p2", concept="INVENTORIES", raw_label="HTK", value=20.0, period="2024", company="TEST", year=2024),
        FinancialFact(id="f3", prov_id="p3", concept="CASH_AND_EQUIVALENTS", raw_label="Tien", value=10.0, period="2024", company="TEST", year=2024),
        FinancialFact(id="f4", prov_id="p4", concept="CURRENT_LIABILITIES", raw_label="NNH", value=50.0, period="2024", company="TEST", year=2024),
        FinancialFact(id="f5", prov_id="p5", concept="LIABILITIES", raw_label="No", value=80.0, period="2024", company="TEST", year=2024),
        FinancialFact(id="f6", prov_id="p6", concept="EQUITY", raw_label="VCSH", value=120.0, period="2024", company="TEST", year=2024),
        FinancialFact(id="f7", prov_id="p7", concept="TOTAL_ASSETS", raw_label="Tong TS", value=200.0, period="2024", company="TEST", year=2024),
        # Báo cáo kết quả kinh doanh
        FinancialFact(id="f8", prov_id="p8", concept="NET_REVENUE", raw_label="DTT", value=300.0, period="2024", company="TEST", year=2024),
        FinancialFact(id="f9", prov_id="p9", concept="GROSS_PROFIT", raw_label="LNG", value=90.0, period="2024", company="TEST", year=2024),
        FinancialFact(id="f10", prov_id="p10", concept="OPERATING_PROFIT", raw_label="LNKD", value=45.0, period="2024", company="TEST", year=2024),
        FinancialFact(id="f11", prov_id="p11", concept="NET_PROFIT", raw_label="LNST", value=30.0, period="2024", company="TEST", year=2024),
    ]

    ratios = engine.compute_all_ratios(facts, company="TEST", year=2024)

    assert len(ratios) == 13
    ratio_dict = {r.ratio_name: r.value for r in ratios}

    # 1. Liquidity
    assert ratio_dict["current_ratio"] == 2.0  # 100 / 50
    assert ratio_dict["quick_ratio"] == 1.6    # (100 - 20) / 50
    assert ratio_dict["cash_ratio"] == 0.2     # 10 / 50

    # 2. Solvency
    assert ratio_dict["debt_to_equity"] == round(80.0 / 120.0, 4)
    assert ratio_dict["debt_to_assets"] == 0.40  # 80 / 200
    assert ratio_dict["financial_leverage"] == round(200.0 / 120.0, 4)

    # 3. Profitability
    assert ratio_dict["gross_margin"] == 0.30       # 90 / 300
    assert ratio_dict["net_profit_margin"] == 0.10  # 30 / 300
    assert ratio_dict["operating_margin"] == 0.15   # 45 / 300
    assert ratio_dict["roa"] == 0.15                # 30 / 200
    assert ratio_dict["roe"] == 0.25                # 30 / 120

    # 4. Efficiency & Health
    assert ratio_dict["asset_turnover"] == 1.50     # 300 / 200
    assert "altman_z_score" in ratio_dict

    # Kiểm tra tính toàn vẹn của Provenance
    for r in ratios:
        assert len(r.input_prov_ids) >= 2
        assert r.is_deterministic is True
