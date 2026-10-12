"""
Từ điển từ lách luật, từ khóa mật mã & Thuật toán phân loại Heuristic
cho tin đăng đồng hồ Replica / Pass giá rẻ tại Việt Nam.
"""

import re
from typing import Dict, List, Tuple, Any

# Danh sách từ lách tên thương hiệu xa xỉ
BRAND_PATTERNS = {
    "Rolex": [
        r"\brolex\b", r"\brô\s*léx\b", r"\brô\s*leks\b", r"\br0lex\b", r"\br\.o\.l\.e\.x\b",
        r"\bsubmariner\b", r"\bdaytona\b", r"\bgmt\s*master\b", r"\bdatejust\b", r"\boyster\b", r"\bcrown\b"
    ],
    "Hublot": [
        r"\bhublot\b", r"\bhúp\s*lót\b", r"\bhúp\s*lot\b", r"\bh\.u\.b\.l\.o\.t\b", r"\bbig\s*bang\b", r"\bclassic\s*fusion\b"
    ],
    "Patek Philippe": [
        r"\bpatek\b", r"\bpa\s*ték\b", r"\bpa\s*tek\b", r"\bp\.a\.t\.e\.k\b", r"\bphilippe\b", r"\bnautilus\b", r"\baquanaut\b", r"\bptk\b"
    ],
    "Omega": [
        r"\bomega\b", r"\bo\.m\.e\.g\.a\b", r"\bomg\b", r"\bseamaster\b", r"\bspeedmaster\b", r"\bmóng\s*ngựa\b"
    ],
    "Audemars Piguet": [
        r"\baudemars\b", r"\bpiguet\b", r"\bap\b", r"\ba\.p\b", r"\broyal\s*oak\b"
    ],
    "Cartier": [
        r"\bcartier\b", r"\bcar\s*tier\b", r"\bsantos\b", r"\bballon\s*bleu\b", r"\btank\b"
    ],
    "Tudor": [
        r"\btudor\b", r"\btu\s*dor\b", r"\bt\.u\.d\.o\.r\b", r"\bblack\s*bay\b", r"\bpelagos\b"
    ],
    "GMT Watch": [
        r"\bgmt\b", r"\bgmt\s*master\b", r"\bpepsi\b", r"\bbatman\b", r"\bcoke\b", r"\bsprite\b"
    ],
    "Richard Mille": [
        r"\brichard\s*mille\b", r"\brm\b", r"\br\.m\b"
    ],
    "Casio / G-Shock": [
        r"\bcasio\b", r"\bg-?\s*shock\b", r"\bedifice\b"
    ],
    "Tissot": [
        r"\btissot\b", r"\bprx\b"
    ],
    "Seiko": [
        r"\bseiko\b", r"\bseiko\s*5\b", r"\bpresage\b"
    ]
}

# Các từ lách chỉ chất lượng rep / xưởng / bộ máy
QUALITY_SLANGS = [
    (r"\b1\s*:\s*1\b", "Rep 1:1", 40),
    (r"\b11\b", "Rep 11", 30),
    (r"\brep\s*1\s*:\s*1\b", "Rep 1:1", 50),
    (r"\bsuper\s*rep\b", "Super Rep", 50),
    (r"\breplica\b", "Replica", 50),
    (r"\bfake\b", "Fake", 50),
    (r"\bhàng\s*hk\b", "Hàng Hồng Kông", 30),
    (r"\bhồng\s*kông\b", "Hàng Hồng Kông", 25),
    (r"\bhongkong\b", "Hàng Hồng Kông", 25),
    (r"\bclean\s*(factory)?\b", "Xưởng Clean (Rep cao cấp)", 45),
    (r"\bvsf\b|\bvs\s*factory\b", "Xưởng VSF (Rep cao cấp)", 45),
    (r"\bnoob\s*(factory)?\b", "Xưởng Noob", 40),
    (r"\bewf\b|\bard\b|\b3k\b|\bzf\b", "Xưởng Rep nổi tiếng", 35),
    (r"\bmáy\s*eta\b", "Bộ máy ETA", 30),
    (r"\bmáy\s*3135\b|\bmáy\s*4130\b|\bmáy\s*3235\b", "Mã máy Clone Rep", 40),
    (r"\bmáy\s*nhật\b", "Máy Nhật", 20),
    (r"\bmáy\s*thụy\s*sĩ\b", "Máy Thụy Sĩ", 20),
    (r"\bchế\b|\bđộ\b", "Độ / Chế", 25),
    (r"\bchính\s*hãng\s*rep\b", "Chính hãng Rep", 45),
    (r"\bchất\s*lượng\s*cao\b", "Chất lượng cao", 15),
]

# Các từ khóa Pass / Thanh lý
PASS_KEYWORDS = [
    (r"\bpass\b", "Pass lại", 20),
    (r"\bpass\s*lại\b", "Pass lại", 25),
    (r"\bthanh\s*lý\b", "Thanh lý", 20),
    (r"\btrải\s*nghiệm\b", "Hàng trải nghiệm", 25),
    (r"\bđược\s*tặng\b", "Được tặng pass", 20),
    (r"\bkhông\s*dùng\b", "Không dùng pass", 15),
    (r"\bxách\s*tay\s*giá\s*mềm\b", "Xách tay giá mềm", 20),
    (r"\bgiá\s*hạt\s*dẻ\b", "Giá hạt dẻ", 15),
    (r"\bxả\s*kho\b", "Xả kho", 20),
]

# Thương hiệu xa xỉ siêu đắt (Giá hãng > 50 triệu - 2 tỷ VND)
LUXURY_BRANDS = ["Rolex", "Hublot", "Patek Philippe", "Audemars Piguet", "Richard Mille", "Cartier", "Omega", "Tudor", "GMT Watch"]


def detect_brand(text: str) -> str:
    """Xác định thương hiệu đồng hồ dựa trên tiêu đề & mô tả."""
    text_lower = text.lower()
    for brand, patterns in BRAND_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return brand
    return "Khác"


# Các từ xác nhận sản phẩm là Đồng hồ (Watch context validation)
WATCH_CONTEXT_WORDS = [
    r"\bđồng\s*hồ\b", r"\bwatch\b", r"\bautomatic\b", r"\bco\b|\bcơ\b", r"\bpin\b", r"\bquartz\b",
    r"\bsize\b", r"\bmm\b", r"\bdây\b", r"\bmặt\b", r"\bniềng\b", r"\bkhóa\b", r"\bcọc\b", r"\bmáy\b",
    r"\bchronograph\b", r"\btích\s*cót\b", r"\bchống\s*nước\b"
]

def is_watch_item(text: str) -> bool:
    """Kiểm tra xem nội dung bài đăng có thực sự thuộc ngành đồng hồ hay không."""
    text_lower = text.lower()
    for pattern in WATCH_CONTEXT_WORDS:
        if re.search(pattern, text_lower):
            return True
    return False


def classify_listing(title: str, description: str, price: int) -> Dict[str, Any]:
    """
    Phân loại tin đăng đồng hồ:
    Trả về dict gồm:
      - brand: Thương hiệu
      - confidence_score: Điểm nghi vấn Rep/Pass (0-100%)
      - matched_slangs: Các mật mã/từ lách đã tìm thấy
      - is_price_anomaly: Có phải bất thường về giá (Hàng hiệu xa xỉ giá < 15M) không
      - is_rep: True nếu confidence_score >= min_confidence
      - reasons: Danh sách lý do nghi vấn
    """
    full_text = f"{title} {description}".lower()

    # Kiểm tra xem có phải sản phẩm đồng hồ không (tránh trường hợp "Đèn Spa Omega", "Piano Rolex")
    if not is_watch_item(full_text):
        return {
            "brand": "Khác",
            "confidence_score": 0,
            "matched_slangs": [],
            "is_price_anomaly": False,
            "reasons": ["Không phải sản phẩm đồng hồ"]
        }

    brand = detect_brand(full_text)
    
    matched_slangs = []
    reasons = []
    score = 0
    
    # 1. Quét từ lách chất lượng (Quality Slangs)
    for pattern, label, weight in QUALITY_SLANGS:
        if re.search(pattern, full_text):
            if label not in matched_slangs:
                matched_slangs.append(label)
                score += weight
                reasons.append(f"Chứa từ mật mã: '{label}' (+{weight}%)")
    
    # 2. Quét từ khóa Pass / Thanh lý
    for pattern, label, weight in PASS_KEYWORDS:
        if re.search(pattern, full_text):
            if label not in matched_slangs:
                matched_slangs.append(label)
                score += weight
                reasons.append(f"Ngôn ngữ pass: '{label}' (+{weight}%)")
    
    # 3. Thuật toán phát hiện bất thường về giá (Price Anomaly Detection)
    is_price_anomaly = False
    if brand in LUXURY_BRANDS:
        # Nếu là thương hiệu xa xỉ mà giá dưới 15.000.000 VNĐ -> Chắc chắn 95% là Rep hoặc Pass Rep
        if 200000 <= price <= 15000000:
            is_price_anomaly = True
            anomaly_weight = 55
            score += anomaly_weight
            reasons.append(f"Bất thường về giá: Thương hiệu xa xỉ '{brand}' bán giá {price:,.0f} VNĐ (+{anomaly_weight}%)")
        elif price < 200000 and price > 0:
            # Giá siêu rẻ < 200k -> Rep giá rẻ chợ đêm
            score += 40
            reasons.append(f"Giá cực rẻ {price:,.0f} VNĐ (+40%)")

    # Chuẩn hóa điểm tối đa 100%
    confidence_score = min(100, score)
    
    return {
        "brand": brand,
        "confidence_score": confidence_score,
        "matched_slangs": matched_slangs,
        "is_price_anomaly": is_price_anomaly,
        "reasons": reasons
    }

