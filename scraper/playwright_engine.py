# Chemin exact : scraper/playwright_engine.py
# [Gemini]
import logging
import time
from typing import Optional
import aiohttp
import asyncio
from bs4 import BeautifulSoup

logger = logging.getLogger("PlaywrightScraperEngine")

class PlaywrightScraperEngine:
    def __init__(self, timeout: int = 30000, max_retries: int = 3, backoff_factor: float = 2.0) -> None:
        self.timeout = timeout / 1000.0  # Conversion en secondes pour aiohttp
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def fetch_html(self, url: str) -> Optional[str]:
        async def _fetch() -> Optional[str]:
            headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) V1Blindee/1.0"}
            timeout_obj = aiohttp.ClientTimeout(total=self.timeout)
            attempt = 0
            while attempt < self.max_retries:
                attempt += 1
                logger.info(f"Tentative {attempt}/{self.max_retries} de récupération de l'URL (HTTP) : {url}")
                try:
                    async with aiohttp.ClientSession(headers=headers, timeout=timeout_obj) as session:
                        async with session.get(url) as response:
                            if response.status == 200:
                                return await response.text()
                            logger.warning(f"Statut HTTP inattendu {response.status} pour {url}")
                except Exception as e:
                    logger.warning(f"Échec de la tentative {attempt} pour {url} : {e}")
                
                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff_factor ** (attempt - 1))
            
            logger.error(f"Épuisement des tentatives ({self.max_retries}) pour l'URL : {url}")
            return None

        try:
            return asyncio.run(_fetch())
        except RuntimeError:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(_fetch())

    def fetch_page_content(self, url: str) -> Optional[str]:
        return self.fetch_html(url)