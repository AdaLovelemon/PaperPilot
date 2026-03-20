import json
import logging
import os
import re
from collections import defaultdict
from typing import Dict, List, Any
import requests
from bs4 import BeautifulSoup
import time

logger = logging.getLogger(__name__)

class TopicCategorizer:
    def __init__(self, topic_config_path: str = "config/topics.json"):
        self.topic_config_path = topic_config_path
        self.topics = self.load_topics()
        self.compiled_topics = {
            topic: [re.compile(pattern, re.IGNORECASE) for pattern in keywords]
            for topic, keywords in self.topics.items()
        }

    def load_topics(self) -> Dict[str, List[str]]:
        if not os.path.exists(self.topic_config_path):
            logger.error(f"Topic config not found at {self.topic_config_path}")
            return {}
        try:
            with open(self.topic_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load topic config: {e}")
            return {}

    def fetch_missing_abstract(self, url: str) -> str:
        """Fetch abstract from conference website if missing."""
        if not url:
            return ""
        
        try:
            # Simple rate limiting feeling
            time.sleep(0.5)
            logger.debug(f"Fetching missing abstract from {url}")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # Common CVF openaccess pattern
            abstract_div = soup.find('div', id='abstract')
            if abstract_div:
                return abstract_div.get_text(separator=' ', strip=True)
            return ""
        except Exception as e:
            logger.warning(f"Failed to fetch abstract from {url}: {e}")
            return ""

    def categorize(self, papers: List[Dict[str, Any]], fill_missing_abstracts: bool = True) -> Dict[str, List[Dict]]:
        topic_groups = defaultdict(list)
        others = []

        total_papers = len(papers)
        logger.info(f"Categorizing {total_papers} papers based on abstract...")

        for i, paper in enumerate(papers):
            if i > 0 and i % 100 == 0:
                logger.info(f"Categorization progress: {i}/{total_papers}")

            abstract = paper.get('abstract', '').strip()
            
            # Use fallback fetch if abstract is empty or too short
            if fill_missing_abstracts and len(abstract) < 50:
                url = paper.get('url') or paper.get('pdf_url', '').replace('.pdf', '.html')
                if url:
                    fetched_abstract = self.fetch_missing_abstract(url)
                    if fetched_abstract:
                        paper['abstract'] = fetched_abstract
                        abstract = fetched_abstract

            content_to_search = abstract.lower() if abstract else ""
            
            matched_any = False
            for topic, regex_list in self.compiled_topics.items():
                if any(regex.search(content_to_search) for regex in regex_list):
                    topic_groups[topic].append(paper)
                    matched_any = True
                    
            if not matched_any:
                others.append(paper)

        topic_groups["99_其他未分类论文_(Others)"] = others
        return topic_groups

    def export_results(self, topic_groups: Dict[str, List[Dict]], output_dir: str):
        os.makedirs(output_dir, exist_ok=True)
        report_lines = ["# 论文前沿研究热点划分统计\n"]
        total = sum(len(v) for v in topic_groups.values() if not v == topic_groups.get("99_其他未分类论文_(Others)", []))
        total += len(topic_groups.get("99_其他未分类论文_(Others)", []))
        report_lines.append(f"> 按摘要进行深入分析。\n\n")

        for topic, topic_papers in sorted(topic_groups.items()):
            out_json_path = os.path.join(output_dir, f"{topic}.json")
            with open(out_json_path, 'w', encoding='utf-8') as f:
                json.dump(topic_papers, f, ensure_ascii=False, indent=2)
                
            topic_name = topic.split('_', 1)[-1].replace('_', ' ')
            report_lines.append(f"- **{topic_name}**: {len(topic_papers)} 篇")
            logger.info(f"Topic [{topic_name}]: {len(topic_papers)} papers saved.")

        report_path = os.path.join(output_dir, "HotTopic_Report.md")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(report_lines))
        logger.info(f"Categorization complete! Results stored in {output_dir}/")
        
