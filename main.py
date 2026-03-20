#!/usr/bin/env python3
"""
Paper Collection System - Main Entry Point

Collect, match, and classify papers from top conferences.
"""

import argparse
import sys
import logging
from typing import List
import io
import json

from core.coordinator import PaperCollectionCoordinator
from core.categorizer import TopicCategorizer
from utils.config_loader import ConfigLoader
from collectors.factory import CollectorFactory
import datetime

# Fix encoding for Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')

logger = logging.getLogger(__name__)

def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def list_conferences():
    """List all available conferences from configuration."""
    config_loader = ConfigLoader()
    conferences = config_loader.load_conferences()

    print("\nAvailable conferences:")
    print("=" * 80)
    for conf in conferences:
        name = conf.get('name', 'Unknown')
        full_name = conf.get('full_name', '')
        collector = conf.get('collector', 'unknown')
        years = conf.get('years', [])

        # 获取年份范围信息
        year_range = conf.get('year_range', {})
        if year_range:
            start_year = year_range.get('start', 2020)
            end_year = year_range.get('end', 'current')
            if end_year == 'current':
                current_year = datetime.datetime.now().year
                year_info = f"{start_year}年-当前 (自动扩展)"
            else:
                year_info = f"{start_year}年-{end_year}年"
        elif years:
            # 如果有具体的年份列表，显示范围
            if len(years) > 1:
                year_info = f"{min(years)}年-{max(years)}年 (具体年份列表)"
            else:
                year_info = f"{years[0]}年"
        else:
            year_info = "年份未配置"

        print(f"  {name:10} | {collector:15} | {full_name}")
        print(f"                可用年份: {year_info}")
        print()

def find_available_year(conference_name: str, max_lookback: int = 5) -> tuple:
    """
    查找会议可用的年份。
    """
    config_loader = ConfigLoader()
    conf = config_loader.get_conference_by_name(conference_name)
    if not conf:
        logger.warning(f"No configuration found for conference: {conference_name}")
        return None, "未配置"

    years = config_loader.get_available_years(conference_name)
    if not years:
        logger.warning(f"No years configured for conference: {conference_name}")
        return None, "无可用年份"

    current_year = datetime.datetime.now().year
    start_year = min(years)

    for year_offset in range(max_lookback):
        check_year = current_year - year_offset
        if check_year < start_year:
            latest_configured = max([y for y in years if y <= current_year])
            return latest_configured, f"{start_year}年往前"

        if check_year not in years:
            continue

        try:
            collector = CollectorFactory.create_collector(conf, check_year)
            if collector.validate_year():
                if check_year == start_year:
                    year_range_str = f"{start_year}年"
                else:
                    year_range_str = f"{start_year}年-{check_year}年往前"
                return check_year, year_range_str
        except Exception as e:
            continue

    latest_configured = max([y for y in years if y <= current_year])
    return latest_configured, f"{start_year}年往前"

def handle_collect(args):
    setup_logging(args.verbose)

    coordinator = PaperCollectionCoordinator(db_path=args.db_path)
    if args.export_json:
        coordinator.export_json_path = args.export_json

    if args.list_conferences:
        list_conferences()
        return 0

    if args.export_json and not args.conference:
        logger.info(f"Exporting papers to {args.export_json}")
        coordinator.export_results(output_path=args.export_json)
        return 0

    if not args.conference:
        logger.error("No conference specified. Use --list-conferences to see available options.")
        return 1

    if args.conference.upper() == 'ALL':
        config_loader = ConfigLoader()
        conferences = config_loader.load_conferences()
        conference_names = [conf['name'] for conf in conferences]
    else:
        conference_names = [name.strip() for name in args.conference.split(',')]

    years = []
    if args.year:
        try:
            years = [int(y.strip()) for y in args.year.split(',')]
        except ValueError:
            logger.error("Invalid year format. Use comma-separated integers.")
            return 1

        conference_years = []
        for conf_name in conference_names:
            for year in years:
                conference_years.append((conf_name, year))
        logger.info(f"User specified years: {years}")
    else:
        logger.info("No year specified, finding available years for each conference...")
        conference_years = []
        year_info_list = []

        for conf_name in conference_names:
            found_year, year_range_str = find_available_year(conf_name, max_lookback=5)
            if found_year:
                conference_years.append((conf_name, found_year))
                year_info_list.append(f"{conf_name}: {year_range_str}")
            else:
                logger.warning(f"No available year found for {conf_name}, skipping")

    if not conference_years:
        logger.error("No valid conference-year pairs to process.")
        return 1

    results = coordinator.collect_multiple_conferences(conference_years)

    print("\n" + "=" * 80)
    print("Collection Summary")
    print("=" * 80)
    total_papers = 0
    for key, papers in results.items():
        print(f"{key}: {len(papers)} papers")
        total_papers += len(papers)

    print(f"\nTotal papers collected: {total_papers}")
    
    if args.export_json:
        coordinator.export_results(output_path=args.export_json)

    return 0

def handle_categorize(args):
    setup_logging(args.verbose)
    
    logger.info(f"Loading papers from {args.input}")
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            papers = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read input file {args.input}: {e}")
        return 1
        
    categorizer = TopicCategorizer(topic_config_path=args.topic_config)
    
    if not categorizer.topics:
        logger.error("No valid topics found in configuration. Aborting.")
        return 1
        
    logger.info(f"Loaded {len(categorizer.topics)} topics from {args.topic_config}")
    
    results = categorizer.categorize(papers, fill_missing_abstracts=args.fill_abstracts)
    
    categorizer.export_results(results, output_dir=args.output_dir)
    
    if args.fill_abstracts:
        try:
            with open(args.input, 'w', encoding='utf-8') as f:
                json.dump(papers, f, ensure_ascii=False, indent=2)
            logger.info(f"Updated {args.input} with newly fetched abstracts.")
        except Exception as e:
            logger.error(f"Failed to write updated papers back to {args.input}: {e}")
            
    return 0

def main():
    parser = argparse.ArgumentParser(
        description='Collect, match, and classify papers from top conferences.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python main.py collect --conference CVPR --year 2024 --export-json papers.json
  uv run python main.py categorize --input papers.json --fill-abstracts
        """
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    parser_collect = subparsers.add_parser('collect', help='Collect papers from conference websites')
    parser_collect.add_argument('--list-conferences', action='store_true', help='List all available conferences')
    parser_collect.add_argument('--conference', '-c', type=str, default='', help='Conference name(s), comma-separated or "ALL"')
    parser_collect.add_argument('--year', '-y', type=str, default='', help='Year(s), comma-separated')
    parser_collect.add_argument('--export-json', type=str, metavar='FILE', help='Export all papers to JSON file')
    parser_collect.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    parser_collect.add_argument('--db-path', type=str, default='papers.db', help='Path to SQLite database file')

    parser_categorize = subparsers.add_parser('categorize', help='Categorize existing JSON papers by abstract topics')
    parser_categorize.add_argument('--input', '-i', type=str, required=True, help='Input JSON file containing papers (e.g. papers.json)')
    parser_categorize.add_argument('--output-dir', '-o', type=str, default='Papers_By_Hot_Topic', help='Output directory to save categorized papers')
    parser_categorize.add_argument('--topic-config', type=str, default='config/topics.json', help='Path to the topic mapping JSON file (keyword regex)')
    parser_categorize.add_argument('--fill-abstracts', action='store_true', help='Automatically fetch missing abstracts from the original website (recommended)')
    parser_categorize.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == 'collect':
        return handle_collect(args)
    elif args.command == 'categorize':
        return handle_categorize(args)

    return 0

if __name__ == '__main__':
    sys.exit(main())
