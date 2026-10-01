"""
test_section_detector.py — Unit tests kiểm thử Section Detector của FinAudit AI.
"""


from src.models import BlockType, ClassifiedBlock, ParsedBlock, StorageTarget
from src.parser.section_detector import SectionDetector, slugify_vietnamese


class TestSectionDetector:
    """Kiểm thử thuật toán nhận diện tiêu đề và gom nhóm Section."""

    def test_slugify_vietnamese(self):
        """Kiểm thử chuyển đổi tiêu đề tiếng Việt có dấu thành slug an toàn."""
        assert slugify_vietnamese("BẢNG CÂN ĐỐI KẾ TOÁN") == "bang_can_doi_ke_toan"
        assert slugify_vietnamese("Báo cáo kết quả kinh doanh") == "bao_cao_ket_qua_kinh_doanh"
        assert slugify_vietnamese("IV. Các chính sách kế toán áp dụng") == "iv_cac_chinh_sach_ke_toan_ap_dung"
        assert slugify_vietnamese("Đặc điểm hoạt động của doanh nghiệp") == "dac_diem_hoat_dong_cua_doanh_nghiep"

    def test_detect_multiple_sections(self):
        """Kiểm thử nhận diện nhiều Section từ danh sách block liên tiếp."""
        detector = SectionDetector()

        # Block 1: Tiêu đề Bảng Cân đối kế toán
        b1 = ClassifiedBlock(
            block=ParsedBlock(
                block_id="p5_b1",
                block_type="text",
                page=5,
                content="BẢNG CÂN ĐỐI KẾ TOÁN\nTại ngày 31 tháng 12 năm 2024",
            ),
            block_type=BlockType.NARRATIVE,
            target=[StorageTarget.VECTOR],
            confidence=0.9,
            classification_method="rule_based",
        )
        # Block 2: Bảng số liệu Bảng Cân đối kế toán
        b2 = ClassifiedBlock(
            block=ParsedBlock(
                block_id="p5_b2",
                block_type="table",
                page=5,
                content="| Chỉ tiêu | Số tiền |\n| --- | --- |\n| Tài sản ngắn hạn | 1.000 |",
            ),
            block_type=BlockType.FINANCIAL_STATEMENT,
            target=[StorageTarget.SQL, StorageTarget.VECTOR],
            confidence=0.95,
            classification_method="rule_based",
        )
        # Block 3: Tiêu đề Báo cáo kết quả kinh doanh (trang 7)
        b3 = ClassifiedBlock(
            block=ParsedBlock(
                block_id="p7_b1",
                block_type="text",
                page=7,
                content="BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH\nCho năm tài chính 2024",
            ),
            block_type=BlockType.NARRATIVE,
            target=[StorageTarget.VECTOR],
            confidence=0.9,
            classification_method="rule_based",
        )
        # Block 4: Bảng KQKD
        b4 = ClassifiedBlock(
            block=ParsedBlock(
                block_id="p7_b2",
                block_type="table",
                page=7,
                content="| Chỉ tiêu | Năm nay |\n| --- | --- |\n| Doanh thu | 5.000 |",
            ),
            block_type=BlockType.FINANCIAL_STATEMENT,
            target=[StorageTarget.SQL, StorageTarget.VECTOR],
            confidence=0.95,
            classification_method="rule_based",
        )

        sections = detector.detect_sections([b1, b2, b3, b4], company="VNM", year=2024)

        assert len(sections) == 2

        # Section 1
        s1 = sections[0]
        assert "BẢNG CÂN ĐỐI KẾ TOÁN" in s1.title
        assert s1.page_start == 5
        assert s1.page_end == 5
        assert len(s1.blocks) == 2
        assert "vnm_2024_s_bang_can_doi_ke_toan" in s1.id

        # Section 2
        s2 = sections[1]
        assert "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH" in s2.title
        assert s2.page_start == 7
        assert s2.page_end == 7
        assert len(s2.blocks) == 2
        assert "vnm_2024_s_bao_cao_ket_qua_hoat_dong" in s2.id

    def test_detect_numbered_headings_in_notes(self):
        """Kiểm thử nhận diện các mục thuyết minh đánh số: 1. Tiền, 2. Hàng tồn kho."""
        detector = SectionDetector()

        b1 = ClassifiedBlock(
            block=ParsedBlock(
                block_id="p12_b1",
                block_type="text",
                page=12,
                content="1. Tiền và các khoản tương đương tiền\nBao gồm tiền mặt tại quỹ và tiền gửi ngân hàng.",
            ),
            block_type=BlockType.NARRATIVE,
            target=[StorageTarget.VECTOR],
            confidence=0.85,
            classification_method="rule_based",
        )
        b2 = ClassifiedBlock(
            block=ParsedBlock(
                block_id="p12_b2",
                block_type="text",
                page=12,
                content="2. Hàng tồn kho\nChi tiết nguyên vật liệu và thành phẩm tồn kho tại ngày kết thúc năm tài chính.",
            ),
            block_type=BlockType.NARRATIVE,
            target=[StorageTarget.VECTOR],
            confidence=0.85,
            classification_method="rule_based",
        )

        sections = detector.detect_sections([b1, b2], company="HPG", year=2024)
        assert len(sections) == 2
        assert "1. Tiền và các khoản tương đương tiền" in sections[0].title
        assert "2. Hàng tồn kho" in sections[1].title

    def test_initial_blocks_without_heading_creates_intro_section(self):
        """Các block đầu tài liệu trước khi xuất hiện heading được gom vào section mở đầu."""
        detector = SectionDetector()
        b_intro = ClassifiedBlock(
            block=ParsedBlock(
                block_id="p1_b1",
                block_type="text",
                page=1,
                content="Công ty Cổ phần Sữa Việt Nam\nĐịa chỉ: Số 10 Tân Trào, Tân Phú, Quận 7, TP.HCM",
            ),
            block_type=BlockType.NARRATIVE,
            target=[StorageTarget.VECTOR],
            confidence=0.8,
            classification_method="rule_based",
        )

        sections = detector.detect_sections([b_intro], company="VNM", year=2024)
        assert len(sections) == 1
        assert "THÔNG TIN CHUNG" in sections[0].title
        assert sections[0].id == "vnm_2024_s_thong_tin_chung"

    def test_detect_roman_hierarchy_and_numbered_notes(self):
        """Kiểm thử nhận diện Phần La Mã V và các mục con 1, 19 kèm Reference Code."""
        detector = SectionDetector()

        b_roman_v = ClassifiedBlock(
            block=ParsedBlock(
                block_id="p27_b1",
                block_type="text",
                page=27,
                content="V. THÔNG TIN BỔ SUNG CHO CÁC KHOẢN MỤC TRÌNH BÀY TRONG BẢNG CÂN ĐỐI KẾ TOÁN",
            ),
            block_type=BlockType.NARRATIVE,
            target=[StorageTarget.VECTOR],
            confidence=0.9,
            classification_method="rule_based",
        )
        b_note_1 = ClassifiedBlock(
            block=ParsedBlock(
                block_id="p27_b2",
                block_type="text",
                page=27,
                content="1. Tiền và các khoản tương đương tiền\nTiền mặt: 1.000 VND",
            ),
            block_type=BlockType.NARRATIVE,
            target=[StorageTarget.VECTOR],
            confidence=0.9,
            classification_method="rule_based",
        )
        b_note_19 = ClassifiedBlock(
            block=ParsedBlock(
                block_id="p42_b1",
                block_type="text",
                page=42,
                content="19. Vốn chủ sở hữu\nChi tiết biến động vốn chủ sở hữu trong năm.",
            ),
            block_type=BlockType.NARRATIVE,
            target=[StorageTarget.VECTOR],
            confidence=0.9,
            classification_method="rule_based",
        )

        sections = detector.detect_sections([b_roman_v, b_note_1, b_note_19], company="VNM", year=2024)
        assert len(sections) == 3

        # Roman V (Level 3 - H3)
        s_v = sections[0]
        assert s_v.level == 3
        assert s_v.canonical_code == "NOTE_SEC_BALANCE_SHEET"
        assert "V. THÔNG TIN BỔ SUNG" in s_v.title

        # Note 1 (Level 4 - H4, Ref: V.1)
        s_1 = sections[1]
        assert s_1.level == 4
        assert s_1.reference_code == "V.1"
        assert s_1.parent_id == s_v.id
        assert "V. THÔNG TIN BỔ SUNG" in s_1.breadcrumb
        assert "1. Tiền và các khoản tương đương tiền" in s_1.breadcrumb

        # Note 19 (Level 4 - H4, Ref: V.19)
        s_19 = sections[2]
        assert s_19.level == 4
        assert s_19.reference_code == "V.19"
        assert s_19.parent_id == s_v.id
        assert "19. Vốn chủ sở hữu" in s_19.breadcrumb

    def test_detect_sub_letter_items_and_child_metadata(self):
        """Kiểm thử nhận diện tiểu mục (a) và cấu trúc child_metadata cho RAG."""
        detector = SectionDetector()

        b_sub = ClassifiedBlock(
            block=ParsedBlock(
                block_id="p14_b1",
                block_type="text",
                page=14,
                content="4. Cấu trúc Tập đoàn\n(a) Các công ty con\nCông ty TNHH Một thành viên Bò Sữa Việt Nam",
            ),
            block_type=BlockType.NARRATIVE,
            target=[StorageTarget.VECTOR],
            confidence=0.9,
            classification_method="rule_based",
        )

        sections = detector.detect_sections([b_sub], company="VNM", year=2024)
        # Sẽ tự động tách thành 2 sections: "4. Cấu trúc Tập đoàn" và "(a) Các công ty con"
        assert len(sections) == 2

        sec_parent = sections[0]
        assert sec_parent.level == 4
        assert "4. Cấu trúc Tập đoàn" in sec_parent.title

        sec_child = sections[1]
        assert sec_child.level == 5
        assert "(a) Các công ty con" in sec_child.title
        assert sec_child.parent_id == sec_parent.id

        # Kiểm tra child_metadata cho Parent-Child RAG
        meta = sec_child.child_metadata
        assert meta["chunk_id"] == sec_child.id
        assert meta["level"] == 5
        assert "(a) Các công ty con" in meta["title"]
        assert "4. Cấu trúc Tập đoàn" in meta["breadcrumb"]

    def test_detect_major_sections_level_2(self):
        """Kiểm thử tự động chèn Level 2 (## PHẦN 1, ## PHẦN 2) khi enable_major_sections=True."""
        detector = SectionDetector(enable_major_sections=True)

        # Block 1: Bảng cân đối kế toán (BCTC cốt lõi)
        b_bs = ClassifiedBlock(
            block=ParsedBlock(
                block_id="p7_b1",
                block_type="text",
                page=7,
                content="BẢNG CÂN ĐỐI KẾ TOÁN\nTại ngày 31 tháng 12 năm 2024",
            ),
            block_type=BlockType.NARRATIVE,
            target=[StorageTarget.VECTOR],
            confidence=0.95,
            classification_method="rule_based",
        )
        # Block 2: Phần Thuyết minh I
        b_note = ClassifiedBlock(
            block=ParsedBlock(
                block_id="p13_b1",
                block_type="text",
                page=13,
                content="I. ĐẶC ĐIỂM HOẠT ĐỘNG CỦA DOANH NGHIỆP\n1. Hình thức sở hữu vốn",
            ),
            block_type=BlockType.NARRATIVE,
            target=[StorageTarget.VECTOR],
            confidence=0.9,
            classification_method="rule_based",
        )

        sections = detector.detect_sections([b_bs, b_note], company="VNM", year=2024)

        # Kỳ vọng:
        # 1. Section Level 2: PHẦN 1: BÁO CÁO TÀI CHÍNH CỐT LÕI
        # 2. Section Level 3: BẢNG CÂN ĐỐI KẾ TOÁN
        # 3. Section Level 2: PHẦN 2: BẢN THUYẾT MINH BÁO CÁO TÀI CHÍNH
        # 4. Section Level 3: I. ĐẶC ĐIỂM HOẠT ĐỘNG CỦA DOANH NGHIỆP
        # 5. Section Level 4: 1. Hình thức sở hữu vốn
        level_2_secs = [s for s in sections if s.level == 2]
        assert len(level_2_secs) == 2

        part_1 = level_2_secs[0]
        assert part_1.title == "PHẦN 1: BÁO CÁO TÀI CHÍNH CỐT LÕI"
        assert part_1.id == "vnm_2024_s_part_1_core"

        part_2 = level_2_secs[1]
        assert part_2.title == "PHẦN 2: BẢN THUYẾT MINH BÁO CÁO TÀI CHÍNH"
        assert part_2.id == "vnm_2024_s_part_2_notes"

        # Kiểm tra H3 con trỏ parent_id đúng về Level 2
        bs_sec = [s for s in sections if "BẢNG CÂN ĐỐI" in s.title][0]
        assert bs_sec.level == 3
        assert bs_sec.parent_id == part_1.id
        assert "PHẦN 1" in bs_sec.breadcrumb


