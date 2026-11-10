sequenceDiagram
    autonumber
    actor Utilisateur
    participant GHA as GitHub Actions (Python + Playwright)
    participant GAS as Web App (Google Apps Script)
    participant GS as Google Sheet

    Utilisateur->>GHA: Déclenchement automatique (Cron)
    Note over GHA,GAS: Le GET/POST GAS est actuellement exercé par le test manuel, pas par run.py ou la CI

    GHA->>GAS: GET /exec?action=get_config&secret=API_SECRET
    activate GAS
    GAS->>GAS: Vérifie API_SECRET
    GAS->>GS: Lit les URL existantes (colonne 'URL' de 'Offres')
    GS-->>GAS: Liste des clés connues
    GAS-->>GHA: JSON de configuration (tableau 'keys')
    deactivate GAS

    loop Pour chaque URL source de la liste
        Note over GHA: Moteur Playwright Headless
        GHA->>GHA: Lance Chromium Headless & émule un navigateur réel
        GHA->>Cible: Navigation sur la page de recherche (Exécute le JS / Anti-bot)
        Cible-->>GHA: Code HTML rendu

        GHA->>GHA: Extrait les URLs brutes des annonces présentes

        alt L'URL est présente dans l'index 'keys' (Déjà connue)
            GHA->>GHA: Ignore l'annonce (Zéro visite de détail)
        else Nouvelle URL (Inconnue dans le Sheet)
            GHA->>Cible: Visite de la page de détail (Playwright)
            Cible-->>GHA: Code HTML de la page détail
            GHA->>GHA: Extrait les métadonnées (Prix, km, année, titre, url)
        end
    end

    GHA->>GAS: POST /exec?signature=HMAC-SHA256 (JSON offers + log + timestamp + request_id)
    activate GAS
    GAS->>GAS: Vérifie HMAC, l'horodatage et le rejeu & verrouille
    GAS->>GS: Ajoute les nouvelles annonces dans 'Offres'
    GAS->>GS: Compte CONFORME / NON CONFORME et insère une ligne en ligne 2 de 'Journal'
    GAS-->>GHA: Bilan JSON (nb Insérées, statut)
    deactivate GAS

    GHA-->>Utilisateur: Fin du cycle / Rapport d'exécution