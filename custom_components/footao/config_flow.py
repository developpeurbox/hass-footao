"""Config flow Footao TV — liste déroulante multi-choix unique (tous clubs)."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN
from .coordinator import load_clubs_async


async def _load_clubs(hass: HomeAssistant) -> dict:
    """Charge clubs.json via GitHub (fallback local automatique).

    force=True : on veut toujours la liste la plus fraîche possible quand
    l'utilisateur ouvre l'écran d'ajout/modification de clubs, même si le
    cache mémoire du coordinator (1h) contient encore une version plus
    ancienne récupérée entre-temps par une autre entrée.
    """
    session = async_get_clientsession(hass)
    return await load_clubs_async(session, force=True)


def _build_options(clubs: dict) -> tuple[list[dict], dict[str, str]]:
    """Aplatit toutes les ligues en une seule liste d'options.

    Retourne :
      - options : liste de {"value": nom_club, "label": "Ligue — Club"}
                  triée par libellé, pour affichage direct sans étape
                  intermédiaire de sélection de ligue.
      - flat    : dict nom_club -> badge_url, pour retrouver les infos
                  du club une fois les choix de l'utilisateur soumis.
    """
    flat: dict[str, str] = {}
    options: list[dict] = []
    for league, teams in clubs.items():
        for name, badge in teams.items():
            flat[name] = badge
            options.append({"value": name, "label": f"{league} — {name}"})
    options.sort(key=lambda o: o["label"])
    return options, flat


def _add_missing_current(
    options: list[dict], flat: dict[str, str], current: dict[str, str]
) -> None:
    """Réinjecte dans les options les clubs déjà sélectionnés mais absents
    du dataset actuel (relégation, renommage, fichier clubs.json modifié...),
    pour ne jamais les faire disparaître silencieusement d'une modification.
    """
    known = {opt["value"] for opt in options}
    for name, badge in current.items():
        if name not in known:
            options.append({"value": name, "label": f"(retiré du dataset) — {name}"})
            flat[name] = badge
    options.sort(key=lambda o: o["label"])


class FootaoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Config flow en une seule étape : choisir directement les clubs
    (toutes ligues confondues, libellé "Ligue — Club").
    Plusieurs instances peuvent coexister (plusieurs groupes de sensors).
    """

    VERSION = 1

    def __init__(self):
        self._clubs: dict = {}

    async def async_step_user(self, user_input=None):
        errors = {}

        if not self._clubs:
            self._clubs = await _load_clubs(self.hass)

        options, flat = _build_options(self._clubs)

        if user_input is not None:
            chosen_names = user_input.get("clubs", [])
            if not chosen_names:
                errors["clubs"] = "no_club"
            else:
                selected = {n: flat[n] for n in chosen_names if n in flat}
                title = ", ".join(sorted(selected.keys()))
                return self.async_create_entry(title=title, data={"selected": selected})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("clubs"): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
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
    """Modifier les clubs d'une entrée existante — une seule étape,
    tous les clubs précédemment cochés sont garantis d'être pré-sélectionnés.
    """

    def __init__(self, config_entry):
        self._config_entry = config_entry
        self._clubs: dict = {}

    async def async_step_init(self, user_input=None):
        errors = {}
        current = dict(self.config_entry.data.get("selected", {}))

        if not self._clubs:
            self._clubs = await _load_clubs(self.hass)

        options, flat = _build_options(self._clubs)
        # Sécurité : ne jamais perdre un club coché même s'il a disparu
        # du dataset (relégation, renommage, etc.)
        _add_missing_current(options, flat, current)

        default_chosen = list(current.keys())

        if user_input is not None:
            chosen_names = user_input.get("clubs", [])
            if not chosen_names:
                errors["clubs"] = "no_club"
            else:
                selected = {n: flat[n] for n in chosen_names if n in flat}
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, "selected": selected},
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("clubs", default=default_chosen): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }),
            errors=errors,
        )
