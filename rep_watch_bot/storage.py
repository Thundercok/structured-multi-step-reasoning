"""
Quản lý lưu trữ SQLite, chống trùng lặp dữ liệu và xuất báo cáo CSV / JSON / Excel.
"""

import os
import sqlite3
import json
import pandas as pd
from typing import List, Optional
from models import WatchListing


class StorageManager:
    def __init__(self, db_path: str = "data/rep_watches.db"):
        self.db_path = db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Khởi tạo bảng SQLite lưu trữ listing đồng hồ."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS listings (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    price INTEGER,
                    source TEXT,
                    brand TEXT,
                    description TEXT,
                    url TEXT,
                    image_url TEXT,
                    location TEXT,
                    seller_name TEXT,
                    seller_phone TEXT,
                    confidence_score INTEGER,
                    matched_slangs TEXT,
                    is_price_anomaly INTEGER,
                    created_at TEXT
                )
            """)
            conn.commit()

    def is_new(self, listing_id: str) -> bool:
        """Kiểm tra tin đăng đã tồn tại trong DB chưa."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM listings WHERE id = ?", (listing_id,))
            return cursor.fetchone() is None

    def save_listing(self, listing: WatchListing) -> bool:
        """Lưu tin mới vào DB. Trả về True nếu lưu mới thành công, False nếu tin đã tồn tại."""
        if not self.is_new(listing.id):
            return False

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO listings (
                    id, title, price, source, brand, description, url, image_url,
                    location, seller_name, seller_phone, confidence_score,
                    matched_slangs, is_price_anomaly, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                listing.id,
                listing.title,
                listing.price,
                listing.source,
                listing.brand,
                listing.description,
                listing.url,
                listing.image_url,
                listing.location,
                listing.seller_name,
                listing.seller_phone,
                listing.confidence_score,
                json.dumps(listing.matched_slangs, ensure_ascii=False),
                1 if listing.is_price_anomaly else 0,
                listing.created_at
            ))
            conn.commit()
            return True

    def get_all_listings(self) -> List[WatchListing]:
        """Lấy toàn bộ dữ liệu tin đã lưu trong DB."""
        listings = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM listings ORDER BY created_at DESC")
            rows = cursor.fetchall()
            for r in rows:
                slangs = json.loads(r[12]) if r[12] else []
                listings.append(WatchListing(
                    id=r[0],
                    title=r[1],
                    price=r[2],
                    source=r[3],
                    brand=r[4],
                    description=r[5],
                    url=r[6],
                    image_url=r[7],
                    location=r[8],
                    seller_name=r[9],
                    seller_phone=r[10],
                    confidence_score=r[11],
                    matched_slangs=slangs,
                    is_price_anomaly=bool(r[13]),
                    created_at=r[14]
                ))
        return listings

    def export_data(self, output_dir: str = "output", format_type: str = "csv") -> str:
        """Xuất báo cáo dữ liệu tin cào ra CSV / Excel / JSON."""
        os.makedirs(output_dir, exist_ok=True)
        listings = self.get_all_listings()
        if not listings:
            return ""

        data = [l.to_dict() for l in listings]
        df = pd.DataFrame(data)

        if format_type in ("excel", "xlsx"):
            filepath = os.path.join(output_dir, "rep_watches_report.xlsx")
            df.to_excel(filepath, index=False, engine="openpyxl")
        elif format_type == "json":
            filepath = os.path.join(output_dir, "rep_watches_report.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            filepath = os.path.join(output_dir, "rep_watches_report.csv")
            df.to_csv(filepath, index=False, encoding="utf-8-sig")

        return filepath
