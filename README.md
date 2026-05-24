# PaperPilot

[**中文版 (Chinese)**](./README_ZH.md) | **English Version**

Collect, enrich, categorize, and export papers from top AI/robotics conferences.

**Supported**: CVPR · ICCV · NeurIPS · ICLR · ICML · CoRL · RSS

Pure JSON storage — no database setup needed.

---

## Quick Start

```bash
# Install
pip install requests beautifulsoup4

# Collect CVPR 2024 papers (with arXiv enrichment for abstract/author completion)
python main.py collect CVPR -y 2024

# Collect NeurIPS 2024
python main.py collect NeurIPS -y 2024

# Export to BibTeX for Zotero
python main.py export -i papers_NeurIPS_2024.json --output-bib neurips.bib --include-abstract
```

---

## Examples

### 1. Collect a single conference

```bash
python main.py collect CVPR -y 2024
# → papers_CVPR_2024.json  (with abstracts, authors, PDF links)
```

### 2. Collect multiple years into separate files

```bash
python main.py collect NeurIPS -y 2023,2024
# → papers_NeurIPS_2023.json
# → papers_NeurIPS_2024.json
```

### 3. Collect multiple conferences, merge into one file

```bash
python main.py collect CVPR,ICCV -y 2023,2024 -o cv_papers.json
# → cv_papers.json  (CVPR 2023 + CVPR 2024 + ICCV 2023 + ICCV 2024 merged)
```

### 4. Collect everything at once

```bash
python main.py collect ALL -y 2024
# → papers_CVPR_2024.json, papers_ICCV_2024.json, ...
```

### 5. Quick sanity test (10 papers per conference)

```bash
python main.py collect ALL -y 2024 -n 10
# Verifies all collectors work without waiting for full results
```

### 6. Full workflow: collect → categorize → export to BibTeX

```bash
# Step 1: Collect CVPR 2024
python main.py collect CVPR -y 2024

# Step 2: Categorize into research topics
python main.py categorize -i papers_CVPR_2024.json
# → Papers_By_Hot_Topic/01_Multimodal_LLM_VLM.json
# → Papers_By_Hot_Topic/02_Embodied_AI_Robotics.json
# → Papers_By_Hot_Topic/HotTopic_Report.md

# Step 3: Batch export each topic to BibTeX (for Zotero import)
python main.py export --input-dir Papers_By_Hot_Topic --output-dir Bibtex --include-abstract
# → Bibtex/01_Multimodal_LLM_VLM.bib
# → Bibtex/02_Embodied_AI_Robotics.bib
```

### 7. Debug a specific collector

```bash
python main.py collect RSS -y 2023 -n 3 -v
# Verbose mode shows HTTP requests and parsing details
```

---

## Commands

### `list` — Show supported conferences

```bash
python main.py list
```

### `collect` — Fetch papers

```bash
python main.py collect [conferences...] [options]

# conferences:  CVPR ICCV NeurIPS ICLR ICML CoRL RSS
#               or ALL (everything)

# Options:
  -y, --year YEAR       Years, comma-separated  (default: current year)
  -o, --output FILE     Merge all into one JSON file
  -n, --max-papers N    Limit per conference/year  (test mode)
  -v, --verbose         Show debug logs
```

### `categorize` — Group papers by research topic

```bash
python main.py categorize -i papers.json

# Options:
  -o, --output-dir DIR      Output directory  (default: Papers_By_Hot_Topic)
  --topic-config FILE        Topic config path  (default: config/topics.json)
```

### `export` — Convert to CSV / BibTeX

```bash
python main.py export -i papers.json --output-bib papers.bib

# Options:
  --output-csv FILE         Export as CSV
  --output-bib FILE         Export as BibTeX
  --dedupe                  Remove duplicate entries
  --include-abstract        Add abstract to BibTeX note field
  --include-keywords        Add keywords to BibTeX note field
  --include-topics          Add topic labels to BibTeX note field
  --include-arxiv-id        Add arXiv ID to BibTeX note field

# Batch: convert all JSONs in a directory
python main.py export --input-dir Papers_By_Hot_Topic --output-dir Bibtex
```

---

## Custom Topics

Edit `config/topics.json` to define your own research areas. Each topic is a list of regex patterns matched against paper titles and abstracts:

```json
{
  "01_Multimodal_LLM_VLM": [
    "\\bllm\\b",
    "vision-language model",
    "visual language model",
    "multimodal"
  ],
  "02_Embodied_AI_Robotics": [
    "embodied",
    "manipulation",
    "locomotion",
    "reinforcement learning"
  ],
  "03_Diffusion_Generation": [
    "diffusion model",
    "image generation",
    "text-to-image",
    "video generation"
  ]
}
```

After editing, re-run `categorize` to regroup your existing JSON files.

---

## Project Structure

```
PaperPilot/
  main.py              # CLI: collect | categorize | export | list
  collectors.py        # All conference scrapers
  classifier.py        # Topic categorizer + keyword extraction
  utils/
    csv_to_bib.py      # CSV → BibTeX converter
  config/
    topics.json        # Custom topic regex patterns
```

---

## How It Works

1. **Collect** scrapes the conference proceedings page — typically one HTTP request per conference/year
2. **Classify** extracts keywords and maps arXiv category codes to readable area names
3. **Categorize** groups papers by regex topic patterns from `config/topics.json`
4. **Export** converts to CSV or BibTeX for import into Zotero, JabRef, etc.

All data is plain JSON — inspectable with any text editor or `jq`.

---

## Data Sources

| Conference | Source | Type |
|-----------|--------|------|
| CVPR, ICCV | openaccess.thecvf.com | CVF HTML |
| NeurIPS | papers.nips.cc | Listing page |
| ICLR | api2.openreview.net | OpenReview v2 API |
| ICML, CoRL | proceedings.mlr.press | PMLR HTML |
| RSS | roboticsproceedings.org | Per-paper pages |

---

## Dependencies

```bash
pip install requests beautifulsoup4
```

Python 3.8+.

## License

MIT License. See [LICENSE](./LICENSE) for details.
