# Chemin exact : run.py [MODIFIED]
# [Gemini]
import sys
import logging
from scraper.orchestrator import PipelineOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("RunScript")

def main() -> None:
    logger.info("Démarrage du runner principal V1 blindée")
    try:
        orchestrator = PipelineOrchestrator()
        success = orchestrator.run()
        if not success:
            logger.error("Le pipeline a retourné un statut d'échec.")
            sys.exit(1)
        logger.info("Pipeline exécuté avec succès.")
    except Exception as e:
        logger.critical(f"Exception critique non gérée dans le runner : {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()