"""Config flow Footao TV — pré-écran ligue(s), puis sélection des clubs dans ces ligues.

150 clubs au total (8 ligues) : une seule liste à cocher est trop longue. On choisit
d'abord une ou plusieurs ligues, puis seuls les clubs de ces ligues sont proposés.
Plusieurs instances de l'intégration peuvent coexister (plusieurs groupes de sensors).
"""
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


def _league_options(clubs: dict) -> list[dict]:
    return [{"value": league, "label": league} for league in sorted(clubs.keys())]


def _club_options(clubs: dict, leagues: list[str]) -> tuple[list[dict], dict[str, str]]:
    """Options de clubs restreintes aux ligues choisies + dict nom_club -> badge_url."""
    flat: dict[str, str] = {}
    options: list[dict] = []
    multi_league = len(leagues) > 1
    for league in leagues:
        for name, badge in clubs.get(league, {}).items():
            flat[name] = badge
            options.append({
                "value": name,
                "label": f"{league} — {name}" if multi_league else name,
            })
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


def _selector(options: list[dict]):
    return SelectSelector(
        SelectSelectorConfig(options=options, multiple=True, mode=SelectSelectorMode.LIST)
    )


class FootaoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Étape 1 : ligues à suivre. Étape 2 : clubs dans ces ligues.

    Plusieurs instances peuvent coexister (plusieurs groupes de sensors).
    """

    VERSION = 1

    def __init__(self):
        self._clubs: dict = {}
        self._leagues: list[str] = []

    async def async_step_user(self, user_input=None):
        errors = {}
        if not self._clubs:
            self._clubs = await _load_clubs(self.hass)

        if user_input is not None:
            self._leagues = user_input.get("leagues", [])
            if not self._leagues:
                errors["leagues"] = "no_league"
            else:
                return await self.async_step_clubs()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("leagues"): _selector(_league_options(self._clubs))}
            ),
            errors=errors,
        )

    async def async_step_clubs(self, user_input=None):
        errors = {}
        options, flat = _club_options(self._clubs, self._leagues)

        if user_input is not None:
            chosen_names = user_input.get("clubs", [])
            if not chosen_names:
                errors["clubs"] = "no_club"
            else:
                selected = {n: flat[n] for n in chosen_names if n in flat}
                title = ", ".join(sorted(selected.keys()))
                return self.async_create_entry(title=title, data={"selected": selected})

        return self.async_show_form(
            step_id="clubs",
            data_schema=vol.Schema({vol.Required("clubs"): _selector(options)}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return FootaoOptionsFlow(config_entry)


class FootaoOptionsFlow(config_entries.OptionsFlow):
    """Modifier les clubs suivis, par ligue(s) choisie(s).

    Les clubs des ligues non re-sélectionnées à l'étape 1 sont conservés tels
    quels : modifier une ligue ne fait jamais perdre les clubs suivis dans
    les autres.
    """

    def __init__(self, config_entry):
        self._config_entry = config_entry
        self._clubs: dict = {}
        self._leagues: list[str] = []
        self._current: dict = {}
        self._untouched: dict = {}

    async def async_step_init(self, user_input=None):
        errors = {}
        if not self._clubs:
            self._clubs = await _load_clubs(self.hass)
        if not self._current:
            self._current = dict(self.config_entry.data.get("selected", {}))

        # Ligue d'appartenance de chaque club déjà suivi, pour pré-cocher les
        # bonnes ligues par défaut (un club peut appartenir à plusieurs ligues
        # du dataset, ex. sélections nationales listées dans plusieurs groupes).
        league_of = {
            name: league
            for league, teams in self._clubs.items()
            for name in teams
        }
        default_leagues = sorted({
            league_of.get(name) for name in self._current if league_of.get(name)
        })

        if user_input is not None:
            self._leagues = user_input.get("leagues", [])
            if not self._leagues:
                errors["leagues"] = "no_league"
            else:
                current_in_league = {
                    n for n in self._current if league_of.get(n) in self._leagues
                }
                # Clubs déjà suivis dans une ligue qu'on ne modifie pas cette
                # fois (ou retirés du dataset) : conservés tels quels.
                self._untouched = {
                    n: b for n, b in self._current.items() if n not in current_in_league
                }
                return await self.async_step_clubs()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("leagues", default=default_leagues): _selector(
                        _league_options(self._clubs)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_clubs(self, user_input=None):
        errors = {}
        options, flat = _club_options(self._clubs, self._leagues)

        default_chosen = [n for n in self._current if n in flat]
        # Sécurité : ne jamais perdre un club coché même s'il a disparu du
        # dataset pour cette sélection de ligues (relégation, renommage...).
        for name in list(self._current):
            if name not in flat and name not in self._untouched:
                default_chosen.append(name)
                flat[name] = self._current[name]
                options.append({"value": name, "label": f"(retiré du dataset) — {name}"})
        options.sort(key=lambda o: o["label"])

        if user_input is not None:
            chosen_names = user_input.get("clubs", [])
            if not chosen_names and not self._untouched:
                errors["clubs"] = "no_club"
            else:
                edited = {n: flat[n] for n in chosen_names if n in flat}
                selected = {**self._untouched, **edited}
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=", ".join(sorted(selected.keys())),
                    data={**self.config_entry.data, "selected": selected},
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="clubs",
            data_schema=vol.Schema(
                {vol.Required("clubs", default=default_chosen): _selector(options)}
            ),
            errors=errors,
        )
