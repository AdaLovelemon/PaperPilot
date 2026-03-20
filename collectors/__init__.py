"""Conference paper collectors."""

from .base import BaseCollector
from .cvf_collector import CVFCollector
from .openreview_collector import OpenReviewCollector
from .pmlr_collector import PMLRCollector
from .ieee_collector import IEEECollector
from .rss_collector import RSSCollector
from .factory import CollectorFactory

__all__ = [
    'BaseCollector',
    'CVFCollector',
    'OpenReviewCollector',
    'PMLRCollector',
    'IEEECollector',
    'RSSCollector',
    'CollectorFactory'
]