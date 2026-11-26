#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Repo-scoped MCP server for riman-ph-incellderm-active-cream-ex-microclimate-study (stdio / FastMCP).

Remote twin: https://mcp.riman.win/mcp
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_NAME = "riman-ph-incellderm-active-cream-ex-microclimate-study"
SLUG = "ph-incellderm-active-cream-ex-microclimate-study"
DEFAULT_THEME_ID = "microclimate"
KAGGLE_DOI = "10.34740/kaggle/dsv/22383536"
HF_DOI = "10.57967/hf/11688"
SITE = "https://www.riman.win"
MCP_REMOTE = "https://mcp.riman.win/mcp"

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: pip install mcp\n"
        f"Original import error: {e}"
    )


mcp = FastMCP(REPO_NAME)


def _find_one(root: Path, pattern: str):
    hits = sorted(root.glob(pattern))
    return hits[0] if hits else None


def _load_report(root: Path | None = None) -> dict:
    root = root or REPO_ROOT
    path = _find_one(root, "*_report.json")
    if not path:
        raise FileNotFoundError(f"no *_report.json under {root}")
    return json.loads(path.read_text(encoding="utf-8"))


def _overview(doc: dict, root: Path, repo_name: str) -> dict:
    en = (doc.get("locales") or {}).get("en") or {}
    meta = doc.get("metadata") or {}
    stats = doc.get("quantitative_metrics") or {}
    theme_id = doc.get("theme_id") or DEFAULT_THEME_ID
    slug = doc.get("slug") or SLUG
    return {
        "repo_name": repo_name,
        "slug": slug,
        "theme_id": theme_id,
        "title_en": en.get("title"),
        "abstract_en": (en.get("abstract") or "")[:1200],
        "country": meta.get("country_name"),
        "product_id": meta.get("product_id"),
        "sample_size": stats.get("sample_size"),
        "overall_mean": stats.get("overall_composite_mean"),
        "top2_box_pct": stats.get("overall_top2_box_pct"),
        "portal_detail": f"{SITE}/www/en/reports/detail/{slug}.html",
        "portal_hub": f"{SITE}/www/en/reports/hub/{theme_id}.html",
        "mcp": MCP_REMOTE,
        "dois": {"kaggle": KAGGLE_DOI, "huggingface": HF_DOI},
    }


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


@mcp.tool()
def list_repos(theme_id: str = "", keyword: str = "", limit: int = 50) -> str:
    """List sibling riman-* packages. Optional theme/keyword filter."""
    parent = REPO_ROOT.parent
    theme_l = (theme_id or "").strip().lower()
    kw = (keyword or "").strip().lower()
    rows = []
    for d in sorted(parent.iterdir()):
        if not d.is_dir() or not d.name.startswith("riman-"):
            continue
        try:
            doc = _load_report(d)
        except Exception:
            continue
        tid = str(doc.get("theme_id") or "")
        if theme_l and tid.lower() != theme_l:
            continue
        en = (doc.get("locales") or {}).get("en") or {}
        blob = json.dumps({"name": d.name, "title": en.get("title"), "theme": tid}, ensure_ascii=False).lower()
        if kw and kw not in blob:
            continue
        rows.append({
            "repo_name": d.name,
            "slug": doc.get("slug"),
            "theme_id": tid,
            "title_en": en.get("title"),
            "overall_mean": (doc.get("quantitative_metrics") or {}).get("overall_composite_mean"),
        })
        if len(rows) >= max(1, int(limit)):
            break
    return json.dumps({"n": len(rows), "repos": rows, "mcp": MCP_REMOTE}, ensure_ascii=False)


@mcp.tool()
def get_repo_overview() -> str:
    """Structured overview + dual DOIs."""
    return json.dumps(_overview(_load_report(), REPO_ROOT, REPO_NAME), ensure_ascii=False, indent=2)


@mcp.tool()
def query_quantitative_csv(column: str = "", contains: str = "", limit: int = 20) -> str:
    """Filter *_quantitative.csv."""
    path = _find_one(REPO_ROOT, "*_quantitative.csv")
    if not path:
        return json.dumps({"error": "csv_not_found"})
    contains_l = (contains or "").lower()
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        for row in reader:
            if column and column not in row:
                continue
            if column:
                cell = str(row.get(column, ""))
                if contains_l and contains_l not in cell.lower():
                    continue
            elif contains_l and contains_l not in json.dumps(row, ensure_ascii=False).lower():
                continue
            rows.append(row)
            if len(rows) >= max(1, int(limit)):
                break
    return json.dumps({"file": path.name, "columns": fields, "n": len(rows), "rows": rows}, ensure_ascii=False)


@mcp.tool()
def search_multilingual_corpus(query: str = "", language: str = "", limit: int = 10) -> str:
    """Search multilingual JSONL."""
    path = _find_one(REPO_ROOT, "*_multilingual_corpus.jsonl")
    if not path:
        return json.dumps({"error": "jsonl_not_found"})
    q = (query or "").lower()
    lang = (language or "").strip()
    hits = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        if q and q not in line.lower():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            obj = {"raw": line[:2000]}
        if lang and str(obj.get("language") or "") != lang:
            continue
        hits.append(obj)
        if len(hits) >= max(1, int(limit)):
            break
    return json.dumps({"file": path.name, "n": len(hits), "hits": hits}, ensure_ascii=False)


@mcp.tool()
def compare_repos(other_repo_name: str) -> str:
    """Compare metrics with sibling riman-{slug}."""
    other = (other_repo_name or "").strip()
    other_root = REPO_ROOT.parent / other
    if not other_root.is_dir():
        return json.dumps({"error": "other_not_found", "other_repo_name": other})
    a = _overview(_load_report(REPO_ROOT), REPO_ROOT, REPO_NAME)
    b = _overview(_load_report(other_root), other_root, other)
    return json.dumps({
        "left": a,
        "right": b,
        "delta": {
            "overall_mean": _num(a.get("overall_mean")) - _num(b.get("overall_mean")),
            "top2_box_pct": _num(a.get("top2_box_pct")) - _num(b.get("top2_box_pct")),
            "sample_size": _num(a.get("sample_size")) - _num(b.get("sample_size")),
        },
        "mcp": MCP_REMOTE,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def list_repo_files() -> str:
    """List package files (excluding .git)."""
    files = []
    for p in sorted(REPO_ROOT.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            files.append(p.relative_to(REPO_ROOT).as_posix())
    return json.dumps({"repo_name": REPO_NAME, "n": len(files), "files": files}, ensure_ascii=False)


@mcp.tool()
def get_citation() -> str:
    """BibTeX + dual DOIs."""
    doc = _load_report()
    slug = doc.get("slug") or SLUG
    en = (doc.get("locales") or {}).get("en") or {}
    title = en.get("title") or slug
    bib_key = str(slug).replace("-", "_")
    detail = f"{SITE}/www/en/reports/detail/{slug}.html"
    bib = "\n".join([
        f"@article{{riman_{bib_key}_2026,",
        "  author    = {RIMAN Global Formulation \\& Market Intelligence Division},",
        f"  title     = {{{title}}},",
        "  year      = {2026},",
        "  publisher = {RIMAN Research},",
        f"  doi       = {{{KAGGLE_DOI}}},",
        f"  url       = {{{detail}}}",
        "}",
    ])
    return json.dumps({
        "bibtex": bib,
        "dois": {"kaggle": KAGGLE_DOI, "huggingface": HF_DOI},
        "portal": detail,
        "mcp": MCP_REMOTE,
    }, ensure_ascii=False, indent=2)


@mcp.resource("repo://riman-ph-incellderm-active-cream-ex-microclimate-study/report")
def report_resource() -> str:
    return json.dumps(_load_report(), ensure_ascii=False)


@mcp.resource("repo://riman-ph-incellderm-active-cream-ex-microclimate-study/citation")
def citation_resource() -> str:
    return get_citation()


if __name__ == "__main__":
    mcp.run()
