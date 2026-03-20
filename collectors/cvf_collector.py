import re
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseCollector

logger = logging.getLogger(__name__)

class CVFCollector(BaseCollector):
    """Collector for CVF conferences (CVPR, ICCV, ECCV)."""

    def __init__(self, conference_name: str, year: int):
        super().__init__(conference_name, year)
        self.base_url = f"https://openaccess.thecvf.com/{conference_name}{year}"
        # Some conferences have different URL patterns
        if conference_name == "ECCV":
            # ECCV uses a different domain
            self.base_url = f"https://www.ecva.net/papers.php"

    def get_conference_url(self) -> str:
        return self.base_url

    def validate_year(self) -> bool:
        """
        Validate if the conference exists for the given year.

        For CVPR and ICCV, check the base URL.
        For ECCV, the URL is fixed, so we need a different approach.
        """
        import requests

        if self.conference_name == "ECCV":
            # ECCV has a fixed URL, so we can't validate by URL alone.
            # We'll try to fetch the page and check for year indicators.
            url = self.base_url
            try:
                response = requests.get(url, timeout=10)
                if response.status_code != 200:
                    return False

                # Check if page contains year information
                # ECCV website might show the year in headings or titles
                content = response.text

                # Look for common patterns: ECCV 2020, ECCV'20, etc.
                year_patterns = [
                    f"ECCV {self.year}",
                    f"ECCV{self.year}",
                    f"ECCV '{str(self.year)[2:]}",  # ECCV '20
                ]

                for pattern in year_patterns:
                    if pattern in content:
                        return True

                # If no year pattern found, try to parse the page structure
                # to see if there are papers (this is a fallback)
                soup = BeautifulSoup(content, 'html.parser')
                paper_elements = soup.find_all('div', class_='paper')
                if paper_elements:
                    # If we find paper elements, assume the page is valid
                    # (but this could be wrong if page shows papers from other years)
                    return True

                # No year patterns and no paper elements found
                logger.debug(f"ECCV {self.year} validation: No year patterns or paper elements found")
                return False

            except Exception as e:
                logger.debug(f"Failed to validate ECCV year {self.year}: {e}")
                return False
        else:
            # For CVPR and ICCV, use parent implementation
            return super().validate_year()

    def fetch_papers(self) -> List[Dict[str, Any]]:
        papers = []

        if self.conference_name in ["CVPR", "ICCV"]:
            # CVPR and ICCV: use ?day=all parameter to get all papers
            all_url = f"{self.base_url}?day=all"
            papers = self._fetch_papers_from_url(all_url)
            if not papers:
                # Fallback to base URL without parameter
                logger.warning(f"No papers found with ?day=all, trying base URL...")
                papers = self._fetch_papers_from_url(self.base_url)
        elif self.conference_name == "ECCV":
            # ECCV has a single page with all papers
            url = f"https://www.ecva.net/papers.php"
            papers = self._fetch_eccv_papers(url)
        else:
            logger.warning(f"Unknown CVF conference: {self.conference_name}")
            # Try generic approach
            papers = self._fetch_papers_from_url(self.base_url)

        return papers

    def _fetch_papers_from_url(self, url: str) -> List[Dict[str, Any]]:
        """Fetch papers from a CVF daily page."""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        papers = []

        # CVF paper entries are typically in <dt> tags with class 'ptitle'
        paper_elements = soup.find_all('dt', class_='ptitle')

        for paper_elem in paper_elements:
            try:
                title_elem = paper_elem.find('a')
                if not title_elem:
                    continue

                title = title_elem.text.strip()
                paper_url = urljoin(url, title_elem.get('href', ''))

                # Find the next <dd> element which contains authors and abstract
                author_elem = paper_elem.find_next('dd')
                authors_text = ""
                if author_elem:
                    # Extract authors (text before first <br>)
                    authors_text = author_elem.get_text(separator=' ', strip=True)
                    # Try to separate authors from abstract
                    if '<br>' in str(author_elem):
                        authors_text = str(author_elem).split('<br>')[0]
                        authors_text = BeautifulSoup(authors_text, 'html.parser').get_text(strip=True)

                # Extract all links from the paper's associated <dd> elements
                arxiv_id = None
                pdf_url = ''
                supplement_url = ''
                all_links = {}
                
                # Links are usually in the next <dd> elements before the next <dt>
                next_node = paper_elem.find_next_sibling()
                link_elements = []
                while next_node and next_node.name != 'dt':
                    if next_node.name == 'dd':
                        link_elements.extend(next_node.find_all('a'))
                    next_node = next_node.find_next_sibling()

                for link in link_elements:
                    href = link.get('href', '')
                    if not href:
                        continue

                    # Make absolute URL
                    absolute_url = urljoin(url, href)

                    # Determine link type from text or URL pattern
                    link_text = link.text.strip().lower()

                    # Check for arXiv link
                    if 'arxiv.org/abs' in href:
                        match = re.search(r'arxiv\.org/abs/([\d\.v]+)', href)
                        if match:
                            arxiv_id = match.group(1)
                            all_links['arxiv'] = absolute_url
                    # Check for supplement material
                    elif 'supplement' in link_text or 'supp' in link_text or 'supplementary' in link_text:
                        supplement_url = absolute_url
                        all_links['supplement'] = absolute_url
                    # Check for PDF link (avoid overwriting with supplemental if order is different)
                    elif 'pdf' in link_text or href.endswith('.pdf') or 'pdf' in href.lower():
                        if 'supplemental' not in href.lower() and 'supp' not in link_text:
                            pdf_url = absolute_url
                        all_links['pdf'] = absolute_url
                    # Check for bibtex
                    elif 'bibtex' in link_text or 'bib' in link_text:
                        all_links['bibtex'] = absolute_url
                    # Check for code or project page
                    elif 'code' in link_text or 'github' in href.lower():
                        all_links['code'] = absolute_url
                    # Check for video
                    elif 'video' in link_text:
                        all_links['video'] = absolute_url
                    # Check for poster
                    elif 'poster' in link_text:
                        all_links['poster'] = absolute_url
                    # Check for slides
                    elif 'slides' in link_text:
                        all_links['slides'] = absolute_url
                    # Check for other paper links (HTML)
                    elif 'paper' in link_text or 'html' in link_text:
                        all_links['paper'] = absolute_url
                    # Default: use link text as key or generic name
                    else:
                        # Use meaningful key if possible
                        if link_text and len(link_text) < 20:
                            key = link_text.replace(' ', '_')
                        else:
                            # Generate generic key
                            key = f'link_{len(all_links)}'
                        all_links[key] = absolute_url

                paper = {
                    'title': title,
                    'authors': self._parse_authors(authors_text),
                    'abstract': self._extract_abstract(author_elem),
                    'url': paper_url,
                    'arxiv_id': arxiv_id,
                    'pdf_url': pdf_url,
                    'supplement_url': supplement_url,
                    'links': all_links,
                    'conference': self.conference_name,
                    'year': self.year,
                    'source': 'cvf'
                }
                papers.append(paper)

            except Exception as e:
                logger.error(f"Error parsing paper element: {e}")
                continue

        logger.info(f"Fetched {len(papers)} papers from {url}")
        return papers

    def _fetch_eccv_papers(self, url: str) -> List[Dict[str, Any]]:
        """Fetch papers from ECCV website."""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch ECCV papers: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        papers = []

        # ECCV paper entries structure may differ
        # This is a simplified parser - needs adjustment based on actual HTML
        paper_elements = soup.find_all('div', class_='paper')

        for paper_elem in paper_elements:
            try:
                title_elem = paper_elem.find('h3')
                if not title_elem:
                    continue

                title = title_elem.text.strip()

                # Extract all links from the paper element
                arxiv_id = None
                pdf_url = ''
                supplement_url = ''
                all_links = {}

                # Find all links in the paper element
                link_elements = paper_elem.find_all('a')

                for link in link_elements:
                    href = link.get('href', '')
                    if not href:
                        continue

                    # Make absolute URL
                    absolute_url = urljoin(url, href)

                    # Determine link type from text or URL pattern
                    link_text = link.text.strip().lower()

                    # Check for arXiv link
                    if 'arxiv.org/abs' in href:
                        match = re.search(r'arxiv\.org/abs/([\d\.v]+)', href)
                        if match:
                            arxiv_id = match.group(1)
                            all_links['arxiv'] = absolute_url
                    # Check for PDF link
                    elif 'pdf' in link_text or href.endswith('.pdf') or 'pdf' in href.lower():
                        pdf_url = absolute_url
                        all_links['pdf'] = absolute_url
                    # Check for supplement material
                    elif 'supplement' in link_text or 'supp' in link_text or 'supplementary' in link_text:
                        supplement_url = absolute_url
                        all_links['supplement'] = absolute_url
                    # Check for other common link types
                    elif 'bibtex' in link_text or 'bib' in link_text:
                        all_links['bibtex'] = absolute_url
                    elif 'code' in link_text or 'github' in href.lower():
                        all_links['code'] = absolute_url
                    elif 'video' in link_text:
                        all_links['video'] = absolute_url
                    elif 'poster' in link_text:
                        all_links['poster'] = absolute_url
                    elif 'slides' in link_text:
                        all_links['slides'] = absolute_url
                    # Default: use meaningful key if possible
                    else:
                        if link_text and len(link_text) < 20:
                            key = link_text.replace(' ', '_')
                        else:
                            key = f'link_{len(all_links)}'
                        all_links[key] = absolute_url

                paper = {
                    'title': title,
                    'authors': [],  # Need to parse from ECCV specific structure
                    'abstract': '',
                    'url': '',
                    'arxiv_id': arxiv_id,
                    'pdf_url': pdf_url,
                    'supplement_url': supplement_url,
                    'links': all_links,
                    'conference': self.conference_name,
                    'year': self.year,
                    'source': 'cvf'
                }
                papers.append(paper)
            except Exception as e:
                logger.error(f"Error parsing ECCV paper: {e}")
                continue

        return papers

    def _parse_authors(self, authors_text: str) -> List[str]:
        """Parse authors string into list of author names."""
        if not authors_text:
            return []

        # Remove common prefixes
        authors_text = authors_text.replace('Authors:', '').strip()

        # Split by commas or 'and'
        authors = re.split(r',\s*|\s+and\s+', authors_text)

        # Clean up each author name
        authors = [author.strip() for author in authors if author.strip()]

        return authors

    def _extract_abstract(self, author_elem) -> str:
        """Extract abstract from author element."""
        if not author_elem:
            return ""

        # Try to find abstract text after authors
        text = str(author_elem)
        if '<br>' in text:
            parts = text.split('<br>')
            if len(parts) > 1:
                # Assume abstract is in the second part
                abstract_html = parts[1]
                soup = BeautifulSoup(abstract_html, 'html.parser')
                return soup.get_text(strip=True)

        return ""