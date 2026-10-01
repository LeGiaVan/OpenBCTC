"""
formula_engine.py — Deterministic Financial Ratio Engine.
Tính toán 13 chỉ số tài chính trọng yếu bằng công thức toán học thuần túy trong Python (Zero-Hallucination).
Lưu vết provenance_id của từng Fact đầu vào để đảm bảo tính minh bạch và có thể kiểm tra chéo (Auditability).
"""

import logging
import re

from src.database.db_manager import DatabaseManager
from src.extractor.ontology import CONCEPT_TO_CODE
from src.models import FinancialFact, FinancialRatio

logger = logging.getLogger(__name__)


class FormulaEngine:
    """Bộ tính toán chỉ số tài chính toán học deterministic."""

    def __init__(self, db_manager: DatabaseManager | None = None) -> None:
        self.db_manager = db_manager

    def compute_all_ratios(
        self,
        facts: list[FinancialFact],
        company: str = "VNM",
        year: int = 2024,
    ) -> list[FinancialRatio]:
        """
        Tính toán toàn bộ các chỉ số tài chính có thể từ danh sách Facts đầu vào.
        Chỉ số nào thiếu dữ liệu đầu vào sẽ được bỏ qua một cách an toàn mà không gây crash.
        """
        def _get_fact_priority(f: FinancialFact) -> int:
            score = 10
            expected_code = CONCEPT_TO_CODE.get(f.concept, "")
            clean_fact_code = re.sub(r"[^\d]", "", str(f.standard_code))
            if expected_code and clean_fact_code == expected_code:
                score += 50
            elif clean_fact_code and expected_code and clean_fact_code != expected_code:
                score -= 30

            lbl = f.raw_label.lower()
            if f.concept in ("NET_REVENUE", "COGS", "GROSS_PROFIT", "OPERATING_PROFIT", "PROFIT_BEFORE_TAX", "NET_PROFIT"):
                if any(k in lbl for k in ["lưu chuyển", "tiền thuần", "biến động", "thanh lý", "cổ tức", "tiền chi", "tiền thu"]):
                    score -= 100
                if f.concept == "NET_REVENUE" and "doanh thu" in lbl:
                    score += 20
                if f.concept == "COGS" and "giá vốn" in lbl:
                    score += 20
                if f.concept == "GROSS_PROFIT" and "lợi nhuận gộp" in lbl:
                    score += 20

            if f.concept in ("SHORT_TERM_RECEIVABLES", "INVENTORIES", "FIXED_ASSETS", "LONG_TERM_RECEIVABLES"):
                if any(k in lbl for k in ["khác", "dự phòng", "nguyên giá", "hao mòn"]):
                    score -= 40

            return score

        # Tạo bản đồ tra cứu nhanh: concept -> FinancialFact có chọn lọc ưu tiên
        facts_map: dict[str, FinancialFact] = {}
        for f in facts:
            if f.period_type == "current" or f.period == str(year):
                if f.concept not in facts_map:
                    facts_map[f.concept] = f
                else:
                    existing = facts_map[f.concept]
                    if _get_fact_priority(f) > _get_fact_priority(existing):
                        facts_map[f.concept] = f

        ratios: list[FinancialRatio] = []

        # ── 1. NHÓM THANH KHOẢN (LIQUIDITY) ──────────────────────────────────────────
        # 1.1 Current Ratio = Tài sản ngắn hạn / Nợ ngắn hạn
        if "CURRENT_ASSETS" in facts_map and "CURRENT_LIABILITIES" in facts_map:
            ca = facts_map["CURRENT_ASSETS"]
            cl = facts_map["CURRENT_LIABILITIES"]
            if cl.value > 0:
                val = ca.value / cl.value
                ratios.append(
                    FinancialRatio(
                        id=f"{company}_{year}_current_ratio",
                        company=company,
                        year=year,
                        ratio_name="current_ratio",
                        ratio_category="liquidity",
                        value=round(val, 4),
                        formula="CURRENT_ASSETS / CURRENT_LIABILITIES",
                        input_prov_ids=[ca.prov_id, cl.prov_id],
                    )
                )

        # 1.2 Quick Ratio = (Tài sản ngắn hạn - Hàng tồn kho) / Nợ ngắn hạn
        if (
            "CURRENT_ASSETS" in facts_map
            and "CURRENT_LIABILITIES" in facts_map
            and "INVENTORIES" in facts_map
        ):
            ca = facts_map["CURRENT_ASSETS"]
            inv = facts_map["INVENTORIES"]
            cl = facts_map["CURRENT_LIABILITIES"]
            if cl.value > 0:
                val = (ca.value - inv.value) / cl.value
                ratios.append(
                    FinancialRatio(
                        id=f"{company}_{year}_quick_ratio",
                        company=company,
                        year=year,
                        ratio_name="quick_ratio",
                        ratio_category="liquidity",
                        value=round(val, 4),
                        formula="(CURRENT_ASSETS - INVENTORIES) / CURRENT_LIABILITIES",
                        input_prov_ids=[ca.prov_id, inv.prov_id, cl.prov_id],
                    )
                )

        # 1.3 Cash Ratio = Tiền & tương đương tiền / Nợ ngắn hạn
        if "CASH_AND_EQUIVALENTS" in facts_map and "CURRENT_LIABILITIES" in facts_map:
            cash = facts_map["CASH_AND_EQUIVALENTS"]
            cl = facts_map["CURRENT_LIABILITIES"]
            if cl.value > 0:
                val = cash.value / cl.value
                ratios.append(
                    FinancialRatio(
                        id=f"{company}_{year}_cash_ratio",
                        company=company,
                        year=year,
                        ratio_name="cash_ratio",
                        ratio_category="liquidity",
                        value=round(val, 4),
                        formula="CASH_AND_EQUIVALENTS / CURRENT_LIABILITIES",
                        input_prov_ids=[cash.prov_id, cl.prov_id],
                    )
                )

        # ── 2. NHÓM ĐÒN BẨY & CƠ CẤU VỐN (SOLVENCY) ──────────────────────────────────
        # 2.1 Debt to Equity = Nợ phải trả / Vốn chủ sở hữu
        liab = facts_map.get("LIABILITIES") or facts_map.get("TOTAL_LIABILITIES")
        eq = facts_map.get("EQUITY")
        if liab and eq and eq.value > 0:
            val = liab.value / eq.value
            ratios.append(
                FinancialRatio(
                    id=f"{company}_{year}_debt_to_equity",
                    company=company,
                    year=year,
                    ratio_name="debt_to_equity",
                    ratio_category="solvency",
                    value=round(val, 4),
                    formula="LIABILITIES / EQUITY",
                    input_prov_ids=[liab.prov_id, eq.prov_id],
                )
            )

        # 2.2 Debt to Assets = Nợ phải trả / Tổng tài sản
        assets = facts_map.get("TOTAL_ASSETS")
        if liab and assets and assets.value > 0:
            val = liab.value / assets.value
            ratios.append(
                FinancialRatio(
                    id=f"{company}_{year}_debt_to_assets",
                    company=company,
                    year=year,
                    ratio_name="debt_to_assets",
                    ratio_category="solvency",
                    value=round(val, 4),
                    formula="LIABILITIES / TOTAL_ASSETS",
                    input_prov_ids=[liab.prov_id, assets.prov_id],
                )
            )

        # 2.3 Financial Leverage = Tổng tài sản / Vốn chủ sở hữu
        if "TOTAL_ASSETS" in facts_map and "EQUITY" in facts_map:
            assets = facts_map["TOTAL_ASSETS"]
            eq = facts_map["EQUITY"]
            if eq.value > 0:
                val = assets.value / eq.value
                ratios.append(
                    FinancialRatio(
                        id=f"{company}_{year}_financial_leverage",
                        company=company,
                        year=year,
                        ratio_name="financial_leverage",
                        ratio_category="solvency",
                        value=round(val, 4),
                        formula="TOTAL_ASSETS / EQUITY",
                        input_prov_ids=[assets.prov_id, eq.prov_id],
                    )
                )

        # ── 3. NHÓM KHẢ NĂNG SINH LỜI (PROFITABILITY) ────────────────────────────────
        # 3.1 Gross Margin = Lợi nhuận gộp / Doanh thu thuần
        if "GROSS_PROFIT" in facts_map and "NET_REVENUE" in facts_map:
            gp = facts_map["GROSS_PROFIT"]
            rev = facts_map["NET_REVENUE"]
            if rev.value > 0:
                val = gp.value / rev.value
                ratios.append(
                    FinancialRatio(
                        id=f"{company}_{year}_gross_margin",
                        company=company,
                        year=year,
                        ratio_name="gross_margin",
                        ratio_category="profitability",
                        value=round(val, 4),
                        formula="GROSS_PROFIT / NET_REVENUE",
                        input_prov_ids=[gp.prov_id, rev.prov_id],
                    )
                )

        # 3.2 Net Profit Margin = Lợi nhuận sau thuế / Doanh thu thuần
        npat = facts_map.get("NET_PROFIT") or facts_map.get("NET_PROFIT_AFTER_TAX")
        rev = facts_map.get("NET_REVENUE")
        if npat and rev and rev.value > 0:
            val = npat.value / rev.value
            ratios.append(
                FinancialRatio(
                    id=f"{company}_{year}_net_profit_margin",
                    company=company,
                    year=year,
                    ratio_name="net_profit_margin",
                    ratio_category="profitability",
                    value=round(val, 4),
                    formula="NET_PROFIT / NET_REVENUE",
                    input_prov_ids=[npat.prov_id, rev.prov_id],
                )
            )

        # 3.3 Operating Margin = Lợi nhuận từ HĐKD / Doanh thu thuần
        op = facts_map.get("OPERATING_PROFIT") or facts_map.get("EBIT")
        if op and rev and rev.value > 0:
            val = op.value / rev.value
            ratios.append(
                FinancialRatio(
                    id=f"{company}_{year}_operating_margin",
                    company=company,
                    year=year,
                    ratio_name="operating_margin",
                    ratio_category="profitability",
                    value=round(val, 4),
                    formula="OPERATING_PROFIT / NET_REVENUE",
                    input_prov_ids=[op.prov_id, rev.prov_id],
                )
            )

        # 3.4 ROA = Lợi nhuận sau thuế / Tổng tài sản
        assets = facts_map.get("TOTAL_ASSETS")
        if npat and assets and assets.value > 0:
            val = npat.value / assets.value
            ratios.append(
                FinancialRatio(
                    id=f"{company}_{year}_roa",
                    company=company,
                    year=year,
                    ratio_name="roa",
                    ratio_category="profitability",
                    value=round(val, 4),
                    formula="NET_PROFIT / TOTAL_ASSETS",
                    input_prov_ids=[npat.prov_id, assets.prov_id],
                )
            )

        # 3.5 ROE = Lợi nhuận sau thuế / Vốn chủ sở hữu
        if npat and eq and eq.value > 0:
            val = npat.value / eq.value
            ratios.append(
                FinancialRatio(
                    id=f"{company}_{year}_roe",
                    company=company,
                    year=year,
                    ratio_name="roe",
                    ratio_category="profitability",
                    value=round(val, 4),
                    formula="NET_PROFIT / EQUITY",
                    input_prov_ids=[npat.prov_id, eq.prov_id],
                )
            )

        # ── 4. HIỆU QUẢ HOẠT ĐỘNG & SỨC KHỎE TÀI CHÍNH (EFFICIENCY & HEALTH) ─────────
        # 4.1 Asset Turnover = Doanh thu thuần / Tổng tài sản
        if rev and assets and assets.value > 0:
            val = rev.value / assets.value
            ratios.append(
                FinancialRatio(
                    id=f"{company}_{year}_asset_turnover",
                    company=company,
                    year=year,
                    ratio_name="asset_turnover",
                    ratio_category="efficiency",
                    value=round(val, 4),
                    formula="NET_REVENUE / TOTAL_ASSETS",
                    input_prov_ids=[rev.prov_id, assets.prov_id],
                )
            )

        # 4.2 Altman Z-Score cho thị trường mới nổi (Emerging Markets Model)
        # Z' = 0.717*X1 + 0.847*X2 + 3.107*X3 + 0.420*X4 + 0.998*X5
        ca = facts_map.get("CURRENT_ASSETS")
        cl = facts_map.get("CURRENT_LIABILITIES")
        if ca and cl and assets and liab and eq and rev and op:
            if assets.value > 0 and liab.value > 0:
                # X1 = Vốn lưu động ròng / Tổng tài sản
                x1 = (ca.value - cl.value) / assets.value
                # X2 = Ước lượng lợi nhuận giữ lại / Tổng tài sản
                retained_fact = facts_map.get("UNDISTRIBUTED_PROFIT")
                x2 = (retained_fact.value / assets.value) if retained_fact else 0.0
                # X3 = EBIT / Tổng tài sản
                x3 = op.value / assets.value
                # X4 = Vốn CSH / Tổng nợ phải trả
                x4 = eq.value / liab.value
                # X5 = Doanh thu thuần / Tổng tài sản
                x5 = rev.value / assets.value

                z_score = 0.717 * x1 + 0.847 * x2 + 3.107 * x3 + 0.420 * x4 + 0.998 * x5
                inputs = [ca.prov_id, cl.prov_id, assets.prov_id, liab.prov_id, eq.prov_id, rev.prov_id, op.prov_id]
                if retained_fact:
                    inputs.append(retained_fact.prov_id)

                ratios.append(
                    FinancialRatio(
                        id=f"{company}_{year}_altman_z_score",
                        company=company,
                        year=year,
                        ratio_name="altman_z_score",
                        ratio_category="financial_health",
                        value=round(z_score, 4),
                        formula="0.717*X1 + 0.847*X2 + 3.107*X3 + 0.420*X4 + 0.998*X5",
                        input_prov_ids=inputs,
                    )
                )

        # Lưu vào SQLite CSDL nếu có db_manager
        if self.db_manager and ratios:
            self.db_manager.save_ratios(ratios)

        return ratios
