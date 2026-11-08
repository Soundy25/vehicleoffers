# parsers/vehicle_parser.py
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup, Tag
from parsers.base_parser import BaseParser, VehicleData

class VehicleParser(BaseParser):
    """Parseur spécifique pour l'extraction sécurisée et asynchrone des données de véhicules."""

    def __init__(self, html_content: str) -> None:
        super().__init__(html_content)
        self.soup: BeautifulSoup = BeautifulSoup(self.html_content, "html.parser")

    async def parse(self) -> List[Dict[str, Any]]:
        """Extrait et nettoie les offres de véhicules de manière hermétique."""
        results: List[Dict[str, Any]] = []
        items = self.soup.select(".vehicle-item")
        for item in items:
            title_elem: Optional[Tag] = item.select_one(".title")
            title_text: str = title_elem.get_text(strip=True) if title_elem else "Inconnu"
            
            raw_item: Dict[str, Any] = {"title": title_text}
            cleaned: Dict[str, Any] = self.validate_and_clean(raw_item)
            results.append(cleaned)
        return results

    def validate_and_clean(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Valide et nettoie un dictionnaire de données véhicule via Pydantic."""
        try:
            validated = VehicleData(title=str(raw_data.get("title", "Inconnu")))
            return validated.model_dump()
        except Exception:
            return {"title": "Inconnu", "price": None, "url": None}