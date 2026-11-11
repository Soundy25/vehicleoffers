sequenceDiagram
    autonumber
    actor Utilisateur
    participant Local as Exécution locale (Python + Playwright)
    participant GAS as Web App (Google Apps Script)
    participant GS as Google Sheet
    participant Cible as Site L'Argus
    participant Nominatim as Géocodage OpenStreetMap
    participant OSRM as Routage voiture OSRM

    Utilisateur->>Local: Lance run.py ou main.py (une actualisation)
    Note over Local,GAS: Exécution en lecture seule; aucun POST ni écriture au Sheet

    Local->>GAS: GET /exec?action=get_config&secret=API_SECRET
    activate GAS
    GAS->>GAS: Vérifie API_SECRET
    GAS->>GS: Lit les URL existantes (colonne 'URL' de 'Offres')
    GS-->>GAS: Liste des clés connues
    GAS->>GS: Lit les règles de 'Cible véhicules'
    GS-->>GAS: Critères de conformité
    GAS-->>Local: JSON de configuration (keys, targets, criteria)
    deactivate GAS

    Local->>Cible: Une navigation vers la recherche L'Argus
    Cible-->>Local: Code HTML rendu, si l'accès est permis

    loop Jusqu'à 3 candidates inconnues présélectionnées
        Note over Local: Playwright standard, sans camouflage, interaction ni retry
        Local->>Local: Extrait les URLs et faits visibles

        Local->>Local: Préfiltre selon les règles de Cible véhicules
        alt URL déjà connue ou annonce explicitement incompatible
            Local->>Local: Ignore l'annonce (zéro visite de détail)
        else Nouvelle candidate ou faits insuffisants pour conclure
            Local->>Cible: Visite séquentielle du détail
            Cible-->>Local: Code HTML du détail
            Local->>Local: Extrait les métadonnées
            Local->>Nominatim: Géocode la commune et Besançon
            Nominatim-->>Local: Coordonnées des centres de communes
            Local->>OSRM: Calcule un itinéraire en voiture
            OSRM-->>Local: Distance routière
            Local->>Local: Évalue la conformité
        end
    end

    Note over Local: Si une commune ou un itinéraire est introuvable, le statut reste À VÉRIFIER
    Local-->>Utilisateur: Rapport local, sans écriture au Sheet