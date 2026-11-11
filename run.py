# Chemin exact : run.py [MODIFIED]
# Chemin exact : run.py [MODIFIÉ]
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
        orchestrator = PipelineOrchestrator.from_environment()
        success = orchestrator.run()
        if not success:
            logger.error("Le pipeline a retourné un statut d'échec.")
            sys.exit(1)
        logger.info("Pipeline exécuté avec succès.")
    except Exception as error:
        logger.critical("Exception critique non gérée dans le runner.", exc_info=error)
        sys.exit(1)

if __name__ == "__main__":
    main()