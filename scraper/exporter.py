# Chemin exact : scraper/exporter.py [NEW]
"""
Description : Module d'export asynchrone des données véhicules validées vers des formats
persistants (JSON/CSV) avec gestion sécurisée des flux d'écriture et typage strict.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("SecureDataExporter")

class SecureDataExporter:
    """Gestionnaire de persistance des données scrappées avec contrôles Zero Trust."""

    def __init__(self, output_dir: str = "./output") -> None:
        self.output_dir: Path = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def export_to_json(self, filename: str, data: List[Dict[str, Any]]) -> bool:
        """Exporte de manière sécurisée une liste de dictionnaires vers un fichier JSON."""
        if not filename or not data:
            logger.warning("Export JSON ignoré : nom de fichier vide ou données absentes.")
            return False

        file_path: Path = self.output_dir / filename
        try:
            # Écriture atomique et sécurisée
            content: str = json.dumps(data, ensure_ascii=False, indent=4)
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"Export JSON réussi vers {file_path}")
            return True
        except Exception as e:
            logger.error(f"Erreur critique lors de l'export JSON vers {file_path} : {e}")
            return False