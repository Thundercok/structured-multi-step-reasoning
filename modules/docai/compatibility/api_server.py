"""
FastAPI Enterprise REST Server for nesy-docai
Run with: uvicorn api_server:app --reload --port 8000
"""

from typing import Dict, Any, List
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
import tempfile
import os
from pathlib import Path
from uuid import uuid4
from nesy_docai import (
    VisionPerceptionEngine,
    SymbolicSolverEngine,
    TaxMasterDataVerifier,
    AuditExcelExporter,
    BoundingBoxVisualizer,
    PDFDocumentProcessor,
    MISAandVATScheduleExporter,
    EInvoiceXMLReaderEngine
)
from nesy_docai.csv_exporter import InvoiceCSVExporter

app = FastAPI(
    title="nesy-docai API",
    description="Enterprise Neuro-Symbolic Document AI REST Server (TT78 XML + System 1 OCR + Z3 SMT System 2)",
    version="1.1.0"
)

# Initialize Core Engine Modules
vision_engine = VisionPerceptionEngine()
symbolic_solver = SymbolicSolverEngine(vision_engine=vision_engine)
tax_verifier = TaxMasterDataVerifier()
excel_exporter = AuditExcelExporter()
misa_vat_exporter = MISAandVATScheduleExporter()
xml_reader = EInvoiceXMLReaderEngine()
visualizer = BoundingBoxVisualizer()
pdf_processor = PDFDocumentProcessor()
csv_exporter = InvoiceCSVExporter()


@app.get("/")
def read_root():
    return {
        "framework": "nesy-docai",
        "version": "1.1.0",
        "system1": "Qwen2.5-VL / TT78 XML Direct / OCR Candidate Generator",
        "system2": "Z3 Presburger SMT Solver",
        "accounting_exporters": ["CSV", "Excel Audit Ledger", "Bảng Kê 01-1/GTGT", "MISA SME Import"],
        "status": "OPERATIONAL"
    }


@app.get("/health")
def health_check():
    return {"status": "HEALTHY", "smt_solver_ready": True}


@app.post("/api/v1/parse-invoice")
async def parse_invoice(file: UploadFile = File(...)):
    """
    Parses an uploaded invoice image/PDF, executes System 1 (Vision) & System 2 (Z3 SMT Solver),
    cross-verifies tax ID, and returns the verified JSON audit record.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")
    
    # Write uploaded bytes to temporary file
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        raw_data = vision_engine.process_invoice_image(tmp_path)
        verified_record = symbolic_solver.solve_and_verify(raw_data)
        tax_info = tax_verifier.verify_tax_id(verified_record.get("seller_tax_id", ""))
        verified_record["tax_verification"] = tax_info
        return verified_record
    finally:
        os.unlink(tmp_path)


@app.post("/api/v1/export-excel")
async def export_excel(audit_records: List[Dict[str, Any]]):
    """
    Exports a list of audit records to a formatted Excel workbook.
    """
    if not audit_records:
        raise HTTPException(status_code=400, detail="Audit records list cannot be empty.")

    output_path = excel_exporter.export_to_excel(audit_records, output_filepath="invoice_audit_report.xlsx")
    return FileResponse(
        path=output_path,
        filename="invoice_audit_report.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.post("/api/v1/export-csv")
async def export_csv(audit_records: List[Dict[str, Any]]):
    if not audit_records:
        raise HTTPException(status_code=400, detail="Audit records list cannot be empty.")
    
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        csv_exporter.export(audit_records, Path(tmp_path))
        return FileResponse(
            path=tmp_path,
            filename="invoice_audit_report.csv",
            media_type="text/csv"
        )
    except Exception as e:
        os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/export-vat-schedule")
async def export_vat_schedule(audit_records: List[Dict[str, Any]], company_name: str = "ĐƠN VỊ SỬ DỤNG", company_mst: str = "0100000000"):
    """
    Exports audit records into Bảng Kê Thuế GTGT 01-1/GTGT and MISA SME / AMIS Excel Import Workbook.
    """
    if not audit_records:
        raise HTTPException(status_code=400, detail="Audit records list cannot be empty.")
    
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        misa_vat_exporter.export_vat_schedule_excel(
            audit_records,
            output_filepath=tmp_path,
            company_name=company_name,
            company_mst=company_mst
        )
        return FileResponse(
            path=tmp_path,
            filename="Bang_Ke_Thue_GTGT_01_1_MISA.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/parse-xml")
async def parse_xml_invoice(file: UploadFile = File(...)):
    """
    Direct 100% exact zero-OCR error parsing for Thông tư 78 e-invoice XML files.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        xml_data = xml_reader.process_xml(tmp_path)
        tax_info = tax_verifier.verify_tax_id(xml_data.get("seller_tax_id", ""))
        xml_data["tax_verification"] = tax_info
        return xml_data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse XML e-invoice: {str(e)}")
    finally:
        os.unlink(tmp_path)


@app.post("/api/v1/parse-batch")
async def parse_batch(files: List[UploadFile], background_tasks: BackgroundTasks):
    """Process multiple invoice files."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    
    results = []
    for file in files:
        suffix = Path(file.filename).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            raw_data = vision_engine.process_invoice_image(tmp_path)
            verified_record = symbolic_solver.solve_and_verify(raw_data)
            verified_record["file_name"] = file.filename
            results.append(verified_record)
        except Exception as e:
            results.append({"file_name": file.filename, "error": str(e), "audit_status": "ERROR"})
        finally:
            os.unlink(tmp_path)
    
    return {"total": len(results), "results": results}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000)
