// benni_media_policy — Volume-Matrix-Panel (Vanilla, kein Bundler/Build-Step).
// control#3: editierbare Matrix (Basis/Szenario/Activity je Tagesphase/Gerät +
// Skalare Grind/Fenster/Cap) + Diagnose-Rechenweg. Alles in Prozent/Prozent-
// punkten (intern 0.0–1.0, keine dB). Persistenz: Tabellen → Matrix-Store
// (set_matrix), Skalare → ConfigEntry-Options (set_scalars, gleiche Quelle wie
// der Options-Flow). Keine nur lokal gehaltenen Werte.

const WS_GET_STATUS = "benni_media_policy/get_status";
const WS_GET_MATRIX = "benni_media_policy/get_matrix";
const WS_SET_MATRIX = "benni_media_policy/set_matrix";
const WS_SET_SCALARS = "benni_media_policy/set_scalars";
const WS_RESET_MATRIX = "benni_media_policy/reset_matrix";
const REFRESH_MS = 4000;

// Editierbare Skalare: {conf = Options-Key (set_scalars), m = matrix.scalars-Key,
// label, mode: "level" (%) | "offset" (pp)}. conf-Namen = PANEL_SCALAR_KEYS.
const SCALAR_GROUPS = [
  { title: "Fenster (gekippt = offen; geschlossen = 0)", fields: [
    { conf: "volume_opening_offset_homepods", m: "opening_offset_homepods", label: "Fenster HomePods", mode: "offset" },
    { conf: "volume_opening_offset_denon", m: "opening_offset_denon", label: "Fenster Denon", mode: "offset" },
  ]},
  { title: "Grind", fields: [
    { conf: "grind_homepods_offset", m: "grind_homepods_offset", label: "Grind HomePods", mode: "offset" },
    { conf: "grind_denon_offset", m: "grind_denon_offset", label: "Grind Denon", mode: "offset" },
  ]},
  { title: "Private Time", fields: [
    { conf: "private_denon_cap", m: "private_denon_cap", label: "Private-Time Denon-Cap", mode: "level" },
  ]},
  { title: "Basis-Fallback & Grenzen", fields: [
    { conf: "volume_homepods_base", m: "homepods_base", label: "Basis-Fallback HomePods", mode: "level" },
    { conf: "volume_denon_base", m: "denon_base", label: "Basis-Fallback Denon", mode: "level" },
    { conf: "volume_homepods_max", m: "homepods_max", label: "Max HomePods", mode: "level" },
    { conf: "volume_denon_max", m: "denon_max", label: "Max Denon", mode: "level" },
    { conf: "volume_ducked_target", m: "ducked_target", label: "Ducking (Quiet)", mode: "level" },
    { conf: "volume_active_min", m: "active_min", label: "Aktiv-Minimum", mode: "level" },
    { conf: "volume_boost_offset", m: "boost_offset", label: "Track-Boost", mode: "offset" },
  ]},
];

const CSS = `
  :host { display:block; height:100%; background:#282a36; color:#f8f8f2;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  .wrap { padding:20px; max-width:1000px; margin:0 auto; }
  h1 { font-size:18px; margin:0 0 4px; color:#ffb86c; }
  .sub { color:#6272a4; font-size:12px; margin:0 0 16px; }
  .card { background:#1e1f29; border:1px solid #44475a; border-radius:10px;
    padding:14px 16px; margin-bottom:14px; }
  .card h2 { font-size:13px; margin:0 0 10px; color:#50fa7b; text-transform:uppercase;
    letter-spacing:.05em; }
  .card h3 { font-size:12px; margin:12px 0 6px; color:#8be9fd; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { padding:5px 8px; border-bottom:1px solid #2b2d3a; text-align:left; }
  th { color:#6272a4; font-weight:normal; }
  td.k { color:#8be9fd; white-space:nowrap; }
  .num { color:#f8f8f2; }
  .muted { color:#6272a4; }
  .warn { color:#ffb86c; } .bad { color:#ff5555; } .ok { color:#50fa7b; }
  input[type=number] { width:78px; background:#282a36; color:#f8f8f2;
    border:1px solid #44475a; border-radius:6px; padding:4px 6px; font-family:inherit; font-size:13px; }
  input:focus { outline:1px solid #bd93f9; }
  .unit { color:#6272a4; margin-left:3px; font-size:11px; }
  button { background:#44475a; color:#f8f8f2; border:0; border-radius:6px;
    padding:6px 12px; cursor:pointer; font-family:inherit; font-size:12px; margin-right:8px; }
  button:hover { background:#6272a4; }
  button.primary { background:#50fa7b; color:#282a36; }
  button.danger { background:#ff5555; color:#f8f8f2; }
  .foot { color:#6272a4; font-size:11px; margin-top:12px; }
  .err { color:#ffb86c; }
  .savedmsg { color:#50fa7b; font-size:11px; margin-left:6px; }
`;

function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
// intern 0.0–1.0 → Prozent-Zahl (1 Nachkommastelle), z.B. 0.35→35, 0.075→7.5.
function toPct(v) {
  if (v === null || v === undefined || v === "") return "";
  return Math.round(Number(v) * 1000) / 10;
}
function fromPct(str) {
  if (str === "" || str === null || str === undefined) return null;
  const n = parseFloat(str);
  if (Number.isNaN(n)) return null;
  return Math.round((n / 100) * 1000) / 1000;
}
function pctLabel(v, mode) {
  if (v === null || v === undefined || v === "") return '<span class="muted">—</span>';
  const p = toPct(v);
  return mode === "offset" ? `${p > 0 ? "+" : ""}${p}` : `${p} %`;
}

class BmpApp extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._matrix = null;
    this._status = null;
    this._error = null;
    this._timer = null;
    this._booted = false;
    this._saved = "";
  }

  set hass(v) {
    this._hass = v;
    if (!this._booted) { this._booted = true; this._render(); this.refresh(); }
  }
  get hass() { return this._hass; }

  connectedCallback() { this._timer = setInterval(() => this.refresh(), REFRESH_MS); }
  disconnectedCallback() { if (this._timer) clearInterval(this._timer); }

  async _ws(msg) { return this._hass.callWS(msg); }

  async refresh() {
    if (!this._hass) return;
    try {
      this._matrix = await this._ws({ type: WS_GET_MATRIX });
      this._status = await this._ws({ type: WS_GET_STATUS });
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
        <h1>Benni Media Policy — Volume-Matrix</h1>
        <p class="sub">Werte intern 0.0–1.0, Anzeige in Prozent / Prozentpunkten · keine dB</p>
        <div id="content"></div>
        <div class="foot">benni_media_policy · Tabellen → Matrix-Store · Skalare → ConfigEntry-Options</div>
      </div>`;
    this.shadowRoot.getElementById("content").addEventListener("click", (e) => this._onClick(e));
  }

  // ---- Diagnose (Rechenweg je Gerät) ----
  _diagCard() {
    const st = (this._status && this._status.status) || {};
    const vf = st.volume_formula || {};
    const data = (this._status && this._status.data) || {};
    const row = (label, v, mode) =>
      `<tr><td class="k">${esc(label)}</td><td class="num">${pctLabel(v, mode)}</td></tr>`;
    const dev = (name, f, target) => {
      if (!f) return "";
      const capRows = (f.cap !== undefined)
        ? row("Cap", f.cap, "level") +
          `<tr><td class="k">Cap aktiv</td><td class="num">${f.cap_active ? '<span class="warn">ja</span>' : 'nein'}</td></tr>` +
          row("Effektiv (nach Cap)", f.effective, "level")
        : "";
      return `<h3>${esc(name)} ${f.plays ? "" : '<span class="muted">(spielt nicht)</span>'}</h3>
        <table>
          ${row("Basis", f.base, "level")}
          ${row("Szenario-Offset", f.scenario_offset, "offset")}
          ${row("Fenster-Offset", f.window_offset, "offset")}
          ${row("Activity-Offset", f.activity_offset, "offset")}
          ${row("Manueller Nudge", f.manual_nudge, "offset")}
          ${row("Track-Boost", f.track_boost, "offset")}
          ${row("Zwischenwert", f.result, "level")}
          ${capRows}
          <tr><td class="k">Policy-Zielwert</td><td class="num ok">${pctLabel(target, "level")}</td></tr>
        </table>`;
    };
    const owner = data.audio_owner || "—";
    const scen = data.audio_scenario || "—";
    return `<div class="card">
      <h2>Diagnose · Rechenweg</h2>
      <table><tr><td class="k">Owner / Szenario</td><td class="num">${esc(owner)} / ${esc(scen)}</td></tr>
      <tr><td class="k">Volume-Policy</td><td class="num">${esc(data.volume_policy || "—")}</td></tr></table>
      ${dev("HomePods", vf.homepods, data.volume_target_homepods)}
      ${dev("Denon", vf.denon, data.volume_target_denon)}
      <p class="muted" style="font-size:11px;margin-top:8px;">Gesendeter/Ist-Wert am Gerät: siehe media-apply bzw. Player-Entity (modulübergreifend).</p>
    </div>`;
  }

  // ---- Skalar-Editor (→ Options via set_scalars) ----
  _scalarCard() {
    const sc = (this._matrix && this._matrix.scalars) || {};
    const group = (g) => {
      const rows = g.fields.map((f) => {
        const val = toPct(sc[f.m]);
        const unit = f.mode === "offset" ? "pp" : "%";
        return `<tr><td class="k">${esc(f.label)}</td>
          <td><input type="number" step="0.5" value="${val}"
            data-scalar="1" data-conf="${esc(f.conf)}"><span class="unit">${unit}</span></td></tr>`;
      }).join("");
      return `<h3>${esc(g.title)}</h3><table>${rows}</table>`;
    };
    return `<div class="card">
      <h2>Skalare (je Gerät getrennt)</h2>
      ${SCALAR_GROUPS.map(group).join("")}
      <div style="margin-top:10px;">
        <button class="primary" data-act="save-scalars">Skalare speichern</button>
        <span class="savedmsg">${this._saved === "scalars" ? "gespeichert ✓" : ""}</span>
      </div>
    </div>`;
  }

  // ---- Tabellen-Editor (base/scenario_off/activity_off → set_matrix) ----
  _tableCard(dim, title, rowKeys, labelFn, mode, savedTag) {
    const cat = (this._matrix && this._matrix.catalog) || {};
    const m = (this._matrix && this._matrix[dim]) || {};
    const hp = m.homepods || {}, dn = m.denon || {};
    const unit = mode === "offset" ? "pp" : "%";
    const rows = (rowKeys || []).map((key) => {
      const hv = dim === "base" ? toPct(hp[key]) : toPct(hp[key] || 0);
      const dv = dim === "base" ? toPct(dn[key]) : toPct(dn[key] || 0);
      return `<tr><td class="k">${esc(labelFn ? labelFn(key) : key)}</td>
        <td><input type="number" step="0.5" value="${hv}"
          data-dim="${dim}" data-device="homepods" data-key="${esc(key)}"><span class="unit">${unit}</span></td>
        <td><input type="number" step="0.5" value="${dv}"
          data-dim="${dim}" data-device="denon" data-key="${esc(key)}"><span class="unit">${unit}</span></td></tr>`;
    }).join("");
    return `<div class="card">
      <h2>${esc(title)}</h2>
      <table><tr><th>Zeile</th><th>HomePods</th><th>Denon</th></tr>${rows}</table>
      <div style="margin-top:10px;">
        <button class="primary" data-act="save-table" data-savedim="${dim}">Speichern</button>
        <span class="savedmsg">${this._saved === savedTag ? "gespeichert ✓" : ""}</span>
      </div>
    </div>`;
  }

  _renderLive() {
    const el = this.shadowRoot && this.shadowRoot.getElementById("content");
    if (!el) return;
    if (this._error) {
      el.innerHTML = `<div class="card err">Fehler: ${esc(this._error)}</div>`;
      return;
    }
    if (!this._matrix) { el.innerHTML = `<div class="card muted">lädt…</div>`; return; }
    const cat = this._matrix.catalog || {};
    const scLabels = cat.scenario_labels || {};
    el.innerHTML =
      this._diagCard() +
      this._scalarCard() +
      this._tableCard("base", "Basiswerte je Tagesphase", cat.dayphases, null, "level", "base") +
      this._tableCard("scenario_off", "Szenario-Offsets", cat.scenarios, (k) => scLabels[k] || k, "offset", "scenario_off") +
      this._tableCard("activity_off", "Activity-Offsets", cat.activities, null, "offset", "activity_off") +
      `<div class="card"><button class="danger" data-act="reset">Matrix-Tabellen auf Defaults zurücksetzen</button></div>`;
  }

  async _onClick(e) {
    const btn = e.target.closest("button");
    if (!btn || !this._hass) return;
    const act = btn.dataset.act;
    try {
      if (act === "save-scalars") {
        const patch = {};
        this.shadowRoot.querySelectorAll('input[data-scalar]').forEach((inp) => {
          const v = fromPct(inp.value);
          if (v !== null) patch[inp.dataset.conf] = v;
        });
        this._matrix = await this._ws({ type: WS_SET_SCALARS, patch });
        this._saved = "scalars";
      } else if (act === "save-table") {
        const dim = btn.dataset.savedim;
        const cells = { homepods: {}, denon: {} };
        this.shadowRoot.querySelectorAll(`input[data-dim="${dim}"]`).forEach((inp) => {
          const v = fromPct(inp.value);
          if (v !== null) cells[inp.dataset.device][inp.dataset.key] = v;
        });
        this._matrix = await this._ws({ type: WS_SET_MATRIX, patch: { [dim]: cells } });
        this._saved = dim;
      } else if (act === "reset") {
        this._matrix = await this._ws({ type: WS_RESET_MATRIX });
        this._saved = "";
      }
      this._error = null;
    } catch (err) {
      this._error = (err && err.message) || String(err);
    }
    this._renderLive();
    setTimeout(() => { this._saved = ""; this._renderLive(); }, 2500);
  }
}

if (!customElements.get("bmp-app")) {
  customElements.define("bmp-app", BmpApp);
}
