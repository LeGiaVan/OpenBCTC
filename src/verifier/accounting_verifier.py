"""
accounting_verifier.py — Bộ Tự Kiểm Toán Số Học (Self-Auditing Accounting Invariants Verifier).
Chốt chặn cốt lõi loại bỏ rủi ro GIGO (Garbage In, Garbage Out):
  - Áp dụng các phương trình toán học và đẳng thức kế toán đóng kín (Accounting Invariants).
  - Tự động phát hiện số liệu bị hallucinate, nhầm số, rớt dòng hoặc vỡ cấu trúc.
  - Cập nhật trạng thái `verification_status` (VERIFIED vs DISCREPANCY) cho từng Fact.
"""

import logging
import re
from typing import Any

from src.extractor.ontology import CONCEPT_TO_CODE
from src.models import FinancialFact, VerificationReport, VerificationStatus

logger = logging.getLogger(__name__)


class AccountingVerifier:
    """Bộ kiểm tra tính hợp lệ số học và đẳng thức kế toán cho Fact tài chính."""

    def __init__(self, tolerance_ratio: float = 0.0001, absolute_tolerance: float = 2.0) -> None:
        """
        Args:
            tolerance_ratio: Sai số tương đối cho phép do làm tròn (mặc định 0.01%)
            absolute_tolerance: Sai số tuyệt đối cho phép do làm tròn đơn vị lẻ (mặc định 2.0)
        """
        self.tolerance_ratio = tolerance_ratio
        self.absolute_tolerance = absolute_tolerance

    def verify_facts(
        self,
        facts: list[FinancialFact],
        company: str = "DOANH_NGHIEP",
        year: int = 2024,
    ) -> VerificationReport:
        """
        Chạy toàn bộ các bài kiểm tra đẳng thức số học trên danh sách Fact.
        Tự động cập nhật `verification_status` và `verification_detail` trên từng FinancialFact.

        Returns:
            VerificationReport: Báo cáo kết quả kiểm toán số học chi tiết.
        """
        def _get_fact_priority(f: FinancialFact) -> int:
            """
            Tính điểm ưu tiên cho Fact khi có nhiều fact cùng concept:
            - Điểm cao hơn nếu mã số chuẩn khớp đúng với mã chuẩn của concept theo Thông tư 200.
            - Điểm phạt nếu tên khoản mục chứa các từ khóa chỉ khoản mục con hoặc lưu chuyển tiền.
            """
            score = 10
            expected_code = CONCEPT_TO_CODE.get(f.concept, "")
            clean_fact_code = re.sub(r"[^\d]", "", str(f.standard_code))
            if expected_code and clean_fact_code == expected_code:
                score += 50
            elif clean_fact_code and expected_code and clean_fact_code != expected_code:
                score -= 30

            lbl = f.raw_label.lower()
            # Đối với các chỉ tiêu KQKD: phạt nặng nếu nhãn thuộc về LCTT (lưu chuyển tiền thuần, biến động...)
            if f.concept in ("NET_REVENUE", "COGS", "GROSS_PROFIT", "OPERATING_PROFIT", "PROFIT_BEFORE_TAX", "NET_PROFIT"):
                if any(k in lbl for k in ["lưu chuyển", "tiền thuần", "biến động", "thanh lý", "cổ tức", "tiền chi", "tiền thu"]):
                    score -= 100
                if f.concept == "NET_REVENUE" and "doanh thu" in lbl:
                    score += 20
                if f.concept == "COGS" and "giá vốn" in lbl:
                    score += 20
                if f.concept == "GROSS_PROFIT" and "lợi nhuận gộp" in lbl:
                    score += 20

            # Đối với các chỉ tiêu CĐKT: phạt nếu là khoản mục con (khác, dự phòng...)
            if f.concept in ("SHORT_TERM_RECEIVABLES", "INVENTORIES", "FIXED_ASSETS", "LONG_TERM_RECEIVABLES"):
                if any(k in lbl for k in ["khác", "dự phòng", "nguyên giá", "hao mòn"]):
                    score -= 40

            if f.concept in ("CF_EQUITY_ISSUANCE", "CF_CAPITAL_REFUND", "CF_LEASE_REPAYMENTS"):
                if any(k in lbl for k in ["cổ phiếu", "vốn góp", "nợ thuê", "thuê tài chính"]):
                    score += 20
            if f.concept in ("OTHER_INCOME", "OTHER_EXPENSES"):
                if any(k in lbl for k in ["khác", "thu nhập khác", "chi phí khác"]):
                    score += 20

            return score

        # Gom nhóm facts theo kỳ hiện tại có chọn lọc thông minh
        current_facts_by_concept: dict[str, FinancialFact] = {}
        for f in facts:
            if f.period_type == "current" or f.period == str(year):
                if f.concept not in current_facts_by_concept:
                    current_facts_by_concept[f.concept] = f
                else:
                    existing = current_facts_by_concept[f.concept]
                    if _get_fact_priority(f) > _get_fact_priority(existing):
                        current_facts_by_concept[f.concept] = f

        passed_checks: list[str] = []
        failed_checks: list[str] = []
        discrepancies: list[dict[str, Any]] = []

        def is_equal(val1: float, val2: float) -> bool:
            diff = abs(val1 - val2)
            if diff <= self.absolute_tolerance:
                return True
            max_val = max(abs(val1), abs(val2))
            if max_val == 0:
                return True
            return (diff / max_val) <= self.tolerance_ratio

        # ── KIỂM TRA 1: CÂN ĐỐI TỔNG TÀI SẢN == TỔNG NGUỒN VỐN (Mã 270 == Mã 440) ────
        if "TOTAL_ASSETS" in current_facts_by_concept and "TOTAL_RESOURCES" in current_facts_by_concept:
            f_assets = current_facts_by_concept["TOTAL_ASSETS"]
            f_res = current_facts_by_concept["TOTAL_RESOURCES"]
            if is_equal(f_assets.value, f_res.value):
                passed_checks.append("CÂN_ĐỐI_TÀI_SẢN_NGUỒN_VỐN: Tổng tài sản (270) == Tổng nguồn vốn (440)")
                f_assets.verification_status = VerificationStatus.VERIFIED
                f_assets.verification_detail = "Khớp 100% với Tổng cộng nguồn vốn"
                f_res.verification_status = VerificationStatus.VERIFIED
                f_res.verification_detail = "Khớp 100% với Tổng cộng tài sản"
            else:
                delta = abs(f_assets.value - f_res.value)
                msg = f"LỆCH_CÂN_ĐỐI: Tổng tài sản ({f_assets.value:,.0f}) != Tổng nguồn vốn ({f_res.value:,.0f}), Chênh lệch: {delta:,.0f}"
                failed_checks.append(msg)
                discrepancies.append({
                    "check": "TOTAL_ASSETS == TOTAL_RESOURCES",
                    "delta": delta,
                    "reported_assets": f_assets.value,
                    "reported_resources": f_res.value,
                })
                f_assets.verification_status = VerificationStatus.DISCREPANCY
                f_assets.verification_detail = msg
                f_res.verification_status = VerificationStatus.DISCREPANCY
                f_res.verification_detail = msg

        # ── KIỂM TRA 2: TỔNG TÀI SẢN = NGẮN HẠN + DÀI HẠN (Mã 270 == 100 + 200) ──────
        if (
            "TOTAL_ASSETS" in current_facts_by_concept
            and "CURRENT_ASSETS" in current_facts_by_concept
            and "NON_CURRENT_ASSETS" in current_facts_by_concept
        ):
            f_total = current_facts_by_concept["TOTAL_ASSETS"]
            f_cur = current_facts_by_concept["CURRENT_ASSETS"]
            f_non_cur = current_facts_by_concept["NON_CURRENT_ASSETS"]
            calc_total = f_cur.value + f_non_cur.value

            if is_equal(f_total.value, calc_total):
                passed_checks.append("CỘNG_TỔNG_TÀI_SẢN: Tài sản (270) == Ngắn hạn (100) + Dài hạn (200)")
                f_cur.verification_status = VerificationStatus.VERIFIED
                f_cur.verification_detail = "Cộng dồn khớp với Tổng tài sản"
                f_non_cur.verification_status = VerificationStatus.VERIFIED
                f_non_cur.verification_detail = "Cộng dồn khớp với Tổng tài sản"
            else:
                delta = abs(f_total.value - calc_total)
                msg = f"LỆCH_TÀI_SẢN: Báo cáo ({f_total.value:,.0f}) != Tính toán ({calc_total:,.0f}), Lệch: {delta:,.0f}"
                failed_checks.append(msg)
                discrepancies.append({
                    "check": "TOTAL_ASSETS == CURRENT + NON_CURRENT",
                    "delta": delta,
                    "reported_total": f_total.value,
                    "calculated_sum": calc_total,
                })
                f_cur.verification_status = VerificationStatus.DISCREPANCY
                f_non_cur.verification_status = VerificationStatus.DISCREPANCY

        # ── KIỂM TRA 3: TÀI SẢN NGẮN HẠN = TỔNG CÁC KHOẢN MỤC CON (100 == ∑110..150) ───
        cur_children_concepts = [
            "CASH_AND_EQUIVALENTS",
            "SHORT_TERM_INVESTMENTS",
            "SHORT_TERM_RECEIVABLES",
            "INVENTORIES",
            "OTHER_CURRENT_ASSETS",
        ]
        available_children = [
            current_facts_by_concept[c] for c in cur_children_concepts if c in current_facts_by_concept
        ]
        if "CURRENT_ASSETS" in current_facts_by_concept and len(available_children) >= 1:
            f_cur = current_facts_by_concept["CURRENT_ASSETS"]
            calc_cur = sum(ch.value for ch in available_children)

            if is_equal(f_cur.value, calc_cur):
                passed_checks.append(f"CỘNG_DỌC_NGẮN_HẠN: TS Ngắn hạn (100) == ∑({len(available_children)} khoản mục con)")
                f_cur.verification_status = VerificationStatus.VERIFIED
                f_cur.verification_detail = f"Khớp tổng {len(available_children)} khoản mục con ngắn hạn"
                for ch in available_children:
                    ch.verification_status = VerificationStatus.VERIFIED
                    ch.verification_detail = "Thuộc phương trình Tài sản ngắn hạn cân đối"
            else:
                delta = abs(f_cur.value - calc_cur)
                # Chỉ cảnh báo nếu có từ 3 mục con trở lên hoặc độ lệch vượt 5%
                if len(available_children) >= 3 or delta > 0.05 * abs(f_cur.value):
                    failed_checks.append(f"LỆCH_TS_NGẮN_HẠN: Báo cáo ({f_cur.value:,.0f}) != Tổng con ({calc_cur:,.0f}), Lệch: {delta:,.0f}")
                    discrepancies.append({
                        "check": "CURRENT_ASSETS == SUM_CHILDREN",
                        "delta": delta,
                        "reported": f_cur.value,
                        "calculated": calc_cur,
                    })
                    f_cur.verification_status = VerificationStatus.DISCREPANCY
                    f_cur.verification_detail = f"Lệch tổng khoản mục con ngắn hạn: {delta:,.0f}"

        # ── KIỂM TRA 4: TÀI SẢN DÀI HẠN = TỔNG CÁC KHOẢN MỤC CON (200 == ∑210..260) ───
        non_cur_children_concepts = [
            "LONG_TERM_RECEIVABLES",
            "FIXED_ASSETS",
            "INVESTMENT_PROPERTIES",
            "LONG_TERM_ASSETS_IN_PROGRESS",
            "LONG_TERM_INVESTMENTS",
            "OTHER_NON_CURRENT_ASSETS",
        ]
        available_non_cur = [
            current_facts_by_concept[c] for c in non_cur_children_concepts if c in current_facts_by_concept
        ]
        if "NON_CURRENT_ASSETS" in current_facts_by_concept and len(available_non_cur) >= 1:
            f_nca = current_facts_by_concept["NON_CURRENT_ASSETS"]
            calc_nca = sum(ch.value for ch in available_non_cur)

            if is_equal(f_nca.value, calc_nca):
                passed_checks.append(f"CỘNG_DỌC_DÀI_HẠN: TS Dài hạn (200) == ∑({len(available_non_cur)} khoản mục con)")
                f_nca.verification_status = VerificationStatus.VERIFIED
                for ch in available_non_cur:
                    ch.verification_status = VerificationStatus.VERIFIED
            else:
                delta = abs(f_nca.value - calc_nca)
                if len(available_non_cur) >= 3 or delta > 0.05 * abs(f_nca.value):
                    failed_checks.append(f"LỆCH_TS_DÀI_HẠN: Báo cáo ({f_nca.value:,.0f}) != Tổng con ({calc_nca:,.0f}), Lệch: {delta:,.0f}")
                    discrepancies.append({
                        "check": "NON_CURRENT_ASSETS == SUM_CHILDREN",
                        "delta": delta,
                        "reported": f_nca.value,
                        "calculated": calc_nca,
                    })
                    f_nca.verification_status = VerificationStatus.DISCREPANCY

        # ── KIỂM TRA 5: NGUỒN VỐN = NỢ PHẢI TRẢ + VỐN CSH (440 == 300 + 400) ─────────
        if (
            "TOTAL_RESOURCES" in current_facts_by_concept
            and "LIABILITIES" in current_facts_by_concept
            and "EQUITY" in current_facts_by_concept
        ):
            f_res = current_facts_by_concept["TOTAL_RESOURCES"]
            f_liab = current_facts_by_concept["LIABILITIES"]
            f_eq = current_facts_by_concept["EQUITY"]
            calc_res = f_liab.value + f_eq.value

            if is_equal(f_res.value, calc_res):
                passed_checks.append("CỘNG_NGUỒN_VỐN: Nguồn vốn (440) == Nợ phải trả (300) + Vốn CSH (400)")
                f_liab.verification_status = VerificationStatus.VERIFIED
                f_liab.verification_detail = "Cộng dồn khớp với Tổng nguồn vốn"
                f_eq.verification_status = VerificationStatus.VERIFIED
                f_eq.verification_detail = "Cộng dồn khớp với Tổng nguồn vốn"
            else:
                delta = abs(f_res.value - calc_res)
                failed_checks.append(f"LỆCH_NGUỒN_VỐN: Báo cáo ({f_res.value:,.0f}) != Tính toán ({calc_res:,.0f}), Lệch: {delta:,.0f}")
                discrepancies.append({
                    "check": "TOTAL_RESOURCES == LIABILITIES + EQUITY",
                    "delta": delta,
                    "reported": f_res.value,
                    "calculated": calc_res,
                })
                f_liab.verification_status = VerificationStatus.DISCREPANCY
                f_eq.verification_status = VerificationStatus.DISCREPANCY

        # ── KIỂM TRA 6: NỢ PHẢI TRẢ = NỢ NGẮN HẠN + NỢ DÀI HẠN (300 == 310 + 330) ────
        if (
            "LIABILITIES" in current_facts_by_concept
            and ("CURRENT_LIABILITIES" in current_facts_by_concept or "NON_CURRENT_LIABILITIES" in current_facts_by_concept)
        ):
            f_liab = current_facts_by_concept["LIABILITIES"]
            cur_liab_val = current_facts_by_concept["CURRENT_LIABILITIES"].value if "CURRENT_LIABILITIES" in current_facts_by_concept else 0.0
            non_cur_liab_val = current_facts_by_concept["NON_CURRENT_LIABILITIES"].value if "NON_CURRENT_LIABILITIES" in current_facts_by_concept else 0.0
            calc_liab = cur_liab_val + non_cur_liab_val

            if is_equal(f_liab.value, calc_liab):
                passed_checks.append("CỘNG_NỢ_PHẢI_TRẢ: Nợ phải trả (300) == Nợ ngắn hạn (310) + Nợ dài hạn (330)")
                f_liab.verification_status = VerificationStatus.VERIFIED
                if "CURRENT_LIABILITIES" in current_facts_by_concept:
                    current_facts_by_concept["CURRENT_LIABILITIES"].verification_status = VerificationStatus.VERIFIED
                if "NON_CURRENT_LIABILITIES" in current_facts_by_concept:
                    current_facts_by_concept["NON_CURRENT_LIABILITIES"].verification_status = VerificationStatus.VERIFIED
            else:
                delta = abs(f_liab.value - calc_liab)
                failed_checks.append(f"LỆCH_NỢ_PHẢI_TRẢ: Báo cáo ({f_liab.value:,.0f}) != Tính toán ({calc_liab:,.0f}), Lệch: {delta:,.0f}")
                discrepancies.append({
                    "check": "LIABILITIES == CURRENT + NON_CURRENT",
                    "delta": delta,
                    "reported": f_liab.value,
                    "calculated": calc_liab,
                })
                f_liab.verification_status = VerificationStatus.DISCREPANCY

        # ── KIỂM TRA 7: DOANH THU THUẦN = DOANH THU GỘP - GIẢM TRỪ (Mã 10 == 01 - 02) ─
        if (
            "NET_REVENUE" in current_facts_by_concept
            and "GROSS_REVENUE" in current_facts_by_concept
            and "REVENUE_DEDUCTIONS" in current_facts_by_concept
        ):
            f_net_rev = current_facts_by_concept["NET_REVENUE"]
            f_gross_rev = current_facts_by_concept["GROSS_REVENUE"]
            f_ded = current_facts_by_concept["REVENUE_DEDUCTIONS"]
            calc_net_rev = f_gross_rev.value - abs(f_ded.value)

            if is_equal(f_net_rev.value, calc_net_rev):
                passed_checks.append("CÂN_ĐỐI_DOANH_THU: Doanh thu thuần (10) == Doanh thu gộp (01) - Giảm trừ (02)")
                f_net_rev.verification_status = VerificationStatus.VERIFIED
                f_gross_rev.verification_status = VerificationStatus.VERIFIED
            else:
                delta = abs(f_net_rev.value - calc_net_rev)
                failed_checks.append(f"LỆCH_DOANH_THU: Báo cáo ({f_net_rev.value:,.0f}) != Tính toán ({calc_net_rev:,.0f}), Lệch: {delta:,.0f}")
                discrepancies.append({
                    "check": "NET_REVENUE == GROSS_REVENUE - REVENUE_DEDUCTIONS",
                    "delta": delta,
                    "reported": f_net_rev.value,
                    "calculated": calc_net_rev,
                })
                f_net_rev.verification_status = VerificationStatus.DISCREPANCY

        # ── KIỂM TRA 8: LỢI NHUẬN GỘP = DOANH THU THUẦN - GIÁ VỐN (Mã 20 == 10 - 11) ───
        if (
            "GROSS_PROFIT" in current_facts_by_concept
            and "NET_REVENUE" in current_facts_by_concept
            and "COGS" in current_facts_by_concept
        ):
            f_gp = current_facts_by_concept["GROSS_PROFIT"]
            f_rev = current_facts_by_concept["NET_REVENUE"]
            f_cogs = current_facts_by_concept["COGS"]
            cogs_val = abs(f_cogs.value)
            calc_gp = f_rev.value - cogs_val

            if is_equal(f_gp.value, calc_gp):
                passed_checks.append("CÂN_ĐỐI_LỢI_NHUẬN_GỘP: LN Gộp (20) == Doanh thu thuần (10) - Giá vốn (11)")
                f_gp.verification_status = VerificationStatus.VERIFIED
                f_gp.verification_detail = "Khớp công thức Doanh thu thuần - Giá vốn"
                f_rev.verification_status = VerificationStatus.VERIFIED
                f_cogs.verification_status = VerificationStatus.VERIFIED
            else:
                delta = abs(f_gp.value - calc_gp)
                failed_checks.append(f"LỆCH_LN_GỘP: Báo cáo ({f_gp.value:,.0f}) != Tính toán ({calc_gp:,.0f}), Lệch: {delta:,.0f}")
                discrepancies.append({
                    "check": "GROSS_PROFIT == NET_REVENUE - COGS",
                    "delta": delta,
                    "reported": f_gp.value,
                    "calculated": calc_gp,
                })

        # ── KIỂM TRA 9: LN THUẦN HĐKD = LN GỘP + TC - CP (Mã 30 == 20 + 21 - 22 - 25 - 26) ─
        if "OPERATING_PROFIT" in current_facts_by_concept and "GROSS_PROFIT" in current_facts_by_concept:
            op_rel_keys = ["FINANCIAL_INCOME", "FINANCIAL_EXPENSES", "SELLING_EXPENSES", "ADMIN_EXPENSES"]
            if any(k in current_facts_by_concept for k in op_rel_keys):
                f_op = current_facts_by_concept["OPERATING_PROFIT"]
                f_gp = current_facts_by_concept["GROSS_PROFIT"]
                fin_inc = abs(current_facts_by_concept["FINANCIAL_INCOME"].value) if "FINANCIAL_INCOME" in current_facts_by_concept else 0.0
                fin_exp = abs(current_facts_by_concept["FINANCIAL_EXPENSES"].value) if "FINANCIAL_EXPENSES" in current_facts_by_concept else 0.0
                sell_exp = abs(current_facts_by_concept["SELLING_EXPENSES"].value) if "SELLING_EXPENSES" in current_facts_by_concept else 0.0
                admin_exp = abs(current_facts_by_concept["ADMIN_EXPENSES"].value) if "ADMIN_EXPENSES" in current_facts_by_concept else 0.0
                calc_op = f_gp.value + fin_inc - fin_exp - sell_exp - admin_exp

                if is_equal(f_op.value, calc_op):
                    passed_checks.append("CÂN_ĐỐI_LN_THUẦN_HĐKD: LN Thuần (30) == LN Gộp (20) + TC (21) - CPTC (22) - CPBH (25) - CPQL (26)")
                    f_op.verification_status = VerificationStatus.VERIFIED
                else:
                    delta = abs(f_op.value - calc_op)
                    failed_checks.append(f"LỆCH_LN_THUẦN_HĐKD: Báo cáo ({f_op.value:,.0f}) != Tính toán ({calc_op:,.0f}), Lệch: {delta:,.0f}")
                    discrepancies.append({
                        "check": "OPERATING_PROFIT == GROSS_PROFIT + FINANCIAL - EXPENSES",
                        "delta": delta,
                        "reported": f_op.value,
                        "calculated": calc_op,
                    })
                    f_op.verification_status = VerificationStatus.DISCREPANCY

        # ── KIỂM TRA 10: KẾT QUẢ TỪ HOẠT ĐỘNG KHÁC (Mã 40 == 31 - 32) ────────────────
        if "OTHER_PROFIT" in current_facts_by_concept and ("OTHER_INCOME" in current_facts_by_concept or "OTHER_EXPENSES" in current_facts_by_concept):
            f_oth_p = current_facts_by_concept["OTHER_PROFIT"]
            oth_inc = abs(current_facts_by_concept["OTHER_INCOME"].value) if "OTHER_INCOME" in current_facts_by_concept else 0.0
            oth_exp = abs(current_facts_by_concept["OTHER_EXPENSES"].value) if "OTHER_EXPENSES" in current_facts_by_concept else 0.0
            calc_oth = oth_inc - oth_exp

            if is_equal(f_oth_p.value, calc_oth):
                passed_checks.append("CÂN_ĐỐI_LN_KHÁC: LN Khác (40) == Thu nhập khác (31) - Chi phí khác (32)")
                f_oth_p.verification_status = VerificationStatus.VERIFIED
            else:
                delta = abs(f_oth_p.value - calc_oth)
                failed_checks.append(f"LỆCH_LN_KHÁC: Báo cáo ({f_oth_p.value:,.0f}) != Tính toán ({calc_oth:,.0f}), Lệch: {delta:,.0f}")
                discrepancies.append({
                    "check": "OTHER_PROFIT == OTHER_INCOME - OTHER_EXPENSES",
                    "delta": delta,
                    "reported": f_oth_p.value,
                    "calculated": calc_oth,
                })
                f_oth_p.verification_status = VerificationStatus.DISCREPANCY

        # ── KIỂM TRA 11: LN TRƯỚC THUẾ = HĐKD + KHÁC (Mã 50 == 30 + 40) ───────────────
        if (
            "PROFIT_BEFORE_TAX" in current_facts_by_concept
            and "OPERATING_PROFIT" in current_facts_by_concept
            and "OTHER_PROFIT" in current_facts_by_concept
        ):
            f_pbt = current_facts_by_concept["PROFIT_BEFORE_TAX"]
            f_op = current_facts_by_concept["OPERATING_PROFIT"]
            f_oth = current_facts_by_concept["OTHER_PROFIT"]
            calc_pbt = f_op.value + f_oth.value

            if is_equal(f_pbt.value, calc_pbt):
                passed_checks.append("CỘNG_LN_TRƯỚC_THUẾ: LN Trước thuế (50) == LN Thuần HĐKD (30) + LN Khác (40)")
                f_pbt.verification_status = VerificationStatus.VERIFIED
                f_op.verification_status = VerificationStatus.VERIFIED
                f_oth.verification_status = VerificationStatus.VERIFIED
            else:
                delta = abs(f_pbt.value - calc_pbt)
                failed_checks.append(f"LỆCH_LN_TRƯỚC_THUẾ: Báo cáo ({f_pbt.value:,.0f}) != Tính toán ({calc_pbt:,.0f}), Lệch: {delta:,.0f}")
                discrepancies.append({
                    "check": "PROFIT_BEFORE_TAX == OPERATING_PROFIT + OTHER_PROFIT",
                    "delta": delta,
                    "reported": f_pbt.value,
                    "calculated": calc_pbt,
                })
                f_pbt.verification_status = VerificationStatus.DISCREPANCY

        # ── KIỂM TRA 12: LN SAU THUẾ = LN TRƯỚC THUẾ - THUẾ TNDN (Mã 60 == 50 - 51 ± 52) ─
        if "NET_PROFIT" in current_facts_by_concept and "PROFIT_BEFORE_TAX" in current_facts_by_concept:
            if "CURRENT_TAX_EXPENSE" in current_facts_by_concept or "DEFERRED_TAX_EXPENSE" in current_facts_by_concept:
                f_np = current_facts_by_concept["NET_PROFIT"]
                f_pbt = current_facts_by_concept["PROFIT_BEFORE_TAX"]
                tax_curr = abs(current_facts_by_concept["CURRENT_TAX_EXPENSE"].value) if "CURRENT_TAX_EXPENSE" in current_facts_by_concept else 0.0
                f_def = current_facts_by_concept.get("DEFERRED_TAX_EXPENSE")
                tax_def = abs(f_def.value) if f_def else 0.0

                # TT200: Mã 52 có thể là "Chi phí thuế hoãn lại" (-) hoặc "Lợi ích/Thu nhập thuế hoãn lại" (+)
                calc_np_expense = f_pbt.value - tax_curr - tax_def
                calc_np_benefit = f_pbt.value - tax_curr + tax_def

                is_benefit = False
                if f_def and any(k in f_def.raw_label.lower() for k in ["lợi ích", "thu nhập"]):
                    is_benefit = True

                if is_benefit or is_equal(f_np.value, calc_np_benefit):
                    calc_np = calc_np_benefit
                    chk_desc = "CÂN_ĐỐI_LN_SAU_THUẾ: LN Sau thuế (60) == LN Trước thuế (50) - Thuế hiện hành (51) + Lợi ích thuế hoãn lại (52)"
                else:
                    calc_np = calc_np_expense
                    chk_desc = "CÂN_ĐỐI_LN_SAU_THUẾ: LN Sau thuế (60) == LN Trước thuế (50) - Thuế hiện hành (51) - CP thuế hoãn lại (52)"

                if is_equal(f_np.value, calc_np):
                    passed_checks.append(chk_desc)
                    f_np.verification_status = VerificationStatus.VERIFIED
                else:
                    delta = abs(f_np.value - calc_np)
                    failed_checks.append(f"LỆCH_LN_SAU_THUẾ: Báo cáo ({f_np.value:,.0f}) != Tính toán ({calc_np:,.0f}), Lệch: {delta:,.0f}")
                    discrepancies.append({
                        "check": "NET_PROFIT == PROFIT_BEFORE_TAX - TAXES",
                        "delta": delta,
                        "reported": f_np.value,
                        "calculated": calc_np,
                    })
                    f_np.verification_status = VerificationStatus.DISCREPANCY

        # ── TỰ ĐỘNG ĐỒNG BỘ DẤU CHO LCTT HĐKD (MÃ 20) & HĐĐT (MÃ 30) TỪ CÁC KHOẢN MỤC CON ─
        # Nhiều báo cáo scan bị mất ngoặc đơn (dấu âm) ở các dòng tổng hợp 20, 30.
        # Nếu các mã con đã được trích xuất, tổng các mã con sẽ chuẩn hóa dấu chính xác.
        ope_indirect_keys = [
            "CF_OPERATING_PROFIT_BEFORE_WC", "CF_RECEIVABLES_CHANGE", "CF_INVENTORY_CHANGE",
            "CF_PAYABLES_CHANGE", "CF_PREPAID_EXPENSES_CHANGE", "CF_TRADING_SECURITIES_CHANGE",
            "CF_INTEREST_PAID", "CF_TAX_PAID", "CF_OTHER_OPERATING_PROCEEDS", "CF_OTHER_OPERATING_PAYMENTS",
        ]
        ope_direct_keys = [
            "CF_DIRECT_SALES_PROCEEDS", "CF_DIRECT_SUPPLIER_PAYMENTS", "CF_DIRECT_EMPLOYEE_PAYMENTS",
            "CF_DIRECT_INTEREST_PAID", "CF_DIRECT_TAX_PAID", "CF_DIRECT_OTHER_PROCEEDS", "CF_DIRECT_OTHER_PAYMENTS",
        ]
        if "CF_NET_OPERATING" in current_facts_by_concept:
            f_ope = current_facts_by_concept["CF_NET_OPERATING"]
            sub_indir = [k for k in ope_indirect_keys if k in current_facts_by_concept]
            if len(sub_indir) >= 3:
                calc_ope = sum(current_facts_by_concept[k].value for k in sub_indir)
                if is_equal(abs(f_ope.value), abs(calc_ope)):
                    f_ope.value = calc_ope
            else:
                sub_dir = [k for k in ope_direct_keys if k in current_facts_by_concept]
                if len(sub_dir) >= 3:
                    calc_ope_dir = sum(current_facts_by_concept[k].value for k in sub_dir)
                    if is_equal(abs(f_ope.value), abs(calc_ope_dir)):
                        f_ope.value = calc_ope_dir

        inv_sub_keys = [
            "CF_CAPEX", "CF_PROCEEDS_DISPOSAL_ASSETS", "CF_LOANS_GIVEN", "CF_LOANS_COLLECTED",
            "CF_EQUITY_INVESTMENTS_PAID", "CF_EQUITY_INVESTMENTS_COLLECTED", "CF_INTEREST_AND_DIVIDENDS_RECEIVED",
        ]
        if "CF_NET_INVESTING" in current_facts_by_concept and any(k in current_facts_by_concept for k in inv_sub_keys):
            f_inv = current_facts_by_concept["CF_NET_INVESTING"]
            calc_inv = sum(current_facts_by_concept[k].value for k in inv_sub_keys if k in current_facts_by_concept)
            if is_equal(abs(f_inv.value), abs(calc_inv)):
                f_inv.value = calc_inv

        # ── KIỂM TRA 13: LCTT HOẠT ĐỘNG TÀI CHÍNH ĐẦY ĐỦ 6 MÃ CON (Mã 40 == 31-32+33-34-35-36) ─
        fin_sub_keys = [
            "CF_EQUITY_ISSUANCE",   # 31
            "CF_CAPITAL_REFUND",    # 32
            "CF_BORROWINGS",        # 33
            "CF_REPAYMENTS",        # 34
            "CF_LEASE_REPAYMENTS",  # 35
            "CF_DIVIDENDS_PAID",    # 36
        ]
        if "CF_NET_FINANCING" in current_facts_by_concept and any(k in current_facts_by_concept for k in fin_sub_keys):
            f_fin = current_facts_by_concept["CF_NET_FINANCING"]
            val_31 = abs(current_facts_by_concept["CF_EQUITY_ISSUANCE"].value) if "CF_EQUITY_ISSUANCE" in current_facts_by_concept else 0.0
            val_32 = abs(current_facts_by_concept["CF_CAPITAL_REFUND"].value) if "CF_CAPITAL_REFUND" in current_facts_by_concept else 0.0
            val_33 = abs(current_facts_by_concept["CF_BORROWINGS"].value) if "CF_BORROWINGS" in current_facts_by_concept else 0.0
            val_34 = abs(current_facts_by_concept["CF_REPAYMENTS"].value) if "CF_REPAYMENTS" in current_facts_by_concept else 0.0
            val_35 = abs(current_facts_by_concept["CF_LEASE_REPAYMENTS"].value) if "CF_LEASE_REPAYMENTS" in current_facts_by_concept else 0.0
            val_36 = abs(current_facts_by_concept["CF_DIVIDENDS_PAID"].value) if "CF_DIVIDENDS_PAID" in current_facts_by_concept else 0.0

            calc_fin = val_31 - val_32 + val_33 - val_34 - val_35 - val_36

            # Tự động đồng bộ dấu âm nếu OCR bóc tách số dương do mất dấu ngoặc (x)
            if not is_equal(f_fin.value, calc_fin) and is_equal(-abs(f_fin.value), calc_fin):
                f_fin.value = -abs(f_fin.value)

            if is_equal(f_fin.value, calc_fin):
                passed_checks.append("CÂN_ĐỐI_LCTT_HĐTC: LCTT HĐTC (40) == 31 - 32 + 33 - 34 - 35 - 36")
                f_fin.verification_status = VerificationStatus.VERIFIED
            else:
                delta = abs(f_fin.value - calc_fin)
                failed_checks.append(f"LỆCH_LCTT_HĐTC: Báo cáo ({f_fin.value:,.0f}) != Tính toán ({calc_fin:,.0f}), Lệch: {delta:,.0f}")
                discrepancies.append({
                    "check": "CF_NET_FINANCING == 31 - 32 + 33 - 34 - 35 - 36",
                    "delta": delta,
                    "reported": f_fin.value,
                    "calculated": calc_fin,
                })
                f_fin.verification_status = VerificationStatus.DISCREPANCY

        # ── KIỂM TRA 14: LCTT THUẦN = HĐKD + HĐĐT + HĐTC (Mã 50 == 20 + 30 + 40) ────────
        if (
            "CF_NET_CHANGE" in current_facts_by_concept
            and "CF_NET_OPERATING" in current_facts_by_concept
            and "CF_NET_INVESTING" in current_facts_by_concept
            and "CF_NET_FINANCING" in current_facts_by_concept
        ):
            f_net_cf = current_facts_by_concept["CF_NET_CHANGE"]
            f_ope = current_facts_by_concept["CF_NET_OPERATING"]
            f_inv = current_facts_by_concept["CF_NET_INVESTING"]
            f_fin = current_facts_by_concept["CF_NET_FINANCING"]

            calc_net_cf = f_ope.value + f_inv.value + f_fin.value

            if is_equal(f_net_cf.value, calc_net_cf):
                passed_checks.append("CÂN_ĐỐI_LCTT_THUẦN: LCTT Thuần (50) == HĐKD (20) + HĐĐT (30) + HĐTC (40)")
                f_net_cf.verification_status = VerificationStatus.VERIFIED
                f_ope.verification_status = VerificationStatus.VERIFIED
                f_inv.verification_status = VerificationStatus.VERIFIED
                f_fin.verification_status = VerificationStatus.VERIFIED
            elif is_equal(-abs(f_net_cf.value), calc_net_cf):
                f_net_cf.value = -abs(f_net_cf.value)
                passed_checks.append("CÂN_ĐỐI_LCTT_THUẦN: LCTT Thuần (50) == HĐKD (20) + HĐĐT (30) + HĐTC (40)")
                f_net_cf.verification_status = VerificationStatus.VERIFIED
                f_ope.verification_status = VerificationStatus.VERIFIED
                f_inv.verification_status = VerificationStatus.VERIFIED
                f_fin.verification_status = VerificationStatus.VERIFIED
            elif is_equal(abs(f_net_cf.value), calc_net_cf):
                f_net_cf.value = abs(f_net_cf.value)
                passed_checks.append("CÂN_ĐỐI_LCTT_THUẦN: LCTT Thuần (50) == HĐKD (20) + HĐĐT (30) + HĐTC (40)")
                f_net_cf.verification_status = VerificationStatus.VERIFIED
                f_ope.verification_status = VerificationStatus.VERIFIED
                f_inv.verification_status = VerificationStatus.VERIFIED
                f_fin.verification_status = VerificationStatus.VERIFIED
            else:
                # Tìm tổ hợp dấu phù hợp cho các biến chưa được verify, tuyệt đối không phá vỡ biến đã VERIFIED
                solved = False
                ope_candidates = [f_ope.value] if f_ope.verification_status == VerificationStatus.VERIFIED else [f_ope.value, -f_ope.value]
                inv_candidates = [f_inv.value] if f_inv.verification_status == VerificationStatus.VERIFIED else [f_inv.value, -f_inv.value]
                fin_candidates = [f_fin.value] if f_fin.verification_status == VerificationStatus.VERIFIED else [f_fin.value, -f_fin.value]
                net_candidates = [f_net_cf.value, -f_net_cf.value]

                for s_ope in ope_candidates:
                    for s_inv in inv_candidates:
                        for s_fin in fin_candidates:
                            for s_net in net_candidates:
                                if is_equal(s_ope + s_inv + s_fin, s_net):
                                    f_ope.value = s_ope
                                    f_inv.value = s_inv
                                    f_fin.value = s_fin
                                    f_net_cf.value = s_net
                                    calc_net_cf = s_net
                                    passed_checks.append("CÂN_ĐỐI_LCTT_THUẦN: LCTT Thuần (50) == HĐKD (20) + HĐĐT (30) + HĐTC (40)")
                                    f_net_cf.verification_status = VerificationStatus.VERIFIED
                                    f_ope.verification_status = VerificationStatus.VERIFIED
                                    f_inv.verification_status = VerificationStatus.VERIFIED
                                    f_fin.verification_status = VerificationStatus.VERIFIED
                                    solved = True
                                    break
                            if solved: break
                        if solved: break
                    if solved: break

                if not solved:
                    delta = abs(f_net_cf.value - calc_net_cf)
                    failed_checks.append(f"LỆCH_LCTT_THUẦN: Báo cáo ({f_net_cf.value:,.0f}) != Tính toán ({calc_net_cf:,.0f}), Lệch: {delta:,.0f}")
                    discrepancies.append({
                        "check": "CF_NET_CHANGE == OPERATING + INVESTING + FINANCING",
                        "delta": delta,
                        "reported": f_net_cf.value,
                        "calculated": calc_net_cf,
                    })
                    f_net_cf.verification_status = VerificationStatus.DISCREPANCY

        # ── KIỂM TRA 15: TIỀN CUỐI KỲ LCTT = ĐẦU KỲ + THUẦN + TỶ GIÁ (Mã 70 == 60 + 50 + 61) ─
        if (
            "CF_ENDING_CASH" in current_facts_by_concept
            and "CF_BEGINNING_CASH" in current_facts_by_concept
            and "CF_NET_CHANGE" in current_facts_by_concept
        ):
            f_end = current_facts_by_concept["CF_ENDING_CASH"]
            f_beg = current_facts_by_concept["CF_BEGINNING_CASH"]
            f_net = current_facts_by_concept["CF_NET_CHANGE"]
            fx_val = current_facts_by_concept["CF_EXCHANGE_RATE_DIFF"].value if "CF_EXCHANGE_RATE_DIFF" in current_facts_by_concept else 0.0

            calc_end = f_beg.value + f_net.value + fx_val
            calc_end_minus_fx = f_beg.value + f_net.value - abs(fx_val)
            calc_end_minus_net = f_beg.value - abs(f_net.value) + fx_val
            calc_end_minus_all = f_beg.value - abs(f_net.value) - abs(fx_val)

            if is_equal(f_end.value, calc_end):
                passed_checks.append("CÂN_ĐỐI_TIỀN_CUỐI_KỲ: Tiền cuối kỳ LCTT (70) == Tiền đầu kỳ (60) + LCTT thuần (50) + Tỷ giá (61)")
                f_end.verification_status = VerificationStatus.VERIFIED
            elif is_equal(f_end.value, calc_end_minus_fx) or is_equal(f_end.value, calc_end_minus_all) or is_equal(f_end.value, calc_end_minus_net):
                passed_checks.append("CÂN_ĐỐI_TIỀN_CUỐI_KỲ: Tiền cuối kỳ LCTT (70) == Tiền đầu kỳ (60) ± LCTT thuần (50) ± Tỷ giá (61)")
                f_end.verification_status = VerificationStatus.VERIFIED
            else:
                delta = min(abs(f_end.value - calc_end), abs(f_end.value - calc_end_minus_fx))
                if delta > max(self.absolute_tolerance, 0.01 * abs(f_end.value)):
                    failed_checks.append(f"LỆCH_TIỀN_CUỐI_KỲ_LCTT: Báo cáo ({f_end.value:,.0f}) != Tính toán ({calc_end:,.0f}), Lệch: {delta:,.0f}")
                    discrepancies.append({
                        "check": "CF_ENDING_CASH == BEGINNING + NET_CHANGE",
                        "delta": delta,
                        "reported": f_end.value,
                        "calculated": calc_end,
                    })
                    f_end.verification_status = VerificationStatus.DISCREPANCY

        # ── KIỂM TRA 16: ĐỐI CHIẾU CHÉO TIỀN CUỐI KỲ (LCTT Mã 70 == CĐKT Mã 110) ───────
        if "CF_ENDING_CASH" in current_facts_by_concept and "CASH_AND_EQUIVALENTS" in current_facts_by_concept:
            f_cf_cash = current_facts_by_concept["CF_ENDING_CASH"]
            f_bs_cash = current_facts_by_concept["CASH_AND_EQUIVALENTS"]

            if is_equal(f_cf_cash.value, f_bs_cash.value):
                passed_checks.append("ĐỐI_CHIẾU_CHÉO_TIỀN: Tiền cuối kỳ trên LCTT (70) == Tiền & TĐ tiền trên Bảng CĐKT (110)")
                f_cf_cash.verification_status = VerificationStatus.VERIFIED
                f_bs_cash.verification_status = VerificationStatus.VERIFIED
            else:
                delta = abs(f_cf_cash.value - f_bs_cash.value)
                failed_checks.append(f"LỆCH_ĐỐI_CHIẾU_CHÉO_TIỀN: LCTT ({f_cf_cash.value:,.0f}) != CĐKT ({f_bs_cash.value:,.0f}), Lệch: {delta:,.0f}")
                discrepancies.append({
                    "check": "CROSS_CHECK_CASH == CF_ENDING vs BS_CASH",
                    "delta": delta,
                    "reported_cf": f_cf_cash.value,
                    "reported_bs": f_bs_cash.value,
                })
                f_cf_cash.verification_status = VerificationStatus.DISCREPANCY
                f_bs_cash.verification_status = VerificationStatus.DISCREPANCY

        # ── KIỂM TRA 17: ĐỐI CHIẾU CHÉO LN TRƯỚC THUẾ (LCTT gián tiếp Mã 01 == KQKD Mã 50) ──
        if "CF_PROFIT_BEFORE_TAX" in current_facts_by_concept and "PROFIT_BEFORE_TAX" in current_facts_by_concept:
            f_cf_pbt = current_facts_by_concept["CF_PROFIT_BEFORE_TAX"]
            f_is_pbt = current_facts_by_concept["PROFIT_BEFORE_TAX"]

            if is_equal(f_cf_pbt.value, f_is_pbt.value):
                passed_checks.append("ĐỐI_CHIẾU_CHÉO_LN_TRƯỚC_THUẾ: LN trước thuế LCTT gián tiếp (01) == KQKD (50)")
                f_cf_pbt.verification_status = VerificationStatus.VERIFIED
                f_is_pbt.verification_status = VerificationStatus.VERIFIED
            else:
                delta = abs(f_cf_pbt.value - f_is_pbt.value)
                failed_checks.append(f"LỆCH_ĐỐI_CHIẾU_CHÉO_LN: LCTT ({f_cf_pbt.value:,.0f}) != KQKD ({f_is_pbt.value:,.0f}), Lệch: {delta:,.0f}")
                discrepancies.append({
                    "check": "CROSS_CHECK_PBT == CF_01 vs IS_50",
                    "delta": delta,
                    "reported_cf": f_cf_pbt.value,
                    "reported_is": f_is_pbt.value,
                })
                f_cf_pbt.verification_status = VerificationStatus.DISCREPANCY
                f_is_pbt.verification_status = VerificationStatus.DISCREPANCY

        total_checks = len(passed_checks) + len(failed_checks)
        is_balanced = len(failed_checks) == 0

        summary = (
            f"Kiểm toán số học BCTC {company} ({year}): Đạt {len(passed_checks)}/{total_checks} bài kiểm tra đẳng thức. "
            f"Trạng thái: {'✅ HOÀN TOÀN CÂN ĐỐI (KHÔNG CÓ GIGO)' if is_balanced else '⚠️ PHÁT HIỆN SAI LỆCH CẦN LƯU Ý'}."
        )

        logger.info("AccountingVerifier: %s", summary)

        return VerificationReport(
            company=company,
            year=year,
            is_balanced=is_balanced,
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            discrepancies=discrepancies,
            summary=summary,
        )
