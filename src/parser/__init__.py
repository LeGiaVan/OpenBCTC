"""
Parser package — Document Intelligence & Parsing cho FinAudit AI.
"""

from src.parser.block_classifier import BlockClassifier
from src.parser.normalizer import OutputNormalizer, normalize_output
from src.parser.ocr_pipeline import OCRPipeline, VisionOCRPipeline
from src.parser.pdf_parser import PDFParser
from src.parser.pdf_type_detector import PageClassification, PDFTypeDetector
from src.parser.section_detector import SectionDetector
from src.parser.text_parser import TextParser

__all__ = [
    "PDFParser",
    "TextParser",
    "OCRPipeline",
    "VisionOCRPipeline",
    "OutputNormalizer",
    "normalize_output",
    "PDFTypeDetector",
    "PageClassification",
    "BlockClassifier",
    "SectionDetector",
]
