import logging
import re
from typing import List, Dict, Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseCollector

logger = logging.getLogger(__name__)

class PMLRCollector(BaseCollector):
    """Collector for PMLR proceedings (ICML)."""

    def __init__(self, conference_name: str, year: int):
        super().__init__(conference_name, year)
        self.base_url = "https://proceedings.mlr.press"
        self.volume = self._get_volume()

    def _get_volume(self) -> str:
        """Get PMLR volume number based on conference and year."""
        # Mapping of conference year to PMLR volume
        # This would need to be updated based on actual PMLR volumes
        volumes = {
            'ICML': {
                2020: 'v119',
                2021: 'v139',
                2022: 'v162',
                2023: 'v202',
                2024: 'v235',
            }
        }

        conference_volumes = volumes.get(self.conference_name.upper(), {})
        return conference_volumes.get(self.year, f"v{self.year}")

    def get_conference_url(self) -> str:
        return f"{self.base_url}/{self.volume}/"

    def fetch_papers(self) -> List[Dict[str, Any]]:
        """Fetch papers from PMLR website."""
        papers = []

        url = self.get_conference_url()

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch PMLR page: {e}")
            return papers

        soup = BeautifulSoup(response.content, 'html.parser')
        paper_elements = soup.find_all('div', class_='paper')

        for paper_elem in paper_elements:
            paper = self._parse_paper_element(paper_elem)
            if paper:
                papers.append(paper)

        logger.info(f"Fetched {len(papers)} papers from PMLR for {self.conference_name} {self.year}")
        return papers

    def _parse_paper_element(self, paper_elem) -> Dict[str, Any]:
        """Parse a PMLR paper element."""
        try:
            # Title
            title_elem = paper_elem.find('p', class_='title')
            if not title_elem:
                return None

            title = title_elem.text.strip()

            # Authors
            authors_elem = paper_elem.find('p', class_='authors')
            authors = []
            if authors_elem:
                # Remove "Authors:" prefix if present
                authors_text = authors_elem.text.replace('Authors:', '').strip()
                authors = [author.strip() for author in authors_text.split(',')]

            # Abstract
            abstract_elem = paper_elem.find('p', class_='abstract')
            abstract = abstract_elem.text.strip() if abstract_elem else ""

            # Links
            links = {}
            supplement_url = ''
            link_elems = paper_elem.find_all('a')

            for link in link_elems:
                href = link.get('href', '')
                if not href:
                    continue

                # Make absolute URL
                absolute_url = href
                if not href.startswith('http'):
                    absolute_url = f"{self.base_url}/{href.lstrip('/')}"

                # Determine link type from text or URL pattern
                link_text = link.text.strip().lower()

                # Check for arXiv link
                if 'arxiv.org/abs' in href:
                    links['arxiv'] = absolute_url
                # Check for PDF link
                elif 'pdf' in link_text or href.endswith('.pdf') or 'pdf' in href.lower():
                    links['pdf'] = absolute_url
                # Check for supplement material
                elif 'supplement' in link_text or 'supp' in link_text or 'supplementary' in link_text:
                    supplement_url = absolute_url
                    links['supplement'] = absolute_url
                # Check for HTML/paper link
                elif 'html' in link_text or 'paper' in link_text:
                    links['paper'] = absolute_url
                # Check for bibtex
                elif 'bibtex' in link_text or 'bib' in link_text:
                    links['bibtex'] = absolute_url
                # Check for code
                elif 'code' in link_text or 'github' in href.lower():
                    links['code'] = absolute_url
                # Check for other common types
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

            # Try to extract arXiv ID from links
            arxiv_id = None
            for link_type, href in links.items():
                if 'arxiv.org' in href:
                    match = re.search(r'arxiv\.org/abs/([\d\.v]+)', href)
                    if match:
                        arxiv_id = match.group(1)
                        break

            # PDF URL
            pdf_url = links.get('pdf', '')
            if pdf_url and not pdf_url.startswith('http'):
                pdf_url = f"{self.base_url}/{pdf_url}"

            # Paper URL
            paper_url = links.get('html', '')
            if paper_url and not paper_url.startswith('http'):
                paper_url = f"{self.base_url}/{paper_url}"

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
                'source': 'pmlr'
            }

            return paper

        except Exception as e:
            logger.error(f"Error parsing PMLR paper element: {e}")
            return None