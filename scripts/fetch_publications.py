#!/usr/bin/env python3
"""
Fetch publications from Google Scholar and save to publications.json.

Run manually:
    pip install -r scripts/requirements.txt
    python scripts/fetch_publications.py

Or triggered automatically by the GitHub Action every two weeks.
"""

import json
import time
import sys
import os

try:
    from scholarly import scholarly
except ImportError:
    print("Error: scholarly not installed. Run: pip install scholarly")
    sys.exit(1)

SCHOLAR_ID = "wIhJS60AAAAJ"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "publications.json")


def fetch_publications():
    print(f"Fetching publications for Google Scholar ID: {SCHOLAR_ID}")

    try:
        author = scholarly.search_author_id(SCHOLAR_ID)
        author = scholarly.fill(author, sections=["publications"])
    except Exception as e:
        print(f"Error connecting to Google Scholar: {e}")
        return False

    raw_pubs = author.get("publications", [])
    print(f"Found {len(raw_pubs)} publications. Fetching details…")

    publications = []
    for i, pub in enumerate(raw_pubs, 1):
        try:
            print(f"  [{i}/{len(raw_pubs)}] {pub.get('bib', {}).get('title', 'Unknown')[:70]}…")
            filled = scholarly.fill(pub)
            bib = filled.get("bib", {})
            publications.append({
                "title":       bib.get("title", ""),
                "authors":     bib.get("author", ""),
                "venue":       bib.get("venue") or bib.get("journal") or bib.get("booktitle") or "",
                "year":        str(bib.get("pub_year", "")),
                "abstract":    bib.get("abstract", ""),
                "url":         filled.get("pub_url", ""),
                "eprint_url":  filled.get("eprint_url", ""),
                "citations":   filled.get("num_citations", 0),
            })
            time.sleep(2)  # be polite to Google Scholar
        except Exception as e:
            print(f"  Warning: could not fetch details — using partial info ({e})")
            bib = pub.get("bib", {})
            publications.append({
                "title":      bib.get("title", ""),
                "authors":    bib.get("author", ""),
                "venue":      bib.get("venue", ""),
                "year":       str(bib.get("pub_year", "")),
                "abstract":   "",
                "url":        "",
                "eprint_url": "",
                "citations":  pub.get("num_citations", 0),
            })

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
