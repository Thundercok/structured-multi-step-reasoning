"""Probe: the four edge bugs from the dossier (Mục 0) + span/annotation sanity. Prints raw output."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

try:
    from contradiction_auditor import audit_answer, atoms, build_index
except ImportError:
    from rat.engine.contradiction_auditor import audit_answer, atoms, build_index

KB = build_index("""Điều 12. Thời gian học tập
Hệ chính quy: thời gian tối đa là 6 năm.
Hệ vừa làm vừa học: thời gian tối đa là 8 năm.
Điều kiện tốt nghiệp: SV phải tích lũy tối thiểu 120 tín chỉ, CPA tối thiểu 2.0 và TOEIC tối thiểu 600.
SV có CPA dưới 1,2 bị buộc thôi học.""")

CASES = [
    ("1 ext-name", "Đối với hệ chính quy chất lượng cao: tối thiểu TOEIC 600.", None),
    ("2 inline canary", "Đối với hệ liên kết quốc tế, tối thiểu TOEIC 600.", None),
    ("3a hệ 4,5 năm", "Đối với hệ 4,5 năm: tối đa 10 năm.", None),
    ("3b hệ 5 năm", "Hệ 5 năm: SV phải tích lũy tối thiểu 150 tín chỉ.", None),
    ("3c hệ 4 scale", "SV cần CPA tối thiểu 2.0 theo hệ 4.", None),
    ("3d hệ 10 scale", "SV đạt CPA 2.0 trên hệ 10 thì tốt nghiệp.", None),
    ("4 evasion", "Đối với hệ đại trà: tối đa 10 năm.", "full-time"),
    ("4b evasion+addressed", "Hệ chính quy: tối đa 6 năm. Đối với hệ đại trà: tối đa 10 năm.", "full-time"),
    ("4c evasion ok-value", "Đối với hệ đại trà: tối đa 6 năm.", "full-time"),
]
for name, ans, q in CASES:
    r = audit_answer(ans, KB, q)
    print(f"{name:22} gate={r.gate:10}",
          [(f.result.verdict.name, f.result.reason, f.tup.condition if f.tup else None) for f in r.findings])

print("\n-- spans (slice of ORIGINAL text) --")
ans = "**Hệ chính quy:**\n- Tối đa 6 năm.\n- Tối thiểu TOEIC 600 (tương đương 5.5 IELTS).\nHệ liên kết quốc tế: tối đa 10 năm."
for a in atoms(ans):
    print(repr(ans[a.start:a.end]), a.scope_src, repr(ans[a.scope_start:a.scope_end]) if a.scope_start >= 0 else None)
r = audit_answer(ans, KB, "full-time")
print([(x.kind, ans[x.start:x.end], x.anchor) for x in r.annotations])
print(r.summary["note"])
