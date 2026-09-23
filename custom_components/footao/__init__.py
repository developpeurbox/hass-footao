"""Intégration Footao TV pour Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import FootaoCoordinator

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
