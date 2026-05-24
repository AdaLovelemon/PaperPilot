"""
PaperPilot — collect, enrich, classify, and export papers from top AI/robotics conferences.

Quick start:
  python main.py list
  python main.py collect                                    # all confs, current year
  python main.py collect CVPR,ICCV -y 2024                  # specific
  python main.py collect ALL -y 2023,2024 -o papers.json    # single output
  python main.py categorize -i papers_CVPR_2024.json
  python main.py export -i papers.json --output-bib papers.bib
  python main.py export --input-dir Papers_By_Hot_Topic --output-dir Bibtex
"""

import argparse
import csv
import datetime
import io
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

import collectors
from classifier import TopicCategorizer, classify_paper

logger = logging.getLogger(__name__)

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="ignore")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="ignore")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_conferences() -> List[dict]:
    return [
        {"name": "CVPR", "full_name": "IEEE/CVF Conference on Computer Vision and Pattern Recognition"},
        {"name": "ICCV", "full_name": "IEEE/CVF International Conference on Computer Vision"},
        {"name": "NeurIPS", "full_name": "Neural Information Processing Systems"},
        {"name": "ICLR", "full_name": "International Conference on Learning Representations"},
        {"name": "ICML", "full_name": "International Conference on Machine Learning"},
        {"name": "CoRL", "full_name": "Conference on Robot Learning"},
        {"name": "RSS", "full_name": "Robotics: Science and Systems"},
    ]


# ---------------------------------------------------------------------------
# Export helpers  (JSON / CSV / BibTeX)
# ---------------------------------------------------------------------------

def _save_json(papers: list, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)
    logger.info("Saved %d papers → %s", len(papers), path)


def _save_csv(papers: list, path: str):
    if not papers:
        logger.info("No papers, skipping CSV.")
        return
    fieldnames = list(papers[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for p in papers:
            row = {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                   for k, v in p.items()}
            w.writerow(row)
    logger.info("Exported %d papers → %s", len(papers), path)


def _save_bib(papers: list, path: str, **kwargs):
    """Export papers as BibTeX via utils/csv_to_bib.py."""
    from utils.csv_to_bib import convert_csv_to_bib
    import tempfile
    tmp_csv = os.path.join(os.path.dirname(path) or ".", f"._tmp_{os.getpid()}.csv")
    try:
        _save_csv(papers, tmp_csv)
        convert_csv_to_bib(input_csv=tmp_csv, output_bib=path, **kwargs)
    finally:
        try:
            os.unlink(tmp_csv)
        except PermissionError:
            pass


def _batch_export_bib(input_dir: str, output_dir: str, **kwargs):
    src, dst = Path(input_dir), Path(output_dir)
    dst.mkdir(parents=True, exist_ok=True)
    for jf in src.glob("*.json"):
        with open(jf, encoding="utf-8") as f:
            papers = json.load(f)
        if papers:
            _save_bib(papers, str(dst / (jf.stem + ".bib")), **kwargs)


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_list():
    confs = _load_conferences()
    print("\nSupported conferences:")
    print("=" * 60)
    for c in confs:
        print(f"  {c['name']:8s}  {c.get('full_name', ''):45s}")
    print()


def cmd_collect(conf_names: List[str], years: List[int],
                output: str, max_papers: int,
                verbose: bool):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )

    confs = _load_conferences()
    lookup = {c["name"].upper(): c for c in confs}

    # Resolve targets
    # Propagate max-papers limit to collectors module-level _LIMIT
    if max_papers:
        collectors._LIMIT = max_papers

    if not conf_names or "ALL" in [n.upper() for n in conf_names]:
        targets = [lookup[k] for k in lookup
                   if k in [x.upper() for x in collectors.supported_conferences()]]
    else:
        targets = []
        for n in conf_names:
            c = lookup.get(n.upper())
            if c:
                targets.append(c)
            else:
                logger.warning("Unknown conference: %s", n)

    if not targets:
        logger.error("No valid conferences specified.")
        return 1

    cur_year = datetime.datetime.now().year
    y_list = years or [cur_year]
    single_out = bool(output)  # user wants everything in one file
    all_papers = []

    for conf in targets:
        name = conf["name"]
        for y in y_list:
            logger.info("=== %s %s ===", name, y)

            if not collectors.validate_year(name, y):
                logger.warning("  %s %s not reachable, skipping.", name, y)
                continue

            raw = collectors.fetch_papers(name, y)
            if not raw:
                logger.warning("  No papers fetched.", name, y)
                continue
            logger.info("  Fetched %d raw papers.", len(raw))

            enriched = []
            for i, p in enumerate(raw):
                try:
                    p.setdefault("primary_category", "unknown")
                    p.setdefault("categories", [])
                    classify_paper(p)
                except Exception as e:
                    logger.error("  Error processing paper %d: %s", i, e)
                    p.setdefault("primary_category", "error")
                    p.setdefault("categories", [])
                enriched.append(p)

            logger.info("  Classified %d papers.", len(enriched))

            if max_papers:
                enriched = enriched[:max_papers]
                logger.info("  Limited to %d papers for testing.", max_papers)
            all_papers.extend(enriched)

            if not single_out:
                # One JSON file per conference-year
                fname = f"papers_{name}_{y}.json"
                _save_json(enriched, fname)

    if single_out:
        _save_json(all_papers, output)

    print(f"\nDone. Total: {len(all_papers)} papers.")
    return 0


def cmd_categorize(input_json: str, output_dir: str, topic_config: str, verbose: bool):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )

    with open(input_json, encoding="utf-8") as f:
        papers = json.load(f)
    logger.info("Loaded %d papers from %s", len(papers), input_json)

    categorizer = TopicCategorizer(topic_config)
    if not categorizer.topics:
        logger.error("No topics loaded from %s", topic_config)
        return 1

    groups = categorizer.categorize(papers)
    categorizer.export(groups, output_dir)

    print(f"\nCategorised {len(papers)} papers → {output_dir}/ ({len(groups)} topics)")
    return 0


def cmd_export(input_json: str, input_dir: str, output_csv: str, output_bib: str,
               output_dir: str, verbose: bool, **bib_kw):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )

    # Batch mode: directory of JSONs → BibTeX files
    if input_dir:
        _batch_export_bib(input_dir, output_dir or "Exported_Bib", **bib_kw)
        print(f"Batch export done → {output_dir or 'Exported_Bib/'}")
        return 0

    if not input_json:
        logger.error("Provide --input (JSON file) or --input-dir (directory).")
        return 1

    with open(input_json, encoding="utf-8") as f:
        papers = json.load(f)

    if not papers:
        logger.warning("No papers in %s", input_json)
        return 1

    if output_csv:
        _save_csv(papers, output_csv)
    if output_bib:
        _save_bib(papers, output_bib, **bib_kw)
    if not output_csv and not output_bib:
        # Default: CSV alongside the JSON
        path = Path(input_json).with_suffix(".csv").name
        _save_csv(papers, path)
        print(f"Exported {len(papers)} papers → {path}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="paperpilot",
        description="Collect, enrich, classify, and export papers from top AI/robotics conferences.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py list
  python main.py collect
  python main.py collect CVPR,ICCV --year 2024
  python main.py collect ALL --year 2023,2024 -o papers.json
  python main.py categorize -i papers_CVPR_2024.json
  python main.py export -i papers.json --output-bib papers.bib
  python main.py export --input-dir Papers_By_Hot_Topic --output-dir Bibtex
        """,
    )
    sub = parser.add_subparsers(dest="command")

    # list
    sub.add_parser("list", help="List supported conferences")

    # collect
    p = sub.add_parser("collect", help="Collect papers from conferences")
    p.add_argument("conferences", nargs="*", default=[],
                   help="Conference names (space/comma separated, or ALL)")
    p.add_argument("--year", "-y", default="",
                   help="Year(s), comma-separated (default: current year)")
    p.add_argument("--output", "-o", default="",
                   help="Single output JSON (default: one file per conference-year)")
    p.add_argument("--max-papers", "-n", type=int, default=0,
                   help="Limit papers per conference/year (for testing)")
    p.add_argument("--verbose", "-v", action="store_true")

    # categorize
    p = sub.add_parser("categorize", help="Categorise papers by topic keywords")
    p.add_argument("--input", "-i", required=True, help="Input JSON file")
    p.add_argument("--output-dir", "-o", default="Papers_By_Hot_Topic",
                   help="Output directory for topic-split JSONs")
    p.add_argument("--topic-config", default="config/topics.json",
                   help="Topic keyword config path")
    p.add_argument("--verbose", "-v", action="store_true")

    # export
    p = sub.add_parser("export", help="Export papers to CSV / BibTeX")
    p.add_argument("--input", "-i", default="", help="Input JSON file")
    p.add_argument("--input-dir", default="",
                   help="Batch mode: input directory with JSON files")
    p.add_argument("--output-csv", default="", help="Output CSV path")
    p.add_argument("--output-bib", default="", help="Output BibTeX path")
    p.add_argument("--output-dir", default="",
                   help="Batch mode: output directory for .bib files")
    p.add_argument("--dedupe", action="store_true", help="Deduplicate BibTeX entries")
    p.add_argument("--include-abstract", action="store_true")
    p.add_argument("--include-keywords", action="store_true")
    p.add_argument("--include-topics", action="store_true")
    p.add_argument("--include-arxiv-id", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "list":
        return cmd_list()

    if args.command == "collect":
        confs = []
        for c in args.conferences:
            confs.extend(x.strip() for x in c.split(",") if x.strip())
        years = []
        if args.year:
            for y in args.year.split(","):
                y = y.strip()
                if y:
                    years.append(int(y))
        return cmd_collect(confs, years, args.output, args.max_papers, args.verbose)

    if args.command == "categorize":
        return cmd_categorize(args.input, args.output_dir, args.topic_config, args.verbose)

    if args.command == "export":
        return cmd_export(
            input_json=args.input,
            input_dir=args.input_dir,
            output_csv=args.output_csv,
            output_bib=args.output_bib,
            output_dir=args.output_dir,
            verbose=args.verbose,
            dedupe=args.dedupe,
            include_abstract=args.include_abstract,
            include_keywords=args.include_keywords,
            include_topics=args.include_topics,
            include_arxiv_id=args.include_arxiv_id,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
