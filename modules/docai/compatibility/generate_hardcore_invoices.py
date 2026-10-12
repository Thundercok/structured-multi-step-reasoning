"""
Generator for Hardcore Invoice Challenge ZIP file.
Contains complex multi-tax rate invoices (5%, 8%, 10%), severe OCR noise,
and mathematical discrepancy/fraudulent invoices.
"""

import os
import json
import zipfile
from PIL import Image, ImageDraw


def generate_hardcore_zip(output_zip: str = "hardcore_invoices_challenge.zip"):
    print(f"Generating Hardcore Invoices Challenge ZIP into {output_zip}...")
    
    tmp_dir = "temp_hard_gen"
    os.makedirs(tmp_dir, exist_ok=True)

    companies = [
        ("0312345678", "CÔNG TY TNHH THIẾT BỊ VĂN PHÒNG SÀI GÒN"),
        ("0101234567", "CÔNG TY CP THƯƠNG MẠI DỊCH VỤ AN PHÁT"),
        ("0319876543", "CÔNG TY TNHH CÔNG NGHỆ SỐ HÀI DÓN"),
        ("0305556667", "CÔNG TY TNHH THƯƠNG MẠI MINH ĐỨC (CẢNH BÁO KÊ KHỐNG)"),
        ("0109998887", "CÔNG TY CP ĐIỆN MÁY VIỆT NAM")
    ]

    hardcore_scenarios = [
        # Scenario 1: Multi-Tax Rates (5%, 8%, 10%)
        {
            "id": "HD-HARD-MULTITAX-001",
            "title": "Hóa Đơn Nhiều Thuế Suất VAT (5%, 8%, 10%)",
            "company": companies[0],
            "items": [
                ("Gạo ST25 (VAT 5%)", "10", "25000", "250000"),
                ("Giấy in A4 (VAT 8% Nghị định 15)", "5", "45000", "225000"),
                ("Dịch vụ CNTT (VAT 10%)", "1", "1000000", "1000000")
            ],
            "subtotal": "1475000",
            "tax": "130500",  # (250k*5% + 225k*8% + 1M*10%) = 12.5k + 18k + 100k = 130,500
            "total": "1605500",
            "note": "Z3 SMT solves system of linear equations across 3 tax brackets"
        },
        # Scenario 2: Severe OCR Distortion
        {
            "id": "HD-HARD-OCRNOISE-002",
            "title": "Hóa Đơn Nhiễu OCR Ký Tự Nặng (S->5, O->0, B->8)",
            "company": companies[1],
            "items": [
                ("Bàn phím AKKO (Nhiễu 1S00000)", "1", "1S00000", "1500000"),
                ("Chuột Logitech (Nhiễu 36OOOO)", "1", "36OOOO", "360000")
            ],
            "subtotal": "186OOOO",
            "tax": "186OOO",
            "total": "2O46OOO",
            "note": "Z3 SMT repairs S, O, B confusion characters simultaneously"
        },
        # Scenario 3: Fraud Discrepancy Detection (UNSAT)
        {
            "id": "HD-FRAUD-UNSAT-003",
            "title": "Hóa Đơn Cố Tình Kê Khống Tiền (Phát Hiện Gian Lận)",
            "company": companies[3],
            "items": [
                ("Linh kiện điện tử gia công", "1", "1000000", "1000000")
            ],
            "subtotal": "1000000",
            "tax": "100000",
            "total": "1800000",  # Fraud: 1M + 100k != 1.8M
            "note": "Z3 SMT Solver flags FLAGGED_UNSAT mathematical fraud alert"
        },
        # Scenario 4: Invoice with Trade Discount
        {
            "id": "HD-HARD-DISCOUNT-004",
            "title": "Hóa Đơn Chiết Khấu Thương Mại Hàng Bán",
            "company": companies[2],
            "items": [
                ("Màn hình Dell UltraSharp", "2", "7500000", "15000000"),
                ("Chiết khấu thương mại (Discount 10%)", "1", "-1500000", "-1500000")
            ],
            "subtotal": "13500000",
            "tax": "1350000",
            "total": "14850000",
            "note": "Presburger integer arithmetic with negative discount line items"
        },
        # Scenario 5: Extreme Thermal Receipt Noise
        {
            "id": "HD-HARD-THERMAL-005",
            "title": "Hóa Đơn Nhiệt Siêu Thị Mờ Chữ (B5OOO, Z0000)",
            "company": companies[4],
            "items": [
                ("Vật tư linh kiện B5OOO", "10", "B5OOO", "850000")
            ],
            "subtotal": "85OOOO",
            "tax": "85OOO",
            "total": "935OOO",
            "note": "Candidate lattice combinatorial expansion resolved by SMT solver"
        }
    ]

    with zipfile.ZipFile(output_zip, "w") as zf:
        for idx, sc in enumerate(hardcore_scenarios):
            img = Image.new("RGB", (650, 850), color="#FFFFFF")
            draw = ImageDraw.Draw(img)
            
            draw.rectangle([(20, 20), (630, 830)], outline="#C00000" if "FRAUD" in sc["id"] else "#1F4E78", width=4)
            draw.text((40, 40), f"THỬ THÁCH HÓA ĐƠN: {sc['title']}", fill="#C00000" if "FRAUD" in sc["id"] else "#1F4E78")
            draw.text((40, 70), f"HÓA ĐƠN SỐ: {sc['id']}", fill="#000000")
            draw.text((40, 95), f"MST: {sc['company'][0]} - {sc['company'][1]}", fill="#000000")
            
            y = 140
            draw.text((40, y), "CHI TIẾT MẶT HÀNG / RÀNG BUỘC:", fill="#333333")
            y += 30
            for item in sc["items"]:
                draw.text((50, y), f"• {item[0]} | x{item[1]} | Giá: {item[2]} -> {item[3]} VND", fill="#000000")
                y += 25
            
            y += 20
            draw.text((40, y), f"TIỀN HÀNG (SUBTOTAL): {sc['subtotal']} VND", fill="#000000")
            draw.text((40, y + 25), f"TIỀN THUẾ (VAT): {sc['tax']} VND", fill="#000000")
            draw.text((40, y + 50), f"TỔNG THANH TOÁN (TOTAL): {sc['total']} VND", fill="#1F4E78")
            
            y += 90
            draw.text((40, y), f"💡 Ghi chú kỹ thuật: {sc['note']}", fill="#555555")
            
            fname = f"{sc['id']}.png"
            fpath = os.path.join(tmp_dir, fname)
            img.save(fpath)
            zf.write(fpath, arcname=fname)
            os.remove(fpath)

    if os.path.exists(tmp_dir):
        os.rmdir(tmp_dir)

    print(f"Successfully created {output_zip} with {len(hardcore_scenarios)} hardcore scenarios!")


if __name__ == "__main__":
    generate_hardcore_zip()
