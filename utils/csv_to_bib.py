import argparse
import csv
import json
import re
from pathlib import Path
from collections import defaultdict


def bibtex_escape(s: str) -> str:
    if s is None:
        return ""
    return (
        str(s)
        .replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("&", "\\&")
    )


def parse_json_list(value):
    """Parse a JSON array string like '["a", "b"]'. Return list[str]."""
    if not value:
        return []
    value = value.strip()
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    # Fallback: split on commas if it isn't valid JSON
    parts = [p.strip() for p in value.split(",")]
    return [p for p in parts if p]


def normalize_authors(authors_value):
    authors = parse_json_list(authors_value)
    # Zotero/BibTeX author format: "First Last and First2 Last2"
    return " and ".join(bibtex_escape(a) for a in authors)


def make_bib_key(authors_value, year, title, arxiv_id=None, used_keys=None):
    """
    Generate a stable citation key.
    Priority:
      1) arxiv_id if present
      2) first_author + year + short title token
    """
    used_keys = used_keys or set()

    if arxiv_id:
        key = re.sub(r"[^A-Za-z0-9]+", "_", arxiv_id).strip("_").lower()
        if key and key not in used_keys:
            return key

    authors = parse_json_list(authors_value)
    first_author_last = "unknown"
    if authors:
        # Use last token of first author name as a rough surname
        first_author_last = (
            re.sub(r"[^A-Za-z]+", "", authors[0].split()[-1]).lower() or "unknown"
        )

    title_part = title.split(":")[0]
    title_token = re.sub(r"[^A-Za-z0-9]+", "", title_part.split()[0]).lower()
    year = str(year).strip() if year else "n.d."

    base = f"{first_author_last}{year}{title_token}"
    base = re.sub(r"[^A-Za-z0-9]+", "", base) or "unknownnd"

    key = base
    idx = 2
    while key in used_keys:
        key = f"{base}{idx}"
        idx += 1
    return key


def build_note(row):
    parts = []

    arxiv_id = row.get("arxiv_id", "").strip()
    if arxiv_id:
        parts.append(f"arXiv: {arxiv_id}")

    pdf_url = row.get("pdf_url", "").strip()
    if pdf_url:
        parts.append(f"PDF: {pdf_url}")

    abstract = row.get("abstract", "").strip()
    if abstract:
        parts.append(f"Abstract: {abstract}")

    keywords = row.get("keywords", "").strip()
    if keywords:
        parts.append(f"Keywords: {keywords}")

    topics = row.get("topics", "").strip()
    if topics:
        parts.append(f"Topics: {topics}")

    return " | ".join(parts)


def infer_entry_type(conference):
    # Conference papers -> @inproceedings
    # If you later want journal articles, you can extend this logic.
    return "inproceedings"


def convert_csv_to_bib(
    input_csv: str,
    output_bib: str,
    dedupe: bool = False,
    include_abstract: bool = False,
    include_keywords: bool = False,
    include_topics: bool = False,
    include_arxiv_id: bool = False,
):
    input_path = Path(input_csv)
    output_path = Path(output_bib)

    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    used_keys = set()
    seen_records = set()
    entries = []

    for row in rows:
        title = (row.get("title") or "").strip()
        authors_value = (row.get("authors") or "").strip()
        conference = (row.get("conference") or "").strip()
        year = (row.get("year") or "").strip()
        url = (row.get("url") or "").strip()
        pdf_url = (row.get("pdf_url") or "").strip()
        arxiv_id = (row.get("arxiv_id") or "").strip()

        if not title:
            continue

        # Dedupe
        if dedupe:
            if arxiv_id:
                dedupe_key = ("arxiv", arxiv_id.lower())
            else:
                dedupe_key = ("title_year", title.lower(), year)
            if dedupe_key in seen_records:
                continue
            seen_records.add(dedupe_key)

        key = make_bib_key(
            authors_value=authors_value,
            year=year,
            title=title,
            arxiv_id=arxiv_id,
            used_keys=used_keys,
        )
        used_keys.add(key)

        author_field = normalize_authors(authors_value)
        entry_type = infer_entry_type(conference)

        fields = [
            f"  title = {{{bibtex_escape(title)}}}",
        ]
        if author_field:
            fields.append(f"  author = {{{author_field}}}")
        if conference:
            fields.append(f"  booktitle = {{{bibtex_escape(conference)}}}")
        if year:
            fields.append(f"  year = {{{bibtex_escape(year)}}}")
        if url:
            fields.append(f"  url = {{{bibtex_escape(url)}}}")

        note_parts = []
        if include_arxiv_id and arxiv_id:
            note_parts.append(f"arXiv: {arxiv_id}")
        if pdf_url:
            note_parts.append(f"PDF: {pdf_url}")
        if include_abstract:
            abstract = (row.get("abstract") or "").strip()
            if abstract:
                note_parts.append(f"Abstract: {abstract}")
        if include_keywords:
            keywords = (row.get("keywords") or "").strip()
            if keywords:
                note_parts.append(f"Keywords: {keywords}")
        if include_topics:
            topics = (row.get("topics") or "").strip()
            if topics:
                note_parts.append(f"Topics: {topics}")

        if note_parts:
            fields.append(f"  note = {{{bibtex_escape(' | '.join(note_parts))}}}")

        entry = f"@{entry_type}{{{key},\n" + ",\n".join(fields) + "\n}"
        entries.append(entry)

    output_path.write_text("\n\n".join(entries) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} entries to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert paper CSV exports to a Zotero-importable BibTeX file."
    )
    parser.add_argument("input_csv", help="Input CSV file (e.g. all_papers.csv)")
    parser.add_argument("output_bib", help="Output .bib file (e.g. all_papers.bib)")
    parser.add_argument(
        "--dedupe",
        action="store_true",
        help="Deduplicate entries by arxiv_id if available, otherwise by title+year",
    )
    parser.add_argument(
        "--include-abstract",
        action="store_true",
        help="Include abstract in the BibTeX note field",
    )
    parser.add_argument(
        "--include-keywords",
        action="store_true",
        help="Include keywords in the BibTeX note field",
    )
    parser.add_argument(
        "--include-topics",
        action="store_true",
        help="Include topics in the BibTeX note field",
    )
    parser.add_argument(
        "--include-arxiv-id",
        action="store_true",
        help="Include arXiv ID in the BibTeX note field",
    )
    args = parser.parse_args()

    convert_csv_to_bib(
        input_csv=args.input_csv,
        output_bib=args.output_bib,
        dedupe=args.dedupe,
        include_abstract=args.include_abstract,
        include_keywords=args.include_keywords,
        include_topics=args.include_topics,
        include_arxiv_id=args.include_arxiv_id,
    )


if __name__ == "__main__":
    main()
