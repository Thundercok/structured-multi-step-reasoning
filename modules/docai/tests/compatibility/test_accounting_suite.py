"""
Test suite for accounting features:
- TT78 XML e-Invoice Direct Reader
- MISA & VAT Tax Schedule (Form 01-1/GTGT) Exporter
- Accountant HITL Review & Re-verification Workbench
"""

import os
import pytest
import xml.etree.ElementTree as ET
from nesy_docai import (
    EInvoiceXMLReaderEngine,
    MISAandVATScheduleExporter,
    AccountantHITLWorkbench,
    NeSyInvoicePipeline
)


def test_xml_einvoice_reader(tmp_path):
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<HDon>
    <DLHDon>
        <TTChung>
            <PBan>2.0.0</PBan>
            <THDon>HÓA ĐƠN GIÁ TRỊ GIA TĂNG</THDon>
            <KHMSHDon>1</KHMSHDon>
            <KHHDon>C26TTH</KHHDon>
            <SHDon>0001234</SHDon>
            <NLap>2026-08-10</NLap>
            <DVTTe>VND</DVTTe>
        </TTChung>
        <NDHDon>
            <NBan>
                <Ten>CÔNG TY TNHH PHẦN MỀM KẾ TOÁN MISA</Ten>
                <MST>0101234567</MST>
                <DChi>Tòa nhà Technosoft, Cầu Giấy, Hà Nội</DChi>
            </NBan>
            <NMua>
                <Ten>CÔNG TY TNHH GIẢI PHÁP SỐ</Ten>
                <MST>0312345678</MST>
            </NMua>
            <DSHHDVu>
                <HHDVu>
                    <STT>1</STT>
                    <Ten>Bản quyền phần mềm MISA SME 2026</Ten>
                    <DVTinh>Bộ</DVTinh>
                    <SLuong>2</SLuong>
                    <DGia>5000000</DGia>
                    <TTien>10000000</TTien>
                    <TSuat>10%</TSuat>
                </HHDVu>
            </DSHHDVu>
            <TToan>
                <TgTCThue>10000000</TgTCThue>
                <TgTThue>1000000</TgTThue>
                <TgTTTBSo>11000000</TgTTTBSo>
            </TToan>
        </NDHDon>
    </DLHDon>
</HDon>"""

    xml_file = tmp_path / "test_invoice.xml"
    xml_file.write_text(xml_content, encoding="utf-8")

    reader = EInvoiceXMLReaderEngine()
    assert reader.is_xml_file(str(xml_file)) is True

    parsed = reader.process_xml(str(xml_file))
    assert parsed["is_xml"] is True
    assert parsed["invoice_id"] == "C26TTH-0001234"
    assert parsed["seller_tax_id"] == "0101234567"
    assert parsed["seller_name"] == "CÔNG TY TNHH PHẦN MỀM KẾ TOÁN MISA"
    assert parsed["subtotal"] == "10000000"
    assert parsed["tax"] == "1000000"
    assert parsed["total"] == "11000000"
    assert parsed["tax_rate"] == "10%"
    assert parsed["audit_status"] == "VERIFIED_XML_DIRECT"


def test_pipeline_with_xml(tmp_path):
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<HDon>
    <DLHDon>
        <TTChung>
            <SHDon>99999</SHDon>
            <KHHDon>K26ABC</KHHDon>
            <NLap>2026-08-10</NLap>
        </TTChung>
        <NDHDon>
            <NBan>
                <Ten>CTY VĂN PHÒNG PHẨM AN PHÁT</Ten>
                <MST>0319876543</MST>
            </NBan>
            <DSHHDVu>
                <HHDVu>
                    <Ten>Giấy in A4 70gsm</Ten>
                    <SLuong>10</SLuong>
                    <DGia>50000</DGia>
                    <TTien>500000</TTien>
                </HHDVu>
            </DSHHDVu>
            <TToan>
                <TgTCThue>500000</TgTCThue>
                <TgTThue>40000</TgTThue>
                <TgTTTBSo>540000</TgTTTBSo>
            </TToan>
        </NDHDon>
    </DLHDon>
</HDon>"""

    xml_file = tmp_path / "invoice_tt78.xml"
    xml_file.write_text(xml_content, encoding="utf-8")

    pipeline = NeSyInvoicePipeline()
    res = pipeline.process_file(str(xml_file))

    assert res["invoice_id"] == "K26ABC-99999"
    assert res["seller_tax_id"] == "0319876543"
    assert res["subtotal"] == "500000"
    assert res["total"] == "540000"
    assert res["audit_status"] == "VERIFIED_XML_DIRECT"


def test_misa_and_vat_exporter(tmp_path):
    records = [
        {
            "is_xml": True,
            "invoice_id": "C26TTH-0001",
            "invoice_form": "1",
            "invoice_symbol": "C26TTH",
            "invoice_number": "0001",
            "invoice_date": "2026-08-10",
            "seller_tax_id": "0101234567",
            "seller_name": "CÔNG TY MISA",
            "seller_address": "Hà Nội",
            "description_summary": "Phần mềm kế toán",
            "subtotal": 10000000,
            "tax": 1000000,
            "tax_rate": "10%",
            "total": 11000000,
            "audit_status": "VERIFIED_XML_DIRECT"
        }
    ]

    exporter = MISAandVATScheduleExporter()
    out_file = tmp_path / "Bang_Ke_01_1.xlsx"
    saved = exporter.export_vat_schedule_excel(records, output_filepath=out_file)

    assert os.path.exists(saved)
    assert saved.stat().st_size > 0


def test_accountant_hitl_workbench():
    records = [
        {
            "file_name": "scan_noisy.png",
            "invoice_id": "HD-FLAGGED",
            "seller_tax_id": "0312345678",
            "seller_name": "CÔNG TY IN ẤN",
            "invoice_date": "2026-08-10",
            "description_summary": "In tờ rơi QC",
            "subtotal": "100000",
            "tax": "10000",
            "tax_rate": "10%",
            "total": "110000",
            "audit_status": "FLAGGED_UNSAT",
            "confidence_score": 0.5
        }
    ]

    workbench = AccountantHITLWorkbench()
    items = workbench.load_records(records)
    assert len(items) == 1
    assert items[0].review_status == "PENDING_REVIEW"

    # Accountant corrects description and re-verifies Z3
    updated = workbench.apply_manual_correction(
        item_index=0,
        corrected_fields={
            "subtotal": "100000",
            "tax": "10000",
            "total": "110000",
            "description_summary": "In tờ rơi QC 500kđ"
        },
        accountant_notes="Đã kiểm tra khớp hóa đơn gốc"
    )

    assert updated.review_status == "APPROVED"
    assert updated.audit_status == "VERIFIED_HUMAN_CORRECTED_SAT"
    assert updated.z3_certificate is not None

    approved = workbench.get_approved_records()
    assert len(approved) == 1
    assert approved[0]["accountant_notes"] == "Đã kiểm tra khớp hóa đơn gốc"
