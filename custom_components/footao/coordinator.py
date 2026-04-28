"""DataUpdateCoordinator Footao TV — programmetv.php?eq=X (toutes compétitions)."""
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

# Nouvelle URL : toutes compétitions pour une équipe, en une seule requête
FOOTAO_URL = "https://www.footao.tv/programmetv.php?eq={eq}"

# Mots-clés des compétitions autorisées (insensible à la casse)
# La compétition est présente dans <span class="ap"> de chaque match
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
    "ligue conference",
    "ligue conférence",
]

FILTRES_EXCLUS = [" Fém.", " Fém", "Féminin", " U19", " U17", " U21", "-19", "-17"]


def load_clubs() -> dict:
    with open(Path(__file__).parent / "clubs.json", encoding="utf-8") as f:
        return json.load(f)


def build_logo_index(clubs: dict) -> dict[str, str]:
    """Construit un index { eq_name_lower → logo_url } depuis clubs.json."""
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
        return True  # pas de label → on laisse passer (prudence)
    cl = comp_label.lower()
    return any(kw in cl for kw in COMPETITIONS_AUTORISEES)


# ─── Parser HTML ─────────────────────────────────────────────────────────────

class FootaoProgParser(HTMLParser):
    """
    Parse programmetv.php?eq=X.

    Structure d'un match :
      <section>
        <h2><a href="...?jr=D&ms=M&an=Y">date label</a></h2>
        <div>
          <time>HH:MM</time>
          <a href="..."><img class="im XX" alt="Chaine ..."></a>
          <a href="...-chaine-tv-..." class="rc">
            <span itemprop="name">Equipe A · Equipe B <span class="agen">cat</span></span>
          </a>
          <span class="ap"><a href="...">Compétition</a> Phase</span>
        </div>
      </section>
    """

    def __init__(self):
        super().__init__()
        self.matches: list[dict] = []

        # État de la date courante
        self._cur_date = ""
        self._cur_iso  = ""

        # État du div/match en cours de parsing
        self._in_h2        = False
        self._in_h2_a      = False
        self._h2_href      = ""

        self._in_time      = False
        self._heure        = ""

        self._img_alt      = ""
        self._img_class    = ""

        self._in_rc        = False   # <a class="rc"> : lien du match
        self._in_name_span = False   # <span itemprop="name">
        self._in_agen      = False   # <span class="agen"> catégorie à exclure
        self._match_name   = ""      # texte accumulé du nom du match
        self._match_href   = ""

        self._in_ap        = False   # <span class="ap"> : compétition
        self._comp_label   = ""      # texte de compétition accumulé

    # ── Utilitaires ──────────────────────────────────────────────────────────

    def _parse_date_from_href(self, href: str) -> tuple[str, str]:
        """Extrait (iso, label) depuis l'href d'un <h2><a>."""
        # Cas spéciaux textuels (résolus plus tard dans handle_data)
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
        """Enregistre le match en cours s'il est complet et valide."""
        name = self._match_name.strip()
        comp = self._comp_label.strip()

        if not (self._cur_iso and self._heure and name):
            return

        _LOGGER.debug(
            "Footao parser: match candidat → '%s' [%s] (%s %s)",
            name, comp, self._cur_iso, self._heure,
        )

        # Filtre catégories (féminines, jeunes…)
        if any(f in name for f in FILTRES_EXCLUS):
            _LOGGER.debug("Footao parser: ignoré (filtre catégorie) → '%s'", name)
            return

        # Filtre compétition
        if not competition_autorisee(comp):
            _LOGGER.debug("Footao parser: ignoré (compétition '%s') → '%s'", comp, name)
            return

        dt_str = f"{self._cur_iso} {self._heure}:00"
        try:    display = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S") > datetime.now()
        except: display = True

        # Nettoyage du nom : on supprime les annotations de catégorie résiduelles
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

        # Réinitialisation pour le prochain match du même div/section
        self._heure     = ""
        self._img_alt   = ""
        self._img_class = ""
        self._match_name = ""
        self._match_href = ""
        self._comp_label = ""

    # ── Handlers ─────────────────────────────────────────────────────────────

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        css = d.get("class", "")

        if tag == "h2":
            self._in_h2 = True
            self._h2_href = ""

        elif tag == "a" and self._in_h2:
            self._in_h2_a = True
            self._h2_href = d.get("href", "")

        elif tag == "time":
            # Flush du match précédent si on en commence un nouveau dans la même section
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
            self._in_agen = True   # catégorie (Fém., U18…) — on capture mais on filtrera

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
                # Fin du span.ap → on a toute l'info, on peut flush
                self._flush_match()

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return

        # Date courante (dans le <h2><a>)
        if self._in_h2 and self._in_h2_a:
            # Cas "Aujourd'hui"
            if "aujourd" in text.lower():
                self._cur_iso  = datetime.now().strftime("%Y-%m-%d")
                self._cur_date = "Aujourd'hui"
            # Cas "Demain"
            elif "demain" in text.lower():
                self._cur_iso  = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                self._cur_date = "Demain"
            else:
                iso, label = self._parse_date_from_href(self._h2_href)
                if iso:
                    self._cur_iso  = iso
                    self._cur_date = text  # ex: "samedi 2 mai"
            return

        # Heure (dans <time>)
        if self._in_time:
            if re.match(r"^\d{2}:\d{2}$", text):
                self._heure = text
            return

        # Nom du match (dans <a class="rc"><span itemprop="name">)
        if self._in_rc and self._in_name_span and not self._in_agen:
            self._match_name += text + " "
            return

        # Catégorie (dans <span class="agen">) — on l'ajoute quand même pour le filtre
        if self._in_agen:
            self._match_name += text + " "
            return

        # Compétition (dans <span class="ap"><a> ou texte direct)
        if self._in_ap and not self._comp_label:
            self._comp_label = text
            return


# ─── Coordinator ─────────────────────────────────────────────────────────────

class FootaoCoordinator(DataUpdateCoordinator):
    """
    selected = {
      "Marseille": {"eq":"Marseille OM","comp":"Ligue 1","logo":"https://..."},
      ...
    }
    Une seule requête par club via programmetv.php?eq=.
    La compétition est lue directement depuis la page (span.ap).
    Filtre : championnat (Ligue 1/2) + coupes d'Europe.
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
                    comp      = cfg.get("comp", "")   # fallback si pas de label dans la page
                    logo_team = cfg.get("logo", "")

                    url = FOOTAO_URL.format(eq=quote(eq, safe=""))
                    _LOGGER.debug("Footao: %s → %s", club_name, url)

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

                    parser = FootaoProgParser()
                    parser.feed(html)

                    _LOGGER.debug(
                        "Footao: %s → %d match(s) après filtre compétition",
                        club_name, len(parser.matches),
                    )

                    if not parser.matches:
                        _LOGGER.debug("Footao: aucun match pour %s", club_name)
                        continue

                    # Trier par datetime et prendre le prochain match futur
                    parser.matches.sort(key=lambda m: m["datetime"])
                    match = next(
                        (m for m in parser.matches if m["display"]),
                        parser.matches[-1],
                    )

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

                    if situation == "dom":
                        logo_dom = logo_team
                        logo_ext = logo_adv
                    else:
                        logo_dom = logo_adv
                        logo_ext = logo_team

                    competition = match.get("competition_label") or comp

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
        
