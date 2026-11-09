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
```

## Test manuel d'écriture GAS
Cette commande envoie une requête signée HMAC-SHA256 conforme aux 14 colonnes de
`gas/Code.gs` et insère la ligne d'exemple dans l'onglet `Vehicles`, après avoir lu les URL
existantes avec un GET authentifié. Elle refuse de réinsérer l'annonce si son URL est déjà
présente. Elle n'est pas appelée par `run.py` ou la CI; lance-la uniquement à la main.
`API_SECRET` et `HMAC_SECRET` doivent être définis dans les propriétés du script Apps Script
et dans l'environnement local; ne les commite pas.

```bash
export GAS_WEB_APP_URL="URL_DE_LA_WEB_APP"
export API_SECRET="SECRET_API_CONFIGURE_DANS_APPS_SCRIPT"
export HMAC_SECRET="SECRET_CONFIGURE_DANS_APPS_SCRIPT"
PYTHONPATH="$PWD" venv/bin/python -m scripts.test_gas_write
```