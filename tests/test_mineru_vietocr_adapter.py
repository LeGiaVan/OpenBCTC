import numpy as np
from PIL import Image
from unittest.mock import MagicMock

from src.parser.mineru_vietocr_adapter import (
    VietOCRRecognizerWrapper,
    is_mineru_available,
    patch_mineru_with_vietocr,
)


def test_vietocr_recognizer_wrapper_batch():
    mock_pred = MagicMock()
    mock_pred.predict_batch.return_value = ["Doanh thu", "12 . 000 . 000"]

    wrapper = VietOCRRecognizerWrapper(mock_pred)

    img1 = np.zeros((32, 100, 3), dtype=np.uint8)
    img2 = np.zeros((32, 80, 3), dtype=np.uint8)

    results, elapse = wrapper([img1, img2])

    assert len(results) == 2
    assert results[0][0] == "Doanh thu"
    assert results[0][1] == 0.95
    assert results[1][0] == "12.000.000"  # Sửa lỗi khoảng cách số tài chính
    assert elapse >= 0.0
    assert mock_pred.predict_batch.called


def test_vietocr_recognizer_wrapper_fallback_single():
    mock_pred = MagicMock(spec=["predict"])
    mock_pred.predict.side_effect = ["Khoản mục 1", "Khoản mục 2"]

    wrapper = VietOCRRecognizerWrapper(mock_pred)

    img1 = Image.new("RGB", (60, 20))
    img2 = Image.new("L", (60, 20))

    results, elapse = wrapper([img1, img2])

    assert len(results) == 2
    assert results[0][0] == "Khoản mục 1"
    assert results[1][0] == "Khoản mục 2"
    assert mock_pred.predict.call_count == 2


def test_is_mineru_available():
    res = is_mineru_available()
    assert isinstance(res, bool)


def test_patch_mineru_with_vietocr_idempotency():
    mock_pred = MagicMock()
    res1 = patch_mineru_with_vietocr(mock_pred)
    res2 = patch_mineru_with_vietocr(mock_pred)
    assert res1 is True
    assert res2 is True
