import sqlite3
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


class PaperStorage:
    """Storage for classified papers using SQLite database."""

    def __init__(self, db_path: str = "papers.db"):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Papers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                arxiv_id TEXT UNIQUE,
                title TEXT NOT NULL,
                abstract TEXT,
                primary_category TEXT,
                categories TEXT,  -- JSON array
                keywords TEXT,    -- JSON array
                topics TEXT,      -- JSON array
                authors TEXT,     -- JSON array
                conference TEXT,
                year INTEGER,
                url TEXT,
                pdf_url TEXT,
                supplement_url TEXT,
                links TEXT,       -- JSON object of all links
                published_date TEXT,
                updated_date TEXT,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for efficient queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_arxiv_id ON papers (arxiv_id)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_conference_year ON papers (conference, year)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_primary_category ON papers (primary_category)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_topics ON papers (topics)")

        # Paper categories junction table for many-to-many relationship
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_categories (
                paper_id INTEGER,
                category TEXT,
                is_primary BOOLEAN,
                FOREIGN KEY (paper_id) REFERENCES papers (id),
                PRIMARY KEY (paper_id, category)
            )
        """)

        # Keywords table for full-text search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
                title, abstract, keywords, content='papers', content_rowid='id'
            )
        """)

        conn.commit()
        conn.close()

    def store_paper(self, paper: Dict[str, Any]) -> bool:
        """Store a single paper in the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Convert lists to JSON strings
            categories_json = json.dumps(paper.get("categories", []))
            keywords_json = json.dumps(paper.get("keywords", []))
            topics_json = json.dumps(paper.get("topics", []))
            authors_json = json.dumps(paper.get("authors", []))
            links_json = json.dumps(paper.get("links", {}))

            # Check if paper already exists
            arxiv_id = paper.get("arxiv_id")
            title = paper.get("title")

            if arxiv_id:
                cursor.execute("SELECT id FROM papers WHERE arxiv_id = ?", (arxiv_id,))
            else:
                cursor.execute("SELECT id FROM papers WHERE title = ?", (title,))

            existing = cursor.fetchone()

            if existing:
                # Update existing paper
                cursor.execute(
                    """
                    UPDATE papers SET
                        title = ?, abstract = ?, primary_category = ?, categories = ?,
                        keywords = ?, topics = ?, authors = ?, conference = ?, year = ?,
                        url = ?, pdf_url = ?, supplement_url = ?, links = ?,
                        published_date = ?, updated_date = ?,
                        source = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE arxiv_id = ?
                """,
                    (
                        paper.get("title"),
                        paper.get("abstract"),
                        paper.get("primary_category"),
                        categories_json,
                        keywords_json,
                        topics_json,
                        authors_json,
                        paper.get("conference"),
                        paper.get("year"),
                        paper.get("url"),
                        paper.get("pdf_url"),
                        paper.get("supplement_url"),
                        links_json,
                        paper.get("published_date"),
                        paper.get("updated_date"),
                        paper.get("source"),
                        paper.get("arxiv_id"),
                    ),
                )
                paper_id = existing[0]
            else:
                # Insert new paper
                cursor.execute(
                    """
                    INSERT INTO papers (
                        arxiv_id, title, abstract, primary_category, categories,
                        keywords, topics, authors, conference, year,
                        url, pdf_url, supplement_url, links,
                        published_date, updated_date, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        paper.get("arxiv_id"),
                        paper.get("title"),
                        paper.get("abstract"),
                        paper.get("primary_category"),
                        categories_json,
                        keywords_json,
                        topics_json,
                        authors_json,
                        paper.get("conference"),
                        paper.get("year"),
                        paper.get("url"),
                        paper.get("pdf_url"),
                        paper.get("supplement_url"),
                        links_json,
                        paper.get("published_date"),
                        paper.get("updated_date"),
                        paper.get("source"),
                    ),
                )
                paper_id = cursor.lastrowid

            # Update categories junction table
            cursor.execute(
                "DELETE FROM paper_categories WHERE paper_id = ?", (paper_id,)
            )

            # Insert primary category
            primary_category = paper.get("primary_category")
            if primary_category:
                cursor.execute(
                    "INSERT INTO paper_categories (paper_id, category, is_primary) VALUES (?, ?, ?)",
                    (paper_id, primary_category, True),
                )

            # Insert secondary categories
            for category in paper.get("categories", []):
                cursor.execute(
                    "INSERT INTO paper_categories (paper_id, category, is_primary) VALUES (?, ?, ?)",
                    (paper_id, category, False),
                )

            # Update full-text search index
            cursor.execute(
                """
                INSERT OR REPLACE INTO papers_fts (rowid, title, abstract, keywords)
                VALUES (?, ?, ?, ?)
            """,
                (paper_id, paper.get("title"), paper.get("abstract"), keywords_json),
            )

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"Failed to store paper {paper.get('arxiv_id')}: {e}")
            return False

    def store_papers(self, papers: List[Dict[str, Any]]) -> int:
        """Store multiple papers and return count of successful stores."""
        success_count = 0
        for paper in papers:
            if self.store_paper(paper):
                success_count += 1
        return success_count

    def get_paper_by_arxiv_id(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a paper by arXiv ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,))
            row = cursor.fetchone()

            if row:
                paper = dict(row)
                # Parse JSON fields
                for field in ["categories", "keywords", "topics", "authors"]:
                    if paper.get(field):
                        paper[field] = json.loads(paper[field])
                return paper
            return None

        except Exception as e:
            logger.error(f"Failed to retrieve paper {arxiv_id}: {e}")
            return None
        finally:
            conn.close()

    def search_papers(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Search papers using full-text search."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT p.* FROM papers p
                JOIN papers_fts f ON p.id = f.rowid
                WHERE papers_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """,
                (query, limit),
            )

            papers = []
            for row in cursor.fetchall():
                paper = dict(row)
                # Parse JSON fields
                for field in ["categories", "keywords", "topics", "authors"]:
                    if paper.get(field):
                        paper[field] = json.loads(paper[field])
                papers.append(paper)

            return papers

        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            return []
        finally:
            conn.close()

    def get_papers_by_conference(
        self, conference: str, year: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get all papers from a specific conference (optionally for a specific year)."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if year:
                cursor.execute(
                    "SELECT * FROM papers WHERE conference = ? AND year = ? ORDER BY title",
                    (conference, year),
                )
            else:
                cursor.execute(
                    "SELECT * FROM papers WHERE conference = ? ORDER BY year DESC, title",
                    (conference,),
                )

            papers = []
            for row in cursor.fetchall():
                paper = dict(row)
                # Parse JSON fields
                for field in ["categories", "keywords", "topics", "authors"]:
                    if paper.get(field):
                        paper[field] = json.loads(paper[field])
                papers.append(paper)

            return papers

        except Exception as e:
            logger.error(f"Failed to get papers for {conference} {year}: {e}")
            return []
        finally:
            conn.close()

    def get_papers_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all papers with a specific category (primary or secondary)."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT p.* FROM papers p
                JOIN paper_categories pc ON p.id = pc.paper_id
                WHERE pc.category = ?
                ORDER BY p.year DESC, p.conference, p.title
            """,
                (category,),
            )

            papers = []
            for row in cursor.fetchall():
                paper = dict(row)
                # Parse JSON fields
                for field in ["categories", "keywords", "topics", "authors"]:
                    if paper.get(field):
                        paper[field] = json.loads(paper[field])
                papers.append(paper)

            return papers

        except Exception as e:
            logger.error(f"Failed to get papers for category {category}: {e}")
            return []
        finally:
            conn.close()

    def export_to_json(self, output_path: str, conferences: Optional[List[str]] = None):
        """Export papers to JSON file."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if conferences:
                placeholders = ",".join(["?"] * len(conferences))
                cursor.execute(
                    f"""
                    SELECT * FROM papers WHERE conference IN ({placeholders}) ORDER BY conference, year, title
                """,
                    conferences,
                )
            else:
                cursor.execute("SELECT * FROM papers ORDER BY conference, year, title")

            papers = []
            for row in cursor.fetchall():
                paper = dict(row)
                # Parse JSON fields
                for field in ["categories", "keywords", "topics", "authors"]:
                    if paper.get(field):
                        paper[field] = json.loads(paper[field])
                papers.append(paper)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(papers, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported {len(papers)} papers to {output_path}")

        except Exception as e:
            logger.error(f"Failed to export to JSON: {e}")
            raise
        finally:
            conn.close()

    def export_to_csv(self, output_path: str, conferences: Optional[List[str]] = None):
        """Export papers to CSV file."""
        import csv

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if conferences:
                placeholders = ",".join(["?"] * len(conferences))
                cursor.execute(
                    f"""
                    SELECT * FROM papers WHERE conference IN ({placeholders}) ORDER BY conference, year, title
                """,
                    conferences,
                )
            else:
                cursor.execute("SELECT * FROM papers ORDER BY conference, year, title")

            rows = cursor.fetchall()
            if not rows:
                logger.info(f"No papers found to export to CSV.")
                return 0

            # Get column names
            fieldnames = rows[0].keys()

            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    paper = dict(row)
                    # Convert JSON fields back to string representations or keep as is since they are strings in db
                    writer.writerow(paper)

            logger.info(f"Exported {len(rows)} papers to {output_path}")
            return len(rows)

        except Exception as e:
            logger.error(f"Failed to export to CSV: {e}")
            raise
        finally:
            conn.close()
