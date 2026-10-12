"""
nesy-docai: Neuro-Symbolic Document AI Research Engine
Production-ready invoice processing with CSV/Excel export for accounting workflows.
"""

__version__ = "1.1.0"
__author__ = "Huỳnh Nhật Huy"

from .system1_vision import VisionPerceptionEngine
from .system2_solver import SymbolicSolverEngine
from .tax_verifier import TaxMasterDataVerifier
from .exporter import AuditExcelExporter
from .visualizer import BoundingBoxVisualizer
from .pdf_processor import PDFDocumentProcessor
from .benchmark_suite import InvoiceBenchmarkSuite
from .cord_loader import RealWorldDatasetLoader

from .pipeline import NeSyInvoicePipeline, ProcessingResult, OCRExtractionError
from .solver.z3_engine import solve_invoice, SolverResult
from .lattice.generator import CandidateLatticeGenerator, InvoiceFields
from .fraud_checker import (
    FraudRiskScorer,
    DuplicateInvoiceRegistry,
    VietnameseTaxIDValidator,
    FraudAuditResult
)
from .layout.bbox_extractor import SpatialLayoutExtractor, BBox, OCRToken
from .csv_exporter import InvoiceCSVExporter
from .config import NeSyConfig
from .tax_code_mapper import infer_tax_code, format_tax_rate
from .intake.xml_reader import EInvoiceXMLReaderEngine
from .misa_vat_exporter import MISAandVATScheduleExporter
from .hitl_workbench import AccountantHITLWorkbench, AccountantReviewItem

__all__ = [
    "VisionPerceptionEngine",
    "SymbolicSolverEngine",
    "TaxMasterDataVerifier",
    "AuditExcelExporter",
    "BoundingBoxVisualizer",
    "PDFDocumentProcessor",
    "InvoiceBenchmarkSuite",
    "RealWorldDatasetLoader",
    "NeSyInvoicePipeline",
    "ProcessingResult",
    "OCRExtractionError",
    "solve_invoice",
    "SolverResult",
    "CandidateLatticeGenerator",
    "InvoiceFields",
    "FraudRiskScorer",
    "DuplicateInvoiceRegistry",
    "VietnameseTaxIDValidator",
    "FraudAuditResult",
    "SpatialLayoutExtractor",
    "BBox",
    "OCRToken",
    "InvoiceCSVExporter",
    "NeSyConfig",
    "infer_tax_code",
    "format_tax_rate",
    "EInvoiceXMLReaderEngine",
    "MISAandVATScheduleExporter",
    "AccountantHITLWorkbench",
    "AccountantReviewItem",
]

