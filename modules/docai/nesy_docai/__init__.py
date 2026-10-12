"""Optional invoice prototype migrated from NeSy-DocAI.

Public compatibility exports load on demand. Importing this package does not
load Z3, spreadsheet libraries, OCR engines, a model, or an audit registry.
"""

from importlib import import_module

__version__ = "1.1.0"
__author__ = "Huỳnh Nhật Huy"

_EXPORTS = {
    "VisionPerceptionEngine": "system1_vision",
    "SymbolicSolverEngine": "system2_solver",
    "TaxMasterDataVerifier": "tax_verifier",
    "AuditExcelExporter": "exporter",
    "BoundingBoxVisualizer": "visualizer",
    "PDFDocumentProcessor": "pdf_processor",
    "InvoiceBenchmarkSuite": "benchmark_suite",
    "RealWorldDatasetLoader": "cord_loader",
    "NeSyInvoicePipeline": "pipeline",
    "ProcessingResult": "pipeline",
    "OCRExtractionError": "pipeline",
    "solve_invoice": "solver.z3_engine",
    "SolverResult": "solver.z3_engine",
    "CandidateLatticeGenerator": "lattice.generator",
    "InvoiceFields": "lattice.generator",
    "FraudRiskScorer": "fraud_checker",
    "DuplicateInvoiceRegistry": "fraud_checker",
    "VietnameseTaxIDValidator": "fraud_checker",
    "FraudAuditResult": "fraud_checker",
    "SpatialLayoutExtractor": "layout.bbox_extractor",
    "BBox": "layout.bbox_extractor",
    "OCRToken": "layout.bbox_extractor",
    "InvoiceCSVExporter": "csv_exporter",
    "NeSyConfig": "config",
    "infer_tax_code": "tax_code_mapper",
    "format_tax_rate": "tax_code_mapper",
    "EInvoiceXMLReaderEngine": "intake.xml_reader",
    "MISAandVATScheduleExporter": "misa_vat_exporter",
    "AccountantHITLWorkbench": "hitl_workbench",
    "AccountantReviewItem": "hitl_workbench",
}


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{_EXPORTS[name]}", __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(_EXPORTS))

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

