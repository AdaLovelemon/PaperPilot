import re
import time
import logging
import urllib.request
import urllib.parse
from xml.etree import ElementTree as ET
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class ArxivPaper:
    """Data class for arXiv paper information."""
    arxiv_id: str
    title: str
    primary_category: str
    categories: List[str]
    abstract: str
    authors: List[str]
    published: str
    updated: str

class ArxivMatcher:
    """Match papers with arXiv and retrieve category information."""

    ARXIV_API = "http://export.arxiv.org/api/query"
    RATE_LIMIT_DELAY = 1.0  # seconds between requests

    def __init__(self, rate_limit_delay: float = None):
        self.rate_limit_delay = rate_limit_delay or self.RATE_LIMIT_DELAY
        self._last_request_time = 0

    def _throttle(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def fetch_by_arxiv_id(self, arxiv_id: str) -> Optional[ArxivPaper]:
        """Fetch paper information by arXiv ID."""
        query = f"id:{arxiv_id}"
        return self._fetch_single_paper(query)

    def fetch_by_title(self, title: str) -> Optional[ArxivPaper]:
        """Fetch paper information by title (exact match)."""
        # Clean title for query
        clean_title = self._clean_title(title)
        query = f'ti:"{clean_title}"'
        return self._fetch_single_paper(query)

    def fetch_by_title_and_authors(self, title: str, authors: List[str]) -> Optional[ArxivPaper]:
        """Fetch paper by title and authors for better matching."""
        clean_title = self._clean_title(title)
        query = f'ti:"{clean_title}"'

        # Add first author if available
        if authors:
            first_author = authors[0].split()[-1]  # Last name
            query += f' AND au:"{first_author}"'

        return self._fetch_single_paper(query)

    def _fetch_single_paper(self, query: str) -> Optional[ArxivPaper]:
        """Make a single arXiv API request and parse result."""
        self._throttle()

        url = f"{self.ARXIV_API}?search_query={urllib.parse.quote(query)}&start=0&max_results=1"

        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'})
            response = urllib.request.urlopen(req)
            root = ET.fromstring(response.read())

            entries = root.findall(self._ns("entry"))
            if not entries:
                return None

            return self._parse_entry(entries[0])

        except Exception as e:
            logger.error(f"arXiv API request failed for query '{query}': {e}")
            return None

    def _ns(self, tag: str) -> str:
        """Utility to handle arXiv Atom XML namespace."""
        return f"{{http://www.w3.org/2005/Atom}}{tag}"

    def _parse_entry(self, entry) -> ArxivPaper:
        """Parse arXiv Atom entry into ArxivPaper object."""
        # arXiv ID
        id_elem = entry.find(self._ns("id"))
        arxiv_id = id_elem.text.split("/abs/")[-1] if id_elem is not None else "unknown"

        # Title
        title_elem = entry.find(self._ns("title"))
        title = title_elem.text.strip().replace("\n", " ") if title_elem is not None else ""

        # Abstract
        summary_elem = entry.find(self._ns("summary"))
        abstract = summary_elem.text.strip().replace("\n", " ") if summary_elem is not None else ""

        # Authors
        authors = []
        author_elems = entry.findall(self._ns("author"))
        for author_elem in author_elems:
            name_elem = author_elem.find(self._ns("name"))
            if name_elem is not None:
                authors.append(name_elem.text)

        # Primary category
        primary_category_elem = entry.find("{http://arxiv.org/schemas/atom}primary_category")
        primary_category = primary_category_elem.attrib.get('term') if primary_category_elem is not None else "unknown"

        # All categories
        categories = []
        category_elems = entry.findall(self._ns("category"))
        for cat_elem in category_elems:
            term = cat_elem.attrib.get('term')
            if term and term != primary_category:
                categories.append(term)

        # Dates
        published_elem = entry.find(self._ns("published"))
        published = published_elem.text if published_elem is not None else ""

        updated_elem = entry.find(self._ns("updated"))
        updated = updated_elem.text if updated_elem is not None else ""

        return ArxivPaper(
            arxiv_id=arxiv_id,
            title=title,
            primary_category=primary_category,
            categories=categories,
            abstract=abstract,
            authors=authors,
            published=published,
            updated=updated
        )

    def _clean_title(self, title: str) -> str:
        """Clean title for arXiv query."""
        # Remove extra whitespace
        title = re.sub(r'\s+', ' ', title.strip())
        # Remove problematic characters for query
        title = title.replace('"', "'")
        return title

    def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """Extract keywords from text (title + abstract)."""
        if not text:
            return []

        # Convert to lowercase
        text = text.lower()

        # Remove punctuation
        text = re.sub(r'[^\w\s]', ' ', text)

        # Get words of reasonable length
        words = re.findall(r'\b[a-z]{4,}\b', text)

        # Common stopwords to ignore
        stopwords = {
            'this', 'that', 'with', 'from', 'propose', 'method', 'model',
            'approach', 'based', 'using', 'paper', 'study', 'research',
            'work', 'proposed', 'novel', 'new', 'approach', 'methodology',
            'results', 'experimental', 'experiments', 'show', 'demonstrate',
            'present', 'introduce', 'investigate', 'analysis', 'analyze'
        }

        # Count word frequencies
        word_counts = defaultdict(int)
        for word in words:
            if word not in stopwords:
                word_counts[word] += 1

        # Sort by frequency (descending)
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)

        # Return top keywords
        keywords = [word for word, count in sorted_words[:max_keywords]]

        return keywords