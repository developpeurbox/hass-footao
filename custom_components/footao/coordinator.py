"""DataUpdateCoordinator Footao TV.

Stratégie de résolution d'URL par club :
  1. GET programmetv.php?eq=<eq>
     - Si la réponse contient une redirection JS (window.location.replace),
       on suit l'URL cible (page dédiée du club, même format HTML).
     - Sinon on parse directement.
  2. Si le parse donne 0 match (club sans page dédiée et programmetv KO),
     fallback : tv-calendrier.php?e=<eq>&c=<comp> pour chaque compétition
     de la liste COMPETITIONS_FALLBACK. On fusionne et on prend le plus proche.
"""
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

FOOTAO_PROG_URL = "https://www.footao.tv/programmetv.php?eq={eq}"
FOOTAO_CAL_URL  = "https://www.footao.tv/tv-calendrier.php?e={eq}&c={comp}"

# Compétitions utilisées en fallback (tv-calendrier.php)
COMPETITIONS_FALLBACK = [
    "Ligue 1",
    "Ligue 2",
    "Ligue des Champions",
    "Ligue Europa",
    "Ligue Conference",
]

# Filtre d'acceptation sur la compétition (programmetv.php / pages dédiées)
COMPETITIONS_AUTORISEES = [
    "ligue 1",
    "ligue 2",
    "champions league",
    "ligue des champions",
    "europa league",
    "ligue europa",
    "conference league",
    "ligue conference",
    "ligue conférence",
]

FILTRES_EXCLUS = [" Fém.", " Fém", "Féminin", " U19", " U17", " U21", "-19", "-17"]

# Regex pour détecter une redirection JS dans le HTML
_RE_JS_REDIRECT = re.compile(
    r'window\.location\.(?:replace|href)\s*[=(]\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def load_clubs() -> dict:
    with open(Path(__file__).parent / "clubs.json", encoding="utf-8") as f:
        return json.load(f)


def build_logo_index(clubs: dict) -> dict[str, str]:
    index: dict[str, str] = {}
    for league_clubs in clubs.values():
        for cfg in league_clubs.values():
            eq   = cfg.get("eq", "")
            logo = cfg.get("logo", "")
            if eq and logo:
                index[eq.lower()] = logo
    return index


def logo_for(name: str, index: dict[str, str]) -> str:
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
    if not comp_label:
        return True
    cl = comp_label.lower()
    return any(kw in cl for kw in COMPETITIONS_AUTORISEES)


def detect_js_redirect(html: str) -> str | None:
    """Retourne l'URL de redirection JS si présente, sinon None."""
    m = _RE_JS_REDIRECT.search(html)
    return m.group(1) if m else None


# ─── Parsers ─────────────────────────────────────────────────────────────────

class FootaoProgParser(HTMLParser):
    """
    Parse programmetv.php?eq= et les pages dédiées (même structure).

    Structure d'un match :
      <h2><a href="...?jr=D&ms=M&an=Y">date</a></h2>
      <div>
        <time>HH:MM</time>
        <a href="..."><img class="im XX" alt="Chaine ..."></a>
        <a href="...-chaine-tv-..." class="rc">
          <span itemprop="name">Equipe A · Equipe B <span class="agen">cat</span></span>
        </a>
        <span class="ap"><a>Compétition</a> Phase</span>
      </div>
    """

    def __init__(self):
        super().__init__()
        self.matches: list[dict] = []

        self._cur_date     = ""
        self._cur_iso      = ""

        self._in_h2        = False
        self._in_h2_a      = False
        self._h2_href      = ""

        self._in_time      = False
        self._heure        = ""

        self._img_alt      = ""
        self._img_class    = ""

        self._in_rc        = False
        self._in_name_span = False
        self._in_agen      = False
        self._match_name   = ""
        self._match_href   = ""

        self._in_ap        = False
        self._comp_label   = ""

    def _parse_date_from_href(self, href: str) -> tuple[str, str]:
        jr = re.search(r"jr=(\d+)", href)
        ms = re.search(r"ms=(\d+)", href)
        an = re.search(r"an=(\d+)", href)
        v  = re.search(r"\?v=([^&]+)", href)
        if jr and ms and an:
            iso   = f"{an.group(1)}-{ms.group(1).zfill(2)}-{jr.group(1).zfill(2)}"
            label = v.group(1).replace("-", " ").capitalize() if v else iso
            return iso, label
        return "", ""

    def _flush_match(self) -> None:
        name = self._match_name.strip()
        comp = self._comp_label.strip()

        if not (self._cur_iso and self._heure and name):
            return

        _LOGGER.debug(
            "Footao parser: candidat → '%s' [%s] (%s %s)",
            name, comp, self._cur_iso, self._heure,
        )

        if any(f in name for f in FILTRES_EXCLUS):
            _LOGGER.debug("Footao parser: ignoré (catégorie) → '%s'", name)
            self._reset_match()
            return

        if not competition_autorisee(comp):
            _LOGGER.debug("Footao parser: ignoré (compétition '%s') → '%s'", comp, name)
            self._reset_match()
            return

        dt_str = f"{self._cur_iso} {self._heure}:00"
        try:    display = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S") > datetime.now()
        except: display = True

        clean_name = re.sub(r"\s*(Fém\.?|U\d{2})\s*", " ", name).strip()
        parts = [p.strip() for p in clean_name.split("·")]

        self.matches.append({
            "date":              self._cur_date,
            "date_iso":          self._cur_iso,
            "datetime":          dt_str,
            "display":           display,
            "heure":             self._heure,
            "chaine":            self._img_alt,
            "img_class":         self._img_class,
            "game":              clean_name,
            "competition_label": comp,
            "domicile":          parts[0] if parts else clean_name,
            "exterieur":         parts[1] if len(parts) >= 2 else "",
        })
        self._reset_match()

    def _reset_match(self) -> None:
        self._heure      = ""
        self._img_alt    = ""
        self._img_class  = ""
        self._match_name = ""
        self._match_href = ""
        self._comp_label = ""

    def handle_starttag(self, tag, attrs):
        d   = dict(attrs)
        css = d.get("class", "")

        if tag == "h2":
            self._in_h2   = True
            self._h2_href = ""

        elif tag == "a" and self._in_h2:
            self._in_h2_a = True
            self._h2_href = d.get("href", "")

        elif tag == "time":
            if self._match_name:
                self._flush_match()
            self._in_time = True
            self._heure   = ""

        elif tag == "img" and "im" in css:
            alt = d.get("alt", "")
            for w in ["tv direct match", "match programme foot soir",
                      "foot programme soir", "match"]:
                alt = alt.replace(w, "")
            self._img_alt   = alt.strip()
            self._img_class = css if isinstance(css, str) else " ".join(css)

        elif tag == "a" and "rc" in css:
            self._in_rc      = True
            self._match_href = d.get("href", "")
            self._match_name = ""

        elif tag == "span" and d.get("itemprop") == "name":
            self._in_name_span = True

        elif tag == "span" and "agen" in css:
            self._in_agen = True

        elif tag == "span" and "ap" in css:
            self._in_ap      = True
            self._comp_label = ""

    def handle_endtag(self, tag):
        if tag == "h2":
            self._in_h2 = self._in_h2_a = False

        elif tag == "a" and self._in_h2:
            self._in_h2_a = False

        elif tag == "time":
            self._in_time = False

        elif tag == "a" and self._in_rc:
            self._in_rc = False

        elif tag == "span":
            if self._in_agen:
                self._in_agen = False
            elif self._in_name_span:
                self._in_name_span = False
            elif self._in_ap:
                self._in_ap = False
                self._flush_match()

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return

        if self._in_h2 and self._in_h2_a:
            if "aujourd" in text.lower():
                self._cur_iso  = datetime.now().strftime("%Y-%m-%d")
                self._cur_date = "Aujourd'hui"
            elif "demain" in text.lower():
                self._cur_iso  = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                self._cur_date = "Demain"
            else:
                iso, _ = self._parse_date_from_href(self._h2_href)
                if iso:
                    self._cur_iso  = iso
                    self._cur_date = text
            return

        if self._in_time:
            if re.match(r"^\d{2}:\d{2}$", text):
                self._heure = text
            return

        if self._in_rc and self._in_name_span:
            self._match_name += text + " "
            return

        if self._in_agen:
            self._match_name += text + " "
            return

        if self._in_ap and not self._comp_label:
            self._comp_label = text
            return


class FootaoCalParser(HTMLParser):
    """
    Fallback : parse tv-calendrier.php?e=&c= (ancienne structure).
    Utilisé quand programmetv.php ne retourne aucun match valide.
    La compétition est injectée via competition_label (connue à l'avance).
    """

    def __init__(self, competition_label: str = ""):
        super().__init__()
        self.matches: list[dict] = []
        self._competition_label = competition_label
        self._cur_date = self._cur_iso = self._heure = ""
        self._img_alt  = self._img_class = ""
        self._in_h2    = self._cap_h2 = self._in_link = False
        self._h2_href  = ""

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
        elif self._in_h2 and tag == "a":
            self._h2_href = d.get("href", ""); self._cap_h2 = True
        elif tag == "img":
            alt = d.get("alt", "")
            for w in ["tv direct match", "match programme foot soir",
                      "foot programme soir", "match"]:
                alt = alt.replace(w, "")
            self._img_alt   = alt.strip()
            css = d.get("class", "")
            self._img_class = css if isinstance(css, str) else " ".join(css)
        elif tag == "a" and not self._in_h2:
            if "-chaine-tv-diffusion-heure" in d.get("href", ""):
                self._in_link = True

    def handle_endtag(self, tag):
        if tag == "h2": self._in_h2 = self._cap_h2 = False
        if tag == "a":  self._in_link = self._cap_h2 = False

    def handle_data(self, data):
        text = data.strip()
        if not text:
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
            if any(f in text for f in FILTRES_EXCLUS):
                return
            dt_str = f"{self._cur_iso} {self._heure}:00"
            try:    display = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S") > datetime.now()
            except: display = True
            parts = [p.strip() for p in text.split("·")]
            self.matches.append({
                "date":              self._cur_date,
                "date_iso":          self._cur_iso,
                "datetime":          dt_str,
                "display":           display,
                "heure":             self._heure,
                "chaine":            self._img_alt,
                "img_class":         self._img_class,
                "game":              text,
                "competition_label": self._competition_label,
                "domicile":          parts[0] if parts else text,
                "exterieur":         parts[1] if len(parts) >= 2 else "",
            })


# ─── Coordinator ─────────────────────────────────────────────────────────────

class FootaoCoordinator(DataUpdateCoordinator):
    """
    selected = {
      "Marseille": {"eq":"Marseille OM","comp":"Ligue 1","logo":"https://..."},
      ...
    }
    Résolution par club :
      1. GET programmetv.php?eq= → détection redirection JS → parse FootaoProgParser
      2. Si 0 match → fallback tv-calendrier.php pour chaque compétition de COMPETITIONS_FALLBACK
    """

    def __init__(self, hass: HomeAssistant, selected: dict) -> None:
        self.selected    = selected
        self._logo_index: dict[str, str] = {}
        super().__init__(hass, _LOGGER, name=DOMAIN,
                         update_interval=timedelta(hours=SCAN_INTERVAL_HOURS))

    async def async_initialize(self) -> None:
        clubs = await self.hass.async_add_executor_job(load_clubs)
        self._logo_index = build_logo_index(clubs)

    async def _fetch_html(
        self, session: aiohttp.ClientSession, ssl_ctx, url: str
    ) -> str | None:
        try:
            async with session.get(
                url, ssl=ssl_ctx, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning("footao %s → HTTP %s", url, resp.status)
                    return None
                return await resp.text()
        except aiohttp.ClientError as err:
            _LOGGER.warning("Erreur footao %s : %s", url, err)
            return None

    async def _fetch_and_parse_prog(
        self,
        session: aiohttp.ClientSession,
        ssl_ctx,
        eq: str,
    ) -> list[dict]:
        """
        Tente programmetv.php?eq= avec suivi de redirection JS.
        Retourne la liste de matchs filtrés (peut être vide).
        """
        url  = FOOTAO_PROG_URL.format(eq=quote(eq, safe=""))
        html = await self._fetch_html(session, ssl_ctx, url)
        if not html:
            return []

        # Détection redirection JS
        redirect = detect_js_redirect(html)
        if redirect:
            _LOGGER.debug("Footao: redirection JS détectée → %s", redirect)
            html = await self._fetch_html(session, ssl_ctx, redirect)
            if not html:
                return []

        parser = FootaoProgParser()
        parser.feed(html)
        _LOGGER.debug(
            "Footao: programmetv '%s' → %d match(s) après filtre", eq, len(parser.matches)
        )
        return parser.matches

    async def _fetch_fallback(
        self,
        session: aiohttp.ClientSession,
        ssl_ctx,
        eq: str,
    ) -> list[dict]:
        """
        Fallback : tv-calendrier.php pour chaque compétition de COMPETITIONS_FALLBACK.
        Retourne la liste fusionnée.
        """
        all_matches: list[dict] = []
        for comp in COMPETITIONS_FALLBACK:
            url  = FOOTAO_CAL_URL.format(eq=quote(eq, safe=""), comp=quote(comp, safe=""))
            _LOGGER.debug("Footao: fallback calendrier '%s' → %s", comp, url)
            html = await self._fetch_html(session, ssl_ctx, url)
            if not html:
                continue
            p = FootaoCalParser(competition_label=comp)
            p.feed(html)
            _LOGGER.debug(
                "Footao: fallback '%s' → %d match(s)", comp, len(p.matches)
            )
            all_matches.extend(p.matches)
        return all_matches

    async def _async_update_data(self) -> dict:
        data: dict = {}
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode    = ssl.CERT_NONE

        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                for club_name, cfg in self.selected.items():
                    eq        = cfg.get("eq", club_name)
                    comp      = cfg.get("comp", "")
                    logo_team = cfg.get("logo", "")

                    # 1) Tentative programmetv.php (+ suivi redirection JS)
                    matches = await self._fetch_and_parse_prog(session, ssl_ctx, eq)

                    # 2) Fallback tv-calendrier si aucun match retourné
                    if not matches:
                        _LOGGER.debug(
                            "Footao: %s → 0 match via programmetv, bascule fallback", club_name
                        )
                        matches = await self._fetch_fallback(session, ssl_ctx, eq)

                    if not matches:
                        _LOGGER.debug("Footao: aucun match pour %s", club_name)
                        continue

                    # Trier et prendre le prochain match futur
                    matches.sort(key=lambda m: m["datetime"])
                    match = next((m for m in matches if m["display"]), matches[-1])

                    _LOGGER.debug(
                        "Footao: %s → retenu : '%s' [%s] %s",
                        club_name, match["game"],
                        match["competition_label"], match["datetime"],
                    )

                    sprite    = get_sprite_style(match["img_class"])
                    eq_lower  = eq.lower()
                    dom_lower = match["domicile"].lower()
                    situation = "dom" if any(w in dom_lower for w in eq_lower.split()) else "ext"

                    logo_adv = logo_for(
                        match["exterieur"] if situation == "dom" else match["domicile"],
                        self._logo_index,
                    )

                    logo_dom = logo_team if situation == "dom" else logo_adv
                    logo_ext = logo_adv  if situation == "dom" else logo_team

                    competition = match.get("competition_label") or comp

                    data[club_name] = {
                        "state": match["chaine"] or "Inconnu",
                        "attributes": {
                            "team":          club_name,
                            "domicile":      match["domicile"],
                            "logoDomicile":  logo_dom,
                            "exterieur":     match["exterieur"],
                            "logoExterieur": logo_ext,
                            "situation":  
