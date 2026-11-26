#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local CLI aligned with RIMAN Registry MCP tools (summary|filter|compare|cite)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KAGGLE_DOI = "10.34740/kaggle/dsv/22383536"
HF_DOI = "10.57967/hf/11688"
SITE = "https://www.riman.win"
MCP = "https://mcp.riman.win/mcp"


def _find_one(root: Path, pattern: str) -> Path | None:
    hits = sorted(root.glob(pattern))
    return hits[0] if hits else None


def _load_report(root: Path | None = None) -> dict:
    root = root or REPO_ROOT
    path = _find_one(root, "*_report.json")
    if not path:
        raise FileNotFoundError(f"no *_report.json under {root}")
    return json.loads(path.read_text(encoding="utf-8"))


def _overview(doc: dict, root: Path) -> dict:
    slug = doc.get("slug")
    theme_id = doc.get("theme_id") or "ontology"
    meta = doc.get("metadata") or {}
    stats = doc.get("quantitative_metrics") or {}
    en = (doc.get("locales") or {}).get("en") or {}
    return {
        "repo_name": f"riman-{slug}",
        "repo_root": str(root),
        "slug": slug,
        "theme_id": theme_id,
        "title_en": en.get("title"),
        "abstract_en": (en.get("abstract") or "")[:1200],
        "country": meta.get("country_name"),
        "country_code": meta.get("country_code"),
        "product_id": meta.get("product_id"),
        "product_name": meta.get("product_name"),
        "sample_size": stats.get("sample_size"),
        "overall_mean": stats.get("overall_composite_mean"),
        "top2_box_pct": stats.get("overall_top2_box_pct"),
        "portal_detail": f"{SITE}/www/en/reports/detail/{slug}.html",
        "portal_hub": f"{SITE}/www/en/reports/hub/{theme_id}.html",
        "mcp": MCP,
        "dois": {"kaggle": KAGGLE_DOI, "huggingface": HF_DOI},
    }


def cmd_summary(_: argparse.Namespace) -> int:
    print(json.dumps(_overview(_load_report(), REPO_ROOT), ensure_ascii=False, indent=2))
    return 0


def cmd_filter(args: argparse.Namespace) -> int:
    column = (args.column or "").strip()
    contains = (args.contains or "").strip().lower()
    lang = (args.lang or "").strip()
    limit = max(1, int(args.limit or 20))
    shown = 0
    csv_path = _find_one(REPO_ROOT, "*_quantitative.csv")
    if csv_path:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            if column and column not in fields:
                print(f"[warn] column '{column}' not in CSV; available={fields}", file=sys.stderr)
            else:
                print(f"## CSV hits from {csv_path.name}")
                for row in reader:
                    if column:
                        cell = str(row.get(column, ""))
                        if contains and contains not in cell.lower():
                            continue
                    elif contains and contains not in json.dumps(row, ensure_ascii=False).lower():
                        continue
                    print(json.dumps(row, ensure_ascii=False))
                    shown += 1
                    if shown >= limit:
                        break
    jsonl = _find_one(REPO_ROOT, "*_multilingual_corpus.jsonl")
    if jsonl:
        print(f"## JSONL hits from {jsonl.name}")
        n = 0
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            if contains and contains not in line.lower():
                continue
            if lang:
                try:
                    obj = json.loads(line)
                    if str(obj.get("language") or "") != lang:
                        continue
                except json.JSONDecodeError:
                    if lang not in line:
                        continue
            print(line[:2000])
            n += 1
            if n >= limit:
                break
        shown += n
    if shown == 0:
        print("[info] no rows matched")
    return 0


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def cmd_compare(args: argparse.Namespace) -> int:
    other_name = (args.other or "").strip()
    other_root = REPO_ROOT.parent / other_name
    if not other_root.is_dir():
        print(f"[error] sibling not found: {other_root}", file=sys.stderr)
        return 1
    a = _overview(_load_report(REPO_ROOT), REPO_ROOT)
    b = _overview(_load_report(other_root), other_root)
    print(json.dumps({
        "left": a,
        "right": b,
        "delta": {
            "overall_mean": _num(a.get("overall_mean")) - _num(b.get("overall_mean")),
            "top2_box_pct": _num(a.get("top2_box_pct")) - _num(b.get("top2_box_pct")),
            "sample_size": _num(a.get("sample_size")) - _num(b.get("sample_size")),
        },
        "mcp": MCP,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_cite(_: argparse.Namespace) -> int:
    doc = _load_report()
    slug = doc.get("slug") or "study"
    en = (doc.get("locales") or {}).get("en") or {}
    title = en.get("title") or slug
    bib_key = str(slug).replace("-", "_")
    detail = f"{SITE}/www/en/reports/detail/{slug}.html"
    bib = f"""@article{{riman_{bib_key}_2026,
  author    = {{RIMAN Global Formulation \\& Market Intelligence Division}},
  title     = {{{title}}},
  year      = {{2026}},
  publisher = {{RIMAN Research}},
  doi       = {{{KAGGLE_DOI}}},
  url       = {{{detail}}}
}}"""
    print(json.dumps({
        "bibtex": bib,
        "dois": {"kaggle": KAGGLE_DOI, "huggingface": HF_DOI},
        "portal": detail,
        "mcp": MCP,
    }, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Query local RIMAN package (MCP-aligned)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("summary"); p.set_defaults(func=cmd_summary)
    p = sub.add_parser("filter")
    p.add_argument("--column", default="")
    p.add_argument("--contains", default="")
    p.add_argument("--lang", default="")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_filter)
    p = sub.add_parser("compare")
    p.add_argument("--other", required=True)
    p.set_defaults(func=cmd_compare)
    p = sub.add_parser("cite"); p.set_defaults(func=cmd_cite)
    args = parser.parse_args()
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
