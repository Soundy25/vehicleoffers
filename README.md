# Chemin exact : README.md [NEW]
# Vehicle Scraper - Zero Trust CI/CD Pipeline

Ce dépôt implmente un pipeline de scraping de véhicules hautement sécurisé, entièrement conteneurisé et soumis à une politique de typage strict (`mypy`) ainsi qu'à des tests continus (`pytest`) orchestrés via GitHub Actions.

## Structure du Projet
- `parsers/base_parser.py` : Classe abstraite de base avec validation Pydantic et typage strict.
- `parsers/vehicle_parser.py` : Extraction des véhicules depuis les blocs JSON-LD schema.org avec validation Pydantic.
- `main.py` : Point d'entrée du pipeline de lecture seule avec gestion des erreurs et journalisation.
- `tests/` : Suite complète de tests unitaires et de bout en bout (E2E).
- `scraper/http_engine.py` : Récupération HTTP utilisée par les collecteurs compatibles.
- `scraper/browser_engine.py` : navigation Playwright ponctuelle, sans camouflage ni interaction automatisée.
- `scraper/orchestrator.py` : actualisation en lecture seule, limitée à L'Argus et à trois pages détail par exécution.
- `Dockerfile` : Environnement Python 3.11 pour les tests et la vérification statique.
- `.github/workflows/pipeline.yml` : Pipeline CI automatisé Zero Trust.

## Exécution locale de la vérification statique et des tests
```bash
docker build -t vehicle-scraper:latest .
docker run --rm vehicle-scraper:latest mypy .
docker run --rm vehicle-scraper:latest pytest
```

## Probe Playwright ponctuel
Playwright utilise Chromium gratuitement. Après installation des dépendances Python et du navigateur,
tu peux lancer une seule navigation explicite vers une page pour laquelle tu as l'autorisation :

```bash
venv/bin/python -m playwright install chromium
PYTHONPATH="$PWD" venv/bin/python -m scripts.probe_site "https://example.com/"
```

Le probe n'effectue ni clic, ni extraction, ni retry et ne conserve pas de session entre les lancements.
Il signale les réponses HTTP 401/403/429 ou quelques pages de vérification courantes, puis s'arrête.
Il n'essaie pas de masquer l'automatisation ni de contourner un blocage. Un statut favorable ne garantit
pas que l'automatisation est autorisée ou qu'elle ne sera pas bloquée ultérieurement.

Le préfiltre de résultats est implémenté dans `scraper/listing_parser.py` :
`select_detail_candidates()` dédoublonne les URL et écarte uniquement les annonces dont
les informations visibles démontrent une incompatibilité. Les champs absents restent
à examiner sur la page détail. Cette fonction est pure et n'ouvre aucune page par elle-même.

`run.py` et `main.py` lancent l'orchestrateur depuis `GAS_WEB_APP_URL` et `API_SECRET`.
Il lit d'abord la configuration GAS, consulte uniquement une recherche L'Argus, puis ouvre
séquentiellement au plus trois détails présélectionnés. Il s'arrête dès qu'un refus d'accès ou
une page de vérification est détecté. L'exécution ne fait aucun POST et n'écrit pas dans le Sheet.
Pour chaque annonce détaillée, `scraper/road_distance.py` géocode la commune et Besançon,
puis demande à OSRM un itinéraire voiture; le calcul compare les centres des communes, pas
les adresses exactes. Il utilise Nominatim et le serveur public OSRM, sans clé ni frais,
avec mise en cache par exécution et au moins une seconde entre les requêtes de géocodage.
Ces services publics n'offrent pas de garantie de disponibilité. Si la commune manque,
ne peut être géocodée ou si aucun itinéraire n'est fourni, le statut reste `À VÉRIFIER`.
Les données cartographiques sont fournies par OpenStreetMap contributors.

## Validation de conformité des annonces
Le GAS lit les critères de chaque ligne de `Cible véhicules` et les renvoie avec `get_config`.
Au POST, il recalcule la colonne `CONFORME` lui-même : `CONFORME`, `NON CONFORME` ou `À VÉRIFIER`
si une donnée requise manque. Les bornes prix/km/année sont inclusives; les exclusions de
`Ne pas retenir` sont recherchées sans distinction de casse dans le titre et la description.
Le client doit fournir les faits extraits dans `vehicle_facts`, indexés par URL, avec `make`,
`model`, `energy`, `seats` et `description`. La distance en kilomètres doit être fournie dans
la colonne `Dist.`. Les commentaires de conformité sont ajoutés à `Comment`. Le script
`testConformityRules()` dans `gas/Code.gs` vérifie les cas principaux sans écrire dans le Sheet.

## Test manuel d'écriture GAS (destructif)
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