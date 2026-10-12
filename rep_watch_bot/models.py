"""
Data Model chuẩn hóa Pydantic v2 cho thông tin Listing đồng hồ cào được.
"""

from datetime import datetime
from typing import List, Dict, Any
from pydantic import BaseModel, Field, computed_field


class WatchListing(BaseModel):
    id: str = Field(description="Unique ID (Hash hoặc ID bài đăng)")
    title: str = Field(description="Tiêu đề bài đăng")
    price: int = Field(description="Giá bán (VND)")
    url: str = Field(description="Đường dẫn tới bài đăng gốc")
    source: str = Field(description="Nguồn cào (Chợ Tốt, WebRep, Facebook)")
    brand: str = Field(default="Khác", description="Thương hiệu (Rolex, Hublot, Patek...)")
    description: str = Field(default="", description="Mô tả chi tiết bài đăng")
    image_url: str = Field(default="", description="Link ảnh sản phẩm")
    location: str = Field(default="Việt Nam", description="Địa điểm / Khu vực")
    seller_name: str = Field(default="Người bán", description="Tên người bán / Cửa hàng")
    seller_phone: str = Field(default="", description="Số điện thoại liên hệ")
    confidence_score: int = Field(default=0, description="Điểm nghi vấn Rep (0 - 100%)")
    matched_slangs: List[str] = Field(default_factory=list, description="Danh sách từ lách đã bắt")
    is_price_anomaly: bool = Field(default=False, description="Bất thường về giá")
    created_at: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        description="Thời gian tạo bản ghi"
    )

    @computed_field
    @property
    def formatted_price(self) -> str:
        """Định dạng giá VND hiển thị đẹp (Ví dụ: 1,500,000 VNĐ hoặc Thương lượng)."""
        if self.price <= 0:
            return "Thỏa thuận / Liên hệ"
        return f"{self.price:,.0f} VNĐ"

    def to_dict(self) -> Dict[str, Any]:
        """Tạo dictionary chuẩn dùng cho xuất báo cáo CSV/Excel/JSON."""
        return {
            "id": self.id,
            "title": self.title,
            "brand": self.brand,
            "price": self.price,
            "formatted_price": self.formatted_price,
            "confidence_score": f"{self.confidence_score}%",
            "matched_slangs": ", ".join(self.matched_slangs),
            "is_price_anomaly": "Có" if self.is_price_anomaly else "Không",
            "location": self.location,
            "seller_name": self.seller_name,
            "seller_phone": self.seller_phone,
            "url": self.url,
            "image_url": self.image_url,
            "source": self.source,
            "created_at": self.created_at
        }
