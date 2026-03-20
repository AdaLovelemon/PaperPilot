import logging
import re
import time
from typing import List, Dict, Any

import requests

from .base import BaseCollector

logger = logging.getLogger(__name__)

class OpenReviewCollector(BaseCollector):
    """Collector for OpenReview conferences (NeurIPS, ICLR, CoRL)."""

    def __init__(self, conference_name: str, year: int):
        super().__init__(conference_name, year)
        self.base_url = "https://api.openreview.net"
        self.conference_id = self._get_conference_id()

    def _get_conference_id(self) -> str:
        """Get OpenReview conference ID based on conference name and year."""
        if self.conference_name.upper() == "NEURIPS":
            return f"NeurIPS.cc/{self.year}/Conference"
        elif self.conference_name.upper() == "ICLR":
            return f"ICLR.cc/{self.year}/Conference"
        elif self.conference_name.upper() == "CORL":
            return f"robot-learning.org/CoRL/{self.year}/Conference"
        else:
            # Default pattern
            return f"{self.conference_name}.cc/{self.year}/Conference"

    def get_conference_url(self) -> str:
        return f"https://openreview.net/group?id={self.conference_id}"

    def fetch_papers(self) -> List[Dict[str, Any]]:
        """Fetch accepted papers from OpenReview API."""
        papers = []

        # OpenReview API endpoint for notes (papers)
        url = f"{self.base_url}/notes"
        params = {
            'invitation': f'{self.conference_id}/-/Accept',
            'limit': 1000,
            'offset': 0
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            for note in data.get('notes', []):
                paper = self._parse_note(note)
                if paper:
                    papers.append(paper)

            logger.info(f"Fetched {len(papers)} papers from OpenReview for {self.conference_name} {self.year}")

        except Exception as e:
            logger.error(f"Failed to fetch papers from OpenReview: {e}")

        return papers

    def _parse_note(self, note: Dict[str, Any]) -> Dict[str, Any]:
        """Parse OpenReview note into paper dictionary."""
        try:
            title = note.get('content', {}).get('title', {}).get('value', '').strip()
            if not title:
                return None

            # Extract arXiv ID from PDF link or content
            arxiv_id = None
            pdf_url = note.get('content', {}).get('pdf', {}).get('value', '')

            if pdf_url:
                # Try to extract arXiv ID from PDF URL
                match = re.search(r'arxiv\.org/pdf/([\d\.v]+)', pdf_url)
                if match:
                    arxiv_id = match.group(1)

            # Create links dictionary
            links = {}
            supplement_url = ''

            if pdf_url:
                links['pdf'] = pdf_url

            # Check for other possible links in note content
            # OpenReview might have supplementary material, code, etc.
            # This is a placeholder for future expansion
            content = note.get('content', {})
            for key, value in content.items():
                if isinstance(value, dict) and 'value' in value:
                    link_value = value['value']
                    if isinstance(link_value, str) and link_value.startswith('http'):
                        # Check for common link types
                        if 'supplement' in key.lower() or 'supplementary' in key.lower():
                            supplement_url = link_value
                            links['supplement'] = link_value
                        elif 'code' in key.lower() or 'github' in key.lower():
                            links['code'] = link_value
                        elif 'video' in key.lower():
                            links['video'] = link_value
                        elif 'poster' in key.lower():
                            links['poster'] = link_value
                        elif 'slides' in key.lower():
                            links['slides'] = link_value

            # Extract authors
            authors = []
            author_ids = note.get('content', {}).get('authors', {}).get('value', [])
            for author_id in author_ids:
                # Try to get author name from profiles
                author_name = self._get_author_name(author_id)
                if author_name:
                    authors.append(author_name)

            # Abstract
            abstract = note.get('content', {}).get('abstract', {}).get('value', '')

            # Keywords (if available)
            keywords = note.get('content', {}).get('keywords', {}).get('value', [])

            paper = {
                'title': title,
                'authors': authors,
                'abstract': abstract,
                'url': f"https://openreview.net/forum?id={note.get('id', '')}",
                'arxiv_id': arxiv_id,
                'pdf_url': pdf_url,
                'supplement_url': supplement_url,
                'links': links,
                'keywords': keywords,
                'conference': self.conference_name,
                'year': self.year,
                'source': 'openreview',
                'openreview_id': note.get('id')
            }

            return paper

        except Exception as e:
            logger.error(f"Error parsing OpenReview note: {e}")
            return None

    def _get_author_name(self, author_id: str) -> str:
        """Get author name from OpenReview profile."""
        try:
            # Simple heuristic: extract name from ID
            # OpenReview IDs are often emails or names
            if '@' in author_id:
                # Email address - use local part
                name_part = author_id.split('@')[0]
                # Replace dots and underscores with spaces
                name = name_part.replace('.', ' ').replace('_', ' ').title()
                return name
            else:
                # Assume it's already a name
                return author_id
        except:
            return author_id

    def fetch_with_retry(self, url: str, params: dict, max_retries: int = 3) -> Dict[str, Any]:
        """Fetch with retry logic."""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Request failed (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise
        return {}