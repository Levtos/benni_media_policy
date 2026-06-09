// benni_media_policy — Vanilla-Debug-Panel (kein Bundler/Build-Step).
// Pollt `benni_media_policy/get_status` und zeigt die rohe Payload (alle Felder).
// Step-1-Scaffold: bewusst nur eine Debug-Maske; die richtige UX folgt später.

const WS_GET_STATUS = "benni_media_policy/get_status";
const REFRESH_MS = 2000;

const CSS = `
  :host { display:block; height:100%; background:#282a36; color:#f8f8f2;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  .wrap { padding:20px; max-width:900px; margin:0 auto; }
  h1 { font-size:18px; margin:0 0 4px; color:#ffb86c; }
  .sub { color:#6272a4; font-size:12px; margin:0 0 16px; }
  .card { background:#1e1f29; border:1px solid #44475a; border-radius:10px;
    padding:14px 16px; margin-bottom:14px; }
  .card h2 { font-size:13px; margin:0 0 10px; color:#50fa7b; text-transform:uppercase;
    letter-spacing:.05em; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  td { padding:5px 8px; border-bottom:1px solid #2b2d3a; vertical-align:top; }
  td.k { color:#8be9fd; width:40%; white-space:nowrap; }
  td.v { color:#f8f8f2; word-break:break-word; }
  .nullv { color:#6272a4; font-style:italic; }
  .true { color:#50fa7b; } .false { color:#ff5555; }
  .err { color:#ffb86c; }
  .foot { color:#6272a4; font-size:11px; margin-top:12px; }
  button { background:#44475a; color:#f8f8f2; border:0; border-radius:6px;
    padding:6px 12px; cursor:pointer; font-family:inherit; font-size:12px; }
  button:hover { background:#6272a4; }
`;

function fmt(v) {
  if (v === null || v === undefined) return '<span class="nullv">null</span>';
  if (v === true) return '<span class="true">true</span>';
  if (v === false) return '<span class="false">false</span>';
  if (Array.isArray(v)) return v.length ? esc(v.join(", ")) : '<span class="nullv">[]</span>';
  if (typeof v === "object") return esc(JSON.stringify(v));
  return esc(String(v));
}
function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
function rows(obj) {
  const o = obj || {};
  const keys = Object.keys(o);
  if (!keys.length) return `<tr><td class="v nullv" colspan="2">—</td></tr>`;
  return keys.map((k) => `<tr><td class="k">${esc(k)}</td><td class="v">${fmt(o[k])}</td></tr>`).join("");
}

class BmpApp extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._status = null;
    this._error = null;
    this._timer = null;
    this._booted = false;
  }

  set hass(v) {
    this._hass = v;
    if (!this._booted) { this._booted = true; this._render(); this.refresh(); }
  }
  get hass() { return this._hass; }

  connectedCallback() {
    this._timer = setInterval(() => this.refresh(), REFRESH_MS);
  }
  disconnectedCallback() {
    if (this._timer) clearInterval(this._timer);
  }

  async refresh() {
    if (!this._hass) return;
    try {
      this._status = await this._hass.callWS({ type: WS_GET_STATUS });
      this._error = null;
    } catch (e) {
      this._error = (e && e.message) || String(e);
    }
    this._renderLive();
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>${CSS}</style>
      <div class="wrap">
        <h1>Benni Media Policy</h1>
        <p class="sub">L2 Policy · rohe Debug-Maske (Step 1)</p>
        <button id="refresh">Aktualisieren</button>
        <div id="content"></div>
        <div class="foot">benni_media_policy · ${WS_GET_STATUS}</div>
      </div>`;
    this.shadowRoot.getElementById("refresh").addEventListener("click", () => this.refresh());
  }

  _renderLive() {
    const el = this.shadowRoot && this.shadowRoot.getElementById("content");
    if (!el) return;
    if (this._error) {
      el.innerHTML = `<div class="card err">Fehler: ${esc(this._error)}</div>`;
      return;
    }
    const s = this._status || {};
    el.innerHTML = `
      <div class="card">
        <h2>Meta</h2>
        <table>
          <tr><td class="k">profile</td><td class="v">${fmt(s.profile)}</td></tr>
          <tr><td class="k">profile_label</td><td class="v">${fmt(s.profile_label)}</td></tr>
          <tr><td class="k">apply_enabled</td><td class="v">${fmt(s.apply_enabled)}</td></tr>
        </table>
      </div>
      <div class="card">
        <h2>data (coordinator)</h2>
        <table>${rows(s.data)}</table>
      </div>
      <div class="card">
        <h2>bindings (Auto-Bind)</h2>
        <table>${rows(s.bindings)}</table>
      </div>`;
  }
}

if (!customElements.get("bmp-app")) {
  customElements.define("bmp-app", BmpApp);
}
