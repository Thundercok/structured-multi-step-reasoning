"""
Scientific Benchmark Evaluator Runner for nesy-docai
Evaluates ANLS, Field F1, STP Rate, and Logic Consistency Rate (LCR).
"""

from nesy_docai.benchmark_suite import InvoiceBenchmarkSuite


def main():
    suite = InvoiceBenchmarkSuite()
    metrics = suite.run_full_evaluation(num_samples=50)

    print("=" * 60)
    print("  VIE-Invoice Benchmark Evaluation Summary (50 Invoices)")
    print("=" * 60)
    print(f"  - Dataset Size:                        {metrics['dataset_size']} Invoices (4 Difficulty Tiers)")
    print(f"  - Pure Neural / OCR Baseline Accuracy: {metrics['pure_ocr_baseline_acc']:.1f}%")
    print(f"  - NeSy-DocAI System 2 (Z3) Accuracy:   {metrics['nesy_docai_acc']:.1f}%")
    print(f"  - Logic & Arithmetic Consistency (LCR): {metrics['lcr_rate']:.1f}%")
    print(f"  - Straight-Through Processing (STP):    {metrics['stp_rate']:.1f}%")
    print(f"  - Average Z3 Resolution Latency:       {metrics['avg_latency_ms']:.2f} ms / invoice")
    print("=" * 60)


if __name__ == "__main__":
    main()
