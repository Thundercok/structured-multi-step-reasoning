"""
rat.crawler.vision_taxonomy — Apple Vision Taxonomy Mapping & Bilingual Translation Dictionary.
Maps Apple Vision classification identifiers (e.g., 'root > object > animal > dog') to rich Vietnamese
and English search terms.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

# Comprehensive mapping from common Apple Vision taxonomy identifiers/keywords to rich Vietnamese concepts
TAXONOMY_MAP: Dict[str, Dict[str, List[str]]] = {
    # 1. Animals & Pets
    "dog": {
        "en": ["dog", "puppy", "canine", "pet", "hound"],
        "vi": ["chó", "cún", "chó con", "thú cưng", "vật nuôi", "chó cưng"]
    },
    "cat": {
        "en": ["cat", "kitten", "feline", "pet"],
        "vi": ["mèo", "mèo con", "thú cưng", "vật nuôi", "mèo cưng"]
    },
    "bird": {
        "en": ["bird", "avian", "feather", "wildlife"],
        "vi": ["chim", "loài chim", "động vật", "thú hoang dã"]
    },
    "animal": {
        "en": ["animal", "wildlife", "mammal", "creature", "pet"],
        "vi": ["động vật", "thú cưng", "con vật", "vật nuôi"]
    },
    "fish": {
        "en": ["fish", "aquarium", "marine", "underwater"],
        "vi": ["cá", "bể cá", "thủy sinh", "dưới nước"]
    },

    # 2. Food, Drinks & Dining
    "food": {
        "en": ["food", "dish", "meal", "cuisine", "dining", "delicacy"],
        "vi": ["đồ ăn", "món ăn", "ẩm thực", "thức ăn", "bữa ăn", "món ngon"]
    },
    "beverage": {
        "en": ["beverage", "drink", "coffee", "tea", "cocktail", "juice"],
        "vi": ["đồ uống", "thức uống", "nước uống", "cà phê", "trà", "nước ép"]
    },
    "coffee": {
        "en": ["coffee", "espresso", "latte", "cappuccino", "cafe"],
        "vi": ["cà phê", "cafe", "quán cà phê"]
    },
    "pizza": {
        "en": ["pizza", "fast food", "italian food"],
        "vi": ["bánh pizza", "pizza", "đồ ăn nhanh"]
    },
    "dessert": {
        "en": ["dessert", "cake", "sweet", "pastry", "bakery", "ice cream"],
        "vi": ["tráng miệng", "bánh ngọt", "bánh kem", "đồ ngọt", "kem"]
    },
    "fruit": {
        "en": ["fruit", "healthy", "fresh", "produce"],
        "vi": ["trái cây", "hoa quả", "quả tươi"]
    },

    # 3. Nature, Landscapes & Outdoors
    "sunset": {
        "en": ["sunset", "dusk", "evening", "twilight", "golden hour", "sundown"],
        "vi": ["hoàng hôn", "chiều tà", "lặn", "mặt trời lặn", "buổi chiều", "bầu trời hoàng hôn"]
    },
    "sunrise": {
        "en": ["sunrise", "dawn", "morning", "sunup"],
        "vi": ["bình minh", "rạng đông", "buổi sáng", "mặt trời mọc"]
    },
    "beach": {
        "en": ["beach", "sea", "ocean", "coast", "shore", "sand", "seaside"],
        "vi": ["biển", "bãi biển", "bờ biển", "đại dương", "bãi cát", "sóng biển", "du lịch biển"]
    },
    "mountain": {
        "en": ["mountain", "hill", "peak", "summit", "valley", "highland"],
        "vi": ["núi", "núi rừng", "đồi núi", "đỉnh núi", "thung lũng", "cao nguyên"]
    },
    "sky": {
        "en": ["sky", "cloud", "blue sky", "atmosphere"],
        "vi": ["bầu trời", "mây", "trời xanh", "không gian"]
    },
    "flower": {
        "en": ["flower", "flora", "bloom", "blossom", "garden", "plant"],
        "vi": ["hoa", "bông hoa", "vườn hoa", "cây cối", "thực vật"]
    },
    "forest": {
        "en": ["forest", "trees", "woods", "jungle", "nature"],
        "vi": ["rừng", "cây cối", "rừng cây", "thiên nhiên", "cây xanh"]
    },

    # 4. Documents, Receipts & Finance
    "receipt": {
        "en": ["receipt", "bill", "invoice", "payment", "transaction", "slip"],
        "vi": ["hóa đơn", "biên lai", "phiếu thu", "thanh toán", "chuyển khoản", "sao kê", "hóa đơn đỏ"]
    },
    "document": {
        "en": ["document", "paper", "text", "form", "contract", "certificate"],
        "vi": ["tài liệu", "văn bản", "giấy tờ", "hợp đồng", "chứng chỉ", "đơn từ"]
    },
    "id_card": {
        "en": ["id card", "identity", "passport", "driver license", "card", "credential"],
        "vi": ["căn cước", "cccd", "chứng minh nhân dân", "cmnd", "hộ chiếu", "bằng lái xe", "thẻ nhân viên"]
    },
    "diagram": {
        "en": ["diagram", "chart", "graph", "plot", "infographic", "flowchart", "presentation"],
        "vi": ["biểu đồ", "đồ thị", "sơ đồ", "bảng biểu", "slide", "thuyết trình", "thống kê"]
    },
    "qr_code": {
        "en": ["qr code", "barcode", "scan", "code"],
        "vi": ["mã qr", "mã vạch", "quét mã", "qr thanh toán"]
    },

    # 5. Technology, Screens & UI
    "screenshot": {
        "en": ["screenshot", "screen capture", "screen", "display", "monitor", "software", "ui"],
        "vi": ["chụp màn hình", "ảnh chụp màn hình", "màn hình", "giao diện", "ứng dụng", "web"]
    },
    "computer": {
        "en": ["computer", "laptop", "pc", "macbook", "keyboard", "desk"],
        "vi": ["máy tính", "laptop", "macbook", "bàn phím", "bàn làm việc"]
    },
    "phone": {
        "en": ["phone", "smartphone", "mobile", "iphone", "screen"],
        "vi": ["điện thoại", "smartphone", "iphone", "màn hình điện thoại"]
    },

    # 6. People & Portraits
    "person": {
        "en": ["person", "people", "human", "face", "portrait", "selfie", "crowd"],
        "vi": ["người", "con người", "khuôn mặt", "chân dung", "ảnh tự sướng", "selfie", "đám đông"]
    },
    "smile": {
        "en": ["smile", "happy", "smiling", "joy", "laugh"],
        "vi": ["nụ cười", "cười", "vui vẻ", "hạnh phúc"]
    },

    # 7. Vehicles & Transportation
    "car": {
        "en": ["car", "automobile", "vehicle", "sedan", "suv", "drive"],
        "vi": ["xe hơi", "ô tô", "xe ô tô", "xe con", "xe cộ"]
    },
    "motorcycle": {
        "en": ["motorcycle", "motorbike", "scooter", "bike"],
        "vi": ["xe máy", "xe mô tô", "xe gắn máy"]
    },
    "bicycle": {
        "en": ["bicycle", "bike", "cycling"],
        "vi": ["xe đạp", "đạp xe"]
    },
    "airplane": {
        "en": ["airplane", "plane", "aircraft", "flight", "aviation", "airport"],
        "vi": ["máy bay", "phi cơ", "chuyến bay", "sân bay", "hàng không"]
    },

    # 8. Architecture & Urban
    "building": {
        "en": ["building", "architecture", "house", "skyscraper", "city", "street"],
        "vi": ["tòa nhà", "kiến trúc", "ngôi nhà", "nhà cửa", "thành phố", "đường phố"]
    },
    "room": {
        "en": ["room", "interior", "living room", "bedroom", "office", "indoor"],
        "vi": ["căn phòng", "nội thất", "phòng khách", "phòng ngủ", "văn phòng", "trong nhà"]
    }
}


def expand_taxonomy_labels(raw_labels: List[str]) -> Tuple[List[str], List[str]]:
    """
    Expand raw Apple Vision taxonomy identifiers into comprehensive English and Vietnamese keywords.
    Returns (english_keywords, vietnamese_keywords).
    """
    en_terms: Set[str] = set()
    vi_terms: Set[str] = set()

    for raw in raw_labels:
        clean_raw = raw.lower().replace("_", " ").strip()
        # Split taxonomy hierarchy paths if present e.g. "animal > mammal > dog"
        parts = [p.strip() for p in clean_raw.replace(">", " ").replace("/", " ").split() if p.strip()]

        for part in parts:
            en_terms.add(part)
            for key, term_dict in TAXONOMY_MAP.items():
                if key == part or key in part or part in key:
                    en_terms.update(term_dict["en"])
                    vi_terms.update(term_dict["vi"])

    return sorted(list(en_terms)), sorted(list(vi_terms))
