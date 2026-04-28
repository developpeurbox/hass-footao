/* ========================================================
   Footao Game Card  — v1.4
   ======================================================== */

class FootaoGameCard extends HTMLElement {

  setConfig(config) {
    if (!config.entity) throw new Error("Vous devez définir une entité.");
    this._config = config;
    // Forcer le re-render si hass est déjà disponible (ex: après sauvegarde config)
    if (this._hass) this.hass = this._hass;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;

    const state = hass.states[this._config.entity];
    if (!state) {
      this.innerHTML = `<ha-card style="padding:16px;color:red">Entité introuvable : ${this._config.entity}</ha-card>`;
      return;
    }

    const a = state.attributes;

    // Si display=false → carte masquée
    if (a.display === false) {
      this.innerHTML = "";
      return;
    }

    // Attributs du match
    const logoDom  = a.logoDomicile  || a.team_domicile_logo  || "";
    const logoExt  = a.logoExterieur || a.team_exterieur_logo || "";
    const gameName = a.game          || a.event_name          || "";
    const chaine   = a.chaine        || state.state           || "";
    const heure    = a.heure         || "";
    const date     = a.date          || "";
    const sprite   = a.logo          || "";

    // Couleurs configurables — appliquées via CSS custom properties sur l'hôte
    this.style.setProperty("--footao-footer-bg",    this._config.footer_bg    || "rgba(0,0,0,0.45)");
    this.style.setProperty("--footao-footer-color", this._config.footer_color || "#c8a96e");

    this.innerHTML = `
      <ha-card>
        <style>
          .foot-card {
            background: #1e1e2e;
            border-radius: 16px;
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,.07);
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
          }
          .foot-top {
            position: relative;
            padding: 18px 16px 14px;
          }
          .foot-bg {
            position: absolute;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            overflow: hidden;
          }
          .foot-bg img {
            position: absolute;
            top: -10px;
            width: 180px;
            height: 180px;
            object-fit: contain;
            opacity: .15;
            filter: grayscale(40%) blur(1px);
          }
          .bg-left  { left: -30px; }
          .bg-right { right: -30px; }
          .foot-body { position: relative; z-index: 1; }
          .foot-game {
            text-align: center;
            font-weight: 700;
            color: #e0e0f0;
            margin-bottom: 20px;
            font-size: 14px;
          }
          .teams {
            display: flex;
            justify-content: space-between;
            align-items: center;
          }
          .team-block {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
            width: 80px;
          }
          .team-logo {
            width: 72px;
            height: 72px;
            object-fit: contain;
            filter: drop-shadow(0 4px 14px rgba(0,0,0,.7));
          }
          .team-name {
            font-size: 11px;
            color: rgba(255,255,255,.55);
            text-align: center;
            line-height: 1.2;
          }
          .center { text-align: center; flex: 1; }
          .sprite  { width: 64px; height: 18px; margin: 0 auto 4px; }
          .chaine  { font-size: 10px; color: rgba(255,255,255,.4); margin-bottom: 4px; }
          .heure   { font-size: 28px; font-weight: 800; color: #fff; }
          .foot-footer {
            background: var(--footao-footer-bg, rgba(0,0,0,0.45));
            border-top: 1px solid rgba(255,255,255,.07);
            padding: 11px 16px;
            text-align: center;
            color: var(--footao-footer-color, #c8a96e);
            font-size: 13px;
            font-weight: 600;
            letter-spacing: .3px;
          }
        </style>

        <div class="foot-card">
          <div class="foot-top">
            <div class="foot-bg">
              ${logoDom ? `<img class="bg-left"  src="${logoDom}">` : ""}
              ${logoExt ? `<img class="bg-right" src="${logoExt}">` : ""}
            </div>
            <div class="foot-body">
              <div class="foot-game">${gameName}</div>
              <div class="teams">
                <div class="team-block">
                  ${logoDom ? `<img class="team-logo" src="${logoDom}">` : `<div style="width:72px;height:72px"></div>`}
                  <span class="team-name">${a.domicile || ""}</span>
                </div>
                <div class="center">
                  ${sprite ? `<div class="sprite" style="${sprite}"></div>` : ""}
                  <div class="chaine">${chaine}</div>
                  <div class="heure">${heure}</div>
                </div>
                <div class="team-block">
                  ${logoExt ? `<img class="team-logo" src="${logoExt}">` : `<div style="width:72px;height:72px"></div>`}
                  <span class="team-name">${a.exterieur || ""}</span>
                </div>
              </div>
            </div>
          </div>
          ${date ? `<div class="foot-footer">${date}</div>` : ""}
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

customElements.define("footao-game-card", FootaoGameCard);

/* ========================================================
   ÉDITEUR GRAPHIQUE
   ======================================================== */

class FootaoGameCardEditor extends HTMLElement {

  constructor() {
    super();
    this._config = {};
    this._hass   = null;
    this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  setConfig(config) {
    this._config = config || {};
    this._render();
  }

  _render() {
    if (!this._hass) return;

    const entities = Object.keys(this._hass.states)
      .filter(e => e.startsWith("sensor.footao_"))
      .sort();

    const current      = this._config?.entity       || "";
    const footerBg     = this._config?.footer_bg    || "rgba(0,0,0,0.45)";
    const footerColor  = this._config?.footer_color || "#c8a96e";

    // Convertit une couleur CSS en valeur utilisable dans <input type="color">
    // input[type=color] n'accepte que les hex #rrggbb
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

        <!-- Sensor -->
        <div class="field">
          <label>Sensor Footao</label>
          <select id="entity-select">
            <option value="">-- Choisir un sensor --</option>
            ${entities.map(e => `<option value="${e}" ${e === current ? "selected" : ""}>${e}</option>`).join("")}
          </select>
        </div>

        <!-- Couleur fond footer -->
        <div class="field">
          <label>Couleur de fond du bandeau</label>
          <div class="color-row">
            <input type="color" id="footer-bg-picker" value="${toHex(footerBg)}">
            <input type="text"  id="footer-bg-text"   value="${footerBg}" placeholder="ex: #1a1a2e ou rgba(0,0,0,0.5)">
          </div>
          <span class="hint">Valeur CSS acceptée : #hex, rgb(), rgba()</span>
        </div>

        <!-- Couleur texte footer -->
        <div class="field">
          <label>Couleur du texte du bandeau</label>
          <div class="color-row">
            <input type="color" id="footer-color-picker" value="${toHex(footerColor)}">
            <input type="text"  id="footer-color-text"   value="${footerColor}" placeholder="ex: #c8a96e">
          </div>
          <span class="hint">Valeur CSS acceptée : #hex, rgb(), rgba()</span>
        </div>

      </div>
    `;

    // ── Listeners ────────────────────────────────────────────────────────────

    const fire = () => {
      this.dispatchEvent(new CustomEvent("config-changed", {
        bubbles: true, composed: true,
        detail: { config: this._config },
      }));
    };

    // Sensor
    this.shadowRoot.getElementById("entity-select").addEventListener("change", (ev) => {
      if (!ev.target.value) return;
      this._config = { ...this._config, entity: ev.target.value };
      fire();
    });

    // Fond footer — picker → texte
    this.shadowRoot.getElementById("footer-bg-picker").addEventListener("input", (ev) => {
      this.shadowRoot.getElementById("footer-bg-text").value = ev.target.value;
      this._config = { ...this._config, footer_bg: ev.target.value };
      fire();
    });
    // Fond footer — texte libre
    this.shadowRoot.getElementById("footer-bg-text").addEventListener("change", (ev) => {
      this._config = { ...this._config, footer_bg: ev.target.value };
      fire();
    });

    // Texte footer — picker → texte
    this.shadowRoot.getElementById("footer-color-picker").addEventListener("input", (ev) => {
      this.shadowRoot.getElementById("footer-color-text").value = ev.target.value;
      this._config = { ...this._config, footer_color: ev.target.value };
      fire();
    });
    // Texte footer — texte libre
    this.shadowRoot.getElementById("footer-color-text").addEventListener("change", (ev) => {
      this._config = { ...this._config, footer_color: ev.target.value };
      fire();
    });
  }
}

customElements.define("footao-game-card-editor", FootaoGameCardEditor);
