import logging
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

from utils.config_loader import ConfigLoader
from collectors.factory import CollectorFactory
from matchers.arxiv_matcher import ArxivMatcher
from classifier.arxiv_category_classifier import ArxivCategoryClassifier
from storage.paper_storage import PaperStorage

logger = logging.getLogger(__name__)

class PaperCollectionCoordinator:
    """Main coordinator for collecting, matching, and classifying papers."""

    def __init__(self, config_dir: str = "config", db_path: str = "papers.db"):
        self.config_loader = ConfigLoader(config_dir)
        self.storage = PaperStorage(db_path)
        self.matcher = ArxivMatcher()
        self.classifier = ArxivCategoryClassifier(self.matcher)

        # Configure logging
        self._setup_logging()

    def _setup_logging(self):
        """Setup basic logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def collect_conference(self, conference_name: str, year: int) -> List[Dict[str, Any]]:
        """
        Collect, match, and classify papers for a specific conference and year.

        Returns:
            List of processed paper dictionaries
        """
        logger.info(f"Starting collection for {conference_name} {year}")

        # Load conference configuration
        conf_config = self.config_loader.get_conference_by_name(conference_name)
        if not conf_config:
            logger.error(f"No configuration found for conference: {conference_name}")
            return []

        # Create collector
        try:
            collector = CollectorFactory.create_collector(conf_config, year)
        except Exception as e:
            logger.error(f"Failed to create collector for {conference_name}: {e}")
            return []

        # Step 0: Validate if conference exists for the given year
        logger.info(f"Validating conference year {conference_name} {year}...")
        if not collector.validate_year():
            logger.warning(f"Conference {conference_name} may not exist for year {year} (or website unreachable). Skipping.")
            return []

        # Step 1: Fetch papers from conference website
        logger.info(f"Fetching papers from {conference_name} {year} website...")
        raw_papers = collector.fetch_papers()
        logger.info(f"Fetched {len(raw_papers)} raw papers from {conference_name} {year}")

        if not raw_papers:
            logger.warning(f"No papers found for {conference_name} {year}")
            return []

        # Modify process: Process in batches so that DB and files can update incrementally
        batch_size = 50
        all_processed_papers = []
        
        for i in range(0, len(raw_papers), batch_size):
            batch = raw_papers[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(raw_papers) + batch_size - 1)//batch_size} (size: {len(batch)})...")
            
            # Match
            enriched_batch = self._enrich_with_arxiv(batch)
            
            # Classify
            classified_batch = self._classify_papers(enriched_batch)
            
            # Store
            success_count = self.storage.store_papers(classified_batch)
            logger.info(f"Stored {success_count} papers from batch in database")
            
            if hasattr(self, 'export_json_path') and self.export_json_path:
                self.export_results(output_path=self.export_json_path)

        return all_processed_papers

    def _enrich_with_arxiv(self, raw_papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich paper data with arXiv information."""
        enriched_papers = []

        for i, paper in enumerate(raw_papers):
            # Print periodic progress to console
            if (i+1) % 50 == 0:
                logger.info(f"Progress: Enriched {i+1}/{len(raw_papers)} papers...")
            
            try:
                # 去重逻辑：对于大批量抓取，直接查询会导致全文检索错误
                # 为避免搜索错误，这里简化去重，由数据库本身的 UPSERT 或主键逻辑保障
                arxiv_info = None

                # Try to get arXiv info by arXiv ID if available
                arxiv_id = paper.get('arxiv_id')
                if arxiv_id:
                    arxiv_info = self.matcher.fetch_by_arxiv_id(arxiv_id)

                # If not found by ID, try by title and authors
                if not arxiv_info and paper.get('title'):
                    authors = paper.get('authors', [])
                    if authors:
                        arxiv_info = self.matcher.fetch_by_title_and_authors(paper['title'], authors)
                    else:
                        arxiv_info = self.matcher.fetch_by_title(paper['title'])

                if arxiv_info:
                    # Merge arXiv info with paper data
                    # Only map fields that are not already present or fallback safely
                    enriched_paper = {
                        **paper,
                        'arxiv_id': arxiv_info.arxiv_id,
                        'title': arxiv_info.title,  # Use arXiv title (more standardized)
                        'abstract': arxiv_info.abstract,
                        'primary_category': arxiv_info.primary_category,
                        'categories': arxiv_info.categories,
                        'authors': arxiv_info.authors,
                        'published_date': arxiv_info.published,
                        'updated_date': arxiv_info.updated
                    }
                    
                    # Log if arXiv is found but we already got some url links
                    if not enriched_paper.get('pdf_url') and paper.get('pdf_url'):
                        enriched_paper['pdf_url'] = paper['pdf_url']
                        
                    enriched_papers.append(enriched_paper)
                else:
                    # Keep paper even without arXiv match
                    logger.debug(f"No arXiv match for paper: {paper.get('title', 'Unknown')} (pdf_url: {paper.get('pdf_url', 'None')})")
                    # Add placeholder arXiv info
                    paper['primary_category'] = 'unknown'
                    paper['categories'] = []
                    enriched_papers.append(paper)

                # Respect rate limiting
                time.sleep(self.matcher.rate_limit_delay)

            except Exception as e:
                logger.error(f"Error enriching paper {paper.get('title', 'Unknown')}: {e}")
                # Add paper with minimal info
                paper['primary_category'] = 'error'
                paper['categories'] = []
                enriched_papers.append(paper)

        return enriched_papers

    def _classify_papers(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Classify papers using the classifier."""
        classified_papers = []

        for paper in papers:
            try:
                classification = self.classifier.classify(paper)

                # Merge classification results into paper
                classified_paper = {
                    **paper,
                    'primary_area': classification['primary_area'],
                    'secondary_areas': classification['secondary_areas'],
                    'keywords': classification['keywords'],
                    'topics': classification['topics']
                }

                classified_papers.append(classified_paper)

            except Exception as e:
                logger.error(f"Error classifying paper {paper.get('arxiv_id', 'Unknown')}: {e}")
                # Add paper without classification
                paper['primary_area'] = 'unknown'
                paper['secondary_areas'] = []
                paper['keywords'] = []
                paper['topics'] = []
                classified_papers.append(paper)

        return classified_papers

    def collect_multiple_conferences(self, conference_years: List[tuple]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Collect papers for multiple conferences and years.

        Args:
            conference_years: List of (conference_name, year) tuples

        Returns:
            Dictionary mapping conference-year to list of papers
        """
        results = {}

        for conference_name, year in conference_years:
            key = f"{conference_name}_{year}"
            try:
                papers = self.collect_conference(conference_name, year)
                results[key] = papers
                logger.info(f"Completed collection for {conference_name} {year}: {len(papers)} papers")
            except Exception as e:
                logger.error(f"Failed to collect {conference_name} {year}: {e}")
                results[key] = []

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about collected papers."""
        # This would query the database for counts
        # For now, return placeholder
        return {
            'total_papers': 0,
            'conferences': {},
            'categories': {}
        }

    def export_results(self, output_format: str = 'json', output_path: Optional[str] = None):
        """Export collected papers to file."""
        if not output_path:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = f"paper_collection_{timestamp}.{output_format}"

        if output_format.lower() == 'json':
            # Export all papers to JSON
            self.storage.export_to_json(output_path)
            logger.info(f"Exported results to {output_path}")
        else:
            raise ValueError(f"Unsupported output format: {output_format}")