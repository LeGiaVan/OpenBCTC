"""
metrics.py — Tập hợp các metrics chuẩn xác để đánh giá cấu trúc bảng tài chính.

Gồm 4 thành phần cốt lõi:
1. Row/Column Count Accuracy (Kiểm tra kích thước logic)
2. Span IoU (Đánh giá mức độ nhận diện đúng ô gộp / merged cells)
3. TEDS-Struct (Tree Edit Distance-based Similarity - Chuẩn học thuật)
4. Error Taxonomy Classifier (Tự động gắn nhãn nguyên nhân gây lỗi)
"""

from __future__ import annotations

from collections import Counter
from typing import Any
from bs4 import BeautifulSoup, Tag


def count_accuracy(pred: dict[str, Any], gt: dict[str, Any]) -> dict[str, Any]:
    """
    Đo độ khớp số lượng hàng và cột giữa bảng dự đoán và ground truth.
    """
    row_match = pred["n_rows"] == gt["n_rows"]
    col_match = pred["n_cols"] == gt["n_cols"]
    row_diff = abs(pred["n_rows"] - gt["n_rows"])
    col_diff = abs(pred["n_cols"] - gt["n_cols"])
    return {
        "row_exact_match": bool(row_match),
        "col_exact_match": bool(col_match),
        "exact_grid_match": bool(row_match and col_match),
        "row_diff": int(row_diff),
        "col_diff": int(col_diff),
    }


def span_iou(
    pred_spans: list[list[int]],
    gt_spans: list[list[int]],
    iou_threshold: float = 0.5,
) -> dict[str, float]:
    """
    Đo độ khớp các vùng ô gộp (merged cells) bằng chỉ số IoU 2D trên tọa độ (r1, c1, r2, c2).
    """
    def _area(span: list[int]) -> int:
        r1, c1, r2, c2 = span
        return (r2 - r1 + 1) * (c2 - c1 + 1)

    def _overlap(s1: list[int], s2: list[int]) -> int:
        r1 = max(s1[0], s2[0])
        c1 = max(s1[1], s2[1])
        r2 = min(s1[2], s2[2])
        c2 = min(s1[3], s2[3])
        if r1 > r2 or c1 > c2:
            return 0
        return (r2 - r1 + 1) * (c2 - c1 + 1)

    # Nếu cả hai đều không có ô gộp -> độ khớp hoàn hảo 100%
    if not pred_spans and not gt_spans:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 0, "fp": 0, "fn": 0}

    matched_gt: set[int] = set()
    tp = 0

    for p in pred_spans:
        for i, g in enumerate(gt_spans):
            if i in matched_gt:
                continue
            inter = _overlap(p, g)
            union = _area(p) + _area(g) - inter
            if union > 0 and (inter / union) >= iou_threshold:
                tp += 1
                matched_gt.add(i)
                break

    precision = tp / len(pred_spans) if pred_spans else (1.0 if not gt_spans else 0.0)
    recall = tp / len(gt_spans) if gt_spans else (1.0 if not pred_spans else 0.0)
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": len(pred_spans) - tp,
        "fn": len(gt_spans) - tp,
    }


# =========================================================================
# TEDS-Struct (Tree Edit Distance-based Similarity) thuần Python (Zhang-Shasha)
# =========================================================================

class TreeNode:
    def __init__(self, label: str):
        self.label = label
        self.children: list[TreeNode] = []


def _html_to_tree(html_str: str) -> TreeNode:
    """Chuyển đổi cây HTML sang TreeNode chỉ chứa thẻ và thuộc tính cấu trúc (rowspan, colspan)."""
    soup = BeautifulSoup(html_str, "html.parser")
    table = soup.find("table")
    if not table:
        return TreeNode("table")

    def _build(tag: Tag) -> TreeNode:
        attrs = []
        if tag.get("rowspan") and int(tag.get("rowspan", 1)) > 1:
            attrs.append(f"rowspan={tag['rowspan']}")
        if tag.get("colspan") and int(tag.get("colspan", 1)) > 1:
            attrs.append(f"colspan={tag['colspan']}")
        attr_str = f"[{','.join(attrs)}]" if attrs else ""
        node = TreeNode(f"{tag.name}{attr_str}")
        for child in tag.find_all(recursive=False):
            if isinstance(child, Tag) and child.name in ("thead", "tbody", "tfoot", "tr", "th", "td"):
                node.children.append(_build(child))
        return node

    return _build(table)


class ZhangShasha:
    """Thuật toán Zhang-Shasha tính khoảng cách chỉnh sửa giữa 2 cây có thứ tự."""
    def __init__(self, tree1: TreeNode, tree2: TreeNode):
        self.t1_nodes, self.t1_lld = self._postorder(tree1)
        self.t2_nodes, self.t2_lld = self._postorder(tree2)
        self.kr1 = self._keyroots(self.t1_lld)
        self.kr2 = self._keyroots(self.t2_lld)

    def _postorder(self, root: TreeNode) -> tuple[list[str], list[int]]:
        labels: list[str] = []
        lld: list[int] = []

        def traverse(node: TreeNode) -> int:
            first_leaf = None
            for child in node.children:
                leaf = traverse(child)
                if first_leaf is None:
                    first_leaf = leaf
            idx = len(labels)
            labels.append(node.label)
            my_leaf = first_leaf if first_leaf is not None else idx
            lld.append(my_leaf)
            return my_leaf

        traverse(root)
        return labels, lld

    def _keyroots(self, lld: list[int]) -> list[int]:
        seen = set()
        krs = []
        for i in range(len(lld) - 1, -1, -1):
            if lld[i] not in seen:
                krs.append(i)
                seen.add(lld[i])
        return sorted(krs)

    def distance(self) -> int:
        n = len(self.t1_nodes)
        m = len(self.t2_nodes)
        if n == 0:
            return m
        if m == 0:
            return n

        treedist: dict[tuple[int, int], int] = {}
        for i in self.kr1:
            for j in self.kr2:
                self._forest_dist(i, j, treedist)
        return treedist.get((n - 1, m - 1), max(n, m))

    def _forest_dist(self, i: int, j: int, treedist: dict[tuple[int, int], int]) -> None:
        li = self.t1_lld[i]
        lj = self.t2_lld[j]
        fdist: dict[tuple[int, int], int] = {(li - 1, lj - 1): 0}

        for di in range(li, i + 1):
            fdist[(di, lj - 1)] = fdist[(di - 1, lj - 1)] + 1
        for dj in range(lj, j + 1):
            fdist[(li - 1, dj)] = fdist[(li - 1, dj - 1)] + 1

        for di in range(li, i + 1):
            for dj in range(lj, j + 1):
                cost = 0 if self.t1_nodes[di] == self.t2_nodes[dj] else 1
                if self.t1_lld[di] == li and self.t2_lld[dj] == lj:
                    fdist[(di, dj)] = min(
                        fdist[(di - 1, dj)] + 1,
                        fdist[(di, dj - 1)] + 1,
                        fdist[(di - 1, dj - 1)] + cost,
                    )
                    treedist[(di, dj)] = fdist[(di, dj)]
                else:
                    fdist[(di, dj)] = min(
                        fdist[(di - 1, dj)] + 1,
                        fdist[(di, dj - 1)] + 1,
                        fdist[(self.t1_lld[di] - 1, self.t2_lld[dj] - 1)] + treedist.get((di, dj), cost),
                    )


def compute_teds_struct(pred_html: str, gt_html: str) -> float:
    """
    Tính chỉ số TEDS-Struct (Tree Edit Distance-based Similarity).
    Thang điểm: 0.0 -> 1.0 (1.0 = cấu trúc hoàn toàn trùng khớp).
    """
    t1 = _html_to_tree(pred_html)
    t2 = _html_to_tree(gt_html)
    zs = ZhangShasha(t1, t2)
    dist = zs.distance()
    max_nodes = max(len(zs.t1_nodes), len(zs.t2_nodes))
    if max_nodes == 0:
        return 1.0
    score = 1.0 - (dist / max_nodes)
    return round(max(0.0, score), 4)


# =========================================================================
# Error Taxonomy (Bộ phân loại nguyên nhân lỗi)
# =========================================================================

def classify_table_error(
    pred: dict[str, Any],
    gt: dict[str, Any],
    span_result: dict[str, float] | None = None,
) -> list[str]:
    """
    Tự động phân tích các triệu chứng sai lệch và gắn nhãn nguyên nhân cụ thể:
    - MISSING_ROWS: Thiếu dòng (thường do bảng ngắt trang hoặc gộp nhầm dòng)
    - EXTRA_ROWS: Thừa dòng (dòng trắng, chú thích bị biến thành dòng bảng)
    - COLUMN_COUNT_MISMATCH: Lệch số cột (thường do header 2 tầng bị hiểu sai)
    - MISSED_MERGED_HEADER: Bỏ sót ô gộp (đặc biệt là header "Năm nay / Năm trước")
    - HALLUCINATED_MERGE: Sinh ra ô gộp không có thực
    - HEADER_DEPTH_MISMATCH: Lệch số tầng header
    """
    errors: list[str] = []

    if pred["n_rows"] < gt["n_rows"]:
        errors.append("MISSING_ROWS")
    elif pred["n_rows"] > gt["n_rows"]:
        errors.append("EXTRA_ROWS")

    if pred["n_cols"] != gt["n_cols"]:
        errors.append("COLUMN_COUNT_MISMATCH")

    if span_result is None:
        span_result = span_iou(pred.get("spans", []), gt.get("spans", []))

    # Nếu ground truth có ô gộp mà recall thấp
    if gt.get("spans") and span_result["recall"] < 0.7:
        errors.append("MISSED_MERGED_HEADER")

    # Nếu prediction tự tạo ô gộp mà precision thấp
    if pred.get("spans") and span_result["precision"] < 0.7:
        errors.append("HALLUCINATED_MERGE")

    # Lệch độ sâu header
    pred_h_depth = len(pred.get("header_rows", []))
    gt_h_depth = len(gt.get("header_rows", []))
    if pred_h_depth != gt_h_depth and (pred_h_depth > 1 or gt_h_depth > 1):
        errors.append("HEADER_DEPTH_MISMATCH")

    return errors if errors else ["OK"]


def error_distribution(all_results: list[dict[str, Any]]) -> dict[str, int]:
    """Thống kê tần suất xuất hiện của từng loại lỗi trên toàn bộ tập dữ liệu."""
    all_errs: list[str] = []
    for r in all_results:
        all_errs.extend(r.get("errors", []))
    counts = Counter(all_errs)
    return dict(sorted(counts.items(), key=lambda item: -item[1]))
