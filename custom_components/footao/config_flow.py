"""Config flow Footao TV — listes déroulantes multi-choix par ligue."""
from __future__ import annotations

import json
from pathlib import Path

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN


def _load_clubs() -> dict:
    clubs_path = Path(__file__).parent / "clubs.json"
    with open(clubs_path, encoding="utf-8") as f:
        return json.load(f)


def _multi_select(options: list[str], default: list[str] | None = None) -> vol.Schema:
    """Champ liste déroulante multi-choix natif HA."""
    selector = SelectSelector(
        SelectSelectorConfig(
            options=options,
            multiple=True,
            mode=SelectSelectorMode.LIST,
        )
    )
    if default is not None:
        return vol.Required("__placeholder__", default=default), selector
    return selector


class FootaoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Config flow en 2 étapes :
      1. Choisir une ou plusieurs ligues (liste déroulante multi-choix)
      2. Choisir les clubs dans ces ligues (liste déroulante multi-choix)
    Plusieurs instances peuvent coexister (plusieurs groupes de sensors).
    """

    VERSION = 1

    def __init__(self):
        self._clubs: dict        = _load_clubs()
        self._sel_leagues: list  = []

    # ── Étape 1 : ligues ─────────────────────────────────────────────────────

    async def async_step_user(self, user_input=None):
        errors  = {}
        leagues = list(self._clubs.keys())

        if user_input is not None:
            chosen = user_input.get("leagues", [])
            if not chosen:
                errors["leagues"] = "no_league"
            else:
                self._sel_leagues = chosen
                return await self.async_step_clubs()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("leagues"): SelectSelector(
                    SelectSelectorConfig(
                        options=leagues,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }),
            errors=errors,
        )

    # ── Étape 2 : clubs ──────────────────────────────────────────────────────

    async def async_step_clubs(self, user_input=None):
        errors = {}

        available: dict[str, str] = {}
        for league in self._sel_leagues:
            available.update(self._clubs.get(league, {}))
        club_names = sorted(available.keys())

        if user_input is not None:
            chosen_names = user_input.get("clubs", [])
            if not chosen_names:
                errors["clubs"] = "no_club"
            else:
                selected = {n: available[n] for n in chosen_names if n in available}
                title    = ", ".join(sorted(selected.keys()))
                return self.async_create_entry(title=title, data={"selected": selected})

        return self.async_show_form(
            step_id="clubs",
            data_schema=vol.Schema({
                vol.Required("clubs"): SelectSelector(
                    SelectSelectorConfig(
                        options=club_names,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return FootaoOptionsFlow(config_entry)


class FootaoOptionsFlow(config_entries.OptionsFlow):
    """Modifier les clubs d'une entrée existante."""

    def __init__(self, config_entry):
        self._config_entry  = config_entry
        self._clubs: dict  = _load_clubs()
        self._sel_leagues: list = []

    # ── Étape 1 : re-choisir les ligues ──────────────────────────────────────

    async def async_step_init(self, user_input=None):
        errors  = {}
        leagues = list(self._clubs.keys())

        if user_input is not None:
            chosen = user_input.get("leagues", [])
            if not chosen:
                errors["leagues"] = "no_league"
            else:
                self._sel_leagues = chosen
                return await self.async_step_clubs()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("leagues"): SelectSelector(
                    SelectSelectorConfig(
                        options=leagues,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }),
            errors=errors,
        )

    # ── Étape 2 : re-choisir les clubs (pré-sélection des clubs actuels) ─────

    async def async_step_clubs(self, user_input=None):
        errors  = {}
        current = set(self.config_entry.data.get("selected", {}).keys())

        available: dict[str, str] = {}
        for league in self._sel_leagues:
            available.update(self._clubs.get(league, {}))
        club_names     = sorted(available.keys())
        default_chosen = [n for n in club_names if n in current]

        if user_input is not None:
            chosen_names = user_input.get("clubs", [])
            if not chosen_names:
                errors["clubs"] = "no_club"
            else:
                selected = {n: available[n] for n in chosen_names if n in available}
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, "selected": selected},
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="clubs",
            data_schema=vol.Schema({
                vol.Required("clubs", default=default_chosen): SelectSelector(
                    SelectSelectorConfig(
                        options=club_names,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }),
            errors=errors,
        )
