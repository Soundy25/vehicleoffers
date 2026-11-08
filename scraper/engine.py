# scraper/engine.py [NEW]
"""
Description : Moteur de scraping asynchrone hautement résilient, doté d'une gestion 
robuste des timeouts, de retries avec backoff exponentiel et d'un typage strict mypy.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
import aiohttp

logger = logging.getLogger("SecureScraperEngine")

class SecureScraperEngine:
    """Moteur de requêtage réseau Zero Trust avec politique de résilience intégrée."""

    def __init__(self, timeout_seconds: float = 10.0, max_retries: int = 3) -> None:
        self.timeout_seconds: float = timeout_seconds
        self.max_retries: int = max_retries

    async def fetch_url(self, url: str) -> Optional[str]:
        """Récupère une ressource web avec gestion des retries et backoff exponentiel."""
        if not url or not url.startswith(("http://", "https://")):
            logger.error(f"URL invalide ou non sécurisée rejetée : {url}")
            return None

        backoff: float = 1.0
        client_timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)

        for attempt in range(1, self.max_retries + 1):
            try:
                async with aiohttp.ClientSession(timeout=client_timeout) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.text()
                        logger.warning(
                            f"Tentative {attempt}/{self.max_retries} - Statut HTTP inattendu {response.status} pour l'URL : {url}"
                        )
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(
                    f"Tentative {attempt}/{self.max_retries} échouée suite à une erreur réseau/timeout : {e}"
                )
            except Exception as e:
                logger.critical(f"Erreur critique inattendue lors de la requête vers {url} : {e}", exc_info=True)
                break

            if attempt < self.max_retries:
                await asyncio.sleep(backoff)
                backoff *= 2.0  # Backoff exponentiel

        logger.error(f"Échec définitif du scraping pour l'URL après {self.max_retries} tentatives : {url}")
        return None