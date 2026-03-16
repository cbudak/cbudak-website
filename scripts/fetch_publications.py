#!/usr/bin/env python3
"""
Fetch publications from Semantic Scholar API and save to publications.json.

Semantic Scholar is free, requires no API key, and works reliably in CI
environments (unlike Google Scholar which blocks datacenter IPs).

Run manually:
    pip install -r scripts/requirements.txt
    python scripts/fetch_publications.py

Or triggered automatically by the GitHub Action every two weeks.
"""

import json
import time
import sys
import os
import requests

AUTHOR_NAME   = "Ceren Budak"
AUTHOR_ID     = "1759771"   # Semantic Scholar ID — 70 papers, correct profile
OUTPUT_PATH   = os.path.join(os.path.dirname(__file__), "..", "publications.json")

SEARCH_URL  = "https://api.semanticscholar.org/graph/v1/author/search"
PAPERS_URL  = "https://api.semanticscholar.org/graph/v1/author/{author_id}/papers"
PAPER_FIELDS = (
    "title,authors,venue,year,abstract,"
    "citationCount,externalIds,openAccessPdf"
)

HEADERS = {"User-Agent": "cbudak-website-publications-bot/1.0"}


def find_author_id(name: str) -> str:
    resp = requests.get(
        SEARCH_URL,
        params={"query": name, "fields": "authorId,name,affiliations"},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    for author in resp.json().get("data", []):
        if "budak" in author["name"].lower():
            print(f"  Found: {author['name']}  (ID: {author['authorId']})")
            return author["authorId"]
    raise ValueError(f"Author '{name}' not found on Semantic Scholar")


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


def fetch_publications() -> bool:
    author_id = AUTHOR_ID
    print(f"Using Semantic Scholar author ID: {author_id} ({AUTHOR_NAME})")
    print("Fetching papers…")
    try:
        raw = fetch_all_papers(author_id)
    except Exception as e:
        print(f"Error fetching papers: {e}")
        return False

    publications = [normalize(p) for p in raw]

    # Sort newest first; entries without a year go to the bottom
    publications.sort(
        key=lambda x: int(x["year"]) if x["year"].isdigit() else 0,
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
