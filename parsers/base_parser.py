# parsers/base_parser.py [MODIFIED]
# Chemin exact : parsers/base_parser.py [MODIFIÉ]
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class VehicleData(BaseModel):
    """Modèle Pydantic garantissant la structure et la validation rigoureuse des données."""
    title: str = Field(..., min_length=1)
    price: Optional[float] = Field(default=None, ge=0.0)
    mileage: Optional[int] = Field(default=None, ge=0)
    year: Optional[int] = Field(default=None, ge=1886)
    city: Optional[str] = None
    seller: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    energy: Optional[str] = None
    seats: Optional[int] = Field(default=None, ge=1)
    description: Optional[str] = None
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
        validated = VehicleData(**raw_data)
        return validated.model_dump()