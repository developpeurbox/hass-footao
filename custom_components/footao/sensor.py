"""Entités sensor Footao TV."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FootaoCoordinator

EMPTY_ATTRS = {
    "team": "", "domicile": "", "logoDomicile": "",
    "exterieur": "", "logoExterieur": "", "situation": "",
    "date": "", "datetime": "", "display": False,
    "heure": "", "logo": "", "chaine": "", "game": "",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FootaoCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [FootaoSensor(coordinator, name) for name in coordinator.selected],
        update_before_add=True,
    )


class FootaoSensor(CoordinatorEntity, SensorEntity):
    """Un sensor = un club suivi."""

    def __init__(self, coordinator: FootaoCoordinator, club_name: str) -> None:
        super().__init__(coordinator)
        self._club   = club_name
        self._attr_name      = f"Footao {club_name}"
        self._attr_unique_id = f"footao_{club_name.lower().replace(' ', '_').replace('-', '_')}"
        self._attr_icon      = "mdi:soccer"

    @property
    def _data(self) -> dict | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._club)

    @property
    def native_value(self) -> str:
        d = self._data
        return d["state"] if d else "Aucun match"

    @property
    def extra_state_attributes(self) -> dict:
        d = self._data
        if d is None:
            return {**EMPTY_ATTRS, "team": self._club}
        return d.get("attributes", {})

    @property
    def device_info(self):
        return {
            "identifiers":  {(DOMAIN, "footao_device")},
            "name":         "Footao TV",
            "model":        "Match Sensor",
            "manufacturer": "habox",
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success
