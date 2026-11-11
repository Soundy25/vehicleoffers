# Chemin exact : tests/test_vehicle_parser.py [MODIFIED]
# Chemin exact : tests/test_vehicle_parser.py [MODIFIÉ]
import asyncio

import pytest

from parsers.vehicle_parser import VehicleParser


def test_vehicle_parser_rejects_empty_html() -> None:
    with pytest.raises(ValueError, match="Le contenu HTML source ne peut pas être vide."):
        VehicleParser("")


def test_vehicle_parser_extracts_schema_vehicle_fields() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Car",
      "name": "Toyota Yaris hybride",
      "brand": {"@type": "Brand", "name": "Toyota"},
      "model": "Yaris",
      "vehicleModelDate": "2021-01-01",
      "mileageFromOdometer": {"@type": "QuantitativeValue", "value": 52300},
      "fuelType": "Hybride",
      "vehicleSeatingCapacity": 5,
      "description": "Carnet d'entretien disponible",
      "offers": {
        "@type": "Offer",
        "price": "12990",
        "seller": {
          "@type": "AutoDealer",
          "name": "Garage Exemple",
          "address": {"addressLocality": "Lyon"}
        }
      },
      "url": "https://example.com/annonce/123"
    }
    </script>
    """

    result = asyncio.run(VehicleParser(html).parse())

    assert result == [
        {
            "title": "Toyota Yaris hybride",
            "price": 12990.0,
            "mileage": 52300,
            "year": 2021,
            "city": "Lyon",
            "seller": "Garage Exemple",
            "make": "Toyota",
            "model": "Yaris",
            "energy": "Hybride",
            "seats": 5,
            "description": "Carnet d'entretien disponible",
            "url": "https://example.com/annonce/123",
        }
    ]


def test_vehicle_parser_does_not_invent_missing_values() -> None:
    html = """
    <script type="application/ld+json">
    {"@type": "Car", "name": "Toyota Yaris"}
    </script>
    """

    result = asyncio.run(VehicleParser(html).parse())

    assert result == [
        {
            "title": "Toyota Yaris",
            "price": None,
            "mileage": None,
            "year": None,
            "city": None,
            "seller": None,
            "make": None,
            "model": None,
            "energy": None,
            "seats": None,
            "description": None,
            "url": None,
        }
    ]


def test_vehicle_parser_returns_no_vehicle_when_json_ld_is_absent() -> None:
    result = asyncio.run(VehicleParser("<html><h1>Toyota Yaris</h1></html>").parse())

    assert result == []