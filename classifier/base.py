import abc
import logging
from typing import Dict, Any, List, Set

logger = logging.getLogger(__name__)

class BaseClassifier(abc.ABC):
    """Abstract base class for paper classifiers."""

    @abc.abstractmethod
    def classify(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify a paper into categories.

        Args:
            paper: Paper dictionary with at least:
                - title (str)
                - abstract (str)
                - arxiv_id (str)
                - primary_category (str)
                - categories (List[str])
                - conference (str)
                - year (int)

        Returns:
            Dictionary with classification results:
                - primary_area (str)
                - secondary_areas (List[str])
                - keywords (List[str])
                - topics (List[str])  # higher-level topics
        """
        pass

    @abc.abstractmethod
    def get_all_categories(self) -> Set[str]:
        """Return all possible categories this classifier can assign."""
        pass