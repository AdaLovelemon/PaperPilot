import logging
from typing import Dict, Any, List, Set
import re

from .base import BaseClassifier
from matchers.arxiv_matcher import ArxivMatcher

logger = logging.getLogger(__name__)

class ArxivCategoryClassifier(BaseClassifier):
    """Classifier based on arXiv categories and extracted keywords."""

    # Mapping from arXiv category prefixes to broader topics
    CATEGORY_TOPICS = {
        'cs': 'Computer Science',
        'math': 'Mathematics',
        'physics': 'Physics',
        'stat': 'Statistics',
        'eess': 'Electrical Engineering & Systems Science',
        'q-bio': 'Quantitative Biology',
        'q-fin': 'Quantitative Finance',
        'econ': 'Economics',
    }

    # Subfield mapping within CS
    CS_SUBFIELDS = {
        'cs.CV': 'Computer Vision',
        'cs.LG': 'Machine Learning',
        'cs.CL': 'Computational Linguistics',
        'cs.AI': 'Artificial Intelligence',
        'cs.RO': 'Robotics',
        'cs.NE': 'Neural and Evolutionary Computing',
        'cs.SY': 'Systems and Control',
        'cs.PL': 'Programming Languages',
        'cs.SE': 'Software Engineering',
        'cs.DS': 'Data Structures and Algorithms',
        'cs.DB': 'Databases',
        'cs.CR': 'Cryptography and Security',
        'cs.GR': 'Graphics',
        'cs.MM': 'Multimedia',
        'cs.IR': 'Information Retrieval',
        'cs.HC': 'Human-Computer Interaction',
        'cs.CY': 'Computers and Society',
        'cs.SI': 'Social and Information Networks',
    }

    def __init__(self, matcher: ArxivMatcher = None):
        self.matcher = matcher or ArxivMatcher()
        self._all_categories = set(self.CATEGORY_TOPICS.keys()) | set(self.CS_SUBFIELDS.keys())

    def classify(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """Classify paper using arXiv categories and extracted keywords."""
        # Use arXiv categories if available
        primary_category = paper.get('primary_category', 'unknown')
        categories = paper.get('categories', [])

        # Extract keywords from title and abstract
        text = f"{paper.get('title', '')} {paper.get('abstract', '')}"
        keywords = self.matcher.extract_keywords(text, max_keywords=10)

        # Determine broader topics
        topics = self._get_topics(primary_category, categories)

        # Map primary category to human-readable name
        primary_area = self._map_category_to_name(primary_category)

        # Map secondary categories
        secondary_areas = [self._map_category_to_name(cat) for cat in categories]

        return {
            'primary_area': primary_area,
            'secondary_areas': secondary_areas,
            'keywords': keywords,
            'topics': topics,
            'arxiv_primary_category': primary_category,
            'arxiv_categories': categories
        }

    def _map_category_to_name(self, category: str) -> str:
        """Map arXiv category code to human-readable name."""
        if not category:
            return 'Unknown'

        # Check CS subfields
        if category in self.CS_SUBFIELDS:
            return self.CS_SUBFIELDS[category]

        # Check general categories
        prefix = category.split('.')[0] if '.' in category else category
        if prefix in self.CATEGORY_TOPICS:
            return self.CATEGORY_TOPICS[prefix]

        # Return category as is
        return category

    def _get_topics(self, primary_category: str, categories: List[str]) -> List[str]:
        """Extract broader topics from categories."""
        topics = set()

        # Add primary category topic
        prefix = primary_category.split('.')[0] if '.' in primary_category else primary_category
        if prefix in self.CATEGORY_TOPICS:
            topics.add(self.CATEGORY_TOPICS[prefix])

        # Add topics from all categories
        for category in categories:
            prefix = category.split('.')[0] if '.' in category else category
            if prefix in self.CATEGORY_TOPICS:
                topics.add(self.CATEGORY_TOPICS[prefix])

        return list(topics)

    def get_all_categories(self) -> Set[str]:
        """Return all possible categories this classifier can assign."""
        return self._all_categories