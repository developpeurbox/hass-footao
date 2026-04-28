"""DataUpdateCoordinator Footao TV — tv-calendrier.php?e=X (toutes compétitions)."""
from __future__ import annotations

import json
import logging
import re
import ssl
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    SCAN_INTERVAL_HOURS,
    SPRITE_BASE_STYLE,
    SPRITE_DEFAULT,
    SPRITE_POSITIONS,
)

_LOGGER = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; rv:19.0) Gecko/20100101 Firefox/19.0"}

# Requête sans comp= → footao retourne toutes les compétitions du club
FOOTAO_CAL_URL = "https://www.footao.tv/tv-calendrier.php?e={eq}"

# Compétitions acceptées (championnat + coupes d'Europe)
# La correspondance est insensible à la casse et partielle (mot-clé contenu dans le libellé)
COMPETITIONS_AUTORISEES = [
    "ligue 1",
    "ligue 2",
    "liga",
    "Bundesliga",
    "Serie A",
    "Premier League",
    "champions league",
    "ligue des champions",
    "europa league",
    "ligue europa",
    "conference league",
    "ligue conférence",
    "ligue conference",
]

FILTRES_EXCLUS = [" Fém.", " Fém", "Féminin", " U19", " U17", " U21", "-19", "-17"]


def load_clubs() -> dict:
    with open(Path(__file__).parent / "clubs.json", encoding="utf-8") as f:
        return json.load(f)


def build_logo_index(clubs: dict) -> dict[str, str]:
    """
    Construit un index { eq_name_lower → logo_url } depuis clubs.json.
    Permet de retrouver le logo d'un adversaire à partir de son nom footao.tv.
    """
    index: dict[str, str] = {}
    for league_clubs in clubs.values():
        for cfg in league_clubs.values():
            eq   = cfg.get("eq", "")
            logo = cfg.get("logo", "")
            if eq and logo:
                index[eq.lower()] = logo
    return index


def logo_for(name: str, index: dict[str, str]) -> str:
    """Cherche le logo d'une équipe par son nom footao.tv (insensible à la casse)."""
    if not name:
        return ""
    nl = name.lower()
    if nl in index:
        return index[nl]
    for key, url in index.items():
        if key in nl or nl in key:
            return url
    return ""


def get_sprite_style(css_class: str) -> str:
    parts = css_class.split() if css_class else []
    key   = parts[1] if len(parts) > 1 else ""
    return SPRITE_BASE_STYLE.format(pos=SPRITE_POSITIONS.get(key, SPRITE_DEFAULT))


def competition_autorisee(comp_label: str) -> bool:
    """Retourne True si la compétition est dans la liste blanche."""
    if not comp_label:
        return True  # Si pas de label de compétition détecté, on laisse passer
    cl = comp_label.lower()
    return any(kw in cl for kw in COMPETITIONS_AUTORISEES)


# ─── Parser HTML ─────────────────────────────────────────────────────────────

class FootaoCalParser(HTMLParser):
    """
    Parse tv-calendrier.php : <h2>date</h2> + heure + img + lien match.
    Capture également le libellé de compétition (balise <h3> ou texte de section).
    """

    def __init__(self):
        super().__init__()
        self.matches: list[dict] = []
        self._cur_date  = self._cur_iso = self._heure = ""
        self._cur_comp  = ""          # libellé de compétition courant
        self._img_alt   = self._img_class = ""
        self._in_h2     = self._cap_h2 = self._in_link = False
        self._in_h3     = False
        self._h2_href   = ""

    def _parse_url(self, href):
        if "Aujourd'hui" in self._cur_date:
            today = datetime.now()
            return today.strftime("%Y-%m-%d"), "Aujourd'hui"
        if "Demain" in self._cur_date:
            tomorrow = datetime.now() + timedelta(days=1)
            return tomorrow.strftime("%Y-%m-%d"), "Demain"

        jr = re.search(r"jr=(\d+)", href)
        ms = re.search(r"ms=(\d+)", href)
        an = re.search(r"an=(\d+)", href)
        v  = re.search(r"\?v=([^&]+)", href)
        if jr and ms and an:
            iso   = f"{an.group(1)}-{ms.group(1).zfill(2)}-{jr.group(1).zfill(2)}"
            label = v.group(1).replace("-", " ").capitalize() if v else iso
            return iso, label
        return "", ""

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "h2":
            self._in_h2 = True; self._h2_href = ""; self._cap_h2 = False
        elif tag == "h3":
            # footao utilise des <h3> pour séparer les compétitions sur la page sans comp=
            self._in_h3 = True
        elif self._in_h2 and tag == "a":
            self._h2_href = d.get("href", ""); self._cap_h2 = True
        elif tag == "img":
            alt = d.get("alt", "")
            for w in ["tv direct match", "match programme foot soir", "foot programme soir", "match"]:
                alt = alt.replace(w, "")
            self._img_alt   = alt.strip()
            css = d.get("class", "")
            self._img_class = css if isinstance(css, str) else " ".join(css)
        elif tag == "a" and not self._in_h2:
            if "-chaine-tv-diffusion-heure" in d.get("href", ""):
                self._in_link = True

    def handle_endtag(self, tag):
        if tag == "h2": self._in_h2 = self._cap_h2 = False
        if tag == "h3": self._in_h3 = False
        if tag == "a":  self._in_link = self._cap_h2 = False

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return

        # Capture du libellé de compétition dans les <h3>
        if self._in_h3:
            self._cur_comp = text
            _LOGGER.debug("Footao parser: compétition détectée → '%s'", text)
            return

        if self._in_h2 and self._cap_h2 and self._h2_href:
            self._cur_date = text
            iso, label = self._parse_url(self._h2_href)
            if iso:
                self._cur_iso = iso; self._cur_date = label; self._heure = ""
            return

        if re.match(r"^\d{2}:\d{2}$", text) and not self._in_link:
            self._heure = text
            return

        if self._in_link and text and self._cur_iso and self._heure:
            _LOGGER.debug(
                "Footao parser: match candidat → '%s' (%s %s) [comp: %s]",
                text, self._cur_iso, self._heure, self._cur_comp,
            )

            # Filtrage catégories exclues (féminines, jeunes…)
            if any(f in text for f in FILTRES_EXCLUS):
                _LOGGER.debug("Footao parser: match ignoré par filtre catégorie → '%s'", text)
                return

            # Filtrage compétition non autorisée
            if not competition_autorisee(self._cur_comp):
                _LOGGER.debug(
                    "Footao parser: match ignoré compétition '%s' → '%s'",
                    self._cur_comp, text,
                )
                return

            dt_str = f"{self._cur_iso} {self._heure}:00"
            try:    display = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S") > datetime.now()
            except: display = True
            parts = [p.strip() for p in text.split("·")]

            self.matches.append({
                "date":       self._cur_date,
                "date_iso":   self._cur_iso,
                "datetime":   dt_str,
                "display":    display,
                "heure":      self._heure,
                "chaine":     self._img_alt,
                "img_class":  self._img_class,
                "game":       text,
                "competition_label": self._cur_comp,
                "domicile":   parts[0] if parts else text,
                "exterieur":  parts[1] if len(parts) >= 2 else "",
            })


# ─── Coordinator ─────────────────────────────────────────────────────────────

class FootaoCoordinator(DataUpdateCoordinator):
    """
    selected = {
      "Marseille": {"eq":"Marseille OM","comp":"Ligue 1","logo":"https://..."},
      ...
    }
    Le champ "comp" n'est plus utilisé comme paramètre URL mais reste disponible
    comme fallback/label dans les attributs si la page ne retourne pas de <h3>.
    """

    def __init__(self, hass: HomeAssistant, selected: dict) -> None:
        self.selected    = selected
        self._logo_index: dict[str, str] = {}
        super().__init__(hass, _LOGGER, name=DOMAIN,
                         update_interval=timedelta(hours=SCAN_INTERVAL_HOURS))

    async def async_initialize(self) -> None:
        """Chargement non bloquant de clubs.json + index logos."""
        clubs = await self.hass.async_add_executor_job(load_clubs)
        self._logo_index = build_logo_index(clubs)

    async def _async_update_data(self) -> dict:
        data: dict = {}
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode    = ssl.CERT_NONE

        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                for club_name, cfg in self.selected.items():
                    eq        = cfg.get("eq", club_name)
                    comp      = cfg.get("comp", "")   # conservé comme fallback label
                    logo_team = cfg.get("logo", "")

                    # Requête sans comp= → toutes compétitions, filtrage côté parser
                    url = FOOTAO_CAL_URL.format(eq=quote(eq, safe=""))

                    _LOGGER.debug(
                        "Footao: récupération calendrier pour %s → %s", club_name, url
                    )

                    try:
                        async with session.get(
                            url, ssl=ssl_ctx,
                            timeout=aiohttp.ClientTimeout(total=15)
                        ) as resp:
                            if resp.status != 200:
                                _LOGGER.warning("footao %s → HTTP %s", url, resp.status)
                                continue
                            html = await resp.text()
                    except aiohttp.ClientError as err:
                        _LOGGER.warning("Erreur footao %s : %s", url, err)
                        continue

                    parser = FootaoCalParser()
                    parser.feed(html)

                    _LOGGER.debug(
                        "Footao: %s → %d matches parsés (après filtre compétition)",
                        club_name, len(parser.matches),
                    )

                    if not parser.matches:
                        _LOGGER.debug("Aucun match pour %s", club_name)
                        continue

                    match    = next((m for m in parser.matches if m["display"]), parser.matches[-1])
                    sprite   = get_sprite_style(match["img_class"])
                    eq_lower = eq.lower()
                    dom_lower = match["domicile"].lower()
                    situation = "dom" if any(w in dom_lower for w in eq_lower.split()) else "ext"

                    # Compétition : libellé capté depuis le <h3>, sinon fallback config
                    competition = match.get("competition_label") or comp

                    logo_adv = logo_for(
                        match["exterieur"] if situation == "dom" else match["domicile"],
                        self._logo_index,
                    )

                    if situation == "dom":
                        logo_dom = logo_team
                        logo_ext = logo_adv
                    else:
                        logo_dom = logo_adv
                        logo_ext = logo_team

                    data[club_name] = {
                        "state": match["chaine"] or "Inconnu",
                        "attributes": {
                            "team":          club_name,
                            "domicile":      match["domicile"],
                            "logoDomicile":  logo_dom,
                            "exterieur":     match["exterieur"],
                            "logoExterieur": logo_ext,
                            "situation":     situation,
                            "competition":   competition,
                            "date":          match["date"],
                            "datetime":      match["datetime"],
                            "display":       match["display"],
                            "heure":         match["heure"],
                            "logo":          sprite,
                            "chaine":        match["chaine"],
                            "game":          match["game"],
                        },
                    }

        except Exception as err:
            raise UpdateFailed(f"Erreur scraping Footao : {err}") from err

        return data
                    
