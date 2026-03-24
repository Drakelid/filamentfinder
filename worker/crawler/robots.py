import httpx
from urllib.parse import urlparse
from typing import Dict, Optional
import structlog
from robotexclusionrulesparser import RobotExclusionRulesParser

from worker.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class RobotsChecker:
    """Handles robots.txt parsing and compliance."""
    
    def __init__(self):
        self._cache: Dict[str, RobotExclusionRulesParser] = {}
        self._user_agent = settings.crawler_user_agent
    
    def _get_robots_url(self, url: str) -> str:
        """Get the robots.txt URL for a given URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc
    
    async def fetch_robots(self, url: str) -> Optional[RobotExclusionRulesParser]:
        """Fetch and parse robots.txt for a URL."""
        domain = self._get_domain(url)
        
        if domain in self._cache:
            return self._cache[domain]
        
        robots_url = self._get_robots_url(url)
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    robots_url,
                    headers={"User-Agent": self._user_agent},
                    follow_redirects=True,
                )
                
                if response.status_code == 200:
                    parser = RobotExclusionRulesParser()
                    parser.parse(response.text)
                    self._cache[domain] = parser
                    logger.info("Fetched robots.txt", domain=domain)
                    return parser
                else:
                    logger.debug("No robots.txt found", domain=domain, status=response.status_code)
                    self._cache[domain] = None
                    return None
                    
        except Exception as e:
            logger.warning("Failed to fetch robots.txt", domain=domain, error=str(e))
            self._cache[domain] = None
            return None
    
    async def is_allowed(self, url: str) -> bool:
        """Check if crawling a URL is allowed by robots.txt."""
        if not settings.crawler_respect_robots_txt:
            return True
        
        parser = await self.fetch_robots(url)
        
        if parser is None:
            return True
        
        try:
            return parser.is_allowed(self._user_agent, url)
        except Exception:
            return True
    
    async def get_crawl_delay(self, url: str) -> Optional[float]:
        """Get the crawl delay specified in robots.txt."""
        parser = await self.fetch_robots(url)
        
        if parser is None:
            return None
        
        try:
            delay = parser.get_crawl_delay(self._user_agent)
            return float(delay) if delay else None
        except Exception:
            return None
