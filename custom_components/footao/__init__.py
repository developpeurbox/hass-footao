"""Intégration Footao TV pour Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import FootaoCoordinator

from homeassistant.core import (
    HomeAssistant,
    CoreState,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.components import websocket_api
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .frontend import JSModuleRegistration
from .const import DOMAIN, INTEGRATION_VERSION


PLATFORMS = ["sensor"]


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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Suppression de l'intégration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_register_frontend(hass: HomeAssistant) -> None:
    """Enregistrer les modules frontend après le démarrage de HA."""
    module_register = JSModuleRegistration(hass)
    await module_register.async_register()


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/version",
    }
)
@websocket_api.async_response
async def websocket_get_version(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Gérer la demande de version du frontend."""
    connection.send_result(
        msg["id"],
        {"version": INTEGRATION_VERSION},
    )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Configurer le composant."""

    # Enregistrer la commande websocket pour la vérification de version
    websocket_api.async_register_command(hass, websocket_get_version)

    async def _setup_frontend(_event=None) -> None:
        await async_register_frontend(hass)

    # Si HA est déjà en cours d'exécution, enregistrer immédiatement
    if hass.state == CoreState.running:
        await _setup_frontend()
    else:
        # Sinon, attendre l'événement STARTED
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _setup_frontend)

    return True
