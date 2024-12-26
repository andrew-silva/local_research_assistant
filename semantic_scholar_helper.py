import requests
from functools import lru_cache
from typing import List, Dict, Any, Optional
import logging
import time
from config import Config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SemanticScholarAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"x-api-key": api_key} if api_key else {}
        self.search_url = "http://api.semanticscholar.org/graph/v1/paper/search"
        self.rec_url = "https://api.semanticscholar.org/recommendations/v1/papers"
        self.session = requests.Session()

    @lru_cache(maxsize=Config.CACHE_SIZE)
    def search_papers(self, query: str, year_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        url = self.search_url
        all_papers = []

        # Parse year filter
        year_start = None
        if year_filter and year_filter.endswith('-'):
            try:
                year_start = int(year_filter[:-1])
            except ValueError:
                logger.warning(f"Invalid year filter: {year_filter}")

        for page in range(Config.MAX_PAGES):
            time.sleep(1)  # Rate limiting

            params = {
                "query": query,
                "fields": "title,url,abstract,publicationTypes,publicationDate,"
                          "openAccessPdf,citationCount,authors,paperId,tldr",
                "limit": Config.PAPERS_PER_PAGE,
                "offset": page * Config.PAPERS_PER_PAGE,
                **({"year": f"{year_start}-"} if year_start else {})
            }

            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=self.headers,
                    timeout=Config.TIMEOUT
                )
                response.raise_for_status()
                papers = response.json().get("data", [])

                # If we got fewer papers than requested, we've reached the end
                if len(papers) < Config.PAPERS_PER_PAGE:
                    all_papers.extend(papers)
                    break

                all_papers.extend(papers)

            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching papers on page {page}: {e}")
                break  # Stop pagination on error

        return all_papers

    def get_recommended_papers(self, paper_ids: List[str], limit: int = 20) -> List[Dict[str, Any]]:
        if not paper_ids:
            return []

        url = self.rec_url
        params = {
            "fields": "title,url,abstract,citationCount,authors,publicationDate,openAccessPdf,paperId,tldr",
            "limit": limit
        }

        try:
            response = self.session.post(
                url,
                json={"positivePaperIds": paper_ids},
                params=params,
                headers=self.headers,
                timeout=Config.TIMEOUT
            )
            response.raise_for_status()
            return response.json().get('recommendedPapers', [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching recommendations: {e}")
            return []
