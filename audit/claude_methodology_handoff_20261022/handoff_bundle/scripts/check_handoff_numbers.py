"""Cross-check of HANDOFF.md against the archived raw outputs.  TEXT MATCHING ONLY: no simulation, no model, no randomness.

A line of HANDOFF.md that carries a source tag  [[file.txt:3]]  [[file.txt:3-8]]  [[a.txt:2,4; b.txt:7]]  is checked:
every decimal-COMMA number written on that line (outside {...}, which marks numbers derived by hand from raw numbers) must occur as a number
in the cited raw line(s) of outputs/<file> (or legacy/<file>).
  - decimal comma (HANDOFF) <-> decimal point (raw);
  - an explicit sign in HANDOFF (+, -, U+2212) must equal the sign written in the raw line;
  - percent <-> fraction is accepted (3,16 <-> 0.0316) for the files that print fractions (og_*, ce_*, ct_*, ct2_*).
Lines (outside code fences) that contain decimal-comma numbers but NO tag are listed as UNTAGGED: those numbers are NOT cross-checked here.
Exit code 1 if any tagged number is not found.
usage: python3.12 -I check_handoff_numbers.py HANDOFF.md BUNDLE_DIR"""
import os
import re
import sys

TAG = re.compile(r"\[\[([\w.]+:[\d,\- ]+(?:;\s*[\w.]+:[\d,\- ]+)*)\]\]")   # only well-formed tags; prose like [[file:dòng]] is ignored
DERIVED = re.compile(r"\{[^{}]*\}")
NUM = re.compile(r"(?<![\d,.])([+\-−])?(\d+,\d+)(?!\d)(?!,\d)")      # a trailing prose comma ("0,144, E3") does not hide the number


def load(bundle, name):
    for d in ("outputs", "legacy"):
        p = os.path.join(bundle, d, name)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return f.read().split("\n")
    raise FileNotFoundError(name)


def parse_tag(tag):
    refs = []
    for part in tag.split(";"):
        name, _, spec = part.strip().partition(":")
        lines = set()
        for s in spec.split(","):
            s = s.strip()
            if "-" in s:
                a, b = s.split("-")
                lines.update(range(int(a), int(b) + 1))
            elif s:
                lines.add(int(s))
        refs.append((name.strip(), lines))
    return refs


def occurs(tok, sign, raw):
    d = len(tok.split(",")[1])
    v = float(tok.replace(",", ".")) / 100
    f = "%.*f" % (d + 2, v)
    cands = {tok.replace(",", "."), f, f.rstrip("0")}
    cands |= {c[1:] for c in list(cands) if c.startswith("0.")}          # raw may print '.667' / 'mu.78' without the leading zero
    sg =r"\+" if sign == "+" else ("-" if sign in ("-", "−") else r"[+\-]?")
    return any(re.search(r"(?<![\d.])" + sg + re.escape(c) + r"(?!\d)", raw) for c in cands)


def main(md_path, bundle):
    with open(md_path, encoding="utf-8") as f:
        md = f.read().split("\n")
    fence, checked, ntok, fails, untagged = False, 0, 0, [], []
    for i, line in enumerate(md, 1):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        tags = TAG.findall(line)
        text = DERIVED.sub(" ", TAG.sub(" ", line))
        toks = [(m.group(1), m.group(2)) for m in NUM.finditer(text)]
        if not tags:
            if toks:
                untagged.append((i, line.strip()[:110]))
            continue
        raw = []
        for t in tags:
            for name, lines in parse_tag(t):
                data = load(bundle, name)
                raw.extend(data[k - 1] for k in sorted(lines) if 0 < k <= len(data))
        raw = "\n".join(raw)
        checked += 1
        for sign, tok in toks:
            ntok += 1
            if not occurs(tok, sign, raw):
                fails.append((i, (sign or "") + tok, line.strip()[:110]))
    print("tagged lines checked: %d | numeric tokens checked: %d | NOT FOUND: %d | untagged lines with decimal-comma numbers: %d" % (
        checked, ntok, len(fails), len(untagged)))
    for i, tok, ln in fails:
        print("  NOT FOUND  HANDOFF.md:%d  token %s  | %s" % (i, tok, ln))
    for i, ln in untagged:
        print("  UNTAGGED   HANDOFF.md:%d | %s" % (i, ln))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
