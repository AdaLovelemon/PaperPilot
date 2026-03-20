import importlib
import logging
from typing import Dict, Any

from .base import BaseCollector

logger = logging.getLogger(__name__)

class CollectorFactory:
    """Factory for creating collector instances based on conference configuration."""

    # Mapping from collector type to class
    COLLECTOR_CLASSES = {
        'cvf': 'cvf_collector.CVFCollector',
        'openreview': 'openreview_collector.OpenReviewCollector',
        'pmlr': 'pmlr_collector.PMLRCollector',
        'ieee': 'ieee_collector.IEEECollector',
        'rss': 'rss_collector.RSSCollector',
        # Add more collectors here
    }

    @classmethod
    def create_collector(cls, conference_config: Dict[str, Any], year: int) -> BaseCollector:
        """
        Create a collector instance based on conference configuration.

        Args:
            conference_config: Dictionary with conference configuration
            year: Conference year

        Returns:
            Collector instance
        """
        collector_type = conference_config.get('collector', 'unknown')
        conference_name = conference_config.get('name', '')

        if collector_type not in cls.COLLECTOR_CLASSES:
            raise ValueError(f"Unknown collector type: {collector_type}")

        module_name, class_name = cls.COLLECTOR_CLASSES[collector_type].rsplit('.', 1)

        try:
            # Import the module
            module = importlib.import_module(f'.{module_name}', package='collectors')
            # Get the class
            collector_class = getattr(module, class_name)
            # Create instance
            return collector_class(conference_name, year)
        except ImportError as e:
            logger.error(f"Failed to import collector module {module_name}: {e}")
            raise
        except AttributeError as e:
            logger.error(f"Collector class {class_name} not found in module {module_name}: {e}")
            raise

    @classmethod
    def get_available_collectors(cls) -> list:
        """Return list of available collector types."""
        return list(cls.COLLECTOR_CLASSES.keys())