# parsers/base_parser.py [MODIFIED]
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class VehicleData(BaseModel):
    """Modèle Pydantic garantissant la structure et la validation rigoureuse des données."""
    title: str = Field(..., min_length=1)
    price: Optional[float] = Field(default=None, ge=0.0)
    url: Optional[str] = Field(default=None)

class BaseParser(ABC):
    """Classe abstraite de base pour les parseurs (Zero Trust & Async)."""
    
    def __init__(self, html_content: str) -> None:
        if not html_content or not html_content.strip():
            raise ValueError("Le contenu HTML source ne peut pas être vide.")
        self.html_content: str = html_content

    @abstractmethod
    async def parse(self) -> List[Dict[str, Any]]:
        """Méthode de parsing asynchrone obligatoire."""
        pass

    def validate_and_clean(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validation unitaire et nettoyage des données via le modèle Pydantic."""
        try:
            validated = VehicleData(**raw_data)
            return validated.model_dump()
        except Exception as e:
            # Gestion fine des exceptions pour éviter la rupture du pipeline en aval
            return {"title": "Donnée invalide", "price": None, "url": None, "error": str(e)}