# Chemin exact : scraper/http_engine.py [NEW]
import asyncio
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger("HttpScraperEngine")


class HttpScraperEngine:
    def __init__(
        self,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def fetch_html(self, url: str) -> Optional[str]:
        if not url or not url.startswith(("http://", "https://")):
            logger.error("URL invalide ou non HTTP rejetée : %s", url)
            return None

        return asyncio.run(self._fetch_html(url))

    async def _fetch_html(self, url: str) -> Optional[str]:
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        backoff = 1.0

        for attempt in range(1, self.max_retries + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.text()
                        if response.status in (403, 429):
                            logger.warning(
                                "Accès refusé ou limité (HTTP %s) pour %s; arrêt des tentatives.",
                                response.status,
                                url,
                            )
                            return None
                        logger.warning(
                            "Tentative %s/%s - Statut HTTP inattendu %s pour %s",
                            attempt,
                            self.max_retries,
                            response.status,
                            url,
                        )
            except (aiohttp.ClientError, asyncio.TimeoutError) as error:
                logger.warning(
                    "Tentative %s/%s échouée pour %s : %s",
                    attempt,
                    self.max_retries,
                    url,
                    error,
                )

            if attempt < self.max_retries:
                await asyncio.sleep(backoff)
                backoff *= self.backoff_factor

        logger.error("Échec définitif de la récupération après %s tentatives : %s", self.max_retries, url)
        return None