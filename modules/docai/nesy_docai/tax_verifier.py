"""
Tax Master Data Verifier Module with Modulo-31 Checksum Validation
"""

from typing import Dict, Any
from nesy_docai.fraud_checker import VietnameseTaxIDValidator


class TaxMasterDataVerifier:
    def __init__(self):
        self.validator = VietnameseTaxIDValidator()
        self.tax_database = {
            "0312345678": {
                "company_name": "CÔNG TY TNHH THIẾT BỊ VĂN PHÒNG SÀI GÒN",
                "status": "ACTIVE_OPERATING",
                "address": "123 Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh",
                "tax_authority": "Chi cục Thuế Quận 1"
            },
            "0101234567": {
                "company_name": "CÔNG TY CP THƯƠNG MẠI DỊCH VỤ AN PHÁT",
                "status": "ACTIVE_OPERATING",
                "address": "45 Lý Thường Kiệt, Quận Hoàn Kiếm, Hà Nội",
                "tax_authority": "Chi cục Thuế Hoàn Kiếm"
            }
        }

    def verify_tax_id(self, tax_id: str) -> Dict[str, Any]:
        """
        Cross-verifies seller tax ID format, Modulo-31 checksum, and GDT registry status.
        """
        clean_id = str(tax_id).strip().replace("-", "")
        mst_valid, mst_msg = self.validator.validate_mst(clean_id)

        record = self.tax_database.get(clean_id)
        if record:
            return {
                "verified": mst_valid,
                "tax_id": clean_id,
                "company_name": record["company_name"],
                "status": record["status"],
                "address": record["address"],
                "verification_message": "Tax ID active and operating legally." if mst_valid else mst_msg
            }

        return {
            "verified": mst_valid,
            "tax_id": clean_id,
            "status": "VALID_MST_UNREGISTERED" if mst_valid else "INVALID_MST_CHECKSUM",
            "verification_message": "MST Modulo-31 valid." if mst_valid else mst_msg
        }
