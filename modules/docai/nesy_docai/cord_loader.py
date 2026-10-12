"""
Compatibility ANLS helper and hardcoded synthetic receipt examples.
"""

import json
from typing import Dict, List, Any


class RealWorldDatasetLoader:
    """
    Historical class name retained for imports. The bundled samples are
    handwritten fixtures, not a fetched/reviewed CORD or MC-OCR dataset.
    """

    def calculate_anls(self, ground_truth: str, prediction: str, threshold: float = 0.5) -> float:
        """
        Calculates Average Normalized Levenshtein Similarity (ANLS) between ground truth and prediction strings.
        """
        g = str(ground_truth).strip().lower()
        p = str(prediction).strip().lower()

        if not g and not p:
            return 1.0
        if not g or not p:
            return 0.0

        # Calculate Levenshtein distance
        m, n = len(g), len(p)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if g[i - 1] == p[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

        dist = dp[m][n]
        max_len = max(m, n)
        nls = 1.0 - (dist / max_len)

        return nls if nls >= threshold else 0.0

    def load_cord_sample_benchmark(self) -> List[Dict[str, Any]]:
        """
        Return two synthetic fixtures. No image corpus or published split is loaded.
        """
        return [
            {
                "id": "CORD_INSPIRED_SYNTHETIC_001",
                "source_dataset": "CORD-inspired synthetic fixture (not a CORD release)",
                "evidence_scope": "synthetic_fixture",
                "image_filename": "receipt_cord_001.png",
                "ground_truth": {
                    "seller_name": "STARBUCKS COFFEE VIETNAM",
                    "seller_tax_id": "0311223344",
                    "line_items": [
                        {"description": "Caffe Latte Tall", "quantity": 1, "unit_price": 65000, "amount": 65000},
                        {"description": "Butter Croissant", "quantity": 2, "unit_price": 45000, "amount": 90000}
                    ],
                    "subtotal": 155000,
                    "tax": 15500,
                    "total": 170500
                },
                "ocr_candidate_input": {
                    "invoice_id": "CORD-001",
                    "seller_name": "STARBUCKS COFFEE VIETNAM",
                    "seller_tax_id": "0311223344",
                    "line_items": [
                        {"item_id": 1, "description": "Caffe Latte Tall", "quantity": "1", "unit_price": "65000", "amount": "65000"},
                        {"item_id": 2, "description": "Butter Croissant", "quantity": "2", "unit_price": "45OOO", "amount": "90000"}
                    ],
                    "subtotal": "155000",
                    "tax": "155OO",
                    "total": "170500"
                }
            },
            {
                "id": "MC_OCR_VN_002",
                "source_dataset": "MC-OCR-inspired synthetic fixture (not an MC-OCR release)",
                "evidence_scope": "synthetic_fixture",
                "image_filename": "mc_ocr_vn_002.png",
                "ground_truth": {
                    "seller_name": "NHÀ SÁCH PHƯƠNG NAM",
                    "seller_tax_id": "0302525123",
                    "line_items": [
                        {"description": "Sách Nghệ Thuật Sống", "quantity": 1, "unit_price": 120000, "amount": 120000},
                        {"description": "Bút Gel Bến Nghé", "quantity": 10, "unit_price": 8000, "amount": 80000}
                    ],
                    "subtotal": 200000,
                    "tax": 16000,
                    "total": 216000
                },
                "ocr_candidate_input": {
                    "invoice_id": "MCOCR-002",
                    "seller_name": "NHÀ SÁCH PHƯƠNG NAM",
                    "seller_tax_id": "0302525123",
                    "line_items": [
                        {"item_id": 1, "description": "Sách Nghệ Thuật Sống", "quantity": "1", "unit_price": "12O000", "amount": "120000"},
                        {"item_id": 2, "description": "Bút Gel Bến Nghé", "quantity": "1O", "unit_price": "8000", "amount": "80000"}
                    ],
                    "subtotal": "200000",
                    "tax": "16000",
                    "total": "216000"
                }
            }
        ]
