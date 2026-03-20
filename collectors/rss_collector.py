import logging
import re
from typing import List, Dict, Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseCollector

logger = logging.getLogger(__name__)

class RSSCollector(BaseCollector):
    """Collector for Robotics: Science and Systems (RSS)."""

    def __init__(self, conference_name: str, year: int):
        super().__init__(conference_name, year)
        self.base_url = "https://www.roboticsproceedings.org"

    def get_conference_url(self) -> str:
        return f"{self.base_url}/rss{self.year}/index.html"

    def fetch_papers(self) -> List[Dict[str, Any]]:
        """Fetch papers from RSS website."""
        papers = []

        url = self.get_conference_url()

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch RSS page: {e}")
            return papers

        soup = BeautifulSoup(response.content, 'html.parser')

        # RSS website structure may vary by year
        # Look for paper links
        paper_links = soup.find_all('a', href=re.compile(r'p\d+\.html'))

        for link in paper_links:
            paper_url = link.get('href')
            if not paper_url.startswith('http'):
                paper_url = f"{self.base_url}/rss{self.year}/{paper_url}"

            paper = self._fetch_paper_details(paper_url)
            if paper:
                papers.append(paper)

        logger.info(f"Fetched {len(papers)} papers from RSS for {self.conference_name} {self.year}")
        return papers

    def _fetch_paper_details(self, paper_url: str) -> Dict[str, Any]:
        """Fetch details for a single paper."""
        try:
            response = requests.get(paper_url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch paper details from {paper_url}: {e}")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        try:
            # Extract title (usually in <h1> or <h2>)
            title_elem = soup.find('h1') or soup.find('h2')
            title = title_elem.text.strip() if title_elem else ""

            # Extract authors
            authors = []
            # Look for author information (varies by year)
            for elem in soup.find_all(['p', 'div']):
                text = elem.get_text().strip()
                if 'authors' in text.lower() or 'author' in text.lower():
                    # Extract author names
                    author_text = text.replace('Authors:', '').replace('Author:', '').strip()
                    authors = [author.strip() for author in author_text.split(',')]
                    break

            # Extract abstract
            abstract = ""
            for elem in soup.find_all(['p', 'div']):
                if 'abstract' in elem.get_text().lower():
                    abstract = elem.get_text().replace('Abstract:', '').strip()
                    break

            # Collect all links
            arxiv_id = None
            pdf_url = ""
            supplement_url = ""
            links = {}

            for link in soup.find_all('a', href=True):
                href = link['href']
                if not href:
                    continue

                # Make absolute URL
                absolute_url = href
                if not href.startswith('http'):
                    # Try different base paths
                    if href.startswith('/'):
                        absolute_url = f"{self.base_url}{href}"
                    else:
                        absolute_url = f"{self.base_url}/rss{self.year}/{href}"

                # Determine link type from text or URL pattern
                link_text = link.text.strip().lower()

                # Check for arXiv link
                if 'arxiv.org/abs' in href:
                    match = re.search(r'arxiv\.org/abs/([\d\.v]+)', href)
                    if match:
                        arxiv_id = match.group(1)
                        links['arxiv'] = absolute_url
                # Check for PDF link
                elif 'pdf' in link_text or href.endswith('.pdf') or 'pdf' in href.lower():
                    pdf_url = absolute_url
                    links['pdf'] = absolute_url
                # Check for supplement material
                elif 'supplement' in link_text or 'supp' in link_text or 'supplementary' in link_text:
                    supplement_url = absolute_url
                    links['supplement'] = absolute_url
                # Check for other common types
                elif 'bibtex' in link_text or 'bib' in link_text:
                    links['bibtex'] = absolute_url
                elif 'code' in link_text or 'github' in href.lower():
                    links['code'] = absolute_url
                elif 'video' in link_text:
                    links['video'] = absolute_url
                elif 'poster' in link_text:
                    links['poster'] = absolute_url
                elif 'slides' in link_text:
                    links['slides'] = absolute_url
                # Default: include all links
                else:
                    if link_text and len(link_text) < 20:
                        key = link_text.replace(' ', '_')
                    else:
                        key = f'link_{len(links)}'
                    links[key] = absolute_url

            paper = {
                'title': title,
                'authors': authors,
                'abstract': abstract,
                'url': paper_url,
                'arxiv_id': arxiv_id,
                'pdf_url': pdf_url,
                'supplement_url': supplement_url,
                'links': links,
                'conference': self.conference_name,
                'year': self.year,
                'source': 'rss'
            }

            return paper

        except Exception as e:
            logger.error(f"Error parsing RSS paper from {paper_url}: {e}")
            return None