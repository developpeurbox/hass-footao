"""Intégration Footao TV pour Home Assistant."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .coordinator import FootaoCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CARD_FILE = "footao-game-card.js"
CARD_URL = f"/{DOMAIN}_static/{CARD_FILE}"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Expose la carte Lovelace embarquée et l'enregistre comme ressource."""
    www = Path(__file__).parent / "www" / CARD_FILE
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(www), cache_headers=False)]
    )
    integration = await async_get_integration(hass, DOMAIN)
    await _async_register_card(hass, f"{CARD_URL}?v={integration.version}")
    return True


async def _async_register_card(hass: HomeAssistant, url: str) -> None:
    """Enregistre la carte comme ressource de tableau de bord (module JS).

    En mode « storage », la ressource est créée ou mise à jour dans la liste
    des ressources Lovelace. En mode YAML (liste non modifiable), on retombe
    sur le chargement par le frontend.
    """
    try:
        lovelace = hass.data.get("lovelace")
        resources = getattr(lovelace, "resources", None)
        if resources is None and isinstance(lovelace, dict):
            resources = lovelace.get("resources")

        if resources is None or not hasattr(resources, "async_create_item"):
            add_extra_js_url(hass, url)
            return

        if not getattr(resources, "loaded", True):
            await resources.async_load()

        for item in resources.async_items():
            if item["url"].split("?")[0] == CARD_URL:
                if item["url"] != url:
                    await resources.async_update_item(
                        item["id"], {"res_type": "module", "url": url}
                    )
                return

        await resources.async_create_item({"res_type": "module", "url": url})
    except Exception:  # noqa: BLE001
        _LOGGER.exception("footao : enregistrement de la carte impossible")
        add_extra_js_url(hass, url)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialisation de l'intégration."""
    selected: dict[str, str] = entry.data.get("selected", {})

    coordinator = FootaoCoordinator(hass, selected)

    # ✅ NOUVEAU : chargement non bloquant de clubs.json
    await coordinator.async_initialize()
    # ✅ Premier rafraîchissement
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ✅ NOUVEAU : recharge l'entrée dès que ses données changent (ex : ajout/
    # retrait d'un club via l'options flow). Sans ça, le coordinator garde
    # l'ancienne liste "selected" figée à l'initialisation, et les nouveaux
    # clubs cochés ne créent jamais leur sensor.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharge l'entrée quand ses options/données ont été modifiées."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Suppression de l'intégration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
