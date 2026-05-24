"""
arXiv matching & topic categorisation.
"""

import json
import logging
import os
import re
from collections import defaultdict
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


def extract_keywords(text: str, max_kw: int = 10) -> List[str]:
    """Extract frequent meaningful words from text as keywords."""
    if not text:
        return []
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    words = re.findall(r"\b[a-z]{4,}\b", text)
    stopwords = {
        "this", "that", "with", "from", "propose", "method", "model",
        "approach", "based", "using", "paper", "study", "research",
        "work", "proposed", "novel", "new", "methodology",
        "results", "experimental", "experiments", "show", "demonstrate",
        "present", "introduce", "investigate", "analysis", "analyze",
        "however", "also", "can", "well", "we", "our", "the", "and", "for",
    }
    counts: Dict[str, int] = defaultdict(int)
    for w in words:
        if w not in stopwords:
            counts[w] += 1
    return [w for w, _ in sorted(counts.items(), key=lambda x: -x[1])[:max_kw]]


# ---------------------------------------------------------------------------
# Topic categoriser  (keyword-based)
# ---------------------------------------------------------------------------

class TopicCategorizer:
    """Group papers by topic keywords defined in a JSON config file."""

    def __init__(self, config_path: str = "config/topics.json"):
        self.topics: Dict[str, List[str]] = {}
        if os.path.exists(config_path):
            with open(config_path, encoding="utf-8") as f:
                self.topics = json.load(f)
        else:
            logger.warning("Topic config not found: %s", config_path)

        self._compiled = {
            topic: [re.compile(p, re.IGNORECASE) for p in patterns]
            for topic, patterns in self.topics.items()
        }

    def categorize(self, papers: List[Dict]) -> Dict[str, List[Dict]]:
        groups: Dict[str, List[Dict]] = defaultdict(list)
        others: List[Dict] = []

        for paper in papers:
            text = (paper.get("abstract") or "") + " " + (paper.get("title") or "")
            text = text.lower()
            matched = False
            for topic, regexes in self._compiled.items():
                if any(r.search(text) for r in regexes):
                    groups[topic].append(paper)
                    matched = True
            if not matched:
                others.append(paper)

        if others:
            groups["99_其他未分类论文_(Others)"] = others
        return groups

    def export(self, groups: Dict[str, List[Dict]], output_dir: str):
        os.makedirs(output_dir, exist_ok=True)
        for topic, papers in groups.items():
            path = os.path.join(output_dir, f"{topic}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(papers, f, ensure_ascii=False, indent=2)

        # Simple report
        report_path = os.path.join(output_dir, "HotTopic_Report.md")
        lines = ["# 论文前沿研究热点划分统计\n"]
        for topic, papers in sorted(groups.items()):
            name = topic.split("_", 1)[-1].replace("_", " ")
            lines.append(f"- **{name}**: {len(papers)} 篇")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        logger.info("Categorization results saved to %s", output_dir)


# ---------------------------------------------------------------------------
# Convenience: classify a paper using arXiv metadata + keyword extraction
# ---------------------------------------------------------------------------

_AREA_MAP = {
    "cs.CV": "Computer Vision", "cs.LG": "Machine Learning", "cs.CL": "Computational Linguistics",
    "cs.AI": "Artificial Intelligence", "cs.RO": "Robotics", "cs.NE": "Neural and Evolutionary Computing",
    "cs.SY": "Systems and Control", "cs.PL": "Programming Languages", "cs.SE": "Software Engineering",
    "cs.DS": "Data Structures and Algorithms", "cs.DB": "Databases", "cs.CR": "Cryptography and Security",
    "cs.GR": "Graphics", "cs.MM": "Multimedia", "cs.IR": "Information Retrieval",
    "cs.HC": "Human-Computer Interaction", "cs.CY": "Computers and Society", "cs.SI": "Social and Information Networks",
}

_CATEGORY_TOPICS = {
    "cs": "Computer Science", "math": "Mathematics", "physics": "Physics",
    "stat": "Statistics", "eess": "Electrical Engineering & Systems Science",
    "q-bio": "Quantitative Biology", "q-fin": "Quantitative Finance", "econ": "Economics",
}


def classify_paper(paper: Dict) -> Dict:
    """Add arXiv-area and keyword fields to a paper dict (in-place & return)."""
    primary = paper.get("primary_category", "unknown")
    categories = paper.get("categories", [])

    text = f"{paper.get('title', '')} {paper.get('abstract', '')}"
    keywords = extract_keywords(text)

    def _area(cat: str) -> str:
        if not cat:
            return "Unknown"
        area = _AREA_MAP.get(cat)
        if area:
            return area
        prefix = cat.split(".")[0] if "." in cat else cat
        return _CATEGORY_TOPICS.get(prefix, cat)

    topics = set()
    for cat in [primary] + list(categories):
        prefix = cat.split(".")[0] if "." in cat else cat
        t = _CATEGORY_TOPICS.get(prefix)
        if t:
            topics.add(t)

    paper["primary_area"] = _area(primary)
    paper["secondary_areas"] = [_area(c) for c in categories]
    paper["keywords"] = keywords
    paper["topics"] = list(topics)
    return paper
