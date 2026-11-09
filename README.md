# Chemin exact : README.md [NEW]
# Vehicle Scraper - Zero Trust CI/CD Pipeline

Ce dépôt implmente un pipeline de scraping de véhicules hautement sécurisé, entièrement conteneurisé et soumis à une politique de typage strict (`mypy`) ainsi qu'à des tests continus (`pytest`) orchestrés via GitHub Actions.

## Structure du Projet
- `parsers/base_parser.py` : Classe abstraite de base avec validation Pydantic et typage strict.
- `parsers/vehicle_parser.py` : Implémentation concrète pour l'extraction BeautifulSoup sécurisée.
- `main.py` : Point d'entrée asynchrone principal avec gestion robuste des erreurs et journalisation.
- `tests/` : Suite complète de tests unitaires et de bout en bout (E2E).
- `scraper/http_engine.py` : Récupération HTTP avec timeout et retries; aucun navigateur n'est lancé pour le moment.
- `Dockerfile` : Environnement Python 3.11 pour les tests et la vérification statique.
- `.github/workflows/pipeline.yml` : Pipeline CI automatisé Zero Trust.

## Exécution locale de la vérification statique et des tests
```bash
docker build -t vehicle-scraper:latest .
docker run --rm vehicle-scraper:latest mypy .
docker run --rm vehicle-scraper:latest pytest