# Chemin exact : main.py [MODIFIED]
# Chemin exact : main.py [MODIFIÉ]
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("MainRunner")

def main() -> None:
    logger.info("Démarrage du pipeline de scraping (Protocole V1 blindée)")
    try:
        # Importation locale pour éviter les boucles circulaires et isoler l'initialisation
        from scraper.orchestrator import PipelineOrchestrator

        orchestrator = PipelineOrchestrator.from_environment()
        success = orchestrator.run()

        if not success:
            logger.error("Le pipeline s'est terminé avec des erreurs signalées par l'orchestrateur.")
            sys.exit(1)

        logger.info("Exécution du pipeline réussie avec succès.")
    except Exception:
        logger.critical("Erreur critique non interceptée dans le pipeline principal.", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()