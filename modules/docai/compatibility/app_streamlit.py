"""
Streamlit Web User Interface for NeSy-DocAI (Neuro-Symbolic Document AI Research Engine)
Supports Live File Upload (PNG, JPG, PDF, ZIP), Real-time macOS Vision / Tesseract OCR,
Z3 Presburger Symbolic Verification, 4-Layer Fraud Shield, and Multi-Format Excel/JSON Export.
"""

import io
import os
import zipfile
import tempfile
import time
import json
from typing import Any, Dict, List
import pandas as pd
import streamlit as st

from nesy_docai import (
    VisionPerceptionEngine,
    SymbolicSolverEngine,
    TaxMasterDataVerifier,
    AuditExcelExporter,
    NeSyInvoicePipeline,
    FraudRiskScorer,
    InvoiceCSVExporter,
    MISAandVATScheduleExporter,
    AccountantHITLWorkbench,
    EInvoiceXMLReaderEngine
)
from pathlib import Path
import re as re_module

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="NeSy-DocAI: Accounting & Document AI Platform",
    page_icon="🧾",
    layout="wide"
)

# Header Section
st.title("🧾 NeSy-DocAI: Accounting Invoice AI & Verification Workbench")
st.markdown("### System 1 (OCR & TT78 XML Direct Engine) + System 2 (Z3 Presburger Solver) + Accountant Review Workbench")

st.markdown("""
> **Vietnamese Accounting & Tax Integrity Suite**:
> Supports **Thông tư 78 / Nghị định 123 e-Invoice XML direct extraction**, **macOS Vision**, **Tesseract 5.5.2**, **Z3 SMT Presburger LIA constraint solving**, **Bảng kê 01-1/GTGT**, and **MISA SME / AMIS 1-Click Excel import**.
""")

# Sidebar Controls
st.sidebar.header("⚙️ Accounting System Configuration")

engine_choice = st.sidebar.selectbox(
    "System 1 Intake & OCR Engine",
    ["Auto-Hybrid (XML Direct + macOS Vision + Tesseract)", "macOS Native Vision (NPU)", "Tesseract 5.5.2 OCR"],
    index=0
)

company_name_input = st.sidebar.text_input("Tên Đơn Vị Sử Dụng (Doanh Nghiệp)", value="CÔNG TY TNHH KẾ TOÁN THÔNG MINH")
company_mst_input = st.sidebar.text_input("Mã Số Thuế Doanh Nghiệp (MST)", value="0101234567")

enable_tax_verification = st.sidebar.checkbox("Verify Vendor Tax Code with GDT Registry", value=True)
enable_fraud_shield = st.sidebar.checkbox("Enable 4-Layer Anti-Fraud Defense Shield", value=True)
z3_timeout_ms = st.sidebar.slider("Z3 Presburger SLA Timeout (ms)", min_value=100, max_value=5000, value=1000, step=100)

st.sidebar.markdown("---")
st.sidebar.subheader("📊 System Status")
st.sidebar.success("✅ XML e-Invoice Engine: READY (TT78/NĐ123)")
st.sidebar.success("✅ System 2 Z3 SMT Solver: READY (Presburger LIA)")
st.sidebar.success("✅ MISA / FAST Exporter: READY")
st.sidebar.info("⚡ Zero-OCR-Error XML Direct Intake: ACTIVE")

# Initialize Engine Instances
@st.cache_resource
def get_engines(timeout: int):
    vision_engine = VisionPerceptionEngine()
    solver_engine = SymbolicSolverEngine(vision_engine=vision_engine, timeout_ms=timeout)
    tax_verifier = TaxMasterDataVerifier()
    exporter = AuditExcelExporter()
    pipeline = NeSyInvoicePipeline()
    fraud_scorer = FraudRiskScorer()
    misa_exporter = MISAandVATScheduleExporter()
    xml_reader = EInvoiceXMLReaderEngine()
    return vision_engine, solver_engine, tax_verifier, exporter, pipeline, fraud_scorer, misa_exporter, xml_reader

vision_engine, solver_engine, tax_verifier, exporter, pipeline, fraud_scorer, misa_exporter, xml_reader = get_engines(z3_timeout_ms)

# Main Processing Options
st.subheader("1. Select Invoice Input Source")
input_option = st.radio("Choose Input Mode:", ["Upload Files (XML, PDF, PNG, JPG, ZIP)", "Live Batch Stress Test (Synthetic & Benchmark Set)"], horizontal=True)

temp_dir = os.path.join(tempfile.gettempdir(), "nesy_docai_uploads")
os.makedirs(temp_dir, exist_ok=True)

records_to_process = []  # List of tuples: (filename, filepath_or_raw_dict)

if input_option == "Upload Files (XML, PDF, PNG, JPG, ZIP)":
    uploaded_files = st.file_uploader("Upload Invoice XML (TT78 e-Invoice), Image, PDF or ZIP batch archive", type=["xml", "png", "jpg", "jpeg", "pdf", "zip"], accept_multiple_files=True)
    if uploaded_files:
        for i, uploaded_file in enumerate(uploaded_files):
            filename = uploaded_file.name
            safe_filename = re_module.sub(r'[^\w.\-]', '_', filename)
            file_path = os.path.join(temp_dir, safe_filename)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())

            if filename.lower().endswith(".zip"):
                try:
                    with zipfile.ZipFile(file_path) as z:
                        for zidx, zname in enumerate(z.namelist()):
                            if not zname.startswith("__MACOSX") and zname.lower().endswith(('.xml', '.png', '.jpg', '.jpeg', '.pdf')):
                                member_path = os.path.realpath(os.path.join(temp_dir, zname))
                                if not member_path.startswith(os.path.realpath(temp_dir)):
                                    st.error(f"Security: Zip Slip detected in entry: {zname}")
                                    continue
                                z.extract(zname, path=temp_dir)
                                rec = pipeline.process_file(member_path)
                                records_to_process.append((os.path.basename(zname), rec))
                except Exception as e:
                    st.error(f"❌ Could not extract ZIP file `{filename}`: {str(e)}")
            elif filename.lower().endswith(".xml"):
                rec = pipeline.process_file(file_path)
                records_to_process.append((filename, rec))
            else:
                rec = pipeline.process_file(file_path)
                records_to_process.append((filename, rec))
else:
    st.info("💡 Generate an automated synthetic invoice batch to test NeSy-DocAI under noisy OCR conditions.")
    batch_size = st.slider("Select Synthetic Batch Size", min_value=1, max_value=500, value=5)
    if st.button("🚀 Run Live Stress Test Batch"):
        companies = [
            ("0312345678", "CÔNG TY TNHH THIẾT BỊ VĂN PHÒNG SÀI GÒN"),
            ("0101234567", "CÔNG TY CP THƯƠNG MẠI DỊCH VỤ AN PHÁT"),
            ("0319876543", "CÔNG TY TNHH CÔNG NGHỆ SỐ HÀI DÓN")
        ]
        items_pool = [
            ("Bút ký cao cấp M&G", "1O000", 10000),
            ("Tập vở HS 200 trang", "15000", 15000),
            ("Giấy in A4 Double A 70gsm", "45000", 45000)
        ]
        for i in range(1, batch_size + 1):
            tax_id, comp_name = companies[(i - 1) % len(companies)]
            item_desc, raw_price_str, real_price = items_pool[(i - 1) % len(items_pool)]
            qty = (i % 5) + 1
            amount = real_price * qty
            tax_val = int(amount * 0.1)
            total_val = amount + tax_val

            mock_inv = {
                "invoice_id": f"HD-2026-{i:03d}",
                "invoice_date": "2026-08-08",
                "seller_tax_id": tax_id,
                "seller_name": comp_name,
                "line_items": [
                    {"item_id": 1, "description": item_desc, "quantity": str(qty), "unit_price": raw_price_str, "amount": str(amount), "bbox": [120, 340, 480, 360]}
                ],
                "subtotal": str(amount),
                "tax": f"{tax_val}OO" if i % 7 == 0 else str(tax_val),
                "total": str(total_val)
            }
            verified = solver_engine.solve_and_verify(mock_inv)
            verified["file_name"] = f"Live_Invoice_{i:03d}.png"
            records_to_process.append((f"Live_Invoice_{i:03d}.png", verified))

# Processing Executions
if records_to_process:
    st.markdown("---")
    st.subheader(f"2. Processing Queue ({len(records_to_process)} Invoices)")

    progress_bar = st.progress(0)
    status_text = st.empty()

    processed_results = []
    table_rows = []

    for idx, (fname, item_data) in enumerate(records_to_process):
        status_text.markdown(f"⏳ **Auditing [{idx+1}/{len(records_to_process)}]:** `{fname}`...")

        try:
            if isinstance(item_data, dict) and "audit_status" in item_data:
                verified = item_data
            else:
                verified = solver_engine.solve_and_verify(item_data)
                verified["file_name"] = fname

            # Tax Verification
            if enable_tax_verification and "tax_verification" not in verified:
                tax_info = tax_verifier.verify_tax_id(verified.get("seller_tax_id", ""))
                verified["tax_verification"] = tax_info

            # 4-Layer Anti-Fraud Audit Shield
            if enable_fraud_shield and "fraud_audit" not in verified:
                fraud_audit = fraud_scorer.audit_invoice_record(verified, file_name=fname)
                verified["fraud_audit"] = fraud_audit

            processed_results.append(verified)

            is_xml = verified.get("is_xml", False)
            is_sat = verified.get("audit_status") == "VERIFIED_SAT" or is_xml
            fraud_level = verified.get("fraud_audit", {}).risk_level if enable_fraud_shield else "LOW"

            risk_badge = "🟢 LOW" if fraud_level == "LOW" else ("🟡 MEDIUM" if fraud_level == "MEDIUM" else "🔴 HIGH")
            audit_str = "⚡ XML_DIRECT (100% Exact)" if is_xml else ("✅ VERIFIED_SAT" if is_sat else f"❌ {verified.get('audit_status')}")

            table_rows.append({
                "File": fname,
                "Invoice ID": verified.get("invoice_id", "N/A"),
                "Date": verified.get("invoice_date", "N/A"),
                "MST Ng Bán": verified.get("seller_tax_id", "N/A"),
                "Tên Ng Bán": verified.get("seller_name", "N/A"),
                "Nội dung diễn giải": verified.get("description_summary", "")[:40] + "...",
                "Subtotal (VNĐ)": f"{self_parse_int(verified.get('subtotal')):,}",
                "Tax Rate": verified.get("tax_rate", "10%"),
                "Tax Amount (VNĐ)": f"{self_parse_int(verified.get('tax')):,}",
                "Total (VNĐ)": f"{self_parse_int(verified.get('total')):,}",
                "Fraud Risk": risk_badge,
                "Audit Status": audit_str,
            })
        except Exception as ex:
            table_rows.append({
                "File": fname,
                "Invoice ID": "N/A",
                "Date": "N/A",
                "MST Ng Bán": "N/A",
                "Tên Ng Bán": "N/A",
                "Nội dung diễn giải": "ERROR",
                "Subtotal (VNĐ)": "0",
                "Tax Rate": "0%",
                "Tax Amount (VNĐ)": "0",
                "Total (VNĐ)": "0",
                "Fraud Risk": "🔴 HIGH",
                "Audit Status": f"❌ ERROR ({str(ex)})",
            })

        progress_bar.progress((idx + 1) / len(records_to_process))
        time.sleep(0.01)

    status_text.success(f"🎉 **Batch Audit Complete!** Successfully processed {len(processed_results)} invoices.")

    # Results Table Display
    df_results = pd.DataFrame(table_rows)
    st.dataframe(df_results, use_container_width=True)

    # ------------------------------------------------------------------
    # EXPORT DOWNLOADS FOR ACCOUNTANTS
    # ------------------------------------------------------------------
    st.markdown("### 📥 Accounting Reports & Exporters")
    st.info("Xuất báo cáo thuế GTGT theo Mẫu 01-1/GTGT hoặc file Excel nhập trực tiếp vào MISA SME / AMIS / FAST.")

    col_exp1, col_exp2, col_exp3, col_exp4 = st.columns([1, 1, 1, 1])

    with col_exp1:
        # Bảng Kê Thuế GTGT Mua Vào (Mẫu 01-1/GTGT)
        vat_out_path = os.path.join(temp_dir, "Bang_Ke_Thue_GTGT_01_1.xlsx")
        misa_exporter.export_vat_schedule_excel(
            processed_results,
            output_filepath=vat_out_path,
            company_name=company_name_input,
            company_mst=company_mst_input
        )
        with open(vat_out_path, "rb") as f_vat:
            st.download_button(
                label="📊 Bảng Kê Thuế GTGT 01-1 (Excel)",
                data=f_vat,
                file_name="Bang_Ke_Thue_GTGT_01_1.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    with col_exp2:
        # Accounting CSV Export
        csv_exporter_obj = InvoiceCSVExporter()
        csv_out_path = os.path.join(temp_dir, "invoice_export_accounting.csv")
        csv_exporter_obj.export(processed_results, Path(csv_out_path))
        with open(csv_out_path, "rb") as f_csv:
            st.download_button(
                label="📑 Accounting CSV (5 Cột Bắt Buộc)",
                data=f_csv,
                file_name="invoice_export_accounting.csv",
                mime="text/csv"
            )

    with col_exp3:
        # Multi-sheet Full Audit Ledger Excel
        excel_out_path = os.path.join(temp_dir, "invoice_audit_ledger.xlsx")
        exporter.export_to_excel(processed_results, output_filepath=excel_out_path)
        with open(excel_out_path, "rb") as f_excel:
            st.download_button(
                label="📘 Audit Ledger & Z3 Certificates (Excel)",
                data=f_excel,
                file_name="invoice_audit_ledger.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    with col_exp4:
        # Structured JSON
        json_str = json.dumps(processed_results, ensure_ascii=False, indent=2, default=str)
        st.download_button(
            label="💻 Full Structured JSON",
            data=json_str,
            file_name="invoice_audit_data.json",
            mime="application/json"
        )

    # ------------------------------------------------------------------
    # HUMAN-IN-THE-LOOP (HITL) ACCOUNTANT VERIFICATION WORKBENCH
    # ------------------------------------------------------------------
    st.markdown("---")
    st.subheader("3. 🧑‍💼 Human-In-The-Loop (HITL) Accountant Review Workbench")
    st.markdown("Kế toán kiểm tra, chỉnh sửa thông tin bị cờ cảnh báo và thực hiện **Re-Verify Z3 SMT Presburger** thời gian thực.")

    hitl_workbench = AccountantHITLWorkbench()
    hitl_items = hitl_workbench.load_records(processed_results)

    item_names = [f"[{i+1}] {item.file_name} — {item.invoice_id} ({item.seller_name[:20]})" for i, item in enumerate(hitl_items)]
    selected_idx = st.selectbox("Select Invoice to Inspect / Edit:", range(len(item_names)), format_func=lambda idx: item_names[idx])

    selected_item = hitl_items[selected_idx]
    target_rec = selected_item.original_data

    col_edit, col_inspect = st.columns([1.2, 1])

    with col_edit:
        st.markdown("#### ✏️ Accountant Edit & Verification Panel")

        with st.form(key=f"hitl_edit_form_{selected_idx}"):
            edit_mst = st.text_input("Mã Số Thuế Người Bán (MST):", value=selected_item.seller_tax_id)
            edit_seller = st.text_input("Tên Người Bán:", value=selected_item.seller_name)
            edit_desc = st.text_area("Nội Dung Diễn Giải (Hàng Hóa / Dịch Vụ):", value=selected_item.description_summary, height=70)
            
            c_sub, c_tax_rate, c_tax, c_tot = st.columns(4)
            with c_sub:
                edit_subtotal = st.text_input("Tiền Hàng (Subtotal):", value=str(selected_item.subtotal))
            with c_tax_rate:
                edit_tax_rate = st.selectbox("Thuế Suất (%):", ["0%", "5%", "8%", "10%"], index=3 if "10" in selected_item.tax_rate else 0)
            with c_tax:
                edit_tax = st.text_input("Tiền Thuế GTGT:", value=str(selected_item.tax))
            with c_tot:
                edit_total = st.text_input("Tổng Thanh Toán:", value=str(selected_item.total))

            accountant_notes = st.text_input("Ghi Chú Kế Toán / Lý Do Điều Chỉnh:", value=selected_item.accountant_notes)

            submitted = st.form_submit_button("🔄 Re-Verify Z3 SMT Constraints & Save Edit")

            if submitted:
                corrections = {
                    "seller_tax_id": edit_mst,
                    "seller_name": edit_seller,
                    "description_summary": edit_desc,
                    "subtotal": edit_subtotal,
                    "tax": edit_tax,
                    "tax_rate": edit_tax_rate,
                    "total": edit_total
                }
                updated_item = hitl_workbench.apply_manual_correction(selected_idx, corrections, accountant_notes=accountant_notes)
                st.success(f"🎉 **Re-verification Complete!** Status: `{updated_item.audit_status}` | Review: `{updated_item.review_status}`")
                st.rerun()

    with col_inspect:
        st.markdown("#### 🛡️ Z3 SMT Proof & Anti-Fraud Audit Status")
        st.info(f"**Current Status:** `{selected_item.audit_status}` | **Review State:** `{selected_item.review_status}`")

        fa = target_rec.get("fraud_audit")
        if fa:
            st.metric("Fraud Risk Score", f"{fa.risk_score}/100", delta=f"Risk: {fa.risk_level}", delta_color="inverse" if fa.risk_score > 20 else "normal")
            st.markdown("**Anti-Fraud Alerts:**")
            for alert in fa.fraud_alerts:
                st.write(alert)

        st.markdown("#### 📜 Proof Certificate")
        proof = selected_item.z3_certificate or target_rec.get("certificate")
        if proof:
            st.json(proof)
        else:
            st.error("No certificate available.")


def self_parse_int(val: Any) -> int:
    if val is None or val == "" or val == "N/A":
        return 0
    try:
        cleaned = str(val).replace(",", "").replace(".", "").replace("đ", "").strip()
        return int(float(cleaned))
    except (ValueError, TypeError):
        return 0
