"""Intégration Footao TV pour Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CARD_JS_FILENAME, CARD_URL, CARD_VERSION, DOMAIN
from .coordinator import FootaoCoordinator

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialisation de l'intégration."""
    selected: dict[str, str] = entry.data.get("selected", {})

    await _async_register_frontend_card(hass)

    coordinator = FootaoCoordinator(hass, selected)
    
    # ✅ NOUVEAU : chargement non bloquant de clubs.json
    await coordinator.async_initialize()
    # ✅ Premier rafraîchissement
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_register_frontend_card(hass: HomeAssistant) -> None:
    """Enregistre footao-game-card.js comme ressource Lovelace (une seule fois)."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("_frontend_registered"):
        return

    card_path = hass.config.path(f"custom_components/{DOMAIN}/www/{CARD_JS_FILENAME}")

    try:
        # Home Assistant >= 2024.7
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, card_path, False)]
        )
    except ImportError:
        # Home Assistant < 2024.7 (API dépréciée mais toujours fonctionnelle)
        hass.http.register_static_path(CARD_URL, card_path, cache_headers=False)

    add_extra_js_url(hass, f"{CARD_URL}?v={CARD_VERSION}")
    domain_data["_frontend_registered"] = True
    _LOGGER.debug("Carte Footao enregistrée sur %s", CARD_URL)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Suppression de l'intégration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
