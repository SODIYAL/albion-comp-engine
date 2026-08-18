/* Loadout layer — per-member gear and spell picks.
 *
 * Inlined into index.html by build_dashboard.py AFTER the data constants and
 * BEFORE _app.js, so _app.js can call into it. Kept out of _app.js because
 * that file is rendering for the whole page already; the panel, the picker
 * and the permalink codec are a separable concern with its own state.
 *
 * DISPLAY ONLY. Gear does not reach the scoring engine — no gear capabilities
 * are curated, so scoring them would be scoring invented numbers. This layer
 * records and shows a loadout; fitness is still weapons alone.
 *
 * Reads: GEAR, ICONS, SPELLS, LOADOUTS, CONTENT, party (from _app.js).
 */

/* Fixed slot order — the codec depends on it, so never reorder without
   bumping the `g` param name. */
const LO_SLOTS = ["head", "armor", "shoes", "cape", "offhand", "potion", "food"];
const LO_SLOT_LABEL = {head: "Helm", armor: "Armor", shoes: "Boots", cape: "Cape",
                       offhand: "Off-hand", potion: "Potion", food: "Food"};
/* Spell slots the caller sheets record (q/w/passive). E is fixed per weapon. */
const LO_SPELLS = ["q", "w", "p"];
const LO_SPELL_LABEL = {q: "Q", w: "W", p: "Passive"};
const LO_SPELL_POOL = {q: "q", w: "w", p: "passive"};

/* LOADOUT[i] mirrors party[i]: {head, armor, ..., q, w, p}. Absent = unset. */
let LOADOUT = [];
/* Which member's panel is open, and which slot inside it is picking. */
let LO_OPEN = null, LO_PICKING = null, LO_FILTER = "";

const loGear = k => (typeof GEAR !== "undefined" && GEAR[k]) || null;
const loName = k => (loGear(k) || {}).name || k;

/* Items for one slot, name-sorted. Built once per slot on first use — the
   picker re-renders on every keystroke of the filter box. */
const LO_BY_SLOT = {};
function loItems(slot){
  if (!LO_BY_SLOT[slot]){
    LO_BY_SLOT[slot] = Object.keys(typeof GEAR !== "undefined" ? GEAR : {})
      .filter(k => GEAR[k].slot === slot)
      .sort((a, b) => loName(a).localeCompare(loName(b)));
  }
  return LO_BY_SLOT[slot];
}

/* ------------------------------------------------------------------ codec */
/* Dictionary encoding: every distinct gear key appears ONCE, then each member
   is a record of base36 indices into it. Indices into the GLOBAL catalogue
   would be shorter but would silently decode to the wrong item the moment an
   upstream patch inserts a helm — real keys in the dictionary keep old links
   correct. Separators are chosen to avoid `_`, which appears inside keys. */
const LO_SEP_MEMBER = "!", LO_SEP_FIELD = ".", LO_UNSET = "-";

function loadoutEncode(){
  const dict = [], at = {};
  const idx = k => (k in at) ? at[k] : (at[k] = dict.push(k) - 1);
  const recs = (party || []).map((_, i) => {
    const L = LOADOUT[i] || {};
    const fields = LO_SLOTS.map(s => (L[s] && loGear(L[s])) ? idx(L[s]).toString(36) : LO_UNSET);
    LO_SPELLS.forEach(s => fields.push(Number.isInteger(L[s]) ? L[s].toString(36) : LO_UNSET));
    return fields.join(LO_SEP_FIELD);
  });
  /* trailing empty members carry no information */
  const empty = LO_SLOTS.concat(LO_SPELLS).map(() => LO_UNSET).join(LO_SEP_FIELD);
  while (recs.length && recs[recs.length - 1] === empty) recs.pop();
  if (!recs.length) return "";
  return dict.join(",") + "~" + recs.join(LO_SEP_MEMBER);
}

function loadoutDecode(str){
  const out = [];
  if (!str) return out;
  const cut = str.indexOf("~");
  if (cut < 0) return out;
  const dict = str.slice(0, cut).split(",");
  str.slice(cut + 1).split(LO_SEP_MEMBER).forEach((rec, i) => {
    const f = rec.split(LO_SEP_FIELD), L = {};
    LO_SLOTS.forEach((s, j) => {
      if (f[j] === undefined || f[j] === LO_UNSET) return;
      const key = dict[parseInt(f[j], 36)];
      /* drop anything this build has no art for rather than render a hole */
      if (key && loGear(key)) L[s] = key;
    });
    LO_SPELLS.forEach((s, j) => {
      const v = f[LO_SLOTS.length + j];
      if (v === undefined || v === LO_UNSET) return;
      const n = parseInt(v, 36);
      if (Number.isInteger(n) && n >= 0) L[s] = n;
    });
    if (Object.keys(L).length) out[i] = L;
  });
  return out;
}

/* ------------------------------------------------------------- defaults */
/* The caller reference loadout for a weapon under the current content, if any
   caller wrote one down. This is what makes an added member start populated
   instead of blank. */
function loadoutReference(w){
  const byContent = (typeof LOADOUTS !== "undefined" && LOADOUTS[CONTENT]) || {};
  const variants = byContent[w];
  return (variants && variants.length) ? variants[0] : null;
}

function loadoutPrefill(i){
  const ref = loadoutReference(party[i]);
  if (!ref) return;
  const L = LOADOUT[i] || (LOADOUT[i] = {});
  Object.entries(ref.gear || {}).forEach(([slot, key]) => {
    if (!(slot in L) && loGear(key)) L[slot] = key;
  });
  /* caller sheets are 1-based ("q3" = third option); the pools are 0-based */
  LO_SPELLS.forEach(s => {
    if (!(s in L) && Number.isInteger(ref[s]) && ref[s] > 0) L[s] = ref[s] - 1;
  });
}

/* Keep LOADOUT aligned with party across add/remove. Called by _app.js. */
function loadoutInsert(i){ LOADOUT.splice(i, 0, undefined); loadoutPrefill(i); }
function loadoutRemove(i){
  LOADOUT.splice(i, 1);
  if (LO_OPEN === i) LO_OPEN = null;
  else if (LO_OPEN !== null && LO_OPEN > i) LO_OPEN--;
  LO_PICKING = null;
}
function loadoutClear(){ LOADOUT = []; LO_OPEN = null; LO_PICKING = null; }

/* ---------------------------------------------------------------- render */
function loTile(i, slot){
  const key = (LOADOUT[i] || {})[slot];
  const art = key && typeof ICONS !== "undefined" && ICONS[key];
  const picking = LO_PICKING && LO_PICKING.i === i && LO_PICKING.slot === slot;
  return `<button class="lo-tile${picking ? " on" : ""}${key ? " set" : ""}"
      data-lo-pick="${i}:${slot}" title="${esc(key ? loName(key) : LO_SLOT_LABEL[slot])}">
    ${art ? `<img src="${art}" width="34" height="34" alt="" loading="lazy">`
          : `<span class="lo-empty"></span>`}
    <span class="lo-tag">${esc(LO_SLOT_LABEL[slot])}</span></button>`;
}

function loSpellPicker(i, s){
  const w = party[i];
  const pool = ((typeof SPELLS !== "undefined" && SPELLS[w]) || {})[LO_SPELL_POOL[s]] || [];
  if (!pool.length) return "";
  const cur = (LOADOUT[i] || {})[s];
  const opts = pool.map(([sid, nm], j) =>
    `<option value="${j}"${j === cur ? " selected" : ""}>${esc(nm)}</option>`).join("");
  return `<label class="lo-sp"><span>${LO_SPELL_LABEL[s]}</span>
    <select data-lo-spell="${i}:${s}"><option value="">—</option>${opts}</select></label>`;
}

function loPickerGrid(){
  if (!LO_PICKING) return "";
  const {i, slot} = LO_PICKING;
  const q = LO_FILTER.trim().toLowerCase();
  const items = loItems(slot).filter(k => !q || loName(k).toLowerCase().includes(q));
  const cur = (LOADOUT[i] || {})[slot];
  const cells = items.map(k =>
    `<button class="lo-opt${k === cur ? " on" : ""}" data-lo-set="${i}:${slot}:${k}" title="${esc(loName(k))}">
      ${typeof ICONS !== "undefined" && ICONS[k]
        ? `<img src="${ICONS[k]}" width="30" height="30" alt="" loading="lazy">` : ""}
      <span>${esc(loName(k))}</span></button>`).join("");
  return `<div class="lo-picker">
    <div class="lo-picker-head">
      <input id="lo-filter" type="search" placeholder="filter ${esc(LO_SLOT_LABEL[slot])}…"
             value="${esc(LO_FILTER)}" autocomplete="off">
      <button class="lo-clear" data-lo-set="${i}:${slot}:">clear slot</button>
      <span class="lo-count">${items.length}</span>
    </div>
    <div class="lo-grid">${cells || '<span class="lo-none">nothing matches</span>'}</div></div>`;
}

/* The panel under an expanded party row. */
function loadoutPanel(i){
  if (LO_OPEN !== i) return "";
  const ref = loadoutReference(party[i]);
  const raw = ref && ref.raw ? Object.entries(ref.raw) : [];
  return `<div class="lo-panel">
    <div class="lo-row">${LO_SLOTS.map(s => loTile(i, s)).join("")}</div>
    <div class="lo-row lo-spells">${LO_SPELLS.map(s => loSpellPicker(i, s)).join("")}</div>
    ${ref ? `<div class="lo-ref">reference: ${esc(ref.caller)}${ref.role ? " · " + esc(ref.role) : ""}
      ${raw.length ? " · wrote " + raw.map(([sl, t]) =>
        `<b>${esc(LO_SLOT_LABEL[sl] || sl)}</b> “${esc(t)}”`).join(", ") : ""}</div>` : ""}
    ${loPickerGrid()}</div>`;
}

/* Click/-change routing. Returns true when it handled the event, so _app.js
   can stop looking. */
function loadoutHandleClick(e){
  const tog = e.target.closest("[data-lo-open]");
  if (tog){
    const i = +tog.dataset.loOpen;
    LO_OPEN = (LO_OPEN === i) ? null : i;
    LO_PICKING = null; LO_FILTER = "";
    if (LO_OPEN !== null) loadoutPrefill(LO_OPEN);
    return true;
  }
  const pick = e.target.closest("[data-lo-pick]");
  if (pick){
    const [i, slot] = pick.dataset.loPick.split(":");
    const same = LO_PICKING && LO_PICKING.i === +i && LO_PICKING.slot === slot;
    LO_PICKING = same ? null : {i: +i, slot};
    LO_FILTER = "";
    return true;
  }
  const set = e.target.closest("[data-lo-set]");
  if (set){
    /* key may be empty (clear) and contains no ":" itself */
    const raw = set.dataset.loSet;
    const a = raw.indexOf(":"), b = raw.indexOf(":", a + 1);
    const i = +raw.slice(0, a), slot = raw.slice(a + 1, b), key = raw.slice(b + 1);
    const L = LOADOUT[i] || (LOADOUT[i] = {});
    if (key) L[slot] = key; else delete L[slot];
    LO_PICKING = null; LO_FILTER = "";
    return true;
  }
  return false;
}

function loadoutHandleChange(e){
  const sel = e.target.closest("[data-lo-spell]");
  if (!sel) return false;
  const [i, s] = sel.dataset.loSpell.split(":");
  const L = LOADOUT[+i] || (LOADOUT[+i] = {});
  if (sel.value === "") delete L[s]; else L[s] = +sel.value;
  return true;
}

function loadoutHandleInput(e){
  if (!e.target.closest("#lo-filter")) return false;
  LO_FILTER = e.target.value;
  return true;
}

/* Count of set fields — drives the row badge so a collapsed row still shows
   that a loadout exists. */
function loadoutCount(i){
  const L = LOADOUT[i] || {};
  return LO_SLOTS.concat(LO_SPELLS).filter(k => L[k] !== undefined).length;
}
