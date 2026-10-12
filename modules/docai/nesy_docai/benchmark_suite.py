"""
Synthetic fixture smoke evaluator; not a measured OCR benchmark.
"""

import time
from typing import Dict, List, Any
from nesy_docai import VisionPerceptionEngine, SymbolicSolverEngine
from nesy_docai.cord_loader import RealWorldDatasetLoader


class InvoiceBenchmarkSuite:
    def __init__(self):
        self.vision = VisionPerceptionEngine()
        self.solver = SymbolicSolverEngine(vision_engine=self.vision)
        self.real_loader = RealWorldDatasetLoader()

    def generate_synthetic_benchmark_dataset(self, count: int = 50) -> List[Dict[str, Any]]:
        dataset = []
        for i in range(1, count + 1):
            tier = (i % 4) + 1
            qty1, price1 = 2, 10000
            qty2, price2 = 5, 15000
            subtotal = (qty1 * price1) + (qty2 * price2)
            tax = 9500
            total = subtotal + tax

            ground_truth = {
                "invoice_id": f"VIE-BENCH-{i:03d}",
                "line_items": [
                    {"quantity": qty1, "unit_price": price1, "amount": qty1 * price1},
                    {"quantity": qty2, "unit_price": price2, "amount": qty2 * price2}
                ],
                "subtotal": subtotal,
                "tax": tax,
                "total": total
            }

            raw_input = {
                "invoice_id": f"VIE-BENCH-{i:03d}",
                "line_items": [
                    {"item_id": 1, "description": "Bút ký", "quantity": "2", "unit_price": "1O000", "amount": "20000"},
                    {"item_id": 2, "description": "Tập vở", "quantity": "5", "unit_price": "15000", "amount": "75000"}
                ],
                "subtotal": "95000", "tax": "95OO", "total": "104500"
            }

            dataset.append({
                "id": i,
                "tier": f"Tier-{tier}",
                "ground_truth": ground_truth,
                "raw_input": raw_input
            })

        return dataset

    def run_full_evaluation(self, num_samples: int = 50) -> Dict[str, Any]:
        if not isinstance(num_samples, int) or isinstance(num_samples, bool) or num_samples < 1:
            raise ValueError("num_samples must be a positive integer.")
        synthetic_dataset = self.generate_synthetic_benchmark_dataset(num_samples)
        real_samples = self.real_loader.load_cord_sample_benchmark()

        correct_sat = 0
        sat_count = 0
        total_time_ms = 0.0
        anls_scores = []

        # 1. Run Synthetic Evaluation
        for sample in synthetic_dataset:
            raw_input = sample["raw_input"]
            start_t = time.time()
            result = self.solver.solve_and_verify(raw_input)
            latency = (time.time() - start_t) * 1000
            total_time_ms += latency

            if result.get("audit_status") == "VERIFIED_SAT":
                sat_count += 1
                gt = sample["ground_truth"]
                if (result.get("subtotal") == gt["subtotal"] and
                    result.get("tax") == gt["tax"] and
                    result.get("total") == gt["total"]):
                    correct_sat += 1

                # Calculate ANLS on total amount string
                anls = self.real_loader.calculate_anls(str(gt["total"]), str(result.get("total")))
                anls_scores.append(anls)
            else:
                anls_scores.append(0.0)

        # 2. Two additional hardcoded synthetic examples (no OCR call).
        real_correct = 0
        for sample in real_samples:
            raw_input = sample["ocr_candidate_input"]
            gt = sample["ground_truth"]

            result = self.solver.solve_and_verify(raw_input)
            if result.get("audit_status") == "VERIFIED_SAT":
                if result.get("total") == gt["total"]:
                    real_correct += 1
                anls = self.real_loader.calculate_anls(str(gt["total"]), str(result.get("total")))
                anls_scores.append(anls)
            else:
                anls_scores.append(0.0)

        mean_anls = sum(anls_scores) / len(anls_scores) if anls_scores else 0.0
        accuracy = (correct_sat / num_samples) * 100
        real_accuracy = (real_correct / len(real_samples)) * 100
        avg_latency = total_time_ms / num_samples

        return {
            "evidence_scope": "synthetic_smoke",
            "ocr_executed": False,
            "unique_synthetic_problem_count": 1,
            "additional_hardcoded_example_count": len(real_samples),
            "timing_scope": "candidate_generation_and_solver_only",
            "dataset_size": num_samples,
            "pure_ocr_baseline_acc": None,
            "nesy_docai_acc": accuracy,
            "synthetic_example_total_accuracy": real_accuracy,
            "mean_anls_score": round(mean_anls, 4),
            "lcr_rate": sat_count / num_samples * 100,
            "stp_rate": None,
            "avg_latency_ms": round(avg_latency, 2)
        }
