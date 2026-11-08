# Chemin exact : scraper/orchestrator.py
# [Gemini]
import logging
from typing import Optional
from scraper.playwright_engine import PlaywrightScraperEngine

logger = logging.getLogger("PipelineOrchestrator")

class PipelineOrchestrator:
    def __init__(self, target_url: str = "https://www.google.com"):
        self.target_url = target_url
        self.engine = PlaywrightScraperEngine()

    def run(self) -> bool:
        logger.info(f"Démarrage de l'orchestration du pipeline pour l'URL : {self.target_url}")
        html_content: Optional[str] = self.engine.fetch_page_content(self.target_url)
        if not html_content:
            logger.error("PipelineOrchestrator: Échec de la récupération du contenu HTML. Arrêt du pipeline.")
            return False
        logger.info("PipelineOrchestrator: Contenu HTML récupéré avec succès.")
        return True