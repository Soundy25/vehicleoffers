# Protocole de Sécurité et d'Intégrité - Pipeline de Scraping Résilient

Ce document formalise les exigences de sécurité, d'intégrité et de résilience applicables à l'ensemble des composants du pipeline (exécuteur GitHub Actions, moteur Python asynchrone, et backend Google Apps Script).

---

## 1. Authentification et Intégrité des Données (HMAC-SHA256)

Toute communication sortante entre le scraper (`main.py`) et l'API de persistance Google Apps Script (`gas/Code.gs`) est signée cryptographiquement via une empreinte **HMAC-SHA256**.

* **Génération (Client Python) :** Le corps de la requête sérialisé en JSON est signé à l'aide d'une clé secrète partagée (`HMAC_SECRET`). La signature est transmise dans l'en-tête HTTP `X-Hub-Signature-256`.
* **Validation (Serveur GAS) :** Le backend vérifie l'en-tête reçu en recalculant la signature HMAC-SHA256 du payload entrant. 
* **Protection contre les attaques temporelles :** La comparaison des signatures côté GAS utilise un algorithme en temps constant (`slowEquals_`) pour prévenir toute exploitation par analyse temporelle (*timing attack*).

---

## 2. Résilience Réseau et Gestion des Erreurs (Zero Trust)

* **Retries et Backoff Exponentiel :** Les appels réseau HTTP gérés par `aiohttp` intègrent un mécanisme de rattrapage automatique sur les codes d'erreur transitoires (429, 500, 502, 503, 504) et les exceptions de timeout.
* **Jitter Temporel :** Un décalage aléatoire est injecté dans le calcul du backoff exponentiel pour éliminer l'effet de pic de charge (*thundering herd*).
* **Timeouts stricts :** Aucun appel réseau ou connexion ne se fait sans un timeout explicite (`REQUEST_TIMEOUT` par défaut à 30 secondes).

---

## 3. Validation Stricte des Structures de Données

* **Typage Stricte & Pydantic :** Tous les payloads extraits par les parsers (`parsers/base_parser.py`) passent par une validation rigoureuse de type via des schémas Pydantic. Les données corrompues, incomplètes ou ne respectant pas les contraintes de domaine (ex: prix négatifs, URLs invalides) sont immédiatement rejetées et journalisées.

---

## 4. Concurrence et Persistance Atomique

* **Verrouillage Atomique (GAS) :** L'API Google Apps Script utilise `LockService.getScriptLock()` avec un timeout de 30 secondes pour garantir l'atomicité des écritures dans Google Sheets et éviter toute condition de course (*race condition*) en cas d'exécutions simultanées.
