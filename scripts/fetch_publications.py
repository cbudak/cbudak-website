#!/usr/bin/env python3
"""
Fetch publications from Semantic Scholar API and save to publications.json.

Semantic Scholar is free, requires no API key, and works reliably in CI
environments (unlike Google Scholar which blocks datacenter IPs).

Papers not yet indexed by Semantic Scholar can be added manually to
publications_extra.json — they are merged in automatically every run.

Run manually:
    pip install -r scripts/requirements.txt
    python scripts/fetch_publications.py

Or triggered automatically by the GitHub Action every two weeks.
"""

import json
import re
import time
import sys
import os
import requests

AUTHOR_NAME   = "Ceren Budak"
AUTHOR_ID     = "1759771"   # Semantic Scholar ID — correct profile (70 papers)
OUTPUT_PATH   = os.path.join(os.path.dirname(__file__), "..", "publications.json")
EXTRA_PATH    = os.path.join(os.path.dirname(__file__), "..", "publications_extra.json")

# Exact titles to exclude (correction notices, errata, mis-attributed entries).
# Add lowercase titles here to permanently suppress them.
BLOCKLIST = {
    "correction",
    "immunet : improved immunization of children through cellular network technology",
    "a study on vlsi on-line stability detectors",
    "aes on gpu: a cuda implementation",
    "mind your ps and vs: a perspective on the challenges of big data management and privacy concerns",
    "gaussian elimination based algorithms on the gpu",  # duplicate of "solving path problems on the gpu"
}

PAPERS_URL  = "https://api.semanticscholar.org/graph/v1/author/{author_id}/papers"
PAPER_FIELDS = (
    "title,authors,venue,year,abstract,"
    "citationCount,externalIds,openAccessPdf"
)

HEADERS = {"User-Agent": "cbudak-website-publications-bot/1.0"}


def fetch_all_papers(author_id: str) -> list:
    papers, offset, limit = [], 0, 100
    while True:
        resp = requests.get(
            PAPERS_URL.format(author_id=author_id),
            params={"fields": PAPER_FIELDS, "limit": limit, "offset": offset},
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        data  = resp.json()
        batch = data.get("data", [])
        papers.extend(batch)
        print(f"  Fetched {len(papers)} papers so far…")
        if len(batch) < limit:
            break
        offset += limit
        time.sleep(1)
    return papers


def normalize(paper: dict) -> dict:
    ext_ids     = paper.get("externalIds") or {}
    open_access = paper.get("openAccessPdf") or {}
    paper_id    = paper.get("paperId", "")

    # Prefer DOI → arXiv → Semantic Scholar page
    if ext_ids.get("DOI"):
        url = f"https://doi.org/{ext_ids['DOI']}"
    elif ext_ids.get("ArXiv"):
        url = f"https://arxiv.org/abs/{ext_ids['ArXiv']}"
    elif paper_id:
        url = f"https://www.semanticscholar.org/paper/{paper_id}"
    else:
        url = ""

    eprint_url = open_access.get("url", "")
    authors    = ", ".join(a["name"] for a in (paper.get("authors") or []))

    return {
        "title":      paper.get("title", ""),
        "authors":    authors,
        "venue":      paper.get("venue", "") or "",
        "year":       str(paper.get("year", "")) if paper.get("year") else "",
        "abstract":   paper.get("abstract", "") or "",
        "url":        url,
        "eprint_url": eprint_url,
        "citations":  paper.get("citationCount", 0) or 0,
    }


def title_key(title: str) -> str:
    """Normalize title for deduplication — lowercase, alphanumeric only."""
    return re.sub(r"[^a-z0-9]", "", title.lower())


def merge_extra(publications: list) -> list:
    """Merge publications_extra.json, skipping papers already in Semantic Scholar."""
    extra_path = os.path.normpath(EXTRA_PATH)
    if not os.path.exists(extra_path):
        return publications

    with open(extra_path, encoding="utf-8") as f:
        extra = json.load(f)

    ss_keys = {title_key(p["title"]) for p in publications}
    added = 0
    for p in extra:
        key = title_key(p.get("title", ""))
        if key and key not in ss_keys:
            publications.append(p)
            ss_keys.add(key)
            added += 1

    if added:
        print(f"  Merged {added} extra papers from publications_extra.json")
    return publications


def fetch_publications() -> bool:
    print(f"Using Semantic Scholar author ID: {AUTHOR_ID} ({AUTHOR_NAME})")
    print("Fetching papers…")
    try:
        raw = fetch_all_papers(AUTHOR_ID)
    except Exception as e:
        print(f"Error fetching papers: {e}")
        return False

    publications = [
        normalize(p) for p in raw
        if p.get("title", "").strip().lower() not in BLOCKLIST
    ]

    # Merge any papers not yet indexed by Semantic Scholar
    publications = merge_extra(publications)

    # Sort newest first; entries without a year go to the bottom
    publications.sort(
        key=lambda x: int(x["year"]) if str(x.get("year", "")).isdigit() else 0,
        reverse=True,
    )

    out = os.path.normpath(OUTPUT_PATH)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(publications, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Saved {len(publications)} publications to {out}")
    return True


if __name__ == "__main__":
    ok = fetch_publications()
    sys.exit(0 if ok else 1)
