/* ========================================================
   Footao Game Card
   ======================================================== */

const FOOTAO_GAME_CARD_VERSION = "v0.1.7";

/* Échappement HTML de toute valeur issue d'une entité ou de la config. */
const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));

/* URL d'image : http(s) ou chemin local absolu uniquement, sinon vide. */
const safeImg = (v) => {
  const u = String(v ?? "").trim();
  return /^(https?:\/\/|\/(?!\/))/i.test(u) ? u : "";
};

/* Logo de chaîne (sprite footao) : l'attribut contient une chaîne CSS complète.
   On n'en garde que la position (deux valeurs numériques) et on reconstruit
   le style avec l'URL du sprite, jamais la valeur brute. */
const spriteStyle = (v) => {
  const m = String(v ?? "").match(
    /background-position:\s*(-?\d+(?:\.\d+)?(?:px)?)\s+(-?\d+(?:\.\d+)?(?:px)?)/i
  );
  return m
    ? `background: url(https://www.footao.tv/i.png?h=4) no-repeat; background-position: ${m[1]} ${m[2]};`
    : "";
};

class FootaoGameCard extends HTMLElement {

  constructor() {
    super();
    this._uid = "footao-" + Math.random().toString(36).slice(2, 9);
  }

  setConfig(config) {
    if (!config.entity) throw new Error("Vous devez définir une entité.");
    this._config = config;
    console.info(`%c FOOTAO-GAME-CARD %c ${FOOTAO_GAME_CARD_VERSION} `, "color:#c8a96e;background:#1e1e2e;font-weight:700;padding:2px 4px;border-radius:4px 0 0 4px", "color:#1e1e2e;background:#c8a96e;font-weight:700;padding:2px 4px;border-radius:0 4px 4px 0");
    if (this._hass) this.hass = this._hass;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;

    const state = hass.states[this._config.entity];
    if (!state) {
      this.innerHTML = `<ha-card style="padding:16px;color:red">Entité introuvable : ${esc(this._config.entity)}</ha-card>`;
      return;
    }

    const b   = state.attributes;
    const uid = this._uid;

    const now = new Date();
    const fin = b.datetime_fin ? new Date(b.datetime_fin.replace(" ", "T")) : null;

    this.style.setProperty("--footao-footer-bg",    this._config.footer_bg    || "rgba(0,0,0,0.45)");
    this.style.setProperty("--footao-footer-color", this._config.footer_color || "#c8a96e");

    const pasDeMatch = (fin && fin < now) || (!b.domicile && !b.exterieur);

    if (pasDeMatch) {
      const logoDom  = safeImg(b.LogoTeam || b.logoTeam || b.LogoDomicile || b.logoDomicile);
      const teamName = b.team     || b.domicile || "";

      this.innerHTML = `
        <ha-card>
          <style>
            #${uid} .foot-card {
              background: #1e1e2e;
              border-radius: 16px;
              position: relative;
              overflow: hidden;
              border: 1px solid rgba(255,255,255,.07);
              font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            }
            #${uid} .foot-top {
              position: relative;
              padding: 18px 16px 14px;
            }
            #${uid} .foot-body { position: relative; z-index: 1; }
            #${uid} .foot-empty {
              display: flex;
              flex-direction: column;
              align-items: center;
              gap: 10px;
            }
            #${uid} .team-logo-wrap {
              position: relative;
              width: 72px;
              height: 72px;
              display: flex;
              align-items: center;
              justify-content: center;
            }
            #${uid} .team-logo-ghost {
              position: absolute;
              top: 50%;
              left: 50%;
              width: 170px;
              height: 170px;
              transform: translate(-50%, -50%);
              object-fit: contain;
              opacity: .15;
              filter: grayscale(40%) blur(1px);
              pointer-events: none;
              z-index: 0;
            }
            #${uid} .team-logo {
              position: relative;
              z-index: 1;
              width: 72px;
              height: 72px;
              object-fit: contain;
              filter: drop-shadow(0 4px 14px rgba(0,0,0,.7));
            }
            #${uid} .team-name {
              font-size: 13px;
              font-weight: 600;
              color: rgba(255,255,255,.75);
              text-align: center;
            }
            #${uid} .no-match-msg {
              font-size: 11px;
              color: rgba(255,255,255,.35);
              text-align: center;
              font-style: italic;
            }
          </style>
          <div id="${uid}">
            <div class="foot-card">
              <div class="foot-top">
                <div class="foot-body">
                  <div class="foot-empty">
                    <div class="team-logo-wrap">
                      ${logoDom ? `<img class="team-logo-ghost" src="${esc(logoDom)}">` : ""}
                      ${logoDom
                        ? `<img class="team-logo" src="${esc(logoDom)}">`
                        : `<div style="width:72px;height:72px"></div>`}
                    </div>
                    ${teamName ? `<span class="team-name">${esc(teamName)}</span>` : ""}
                    <span class="no-match-msg">Aucun match prévu prochainement</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </ha-card>
      `;
      return;
    }

    const logoDom    = safeImg(b.LogoDomicile  || b.logoDomicile  || b.team_domicile_logo);
    const logoExt    = safeImg(b.LogoExterieur || b.logoExterieur || b.team_exterieur_logo);
    const gameName   = b.game          || b.event_name    || "";
    const logo1      = spriteStyle(b.Logo1 || b.logo1);
    const diffuseur1 = b.diffuseur1    || "";
    const logo2      = spriteStyle(b.Logo2 || b.logo2);
    const diffuseur2 = b.diffuseur2    || "";
    const heure      = b.heure         || "";
    const date       = b.date          || "";

    this.innerHTML = `
      <ha-card>
        <style>
          #${uid} .foot-card {
            background: #1e1e2e;
            border-radius: 16px;
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,.07);
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
          }
          #${uid} .foot-top {
            position: relative;
            padding: 18px 16px 14px;
          }
          #${uid} .foot-body { position: relative; z-index: 1; }
          #${uid} .foot-game {
            text-align: center;
            margin-bottom: 20px;
          }
          #${uid} .foot-game-name {
            font-weight: 700;
            color: #e0e0f0;
            font-size: 16px;
            display: block;
          }
          #${uid} .foot-game-competition {
            font-size: 12px;
            color: rgba(255,255,255,.4);
            display: block;
            margin-top: 3px;
            font-style: italic;
          }
          #${uid} .teams {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: clamp(20px, 8%, 64px);
          }
          #${uid} .team-block {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
            width: 80px;
            flex: 0 0 auto;
          }
          #${uid} .team-logo-wrap {
            position: relative;
            width: 72px;
            height: 72px;
            display: flex;
            align-items: center;
            justify-content: center;
          }
          #${uid} .team-logo-ghost {
            position: absolute;
            top: 50%;
            left: 50%;
            width: 170px;
            height: 170px;
            transform: translate(-50%, -50%);
            object-fit: contain;
            opacity: .15;
            filter: grayscale(40%) blur(1px);
            pointer-events: none;
            z-index: 0;
          }
          #${uid} .team-logo {
            position: relative;
            z-index: 1;
            width: 72px;
            height: 72px;
            object-fit: contain;
            filter: drop-shadow(0 4px 14px rgba(0,0,0,.7));
          }
          #${uid} .team-name {
            font-size: 11px;
            color: rgba(255,255,255,.55);
            text-align: center;
            line-height: 1.2;
          }
          #${uid} .center { text-align: center; flex: 0 0 auto; min-width: 96px; }
          #${uid} .sprite  { width: 64px; height: 15px; margin: 0 auto 4px; }
          #${uid} .chaine  { font-size: 12px; color: rgba(255,255,255,.4); margin-bottom: 4px; }
          #${uid} .channel-zone {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2px;
            margin-bottom: 5px;
          }
          #${uid} .channel-logo {
            width: 64px;
            height: 24px;
            object-fit: contain;
          }
          #${uid} .heure   { font-size: 28px; font-weight: 800; color: #fff; }
          #${uid} .foot-footer {
            background: var(--footao-footer-bg, rgba(0,0,0,0.45));
            border-top: 1px solid rgba(255,255,255,.07);
            padding: 11px 16px;
            text-align: center;
            color: var(--footao-footer-color, #c8a96e);
            font-size: 16px;
            font-weight: 600;
            letter-spacing: .3px;
          }
        </style>

        <div id="${uid}">
          <div class="foot-card">
            <div class="foot-top">
              <div class="foot-body">
                <div class="foot-game">
                  <span class="foot-game-name">${esc(gameName)}</span>
                  ${b.competition
                    ? `<span class="foot-game-competition">${esc(b.competition)}</span>`
                    : ""}
                </div>
                <div class="teams">
                  <div class="team-block">
                    <div class="team-logo-wrap">
                      ${logoDom ? `<img class="team-logo-ghost" src="${esc(logoDom)}">` : ""}
                      ${logoDom
                        ? `<img class="team-logo" src="${esc(logoDom)}">`
                        : `<div style="width:72px;height:72px"></div>`}
                    </div>
                    <span class="team-name">${esc(b.domicile)}</span>
                  </div>
                  <div class="center">
                    ${diffuseur1 ? `
                      <div class="channel-zone">
                        ${logo1 ? `<div class="sprite" style="${esc(logo1)}"></div>` : ""}
                        <div class="chaine">${esc(diffuseur1)}</div>
                      </div>
                    ` : ""}

                    ${diffuseur2 ? `
                      <div class="channel-zone">
                        ${logo2 ? `<div class="sprite" style="${esc(logo2)}"></div>` : ""}
                        <div class="chaine">${esc(diffuseur2)}</div>
                      </div>
                    ` : ""}

                    ${!diffuseur1 && !diffuseur2
                      ? `<div class="chaine">${esc(state.state)}</div>`
                      : ""}

                    <div class="heure">${esc(heure)}</div>
                  </div>
                  <div class="team-block">
                    <div class="team-logo-wrap">
                      ${logoExt ? `<img class="team-logo-ghost" src="${esc(logoExt)}">` : ""}
                      ${logoExt
                        ? `<img class="team-logo" src="${esc(logoExt)}">`
                        : `<div style="width:72px;height:72px"></div>`}
                    </div>
                    <span class="team-name">${esc(b.exterieur)}</span>
                  </div>
                </div>
              </div>
            </div>
            ${date ? `<div class="foot-footer">${esc(date)}</div>` : ""}
          </div>
        </div>
      </ha-card>
    `;
  }

  static getConfigElement() {
    return document.createElement("footao-game-card-editor");
  }

  static getStubConfig() {
    return { entity: "" };
  }

  getCardSize() { return 3; }
}

if (!customElements.get("footao-game-card")) {
  customElements.define("footao-game-card", FootaoGameCard);
}

/* Déclare la carte dans le sélecteur de cartes de Lovelace. */
window.customCards = window.customCards || [];
window.customCards.push({
  type: "footao-game-card",
  name: "Footao Game Card",
  description: "Prochain match d'un club de football (intégration footao).",
});

/* ========================================================
   ÉDITEUR GRAPHIQUE
   ======================================================== */

class FootaoGameCardEditor extends HTMLElement {

  constructor() {
    super();
    this._config = {};
    this._hass   = null;
    this._built  = false;
    this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._render();
  }

  setConfig(config) {
    const entityChanged = (config?.entity || "") !== (this._config?.entity || "");
    this._config = config || {};
    if (!this._built || entityChanged) this._render();
  }

  _render() {
    if (!this._hass) return;
    this._built = true;

    const entities = Object.keys(this._hass.states)
      .filter(e => e.startsWith("sensor.footao_"))
      .sort();

    const current     = this._config?.entity       || "";
    const footerBg    = this._config?.footer_bg    || "rgba(0,0,0,0.45)";
    const footerColor = this._config?.footer_color || "#c8a96e";

    const toHex = (c) => {
      if (!c || c.startsWith("rgba") || c.startsWith("rgb")) return "#000000";
      return c;
    };

    this.shadowRoot.innerHTML = `
      <style>
        .editor        { padding: 16px; display: flex; flex-direction: column; gap: 14px; }
        .field         { display: flex; flex-direction: column; gap: 4px; }
        label          { font-size: 13px; color: var(--primary-text-color, #fff); }
        select, input[type="text"] {
          width: 100%;
          padding: 8px 10px;
          border-radius: 8px;
          border: 1px solid rgba(255,255,255,.2);
          background: var(--card-background-color, #1e1e2e);
          color: var(--primary-text-color, #fff);
          font-size: 14px;
          cursor: pointer;
          box-sizing: border-box;
        }
        .color-row     { display: flex; align-items: center; gap: 10px; }
        input[type="color"] {
          width: 40px; height: 36px;
          border: none; border-radius: 8px;
          cursor: pointer; padding: 2px;
          background: transparent;
          flex-shrink: 0;
        }
        input[type="text"] { flex: 1; }
        .hint { font-size: 11px; color: rgba(255,255,255,.35); }
      </style>

      <div class="editor">

        <div class="field">
          <label>Sensor Footao</label>
          <select id="entity-select">
            <option value="">-- Choisir un sensor --</option>
            ${entities.map(e => `<option value="${esc(e)}" ${e === current ? "selected" : ""}>${esc(e)}</option>`).join("")}
          </select>
        </div>

        <div class="field">
          <label>Couleur de fond du bandeau</label>
          <div class="color-row">
            <input type="color" id="footer-bg-picker" value="${esc(toHex(footerBg))}">
            <input type="text"  id="footer-bg-text"   value="${esc(footerBg)}" placeholder="ex: #1a1a2e ou rgba(0,0,0,0.5)">
          </div>
          <span class="hint">Valeur CSS acceptée : #hex, rgb(), rgba()</span>
        </div>

        <div class="field">
          <label>Couleur du texte du bandeau</label>
          <div class="color-row">
            <input type="color" id="footer-color-picker" value="${esc(toHex(footerColor))}">
            <input type="text"  id="footer-color-text"   value="${esc(footerColor)}" placeholder="ex: #c8a96e">
          </div>
          <span class="hint">Valeur CSS acceptée : #hex, rgb(), rgba()</span>
        </div>

      </div>
    `;

    const fire = () => {
      this.dispatchEvent(new CustomEvent("config-changed", {
        bubbles: true, composed: true,
        detail: { config: this._config },
      }));
    };

    this.shadowRoot.getElementById("entity-select").addEventListener("change", (ev) => {
      if (!ev.target.value) return;
      this._config = { ...this._config, entity: ev.target.value };
      fire();
    });

    this.shadowRoot.getElementById("footer-bg-picker").addEventListener("input", (ev) => {
      this.shadowRoot.getElementById("footer-bg-text").value = ev.target.value;
      this._config = { ...this._config, footer_bg: ev.target.value };
      fire();
    });
    this.shadowRoot.getElementById("footer-bg-text").addEventListener("change", (ev) => {
      this._config = { ...this._config, footer_bg: ev.target.value };
      fire();
    });

    this.shadowRoot.getElementById("footer-color-picker").addEventListener("input", (ev) => {
      this.shadowRoot.getElementById("footer-color-text").value = ev.target.value;
      this._config = { ...this._config, footer_color: ev.target.value };
      fire();
    });
    this.shadowRoot.getElementById("footer-color-text").addEventListener("change", (ev) => {
      this._config = { ...this._config, footer_color: ev.target.value };
      fire();
    });
  }
}

if (!customElements.get("footao-game-card-editor")) {
  customElements.define("footao-game-card-editor", FootaoGameCardEditor);
}
