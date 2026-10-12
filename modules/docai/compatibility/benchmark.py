"""
Compatibility synthetic smoke runner. Does not run OCR or load a real corpus.
"""

from nesy_docai.benchmark_suite import InvoiceBenchmarkSuite


def main():
    suite = InvoiceBenchmarkSuite()
    metrics = suite.run_full_evaluation(num_samples=50)

    print("=" * 60)
    print("  NeSy-DocAI SYNTHETIC SMOKE (repeated fixture; not 50 independent invoices)")
    print("=" * 60)
    print(f"  - Repeated synthetic rows:             {metrics['dataset_size']}")
    print("  - OCR baseline:                        unmeasured")
    print(f"  - Synthetic candidate totals matched: {metrics['nesy_docai_acc']:.1f}%")
    print(f"  - Logic & Arithmetic Consistency (LCR): {metrics['lcr_rate']:.1f}%")
    print("  - Automatic approval:                  unavailable; review required")
    print(f"  - Candidate generation + Z3 time:      {metrics['avg_latency_ms']:.2f} ms / fixture")
    print("=" * 60)


if __name__ == "__main__":
    main()
