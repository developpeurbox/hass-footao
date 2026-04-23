from __future__ import annotations
import json
import logging
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import json as hass_json

from .const import DOMAIN, SCAN_INTERVAL_HOURS, SPRITE_BASE_STYLE, SPRITE_DEFAULT, SPRITE_POSITIONS

_LOGGER = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

FOOTAO_CAL_URL = "https://www.footao.tv/tv-calendrier.php?e={eq}&c={comp}"

FILTRES_EXCLUS = [" Fém.", " Féminin", " U19", " U17", " U21", "-19", "-17"]

# ───────────────────────────────────────────────────────────────

def build_logo_index(clubs: dict) -> dict:
    index = {}
    for league in clubs.values():
        for cfg in league.values():
            if cfg.get("eq") and cfg.get("logo"):
                index[cfg["eq"].lower()] = cfg["logo"]
    return index


def logo_for(name: str, index: dict) -> str:
    if not name:
        return ""
    name = name.lower()
    if name in index:
        return index[name]
    for k, v in index.items():
        if k in name or name in k:
            return v
    return ""


def get_sprite_style(css_class: str) -> str:
    key = css_class.split()[1] if css_class and len(css_class.split()) > 1 else ""
    return SPRITE_BASE_STYLE.format(pos=SPRITE_POSITIONS.get(key, SPRITE_DEFAULT))


# ───────────────────────────────────────────────────────────────

class FootaoCalParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.matches = []
        self.cur_iso = ""
        self.cur_date = ""
        self.heure = ""
        self.img_alt = ""
        self.img_class = ""
        self.in_link = False

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)

        if tag == "h2":
            self.cur_iso = self.cur_date = ""

        if tag == "a" and "jr=" in d.get("href", ""):
            m = re.search(r"jr=(\d+).*ms=(\d+).*an=(\d+)", d["href"])
            if m:
                self.cur_iso = f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
                self.cur_date = self.cur_iso

        if tag == "img":
            self.img_alt = d.get("alt", "").strip()
            self.img_class = d.get("class", "")

        if tag == "a" and "-chaine-tv-diffusion-heure" in d.get("href", ""):
            self.in_link = True

    def handle_endtag(self, tag):
        if tag == "a":
            self.in_link = False

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return

        if re.match(r"^\d{2}:\d{2}$", text):
            self.heure = text

        if self.in_link and "·" in text:
            if any(f in text for f in FILTRES_EXCLUS):
                return

            dt = f"{self.cur_iso} {self.heure or '00:00'}:00"

            self.matches.append({
                "datetime": dt,
                "date": self.cur_date,
                "heure": self.heure,
                "game": text,
                "domicile": text.split("·")[0].strip(),
                "exterieur": text.split("·")[1].strip(),
                "img_class": self.img_class,
                "chaine": self.img_alt,
            })


# ───────────────────────────────────────────────────────────────

class FootaoCoordinator(DataUpdateCoordinator):

    def __init__(self, hass: HomeAssistant, selected: dict):
        self.selected = selected

        clubs_path = Path(__file__).parent / "clubs.json"
        clubs = hass_json.load_json(clubs_path)
        self.logo_index = build_logo_index(clubs)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=SCAN_INTERVAL_HOURS),
        )

    async def _async_update_data(self):
        data = {}

        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                for club, cfg in self.selected.items():
                    eq = cfg.get("eq", club)
                    comp = cfg.get("comp", "")
                    logo_team = cfg.get("logo", "")

                    url = FOOTAO_CAL_URL.format(
                        eq=quote(eq, safe=""),
                        comp=quote(comp, safe="")
                    )

                    async with session.get(url, timeout=15) as resp:
                        html = await resp.text()

                    parser = FootaoCalParser()
                    parser.feed(html)

                    if not parser.matches:
                        data[club] = {
                            "state": "Aucun match",
                            "attributes": {
                                "domicile": club,
                                "exterieur": "",
                                "logoDomicile": logo_team,
                                "logoExterieur": "",
                                "game": "Aucun match programmé",
                                "date": "",
                                "heure": "",
                                "chaine": "",
                                "logo": get_sprite_style(""),
                            }
                        }
                        continue

                    future = [
                        m for m in parser.matches
                        if datetime.fromisoformat(m["datetime"]) > datetime.now()
                    ]

                    match = sorted(
                        future or parser.matches,
                        key=lambda m: m["datetime"]
                    )[0]

                    situation = "dom" if eq.lower() in match["domicile"].lower() else "ext"
                    adv = match["exterieur"] if situation == "dom" else match["domicile"]

                    data[club] = {
                        "state": match["chaine"] or "Inconnu",
                        "attributes": {
                            "domicile": match["domicile"],
                            "exterieur": match["exterieur"],
                            "logoDomicile": logo_team if situation == "dom" else logo_for(adv, self.logo_index),
                            "logoExterieur": logo_for(adv, self.logo_index) if situation == "dom" else logo_team,
                            "game": match["game"],
                            "date": match["date"],
                            "heure": match["heure"],
                            "chaine": match["chaine"],
                            "logo": get_sprite_style(match["img_class"]),
                        }
                    }

            return data

        except Exception as err:
            raise UpdateFailed(err)
