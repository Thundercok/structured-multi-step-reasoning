"""
Script to generate a large test ZIP archive containing 100 realistic invoice files
for stress-testing NeSy-DocAI batch processing.
"""

import os
import json
import zipfile
from PIL import Image, ImageDraw, ImageFont


def generate_100_invoices_zip(output_zip: str = "large_invoices_batch_100.zip"):
    print(f"Generating 100 test invoices into {output_zip}...")
    
    companies = [
        ("0312345678", "CÔNG TY TNHH THIẾT BỊ VĂN PHÒNG SÀI GÒN"),
        ("0101234567", "CÔNG TY CP THƯƠNG MẠI DỊCH VỤ AN PHÁT"),
        ("0319876543", "CÔNG TY TNHH CÔNG NGHỆ SỐ HÀI DÓN"),
        ("0305556667", "CÔNG TY TNHH THƯƠNG MẠI MINH ĐỨC"),
        ("0109998887", "CÔNG TY CP ĐIỆN MÁY VIỆT NAM"),
        ("0400112233", "CÔNG TY TNHH NÔNG SẢN ĐÀ NẮNG"),
        ("1800445566", "CÔNG TY TNHH VẬT TƯ CẦN THƠ")
    ]

    items_pool = [
        ("Bút ký cao cấp M&G", 10000),
        ("Tập vở HS 200 trang", 15000),
        ("Giấy in A4 Double A 70gsm", 45000),
        ("Chuột máy tính không dây Logitech", 120000),
        ("Bàn phím cơ AKKO 3087", 1000000),
        ("Tai nghe Bluetooth Sony", 1500000),
        ("Màn hình Dell UltraSharp 27 inch", 7500000),
        ("Ổ cứng SSD Samsung 1TB", 2200000)
    ]

    with zipfile.ZipFile(output_zip, "w") as zf:
        for idx in range(1, 101):
            inv_num = f"{idx:03d}"
            tax_id, comp_name = companies[(idx - 1) % len(companies)]
            
            # Create a lightweight synthetic invoice image
            img = Image.new("RGB", (600, 800), color="#FFFFFF")
            draw = ImageDraw.Draw(img)
            
            draw.rectangle([(20, 20), (580, 780)], outline="#1F4E78", width=3)
            draw.text((40, 40), f"HÓA ĐƠN GTGT - HD-2026-{inv_num}", fill="#000000")
            draw.text((40, 70), f"MST: {tax_id} - {comp_name[:35]}", fill="#000000")
            
            item_desc, item_price = items_pool[(idx - 1) % len(items_pool)]
            qty = (idx % 5) + 1
            amount = item_price * qty
            tax_amount = int(amount * 0.1)
            total = amount + tax_amount
            
            draw.text((40, 120), f"1. {item_desc} x{qty}: {amount:,} VND", fill="#333333")
            draw.text((40, 160), f"Tiền hàng: {amount:,} VND", fill="#333333")
            draw.text((40, 180), f"Thuế VAT (10%): {tax_amount:,} VND", fill="#333333")
            draw.text((40, 210), f"TỔNG CỘNG: {total:,} VND", fill="#1F4E78")
            
            tmp_dir = "temp_gen"
            os.makedirs(tmp_dir, exist_ok=True)
            img_filename = f"Invoice_2026_{inv_num}.png"
            img_path = os.path.join(tmp_dir, img_filename)
            img.save(img_path)
            
            zf.write(img_path, arcname=img_filename)
            os.remove(img_path)
            
        if os.path.exists("temp_gen"):
            os.rmdir("temp_gen")

    print(f"Successfully generated {output_zip} with 100 invoices!")


if __name__ == "__main__":
    generate_100_invoices_zip()
