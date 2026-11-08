# Protocole de Développement et Gouvernance Technique (V1 Blindée)

Ce document formalise les règles permanentes d'ingénierie applicables à l'ensemble du projet pour garantir une qualité de niveau expert senior.

## 1. Analyse de vulnérabilité (Zero Trust)
* Traque systématique des failles d'injection.
* Rejet strict des types laxistes (`Any` non contrôlé, typage incomplet).
* Application obligatoire de timeouts sur toutes les requêtes réseau et opérations d'E/S.
* Gestion rigoureuse des fuites de ressources (fermeture systématique des contextes, sessions, navigateurs).

## 2. Résilience native
* Mécanismes de rattrapage intégrés (retries avec backoff exponentiel et jitter).
* Validation structurelle stricte des données entrantes et sortantes (via schémas Pydantic).
* Gestion fine et typée des exceptions.

## 3. Traçabilité absolue
* Chaque bloc de code fourni doit comporter une note de PR explicative.
* Le chemin d'accès exact et le nom du fichier doivent figurer en haut du bloc de code sous forme de commentaire, accompagnés de la mention explicite `[NEW]` ou `[MODIFIÉ]`.
