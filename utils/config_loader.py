import json
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class ConfigLoader:
    """Load configuration for the paper collection system."""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)

    def load_conferences(self) -> List[Dict[str, Any]]:
        """Load conference configurations."""
        config_file = self.config_dir / "conferences.json"
        if not config_file.exists():
            logger.error(f"Conference config file not found: {config_file}")
            return []

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('conferences', [])
        except Exception as e:
            logger.error(f"Failed to load conference config: {e}")
            return []

    def get_conference_by_name(self, name: str) -> Dict[str, Any]:
        """Get configuration for a specific conference by name."""
        conferences = self.load_conferences()
        for conf in conferences:
            if conf.get('name', '').upper() == name.upper():
                return conf
        return {}

    def get_conferences_by_collector(self, collector_type: str) -> List[Dict[str, Any]]:
        """Get all conferences that use a specific collector type."""
        conferences = self.load_conferences()
        return [conf for conf in conferences if conf.get('collector') == collector_type]

    def get_available_years(self, conference_name: str) -> List[int]:
        """Get available years for a conference.

        Supports multiple year formats:
        1. Static list: "years": [2020, 2021, 2022, 2023, 2024]
        2. Range: "year_range": {"start": 2020, "end": 2024}
        3. Dynamic: "year_range": {"start": 2020, "end": "current"} (end is current year)
        """
        conf = self.get_conference_by_name(conference_name)
        if not conf:
            return []

        # Check for year range configuration
        if 'year_range' in conf:
            year_range = conf['year_range']
            start_year = year_range.get('start', 2020)
            end_year = year_range.get('end', 'current')

            if end_year == 'current':
                # Import here to avoid circular imports
                import datetime
                end_year = datetime.datetime.now().year

            # Generate list of years from start to end (inclusive)
            return list(range(start_year, end_year + 1))

        # Fall back to static years list
        return conf.get('years', [])

    def save_conference_config(self, conferences: List[Dict[str, Any]]):
        """Save conference configurations."""
        config_file = self.config_dir / "conferences.json"
        try:
            data = {'conferences': conferences}
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved conference config to {config_file}")
        except Exception as e:
            logger.error(f"Failed to save conference config: {e}")
            raise