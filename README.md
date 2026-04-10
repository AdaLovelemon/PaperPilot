# PaperPilot

[**中文版 (Chinese)**](./README_CN.md) | **English Version**

An automated scholarly paper collection and categorization system for top-tier computer science and robotics conferences (CVPR, ICCV, NeurIPS, ECCV, ICML, ICLR, ICRA, IROS, RSS, CoRL and more). It helps researchers keep up with the latest trends by automatically fetching paper metadata and categorizing them based on **Abstracts** using custom hot-topic definitions.

## Key Features

- **Dual-Engine Architecture**: Separates "Collection" (scraping) from "Categorization" (analysis), allowing you to re-categorize existing datasets anytime.
- **Smart Abstract Completion**: Automatically visits source pages (e.g., CVF, OpenReview) to fetch missing abstracts if they aren't available in the initial metadata.
- **Multi-Conference Support**: Pre-configured for over 10 flagship conferences.
- **Regex-Based Topic Splitting**: Highly flexible categorization using `config/topics.json`. Define your own research interests (e.g., "Embodied AI", "LLMs", "Diffusion") and get organized folders and reports instantly.
- **Robust Storage**: Supports JSON exports and SQLite database storage for full-text search.
- **Scalable Collection**: Real-time batch saving (every 50 papers) to prevent data loss during long scraping sessions.

## Project Structure

```
PaperPilot/
 collectors/          # Conference-specific scrapers (CVF, OpenReview, PMLR, etc.)
 classifier/          # Legacy arXiv category classification
 matchers/            # Paper matching engines (e.g., linking to arXiv)
 storage/             # Data persistence (SQLite & JSON)
 utils/               # Configuration & common helpers
 core/                # Core orchestration logic
    coordinator.py   # Collection workflow scheduler
    categorizer.py   # Abstract-based topic analysis scheduler
 config/              # User-editable configurations
    conferences.json # Target conference metadata
    topics.json      # Custom topic regex dictionary
 csv_to_bib.py        # CSV to BibTeX conversion utility
 main.py              # Main CLI entry point
 pyproject.toml       # Project metadata
 README.md            # English Documentation
 README_CN.md         # Chinese Documentation
```

## Getting Started

### Prerequisites

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) (Highly Recommended) or pip

### Installation

1. Clone the repository:
```bash
git clone https://github.com/<your-username>/PaperPilot.git
cd PaperPilot
```

2. Install dependencies:
```bash
uv sync
```

## Usage

### Phase 1: Collect Papers (`collect`)

Fetch paper listings from official websites or ArXiv.

1. List supported conferences:
```bash
uv run python main.py collect --list-conferences
```

2. Collect a specific conference and year:
```bash
# Example: Collect CVPR 2025 papers
uv run python main.py collect --conference CVPR --year 2025 --export-json papers.json --verbose
```

### Phase 2: Categorize by Hot Topics (`categorize`)

Analyze the collected JSON and split papers into topic-specific folders based on their **Abstracts**.

```bash
uv run python main.py categorize --input papers.json --fill-abstracts --verbose
```

**Key Arguments:**
- `--fill-abstracts`: Attempts to scrape missing abstracts from source HTML pages if not present in the local cache.
- `--topic-config`: Path to your topic definitions (defaults to `config/topics.json`).

**Output:**
A directory `Papers_By_Hot_Topic/` will be created containing partitioned JSON files and a `HotTopic_Report.md` summarizing the distribution.

### Phase 3: Export to CSV / BibTeX (`export`)

Export papers from the database to CSV format and optionally convert them to a Zotero-importable BibTeX file.

```bash
# Export all papers to CSV and convert to BibTeX
uv run python main.py export --output-csv all_papers.csv --output-bib all_papers.bib --include-abstract --dedupe

# Export only specific conferences
uv run python main.py export --conference CVPR,ICCV --output-bib cv_papers.bib
```

**Key Arguments:**
- `--output-csv`: Output CSV file path.
- `--output-bib`: Output BibTeX file path.
- `--conference`: Comma-separated list of conferences to filter by.
- `--dedupe`: Deduplicate BibTeX entries by arXiv ID or title+year.
- `--include-abstract`: Include abstract in the BibTeX note field.
- `--include-keywords`: Include keywords in the BibTeX note field.
- `--include-topics`: Include topics in the BibTeX note field.
- `--include-arxiv-id`: Include arXiv ID in the BibTeX note field.

## Customization

### Defining Your Topics (`config/topics.json`)
You can add your own research interests using regex patterns:

```json
{
  "01_Multimodal_LLM_VLM": ["\\bllm\\b", "vision-language model"],
  "02_Embodied_AI_Robotics": ["embodied", "manipulation", "locomotion"]
}
```

---

## License
MIT License
