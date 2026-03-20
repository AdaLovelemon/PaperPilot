import abc
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class BaseCollector(abc.ABC):
    """Abstract base class for conference paper collectors."""

    def __init__(self, conference_name: str, year: int):
        self.conference_name = conference_name
        self.year = year

    @abc.abstractmethod
    def fetch_papers(self) -> List[Dict[str, Any]]:
        """
        Fetch all accepted papers from the conference website.

        Returns:
            List of paper dictionaries, each containing at least:
                - title (str)
                - authors (List[str])
                - abstract (Optional[str])
                - url (Optional[str])
                - arxiv_id (Optional[str]) if available directly
                - pdf_url (Optional[str])
                - other metadata
        """
        pass

    @abc.abstractmethod
    def get_conference_url(self) -> str:
        """Return the URL of the conference proceedings page."""
        pass

    def validate_year(self) -> bool:
        """
        Validate if the conference exists for the given year.

        Default implementation tries to fetch the conference URL and checks
        if response status code is 200.

        Returns:
            True if conference exists for this year, False otherwise
        """
        import requests
        from urllib.parse import urljoin

        try:
            url = self.get_conference_url()
            # For some collectors, the base URL might need year substitution
            # We'll try the URL as-is first
            response = requests.get(url, timeout=10)
            # Accept 2xx status codes (200, 201, etc.)
            if 200 <= response.status_code < 300:
                return True
            else:
                logger.debug(f"URL {url} returned status {response.status_code}")
                return False
        except Exception as e:
            logger.debug(f"Failed to validate year {self.year} for {self.conference_name}: {e}")
            return False

    def run(self) -> List[Dict[str, Any]]:
        """Main entry point to fetch papers."""
        logger.info(f"Collecting papers from {self.conference_name} {self.year}")
        papers = self.fetch_papers()
        logger.info(f"Collected {len(papers)} papers from {self.conference_name} {self.year}")
        return papers