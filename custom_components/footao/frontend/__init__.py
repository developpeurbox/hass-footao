from pathlib import Path
import json
from typing import Final

# Lire la version depuis manifest.json
MANIFEST_PATH = Path(__file__).parent / "manifest.json"
with open(MANIFEST_PATH, encoding="utf-8") as f:
    INTEGRATION_VERSION: Final[str] = json.load(f).get("version", "0.0.0")

DOMAIN: Final[str] = "Footao TV"

# URL de base pour les ressources frontend
URL_BASE: Final[str] = "/Footao TV"

# Liste des modules JavaScript à enregistrer
JSMODULES: Final[list[dict[str, str]]] = [
    {
        "name": "Footao Tv Game Card",
        "filename": "footao-game-card.j",
        "version": INTEGRATION_VERSION,
    },
    # Ajouter l'éditeur si nécessaire
    {
        "name": "Footao Tv Game Card",
        "filename": "footao-game-card.j",
        "version": INTEGRATION_VERSION,
    },
]
