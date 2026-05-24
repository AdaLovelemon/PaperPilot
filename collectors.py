"""
Paper collectors for various conference proceedings.
Supports: CVF (CVPR/ICCV), PMLR (ICML/CoRL), RSS, NeurIPS, OpenReview (ICLR).
"""

import re
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Set this to > 0 to truncate each collector's output (for testing).
# Main.py also has --max-papers, but this avoids the slow work of fetching
# thousands of papers only to slice at the end.
_LIMIT = 0  # 0 = no limit

# Shared headers for all HTTP requests
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Link-parsing helpers (shared across collectors)
# ---------------------------------------------------------------------------

def _classify_link(href: str, link_text: str) -> str:
    """Return a canonical link-type key for a given href and visible text."""
    t = link_text.strip().lower()
    hl = href.lower()
    # arXiv
    if "arxiv.org/abs" in hl:
        return "arxiv"
    # PDF
    if t == "pdf" or hl.endswith(".pdf") or "/pdf/" in hl:
        return "pdf"
    # supplementary
    if any(w in t for w in ("supplement", "supp", "supplementary")):
        return "supplement"
    # BibTeX
    if t in ("bibtex", "bib") or "bibtex" in hl:
        return "bibtex"
    # code / github
    if "code" in t or "github" in hl or "code" in hl:
        return "code"
    # video
    if "video" in t:
        return "video"
    # poster
    if "poster" in t:
        return "poster"
    # slides
    if "slides" in t:
        return "slides"
    # HTML / paper page
    if t in ("html", "paper", "abs") or "/html/" in hl:
        return "html"
    return "other"


def _extract_arxiv_id(href: str) -> Optional[str]:
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([\d\.v]+)", href)
    return m.group(1) if m else None


def _parse_links_from_elements(
    link_elems: List,
    base_url: str,
) -> Dict[str, str]:
    """Parse a list of <a> elements into a dict of canonical link types.

    Returns a dict like {"pdf": "https://...", "arxiv": "https://...", ...}.
    """
    links: Dict[str, str] = {}
    for a in link_elems:
        href = a.get("href", "")
        if not href:
            continue
        abs_url = urljoin(base_url, href)
        key = _classify_link(href, a.text)
        # Prefer first occurrence of each type
        if key not in links:
            links[key] = abs_url
    return links


# ---------------------------------------------------------------------------
# CVF collector  (CVPR, ICCV)
# ---------------------------------------------------------------------------

def _fetch_cvf_papers(name: str, year: int) -> List[Dict]:
    """Fetch papers from openaccess.thecvf.com (CVPR / ICCV)."""
    url = f"https://openaccess.thecvf.com/{name}{year}?day=all"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Failed to fetch %s %s: %s", name, year, e)
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    papers: List[Dict] = []

    # Single pass: walk dt/dd children sequentially instead of O(N²) sibling lookups
    pending = None  # {"title": ..., "url": ..., "dds": [...]}
    for child in soup.find_all(["dt", "dd"]):
        if child.name == "dt" and child.get("class") and "ptitle" in child["class"]:
            # Finalize previous paper
            if pending is not None:
                papers.append(_parse_cvf_paper(pending, url, name, year))
            title_link = child.find("a")
            pending = {
                "title": title_link.text.strip() if title_link else "",
                "url": urljoin(url, title_link["href"]) if title_link else "",
                "dds": [],
            }
        elif child.name == "dd" and pending is not None:
            pending["dds"].append(child)

    if pending is not None:
        papers.append(_parse_cvf_paper(pending, url, name, year))

    logger.info("Fetched %d papers from %s %s", len(papers), name, year)

    # Respect _LIMIT before expensive detail scraping
    if _LIMIT > 0 and len(papers) > _LIMIT:
        papers = papers[:_LIMIT]

    # Scrape individual pages for abstract (CVF listing pages no longer include abstracts)
    if papers:
        logger.info("Scraping paper details for %d papers...", len(papers))
        papers = _scrape_cvf_paper_details(papers, url)
        logger.info("Paper detail scraping complete.")

    return papers


def _parse_cvf_paper(pending: dict, base_url: str, conf: str, year: int) -> Dict:
    """Parse a single CVF paper entry from pre-collected dt+dd elements.

    Handles two formats:
      - New: authors in <form class="authsearch"><a>Author Name</a></form>, links in later DDs
      - Old: free-text "Authors: N1, N2<br>Abstract..." in first DD
    """
    try:
        # Extract authors from form elements (new format) or free text (old)
        authors: List[str] = []
        abstract = ""  # listing page no longer has abstracts
        link_elems = []

        if pending["dds"]:
            first_dd = pending["dds"][0]
            auth_forms = first_dd.find_all("form", class_="authsearch")
            if auth_forms:
                # New format: authors in <form> elements
                for form in auth_forms:
                    a = form.find("a")
                    if a and a.text.strip():
                        authors.append(a.text.strip().rstrip(","))
                # Links are in DDs without auth forms
                for dd in pending["dds"]:
                    if not dd.find("form", class_="authsearch"):
                        link_elems.extend(dd.find_all("a"))
            else:
                # Old format: free-text "Authors: N1, N2<br>Abstract..."
                strings = list(first_dd.stripped_strings)
                if strings:
                    author_text = strings[0].replace("Authors:", "").strip()
                    authors = [a.strip() for a in re.split(r",\s*|\s+and\s+", author_text) if a.strip()]
                if len(strings) > 1:
                    abstract = strings[1]
                link_elems = [a for dd in pending["dds"] for a in dd.find_all("a")]

        links = _parse_links_from_elements(link_elems, base_url)
        pdf_url = links.get("pdf", "")
        arxiv_id = _extract_arxiv_id(links.get("arxiv", ""))

        return {
            "title": pending["title"],
            "authors": authors,
            "abstract": abstract,
            "url": pending["url"],
            "pdf_url": pdf_url,
            "arxiv_id": arxiv_id,
            "links": links,
            "conference": conf,
            "year": year,
            "source": "cvf",
        }
    except Exception as e:
        logger.error("Error parsing CVF entry: %s", e)
        return {
            "title": pending["title"],
            "authors": [],
            "abstract": "",
            "url": pending["url"],
            "pdf_url": "",
            "arxiv_id": None,
            "links": {},
            "conference": conf,
            "year": year,
            "source": "cvf",
        }


def _scrape_cvf_paper_details(papers: List[Dict], base_url: str) -> List[Dict]:
    """Scrape individual CVF paper pages for abstracts.
    Uses concurrent requests with retries for robustness.
    """
    import concurrent.futures
    import time

    def _scrape_one(paper: Dict) -> Dict:
        url = paper.get("url", "")
        if not url:
            return paper

        for attempt in range(3):
            try:
                resp = requests.get(url, headers=_HEADERS, timeout=15)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.content, "html.parser")

                abs_div = soup.find("div", id="abstract")
                if abs_div:
                    paper["abstract"] = abs_div.text.strip()

                break  # success, no more retries
            except Exception as e:
                if attempt < 2:
                    wait = (attempt + 1) * 2  # 2s, 4s backoff
                    logger.debug("Retrying CVF paper detail in %ds (%s)", wait, e)
                    time.sleep(wait)
                else:
                    logger.debug("Failed to scrape CVF paper detail: %s", e)

        return paper

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        return list(executor.map(_scrape_one, papers))


# ---------------------------------------------------------------------------
# OpenReview v2 collector  (ICLR)
# ---------------------------------------------------------------------------

def _or_v2_conference_id(name: str, year: int) -> str:
    """Map conference name/year to OpenReview v2 venue ID."""
    mapping = {
        "ICLR": f"ICLR.cc/{year}/Conference",
    }
    return mapping.get(name.upper(), f"{name.upper()}.cc/{year}/Conference")


def _fetch_openreview_v2_papers(name: str, year: int) -> List[Dict]:
    """Fetch accepted papers from OpenReview API.

    Tries api2.openreview.net (v2-native, ICLR 2024+) first,
    falls back to api.openreview.net (v1-migrated, ICLR 2022-2023).
    No OAuth needed for public reads.
    """
    conf_id = _or_v2_conference_id(name, year)
    papers: List[Dict] = []

    # Try v2-native endpoint first, then v1-migrated
    api_attempts = [
        {"base": "https://api2.openreview.net/notes", "invitation": f"{conf_id}/-/Submission",
         "params": {"content.venueid": conf_id}},
        {"base": "https://api.openreview.net/notes", "invitation": f"{conf_id}/-/Blind_Submission",
         "params": {}},
    ]

    api_base = None
    inv_params = None
    invitation = None
    for attempt in api_attempts:
        params = {"invitation": attempt["invitation"], "limit": 10}
        params.update(attempt["params"])
        try:
            resp = requests.get(attempt["base"], params=params, headers=_HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("notes"):
                api_base = attempt["base"]
                inv_params = attempt["params"]
                invitation = attempt["invitation"]
                break
        except requests.RequestException as e:
            logger.debug("OpenReview query failed (%s): %s", attempt["invitation"], e)

    if not api_base:
        logger.warning("No papers found for %s %s on OpenReview", name, year)
        return []

    def _v(c: dict, key: str, default=""):
        val = c.get(key, default)
        return val.get("value", val) if isinstance(val, dict) else val

    # Paginate through all notes
    offset = 0
    page_size = 1000
    while True:
        params = {"invitation": invitation, "limit": page_size, "offset": offset}
        params.update(inv_params)
        try:
            resp = requests.get(api_base, params=params, headers=_HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.warning("OpenReview pagination failed at offset %d: %s", offset, e)
            break

        notes = data.get("notes", [])
        if not notes:
            break

        for note in notes:
            try:
                c = note.get("content", {})
                venue = _v(c, "venue", "")

                # Skip non-accepted submissions
                if venue.startswith("Submitted to") or "Withdrawn" in venue or "Desk Rejected" in venue:
                    continue

                title = _v(c, "title", "").strip()
                if not title:
                    continue

                pdf_url = _v(c, "pdf", "")
                if pdf_url and not pdf_url.startswith("http"):
                    pdf_url = f"https://openreview.net{pdf_url}"
                arxiv_id = _extract_arxiv_id(pdf_url) if pdf_url else None

                authors_raw = _v(c, "authors", [])
                authors = [a.split("@")[0].replace(".", " ").replace("_", " ").title()
                           if "@" in a else a for a in authors_raw] if isinstance(authors_raw, list) else []

                abstract = _v(c, "abstract", "")
                keywords = _v(c, "keywords", [])

                links = {}
                if pdf_url:
                    links["pdf"] = pdf_url
                supp = _v(c, "supplementary_material", "")
                if supp:
                    links["supplement"] = supp

                papers.append({
                    "title": title,
                    "authors": authors,
                    "abstract": abstract,
                    "url": f"https://openreview.net/forum?id={note.get('forum', '')}",
                    "pdf_url": pdf_url,
                    "arxiv_id": arxiv_id,
                    "links": links,
                    "keywords": keywords if isinstance(keywords, list) else [],
                    "conference": name,
                    "year": year,
                    "source": "openreview_v2",
                })
            except Exception as e:
                logger.error("Error parsing OpenReview entry: %s", e)

        offset += len(notes)
        if len(notes) < page_size:
            break

    logger.info("Fetched %d papers from OpenReview %s %s", len(papers), name, year)
    return papers


# ---------------------------------------------------------------------------
# PMLR collector  (ICML, CoRL)
# ---------------------------------------------------------------------------

_PMLR_VOLUMES = {
    "ICML": {2020: "v119", 2021: "v139", 2022: "v162", 2023: "v202", 2024: "v235", 2025: "v267"},
    "CORL": {2017: "v78", 2018: "v87", 2019: "v100", 2020: "v155", 2021: "v164", 2022: "v205", 2023: "v229", 2024: "v270", 2025: "v305"},
}


def _scrape_pmlr_paper_details(papers: List[Dict]) -> List[Dict]:
    """Scrape individual PMLR paper pages for abstracts.
    Uses concurrent requests for speed.
    """
    import concurrent.futures

    def _scrape_one(paper: Dict) -> Dict:
        url = paper.get("url", "")
        if not url:
            return paper
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")

            abstract_div = soup.find("div", id="abstract")
            if abstract_div:
                paper["abstract"] = abstract_div.text.strip()

        except Exception as e:
            logger.debug("Failed to scrape PMLR paper detail: %s", e)

        return paper

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        return list(executor.map(_scrape_one, papers))


def _fetch_pmlr_papers(name: str, year: int) -> List[Dict]:
    """Fetch papers from proceedings.mlr.press (ICML)."""
    volumes = _PMLR_VOLUMES.get(name.upper(), {})
    vol = volumes.get(year)
    if not vol:
        logger.warning("Unknown PMLR volume for %s %s", name, year)
        return []

    url = f"https://proceedings.mlr.press/{vol}/"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Failed to fetch PMLR %s %s: %s", name, year, e)
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    papers: List[Dict] = []

    for paper_div in soup.find_all("div", class_="paper"):
        try:
            title_elem = paper_div.find("p", class_="title")
            if not title_elem:
                continue
            title = title_elem.text.strip()

            # Authors: may be in p.authors (older PMLR) or p.details > span.authors (newer PMLR)
            authors = []
            authors_elem = paper_div.find("p", class_="authors")
            if authors_elem:
                authors = [a.strip() for a in authors_elem.text.replace("Authors:", "").split(",") if a.strip()]
            else:
                span_authors = paper_div.select_one("p.details span.authors")
                if span_authors:
                    authors = [a.strip() for a in span_authors.get_text(strip=True).split(",")] if span_authors else []

            link_elems = paper_div.find_all("a")
            links = _parse_links_from_elements(link_elems, url)
            pdf_url = links.get("pdf", "")
            arxiv_id = _extract_arxiv_id(links.get("arxiv", ""))
            paper_url = links.get("html", "")

            papers.append({
                "title": title,
                "authors": authors,
                "abstract": "",
                "url": paper_url,
                "pdf_url": pdf_url,
                "arxiv_id": arxiv_id,
                "links": links,
                "conference": name,
                "year": year,
                "source": "pmlr",
            })
        except Exception as e:
            logger.error("Error parsing PMLR entry: %s", e)

    logger.info("Fetched %d papers from PMLR %s %s", len(papers), name, year)

    # Respect _LIMIT before expensive detail scraping
    if _LIMIT > 0 and len(papers) > _LIMIT:
        papers = papers[:_LIMIT]

    # Scrape individual pages for abstract
    if papers:
        logger.info("Scraping paper details for %d papers...", len(papers))
        papers = _scrape_pmlr_paper_details(papers)
        logger.info("Paper detail scraping complete.")

    return papers


# ---------------------------------------------------------------------------
# RSS collector
# ---------------------------------------------------------------------------

def _rss_volume(year: int) -> int:
    """RSS uses volume numbers (year - 2004). RSS XXI = 2025, RSS XX = 2024, etc."""
    return year - 2004


def _fetch_rss_papers(year: int) -> List[Dict]:
    """Fetch papers from roboticsproceedings.org (RSS). Uses volume numbers."""
    vol = _rss_volume(year)
    index_url = f"https://www.roboticsproceedings.org/rss{vol}/index.html"
    try:
        resp = requests.get(index_url, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Failed to fetch RSS %s: %s", year, e)
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    papers: List[Dict] = []

    for a in soup.find_all("a", href=re.compile(r"^p\d+\.html$")):
        if _LIMIT > 0 and len(papers) >= _LIMIT:
            break
        title = a.text.strip()
        # Skip non-paper links (page titles like "RSS XIX")
        if not title or re.match(r"^(Robotics|RSS|Table|Content|Author)", title, re.I):
            continue
        href = a["href"]
        paper_url = urljoin(f"https://www.roboticsproceedings.org/rss{_rss_volume(year)}/", href)
        try:
            pr = requests.get(paper_url, headers=_HEADERS, timeout=30)
            pr.raise_for_status()
        except requests.RequestException as e:
            logger.warning("Failed to fetch %s: %s", paper_url, e)
            continue

        psoup = BeautifulSoup(pr.content, "html.parser")
        try:
            # Use the title from the index page link text
            authors: List[str] = []
            abstract = ""
            for tag in psoup.find_all(["p", "div"]):
                txt = tag.get_text().strip()
                low = txt.lower()
                if "author" in low and not authors:
                    authors = [a.strip() for a in txt.replace("Authors:", "").replace("Author:", "").split(",") if a.strip()]
                if "abstract" in low and not abstract:
                    abstract = txt.replace("Abstract:", "").strip()

            link_elems = psoup.find_all("a")
            links = _parse_links_from_elements(link_elems, f"https://www.roboticsproceedings.org/rss{_rss_volume(year)}/")
            pdf_url = links.get("pdf", "")
            arxiv_id = _extract_arxiv_id(links.get("arxiv", ""))

            papers.append({
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "url": paper_url,
                "pdf_url": pdf_url,
                "arxiv_id": arxiv_id,
                "links": links,
                "conference": "RSS",
                "year": year,
                "source": "rss",
            })
        except Exception as e:
            logger.error("Error parsing RSS paper %s: %s", paper_url, e)

    logger.info("Fetched %d papers from RSS %s", len(papers), year)
    return papers


# ---------------------------------------------------------------------------
# NeurIPS collector  (papers.nips.cc)
# ---------------------------------------------------------------------------

def _scrape_neurips_paper_details(papers: List[Dict]) -> List[Dict]:
    """Scrape individual NeurIPS paper pages for abstract, PDF URL, and date.
    Uses concurrent requests for speed.
    """
    import concurrent.futures

    def _scrape_one(paper: Dict) -> Dict:
        url = paper.get("url", "")
        if not url:
            return paper
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")

            # Abstract from <h2>Abstract</h2> + next sibling
            h2 = soup.find("h2", string=lambda t: t and "abstract" in t.lower())
            if h2:
                nxt = h2.find_next_sibling(["p", "div"])
                if nxt:
                    paper["abstract"] = nxt.text.strip()

            # PDF URL from meta tag
            pdf_meta = soup.find("meta", attrs={"name": "citation_pdf_url"})
            if pdf_meta:
                paper["pdf_url"] = pdf_meta.get("content", "")

            # Publication date
            date_meta = soup.find("meta", attrs={"name": "citation_publication_date"})
            if date_meta:
                paper["published_date"] = date_meta.get("content", "")

        except Exception as e:
            logger.debug("Failed to scrape NeurIPS paper detail: %s", e)

        return paper

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        return list(executor.map(_scrape_one, papers))


def _fetch_neurips_papers(year: int) -> List[Dict]:
    """Fetch papers from papers.nips.cc, scraping detail pages for abstracts and PDF URLs."""
    index_url = f"https://papers.nips.cc/paper_files/paper/{year}"
    try:
        resp = requests.get(index_url, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Failed to fetch NeurIPS %s: %s", year, e)
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    papers: List[Dict] = []
    seen_titles: set = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if f"/paper_files/paper/{year}/hash/" not in href or "-Abstract-Conference" not in href:
            continue
        title = a.text.strip()
        if not title or title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())

        paper_url = f"https://papers.nips.cc{href}"

        # Extract authors from parent div's .paper-authors span (listing page)
        authors = []
        parent_div = a.find_parent("div", class_="paper-content")
        if parent_div:
            authors_span = parent_div.find("span", class_="paper-authors")
            if authors_span:
                authors = [au.strip() for au in authors_span.text.split(",") if au.strip()]

        papers.append({
            "title": title,
            "authors": authors,
            "abstract": "",
            "url": paper_url,
            "pdf_url": "",
            "arxiv_id": None,
            "links": {},
            "conference": "NeurIPS",
            "year": year,
            "source": "neurips",
        })

    logger.info("Fetched %d papers from NeurIPS %s", len(papers), year)

    # Respect _LIMIT before expensive detail scraping
    if _LIMIT > 0 and len(papers) > _LIMIT:
        papers = papers[:_LIMIT]

    # Scrape individual pages for abstract, PDF URL, and date
    if papers:
        logger.info("Scraping paper details for %d papers...", len(papers))
        papers = _scrape_neurips_paper_details(papers)
        logger.info("Paper detail scraping complete.")

    return papers


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _truncate(papers: List) -> List:
    """When _LIMIT > 0, return only the first _LIMIT papers."""
    if _LIMIT > 0 and len(papers) > _LIMIT:
        return papers[:_LIMIT]
    return papers


_COLLECTOR_MAP = {
    "CVPR":  ("cvf", lambda n, y: _fetch_cvf_papers(n, y)),
    "ICCV":  ("cvf", lambda n, y: _fetch_cvf_papers(n, y)),
    "NEURIPS": ("neurips", lambda n, y: _fetch_neurips_papers(y)),
    "ICLR":  ("openreview_v2", _fetch_openreview_v2_papers),
    "CORL":  ("pmlr", _fetch_pmlr_papers),
    "ICML":  ("pmlr", _fetch_pmlr_papers),
    "RSS":   ("rss", lambda n, y: _fetch_rss_papers(y)),
}


def validate_year(name: str, year: int) -> bool:
    """Check whether the conference website is reachable for *year*."""
    conf_name = name.upper()
    try:
        if conf_name in _COLLECTOR_MAP:
            base_urls = {
                "CVPR": f"https://openaccess.thecvf.com/CVPR{year}?day=all",
                "ICCV": f"https://openaccess.thecvf.com/ICCV{year}?day=all",
                "NEURIPS": f"https://papers.nips.cc/paper_files/paper/{year}",
                "ICLR": f"https://api2.openreview.net/notes?invitation=ICLR.cc/{year}/Conference/-/Submission&content.venueid=ICLR.cc/{year}/Conference&limit=1",
                "CORL": f"https://proceedings.mlr.press/{_PMLR_VOLUMES.get('CORL', {}).get(year, '')}/",
                "ICML": f"https://proceedings.mlr.press/{_PMLR_VOLUMES.get('ICML', {}).get(year, '')}/",
                "RSS": f"https://www.roboticsproceedings.org/rss{_rss_volume(year)}/index.html",
            }
            url = base_urls.get(conf_name)
            if not url:
                return False
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            return resp.ok
    except requests.RequestException:
        pass
    return False


def fetch_papers(name: str, year: int) -> List[Dict]:
    """Fetch papers for a conference *name* in *year*.

    Returns a list of paper dicts (may be empty if unreachable or unsupported).
    """
    entry = _COLLECTOR_MAP.get(name.upper())
    if entry is None:
        logger.warning("Unsupported conference: %s", name)
        return []
    _, fn = entry
    papers = fn(name, year)
    return _truncate(papers)


def supported_conferences() -> List[str]:
    """Return list of supported conference names."""
    return list(_COLLECTOR_MAP.keys())
