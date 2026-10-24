import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import time, unicodedata, statistics
try:
    from contradiction_auditor import audit_answer, build_index, V
except ImportError:
    from rat.engine.contradiction_auditor import audit_answer, build_index, V

SRC = "Hệ chính quy: tối đa 6 năm.\nHệ vừa làm vừa học: tối đa 8 năm.\nSV cần TOEIC tối thiểu 600."
KB = build_index(SRC)
def g(a, q=None):
    r = audit_answer(a, KB, q); return r.gate, [(f.result.verdict.name, f.result.reason) for f in r.findings]
A = "Hệ chính quy được học tối đa 7 năm."
print("NFC     ", g(A))
print("NFD     ", g(unicodedata.normalize("NFD", A)))
print("NFD src ", audit_answer(A, build_index(unicodedata.normalize("NFD", SRC))).gate)
print("CRLF    ", g("Hệ chính quy:\r\n- Tối đa 7 năm.\r\n- Tối thiểu TOEIC 600.\r\n"))
print("NBSP    ", g("Hệ chính quy được học tối đa 7 năm."))
print("empty   ", g(""), g("   \n\n"))
print("nested  ", g("Hệ chính quy:\n  - Thời gian:\n    - Tối đa 7 năm."))
long = ("Quy chế rất dài. " * 50 + "Hệ chính quy: tối đa 6 năm.\n- Tối thiểu TOEIC 600.\n") * 10
ts = []
for _ in range(50):
    t = time.perf_counter(); audit_answer(long, KB, "full-time"); ts.append((time.perf_counter() - t) * 1e3)
print(f"len={len(long)} chars  audit_answer median {statistics.median(ts):.2f} ms  max {max(ts):.2f} ms")
short = "Hệ chính quy tối đa 6 năm. TOEIC tối thiểu 600."
ts = []
for _ in range(200):
    t = time.perf_counter(); audit_answer(short, KB); ts.append((time.perf_counter() - t) * 1e3)
print(f"short answer median {statistics.median(ts):.3f} ms")
