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
Cette commande utilise le contrat Apps Script `GET?action=get_config` puis un POST JSON
signé par HMAC-SHA256. Elle insère deux lignes d'exemple de 14 colonnes dans `Offres`
(une `CONFORME`, une `NON CONFORME`), après avoir vérifié leurs URL, puis une entrée de cinq
colonnes dans `Journal`. Le GAS compte les deux catégories parmi les
annonces réellement ajoutées et écrit le résultat dans le journal; `total_count` indique le
nombre d'annonces du lot. La signature et un identifiant unique horodaté protègent le POST
contre les modifications et les rejeux. Redéploie `gas/Code.gs` dans Apps Script avant de
lancer ce test. Il n'est pas appelé par `run.py` ou la CI. `API_SECRET` et `HMAC_SECRET`
doivent être définis dans les propriétés du script Apps Script et dans l'environnement local;
ne les commite pas.

Pour vérifier depuis l'éditeur Apps Script que le classeur est accessible et que les deux
onglets existent et acceptent une écriture, exécute manuellement `testEcriture()`. La fonction
échoue explicitement si `Offres` ou `Journal` manque, ou si les onglets
n'ont pas assez de colonnes; elle ne crée pas ces onglets. En cas de succès, elle ajoute une
annonce `CONFORME` et une annonce `NON CONFORME` dans `Offres`, puis insère une ligne de
résultat en ligne 2 de `Journal`, avec les valeurs de test `99/99/9999`, `99:99`, `99:99`
et `9` dans les quatre premières colonnes. Le POST normal insère également chaque nouvelle
ligne de journal en ligne 2, de sorte que l'actualisation la plus récente reste en haut.

```bash
export GAS_WEB_APP_URL="URL_DE_LA_WEB_APP"
export API_SECRET="SECRET_API_CONFIGURE_DANS_APPS_SCRIPT"
export HMAC_SECRET="SECRET_HMAC_CONFIGURE_DANS_APPS_SCRIPT"
PYTHONPATH="$PWD" venv/bin/python -m scripts.test_gas_write
```