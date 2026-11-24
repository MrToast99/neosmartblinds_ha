/**
 * Neo Smart Blinds Card
 *
 * Room tiles for Neo Smart Blinds (Cloud): open, stop and close, the two favourite
 * positions and a "set to %" slider for a whole room, with every blind and every
 * schedule one tap deeper. Modelled on the Neo app's own room list.
 *
 * Usage:
 *   type: custom:neosmartblinds-card
 *   room: Master              # optional: a room name; leave out to list every room
 *   title: Blinds             # optional heading above the tiles
 *   show_all: true            # optional, an "All rooms" tile above the rooms
 *   show_blinds: true         # optional, expandable list of each blind in a room
 *   show_schedules: true      # optional, schedule switches inside a room
 *   start_expanded: false     # optional, open every room's details at first
 *
 * The integration serves this file and adds it to Lovelace's resources itself.
 * The card asks the integration (neosmartblinds/card_info) which entities each room
 * has, then reads live state from Home Assistant.
 */

const CARD_VERSION = "1.0.0";
const DOMAIN = "neosmartblinds";

const EN = {
  loading: "Loading…",
  notReady: "The Neo Smart Blinds integration isn't loaded.",
  noRooms: "No rooms found for this account.",
  noRoom: "No room called “{room}”.",
  allRooms: "All rooms",
  allRoomsSub: "Every room at once",
  open: "Open",
  close: "Close",
  stop: "Stop",
  favorite: "Favorite {n}",
  setPosition: "Set position",
  position: "Position",
  closed: "Closed",
  opened: "Open",
  blind: "blind",
  blinds: "blinds",
  schedule: "schedule",
  schedules: "schedules",
  noSchedules: "No schedules",
  details: "Show blinds and schedules",
  hideDetails: "Hide blinds and schedules",
  unavailable: "Unavailable",
  panelTitle: "Neo Smart Blinds",
  menu: "Menu",
  // Editor
  edType: "Room",
  edAllRooms: "All rooms",
  edTitle: "Title",
  edShowAll: "Show the “All rooms” tile",
  edShowBlinds: "Show each blind",
  edShowSchedules: "Show schedules",
  edExpanded: "Start with details open",
};

const t = (key, vars) => {
  let s = EN[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, v);
  return s;
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const plural = (n, one, many) => `${n} ${n === 1 ? t(one) : t(many)}`;

const CSS = `
  :host { display: block; }
  ha-card { overflow: hidden; }
  .wrap { container-type: inline-size; padding: 12px; display: flex; flex-direction: column; gap: 12px; }
  .title { font-size: 1.25rem; font-weight: 500; padding: 4px 4px 0; color: var(--primary-text-color); }
  .msg { padding: 24px 16px; text-align: center; color: var(--secondary-text-color); }
  .tiles { display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }
  @container (max-width: 340px) { .tiles { grid-template-columns: 1fr; } }

  .tile {
    border-radius: var(--ha-card-border-radius, 12px);
    background: var(--card-background-color);
    border: 1px solid var(--divider-color);
    overflow: hidden;
    display: flex; flex-direction: column;
  }
  .band {
    display: flex; align-items: flex-end; justify-content: space-between; gap: 8px;
    padding: 14px 14px 10px; min-height: 56px;
    background: color-mix(in srgb, var(--primary-color) 14%, var(--card-background-color));
  }
  .tile.all .band { background: color-mix(in srgb, var(--primary-color) 26%, var(--card-background-color)); }
  .name { font-size: 1.1rem; font-weight: 500; color: var(--primary-text-color); line-height: 1.2; overflow-wrap: anywhere; }
  .sub { font-size: 0.8rem; color: var(--secondary-text-color); margin-top: 2px; }
  .state { font-size: 0.85rem; color: var(--secondary-text-color); white-space: nowrap; }

  .bar { display: flex; align-items: center; gap: 2px; padding: 4px 6px; }
  .bar .grow { flex: 1; }
  button {
    font: inherit; color: var(--primary-text-color); background: none; border: 0; cursor: pointer;
    border-radius: 50%; width: 44px; height: 44px; display: inline-grid; place-items: center; padding: 0;
    position: relative; -webkit-tap-highlight-color: transparent;
  }
  button:hover { background: color-mix(in srgb, var(--primary-text-color) 8%, transparent); }
  button:focus-visible { outline: 2px solid var(--primary-color); outline-offset: -2px; }
  button[disabled] { opacity: 0.35; cursor: default; pointer-events: none; }
  button.on { background: color-mix(in srgb, var(--primary-color) 18%, transparent); color: var(--primary-color); }
  button.sm { width: 36px; height: 36px; }
  .fav ha-icon { --mdc-icon-size: 26px; }
  .fav b { position: absolute; inset: 0; display: grid; place-items: center; font-size: 0.62rem; color: var(--card-background-color); padding-top: 1px; }
  .fav.sm ha-icon { --mdc-icon-size: 22px; }
  .flash { animation: flash 0.35s ease-out; }
  @keyframes flash { 0% { background: color-mix(in srgb, var(--primary-color) 35%, transparent); } 100% { background: transparent; } }

  .pos { display: flex; align-items: center; gap: 10px; padding: 0 14px 10px; }
  .pos input[type=range] { flex: 1; min-width: 0; accent-color: var(--primary-color); height: 28px; margin: 0; }
  .pos output { width: 3.2em; text-align: right; font-variant-numeric: tabular-nums; color: var(--secondary-text-color); }

  .more { border-top: 1px solid var(--divider-color); padding: 4px 0; }
  .sec { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--secondary-text-color); padding: 8px 14px 2px; }
  .row { display: flex; align-items: center; gap: 4px; padding: 2px 8px 2px 14px; min-height: 40px; }
  .row .label { flex: 1; min-width: 0; }
  .row .label .t { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .row .label .s { font-size: 0.78rem; color: var(--secondary-text-color); }
  .blindpos { display: flex; align-items: center; gap: 8px; padding: 0 14px 6px 14px; }
  .blindpos input { flex: 1; min-width: 0; accent-color: var(--primary-color); height: 24px; margin: 0; }
  .blindpos output { width: 3.2em; text-align: right; font-size: 0.8rem; color: var(--secondary-text-color); font-variant-numeric: tabular-nums; }

  .toggle { width: 44px; height: 26px; border-radius: 13px; background: var(--disabled-color, #9e9e9e); position: relative; flex: none; }
  .toggle::after { content: ""; position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; border-radius: 50%; background: #fff; transition: transform 0.15s; }
  .toggle[aria-checked=true] { background: var(--primary-color); }
  .toggle[aria-checked=true]::after { transform: translateX(18px); }
  button.toggle { border-radius: 13px; width: 44px; height: 26px; }
  button.toggle:hover { background: var(--disabled-color, #9e9e9e); }
  button.toggle[aria-checked=true]:hover { background: var(--primary-color); }
  .unavail { opacity: 0.5; }
`;

class NeoSmartBlindsCard extends HTMLElement {
  static getStubConfig() {
    return { show_all: true, show_blinds: true, show_schedules: true };
  }

  static getConfigElement() {
    return document.createElement("neosmartblinds-card-editor");
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._info = null;
    this._error = null;
    this._loading = false;
    this._expanded = new Set();
    this._percentOpen = new Set();
    this._dragging = false;
    this._lastKey = "";
    this.shadowRoot.innerHTML = `<style>${CSS}</style><ha-card><div class="wrap" id="root"></div></ha-card>`;
    this._root = this.shadowRoot.getElementById("root");
    this.shadowRoot.addEventListener("click", (e) => this._click(e));
    this.shadowRoot.addEventListener("input", (e) => this._input(e));
    this.shadowRoot.addEventListener("change", (e) => this._change(e));
    this.shadowRoot.addEventListener("pointerdown", (e) => { if (e.target.type === "range") this._dragging = true; });
    const release = () => { this._dragging = false; };
    this.shadowRoot.addEventListener("pointerup", release);
    this.shadowRoot.addEventListener("pointercancel", release);
  }

  setConfig(config) {
    this._config = {
      show_all: true, show_blinds: true, show_schedules: true, start_expanded: false, ...config,
    };
    this._started = false;
    this._paint();
  }

  getCardSize() {
    return 3 + (this._rooms().length || 1) * 2;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  connectedCallback() {
    // Back on a dashboard after the integration was reloaded: fetch the rooms again.
    if (this._hass && this._info) this._load();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._load();
    this._paint();
  }

  async _load() {
    if (this._loading || !this._hass) return;
    this._loading = true;
    try {
      this._info = await this._hass.callWS({ type: `${DOMAIN}/card_info` });
      this._error = null;
    } catch (err) {
      this._info = null;
      this._error = err && err.code === "unknown_command" ? t("notReady") : (err && err.message) || t("notReady");
    } finally {
      this._loading = false;
      this._paint();
    }
  }

  // The rooms this card shows: one named room, or all of them.
  _rooms() {
    const all = (this._info && this._info.rooms) || [];
    const want = this._config && this._config.room;
    if (!want) return all;
    const w = String(want).toLowerCase();
    return all.filter((r) => r.id === want || r.name.toLowerCase() === w);
  }

  _state(entity) {
    return entity && this._hass ? this._hass.states[entity] : undefined;
  }

  _call(domain, service, entityIds, extra) {
    const ids = (Array.isArray(entityIds) ? entityIds : [entityIds]).filter(Boolean);
    if (!ids.length) return;
    this._hass.callService(domain, service, { entity_id: ids, ...(extra || {}) });
  }

  // "Open", "Closed", "40%" or "" for a cover.
  _coverText(entity) {
    const s = this._state(entity);
    if (!s) return t("unavailable");
    if (s.state === "unavailable") return t("unavailable");
    const pos = s.attributes.current_position;
    if (typeof pos === "number") return `${pos}%`;
    if (s.state === "open") return t("opened");
    if (s.state === "closed") return t("closed");
    return "";
  }

  _position(entity) {
    const s = this._state(entity);
    const pos = s && s.attributes.current_position;
    return typeof pos === "number" ? pos : 50;
  }

  // ---- painting ----------------------------------------------------------

  _paint() {
    if (!this._config || !this._hass) return;
    // A slider being dragged would be replaced under the finger by a repaint.
    if (this._dragging) return;
    const focused = this.shadowRoot.activeElement;
    if (focused && focused.type === "range") return; // keyboard-adjusting a slider
    const root = this._root;
    if (!this._info) {
      root.innerHTML = `<div class="msg">${esc(this._error || t("loading"))}</div>`;
      return;
    }
    const rooms = this._rooms();
    if (!rooms.length) {
      const want = this._config.room;
      root.innerHTML = `<div class="msg">${esc(want ? t("noRoom", { room: want }) : t("noRooms"))}</div>`;
      return;
    }
    if (!this._started) {
      this._started = true;
      if (this._config.start_expanded) rooms.forEach((r) => this._expanded.add(r.id));
    }

    const c = this._config;
    const parts = [];
    if (c.title) parts.push(`<div class="title">${esc(c.title)}</div>`);
    const tiles = [];
    if (c.show_all && !c.room && rooms.length > 1) tiles.push(this._allTile(rooms));
    for (const room of rooms) tiles.push(this._roomTile(room));
    parts.push(`<div class="tiles">${tiles.join("")}</div>`);

    // Skip the DOM rebuild when nothing visible changed (keeps focus and animations).
    const html = parts.join("");
    if (html === this._lastKey) return;
    this._lastKey = html;
    root.innerHTML = html;
  }

  _icon(name) {
    return `<ha-icon icon="${name}"></ha-icon>`;
  }

  _favBtn(n, ids, key, small) {
    const usable = (Array.isArray(ids) ? ids : [ids]).filter(Boolean);
    return `<button class="fav${small ? " sm" : ""}" data-act="fav" data-n="${n}" data-key="${esc(key)}" ${usable.length ? "" : "disabled"}
      title="${esc(t("favorite", { n }))}" aria-label="${esc(t("favorite", { n }))}">${this._icon("mdi:heart")}<b>${n}</b></button>`;
  }

  _controlBtns(key, small) {
    const cls = small ? "sm" : "";
    return `
      <button class="${cls}" data-act="open" data-key="${esc(key)}" title="${esc(t("open"))}" aria-label="${esc(t("open"))}">${this._icon("mdi:chevron-up")}</button>
      <button class="${cls}" data-act="stop" data-key="${esc(key)}" title="${esc(t("stop"))}" aria-label="${esc(t("stop"))}">${this._icon("mdi:stop")}</button>
      <button class="${cls}" data-act="close" data-key="${esc(key)}" title="${esc(t("close"))}" aria-label="${esc(t("close"))}">${this._icon("mdi:chevron-down")}</button>`;
  }

  _allTile(rooms) {
    const key = "all";
    const blinds = rooms.reduce((n, r) => n + r.blinds.length, 0);
    const canSet = rooms.some((r) => r.blinds.some((b) => b.has_percent));
    const open = this._percentOpen.has(key);
    return `<div class="tile all" data-tile="${key}">
      <div class="band"><div><div class="name">${esc(t("allRooms"))}</div><div class="sub">${esc(plural(blinds, "blind", "blinds"))}</div></div></div>
      <div class="bar">
        ${this._controlBtns(key)}
        ${this._favBtn(1, rooms.flatMap((r) => r.favorites.slice(0, 1)), key)}
        ${this._favBtn(2, rooms.flatMap((r) => r.favorites.slice(1, 2)), key)}
        <button class="${open ? "on" : ""}" data-act="percent" data-key="${key}" ${canSet ? "" : "disabled"}
          title="${esc(t("setPosition"))}" aria-label="${esc(t("setPosition"))}" aria-pressed="${open}">${this._icon("mdi:percent")}</button>
      </div>
      ${open ? this._slider(key, 50) : ""}
    </div>`;
  }

  _slider(key, value) {
    return `<div class="pos"><input type="range" min="1" max="99" step="1" value="${value}" data-key="${esc(key)}" aria-label="${esc(t("position"))}"><output>${value}%</output></div>`;
  }

  _roomTile(room) {
    const c = this._config;
    const key = room.id;
    const blindCount = room.blinds.length;
    const schedCount = room.schedules.length;
    const sub = `${plural(blindCount, "blind", "blinds")} | ${schedCount ? plural(schedCount, "schedule", "schedules") : t("noSchedules")}`;
    const canSet = room.blinds.some((b) => b.has_percent);
    const hasMore = (c.show_blinds && blindCount > 0) || (c.show_schedules && schedCount > 0);
    const expanded = hasMore && this._expanded.has(key);
    const percentOpen = this._percentOpen.has(key);
    const state = this._coverText(room.entity);
    const unavail = state === t("unavailable");

    // The room's cover reports no position of its own, so show the blinds' average if they all report one.
    const positions = room.blinds.map((b) => this._state(b.entity)?.attributes.current_position).filter((p) => typeof p === "number");
    const avg = positions.length && positions.length === blindCount ? Math.round(positions.reduce((a, b) => a + b, 0) / positions.length) : null;

    return `<div class="tile${unavail ? " unavail" : ""}" data-tile="${esc(key)}">
      <div class="band">
        <div><div class="name">${esc(room.name)}</div><div class="sub">${esc(sub)}</div></div>
        ${avg !== null ? `<div class="state">${avg}%</div>` : ""}
      </div>
      <div class="bar">
        ${this._controlBtns(key)}
        ${this._favBtn(1, room.favorites[0], key)}
        ${this._favBtn(2, room.favorites[1], key)}
        <button class="${percentOpen ? "on" : ""}" data-act="percent" data-key="${esc(key)}" ${canSet ? "" : "disabled"}
          title="${esc(t("setPosition"))}" aria-label="${esc(t("setPosition"))}" aria-pressed="${percentOpen}">${this._icon("mdi:percent")}</button>
        <span class="grow"></span>
        ${hasMore ? `<button data-act="expand" data-key="${esc(key)}" aria-expanded="${expanded}"
          title="${esc(expanded ? t("hideDetails") : t("details"))}" aria-label="${esc(expanded ? t("hideDetails") : t("details"))}">${this._icon(expanded ? "mdi:chevron-up" : "mdi:chevron-down")}</button>` : ""}
      </div>
      ${percentOpen ? this._slider(key, avg ?? 50) : ""}
      ${expanded ? this._moreHtml(room) : ""}
    </div>`;
  }

  _moreHtml(room) {
    const c = this._config;
    const out = [];
    if (c.show_blinds && room.blinds.length) {
      out.push(`<div class="sec">${esc(t("blinds"))}</div>`);
      for (const [i, b] of room.blinds.entries()) {
        const key = `${room.id}#${i}`;
        const pos = this._position(b.entity);
        out.push(`<div class="row">
          <div class="label"><div class="t">${esc(b.name)}</div><div class="s">${esc(this._coverText(b.entity))}</div></div>
          ${this._controlBtns(key, true)}
          ${this._favBtn(1, b.favorites[0], key, true)}
          ${this._favBtn(2, b.favorites[1], key, true)}
        </div>`);
        if (b.has_percent) {
          out.push(`<div class="blindpos"><input type="range" min="1" max="99" step="1" value="${pos}" data-key="${esc(key)}" aria-label="${esc(t("position"))}: ${esc(b.name)}"><output>${pos}%</output></div>`);
        }
      }
    }
    if (c.show_schedules && room.schedules.length) {
      out.push(`<div class="sec">${esc(t("schedules"))}</div>`);
      for (const [i, s] of room.schedules.entries()) {
        const st = this._state(s.entity);
        const on = st && st.state === "on";
        out.push(`<div class="row">
          <div class="label"><div class="t">${esc(s.name)}</div></div>
          <button class="toggle" role="switch" aria-checked="${on ? "true" : "false"}" aria-label="${esc(s.name)}"
            data-act="schedule" data-key="${esc(room.id)}" data-i="${i}" ${st ? "" : "disabled"}></button>
        </div>`);
      }
    }
    return `<div class="more">${out.join("")}</div>`;
  }

  // ---- targets -----------------------------------------------------------

  // Map a data-key to what it controls: { covers, favorites:[[...],[...]], settable }.
  _target(key) {
    const rooms = (this._info && this._info.rooms) || [];
    if (key === "all") {
      const list = this._rooms();
      return {
        covers: list.map((r) => r.entity),
        favorites: [list.map((r) => r.favorites[0]), list.map((r) => r.favorites[1])],
        settable: list.flatMap((r) => r.blinds.filter((b) => b.has_percent).map((b) => b.entity)),
      };
    }
    const [roomId, idx] = key.split("#");
    const room = rooms.find((r) => r.id === roomId);
    if (!room) return null;
    if (idx === undefined) {
      return {
        covers: [room.entity],
        favorites: [[room.favorites[0]], [room.favorites[1]]],
        settable: room.blinds.filter((b) => b.has_percent).map((b) => b.entity),
        room,
      };
    }
    const b = room.blinds[Number(idx)];
    if (!b) return null;
    return {
      covers: [b.entity],
      favorites: [[b.favorites[0]], [b.favorites[1]]],
      settable: b.has_percent ? [b.entity] : [],
      room,
    };
  }

  // ---- events ------------------------------------------------------------

  _click(e) {
    const el = e.target.closest("[data-act]");
    if (!el || el.disabled) return;
    const act = el.dataset.act;
    const key = el.dataset.key;

    if (act === "expand") {
      this._expanded.has(key) ? this._expanded.delete(key) : this._expanded.add(key);
      this._lastKey = "";
      this._paint();
      return;
    }
    if (act === "percent") {
      this._percentOpen.has(key) ? this._percentOpen.delete(key) : this._percentOpen.add(key);
      this._lastKey = "";
      this._paint();
      return;
    }
    if (act === "schedule") {
      const room = ((this._info && this._info.rooms) || []).find((r) => r.id === key);
      const sched = room && room.schedules[Number(el.dataset.i)];
      if (sched) {
        const on = el.getAttribute("aria-checked") === "true";
        this._call("switch", on ? "turn_off" : "turn_on", sched.entity);
      }
      return;
    }

    const target = this._target(key);
    if (!target) return;
    el.classList.remove("flash");
    void el.offsetWidth; // restart the feedback animation
    el.classList.add("flash");
    if (act === "open") this._call("cover", "open_cover", target.covers);
    else if (act === "close") this._call("cover", "close_cover", target.covers);
    else if (act === "stop") this._call("cover", "stop_cover", target.covers);
    else if (act === "fav") this._call("button", "press", target.favorites[Number(el.dataset.n) - 1]);
  }

  // Live value next to a slider while it moves.
  _input(e) {
    const input = e.target;
    if (input.type !== "range") return;
    const out = input.parentElement.querySelector("output");
    if (out) out.textContent = `${input.value}%`;
  }

  // Send the position once the slider is let go.
  _change(e) {
    const input = e.target;
    if (input.type !== "range") return;
    this._dragging = false;
    const target = this._target(input.dataset.key);
    if (target) this._call("cover", "set_cover_position", target.settable, { position: Number(input.value) });
  }
}

// ---- editor ---------------------------------------------------------------

class NeoSmartBlindsCardEditor extends HTMLElement {
  constructor() {
    super();
    this._rooms = [];
    this._loaded = false;
  }

  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._loaded) {
      this._loaded = true;
      hass.callWS({ type: `${DOMAIN}/card_info` }).then((info) => {
        this._rooms = (info && info.rooms) || [];
        this._render();
      }).catch(() => {});
    }
    if (this._form) this._form.hass = hass;
  }

  _schema() {
    const options = [{ value: "", label: t("edAllRooms") }, ...this._rooms.map((r) => ({ value: r.name, label: r.name }))];
    return [
      { name: "room", label: t("edType"), selector: { select: { options, mode: "dropdown" } } },
      { name: "title", label: t("edTitle"), selector: { text: {} } },
      { name: "show_all", label: t("edShowAll"), selector: { boolean: {} } },
      { name: "show_blinds", label: t("edShowBlinds"), selector: { boolean: {} } },
      { name: "show_schedules", label: t("edShowSchedules"), selector: { boolean: {} } },
      { name: "start_expanded", label: t("edExpanded"), selector: { boolean: {} } },
    ];
  }

  _render() {
    if (!this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => s.label || s.name;
      this._form.addEventListener("value-changed", (ev) => {
        const value = { ...ev.detail.value };
        if (!value.room) delete value.room;
        if (!value.title) delete value.title;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: value }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    if (this._hass) this._form.hass = this._hass;
    this._form.schema = this._schema();
    this._form.data = {
      room: "", show_all: true, show_blinds: true, show_schedules: true, start_expanded: false, ...this._config,
    };
  }
}

// ---- sidebar page -----------------------------------------------------------

const PANEL_CSS = `
  :host { display: block; min-height: 100vh; min-height: 100dvh; box-sizing: border-box;
    background: var(--lovelace-background, var(--primary-background-color)); color: var(--primary-text-color); }
  header { display: flex; align-items: center; gap: 4px; min-height: 56px; box-sizing: border-box;
    padding: 0 16px 0 calc(env(safe-area-inset-left, 0px) + 16px); padding-top: env(safe-area-inset-top, 0px);
    background: var(--app-header-background-color, var(--primary-color)); color: var(--app-header-text-color, #fff); }
  header .title { font-size: 1.25rem; font-weight: 400; }
  header .menu { background: none; border: 0; color: inherit; width: 44px; height: 44px; margin-left: -12px; border-radius: 50%; cursor: pointer; display: grid; place-items: center; }
  header .menu:focus-visible { outline: 2px solid currentColor; }
  main { max-width: 1200px; margin: 0 auto;
    padding: 16px calc(env(safe-area-inset-right, 0px) + 16px) calc(env(safe-area-inset-bottom, 0px) + 16px) calc(env(safe-area-inset-left, 0px) + 16px); }
  @media (max-width: 600px) { main { padding: 8px calc(env(safe-area-inset-right, 0px) + 8px) calc(env(safe-area-inset-bottom, 0px) + 8px) calc(env(safe-area-inset-left, 0px) + 8px); } }
`;

// The sidebar page (see sidebar.py): the card with every room, under a header with the menu button.
class NeoSmartBlindsPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._narrow = false;
    this.shadowRoot.innerHTML = `<style>${PANEL_CSS}</style><header id="head"></header><main id="main"></main>`;
    this._head = this.shadowRoot.getElementById("head");
    this._card = document.createElement("neosmartblinds-card");
    this._card.setConfig({ show_all: true, show_blinds: true, show_schedules: true });
    this.shadowRoot.getElementById("main").appendChild(this._card);
    this.shadowRoot.addEventListener("click", (e) => {
      if (e.target.closest("[data-act=menu]")) {
        this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
      }
    });
    this._paintHead();
  }

  set hass(hass) {
    this._hass = hass;
    this._card.hass = hass;
  }

  set narrow(narrow) {
    this._narrow = !!narrow;
    this._paintHead();
  }

  set panel(_panel) { /* no configuration */ }
  set route(_route) { /* a single page */ }

  _paintHead() {
    this._head.innerHTML = `${this._narrow ? `<button class="menu" data-act="menu" title="${esc(t("menu"))}" aria-label="${esc(t("menu"))}"><ha-icon icon="mdi:menu"></ha-icon></button>` : ""}
      <div class="title">${esc(t("panelTitle"))}</div>`;
  }
}

if (!customElements.get("neosmartblinds-card")) customElements.define("neosmartblinds-card", NeoSmartBlindsCard);
if (!customElements.get("neosmartblinds-panel")) customElements.define("neosmartblinds-panel", NeoSmartBlindsPanel);
if (!customElements.get("neosmartblinds-card-editor")) customElements.define("neosmartblinds-card-editor", NeoSmartBlindsCardEditor);

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "neosmartblinds-card")) {
  window.customCards.push({
    type: "neosmartblinds-card",
    name: "Neo Smart Blinds",
    description: "Room tiles with open, stop, close, favorites and a position slider, plus each blind and schedule.",
    preview: false,
    documentationURL: "https://github.com/MrToast99/NeoSmartBlinds_HA",
  });
}
console.info(`%c NEOSMARTBLINDS-CARD %c ${CARD_VERSION} `, "color:#fff;background:#1c7ed6;font-weight:700", "color:#1c7ed6");
