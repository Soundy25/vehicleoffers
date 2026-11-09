sequenceDiagram
    autonumber
    actor Utilisateur
    participant GHA as GitHub Actions (Python + Playwright)
    participant GAS as Web App (Google Apps Script)
    participant GS as Google Sheet

    Utilisateur->>GHA: Déclenchement automatique (Cron)

    GHA->>GAS: GET /exec?secret=API_SECRET
    activate GAS
    GAS->>GS: Lit 'Sources', 'Cible véhicules' & 'Offres' (Clés existantes)
    GS-->>GAS: Retourne critères, sources et index des clés connues
    GAS-->>GHA: JSON de configuration (incluant le tableau 'keys')
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

    GHA->>GAS: POST /exec (Lot de nouvelles offres uniquement + Secret)
    activate GAS
    GAS->>GAS: Verrouillage (LockService) & Authentification secret
    GAS->>GS: Double-vérification anti-doublon & Insertion (Ligne 2)
    GAS->>GS: Tri par conformité & Coloration
    GAS->>GS: Clôture de la session dans le 'Journal des actualisations'
    GAS-->>GHA: Bilan JSON (nb Insérées, statut)
    deactivate GAS

    GHA-->>Utilisateur: Fin du cycle / Rapport d'exécution