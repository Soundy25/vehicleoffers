# Protocole de Sécurité et d'Intégrité - Pipeline de Scraping Résilient

Ce document formalise les exigences de sécurité, d'intégrité et de résilience applicables à l'ensemble des composants du pipeline (exécuteur GitHub Actions, moteur Python asynchrone, et backend Google Apps Script).

---

## 1. Authentification et intégrité de l'API Google Apps Script

La lecture de configuration et l'écriture utilisent des secrets distincts configurés dans les propriétés du script.

* **Lecture de configuration :** le client appelle `GET?action=get_config&secret=...`.
* **Écriture :** le client signe les octets exacts du JSON POST avec HMAC-SHA256 et `HMAC_SECRET`. La signature est passée en paramètre `signature`, car l'événement `doPost(e)` d'Apps Script n'expose pas les en-têtes HTTP arbitraires.
* Le corps signé contient un horodatage et un identifiant UUID; le serveur vérifie une fenêtre de cinq minutes et utilise `CacheService` pour refuser les UUID déjà vus pendant dix minutes (protection anti-rejeu au mieux, le cache Apps Script n'étant pas un stockage durable).
* Les échanges passent par HTTPS. `API_SECRET` et la signature dans les paramètres URL peuvent apparaître dans des journaux intermédiaires; l'accès à ces journaux doit être limité.

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
