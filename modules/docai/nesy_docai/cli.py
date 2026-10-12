"""Inspect invoices locally; export review candidates without auto-approval."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from nesy_docai import __version__


def _export(records, path, output_format):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        with path.open("x", encoding="utf-8") as stream:
            json.dump(records, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        return
    headers = ["file", "status", "review_required", "subtotal_candidate", "tax_candidate", "total_candidate", "source_sha256"]
    rows = []
    for record in records:
        values, source = record.get("candidate_values") or {}, record.get("source") or {}
        name = source.get("filename", "")
        if name.lstrip().startswith(("=", "+", "-", "@")):
            name = "'" + name
        rows.append([name, record["status"], True, values.get("subtotal"), values.get("tax"),
                     values.get("total"), source.get("sha256", "")])
    if output_format == "csv":
        with path.open("x", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerows(rows)
    else:
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Review candidates"
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        with path.open("xb") as stream:
            workbook.save(stream)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local invoice inspection; all results require review against the source.")
    parser.add_argument("input", type=Path, help="One invoice file or a directory of XML/PDF/PNG/JPG files")
    parser.add_argument("-o", "--output", type=Path, help="New output path; existing files are never overwritten")
    parser.add_argument("-f", "--format", choices=["json", "csv", "xlsx"], default="json")
    parser.add_argument("--fields-json", action="store_true", help="Read one JSON object containing already extracted invoice fields")
    parser.add_argument("--timeout-ms", type=int, default=1000, help="Z3 time budget per invoice (1–10000 ms)")
    parser.add_argument("--max-pages", type=int, default=25, help="Maximum PDF pages to inspect (1–100)")
    parser.add_argument("--version", action="version", version=f"NeSy-DocAI {__version__} (migrated prototype)")
    args = parser.parse_args(argv)
    if args.output is None and args.format != "json":
        parser.error("CSV/Excel export requires --output.")
    if args.output and args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    if not args.input.exists():
        parser.error(f"Input does not exist: {args.input}")
    if not 1 <= args.timeout_ms <= 10000 or not 1 <= args.max_pages <= 100:
        parser.error("Use timeout-ms 1–10000 and max-pages 1–100.")
    try:
        from nesy_docai.service import DOCUMENT_EXTENSIONS, inspect_invoice_file, review_invoice_fields

        if args.fields_json:
            raw = json.loads(args.input.read_text(encoding="utf-8"))
            record = review_invoice_fields(raw, timeout_ms=args.timeout_ms)
            import hashlib
            record["source"] = {"path": str(args.input.resolve()), "filename": args.input.name,
                                "sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(), "engine": "supplied_fields"}
            records = [record]
        else:
            files = sorted(p for p in args.input.iterdir() if p.is_file() and p.suffix.lower() in DOCUMENT_EXTENSIONS) if args.input.is_dir() else [args.input]
            if not files:
                parser.error("No supported invoice files found.")
            records = []
            for path in files:
                try:
                    records.append(inspect_invoice_file(path, timeout_ms=args.timeout_ms, max_pages=args.max_pages))
                except (OSError, ValueError) as exc:
                    records.append({"status": "ERROR", "review_required": True, "error": str(exc),
                                    "source": {"path": str(path.resolve()), "filename": path.name}})
        if args.output:
            _export(records, args.output, args.format)
        else:
            print(json.dumps(records, ensure_ascii=False, indent=2))
        return 0 if all(r["status"] == "SAT" for r in records) else 2
    except ImportError as exc:
        print(f"Missing optional dependency: {exc}. Install requirements-docai.txt.", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
