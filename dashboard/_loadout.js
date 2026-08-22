/* Loadout layer — per-member gear and spell picks.
 *
 * Inlined into index.html by build_dashboard.py AFTER the data constants and
 * BEFORE _app.js, so _app.js can call into it. Kept out of _app.js because
 * that file is rendering for the whole page already; the panel, the picker
 * and the permalink codec are a separable concern with its own state.
 *
 * Display layer. Since 2026-08-20 gear IS curated and scored engine-side
 * (dataset `gear`, engine build_extra/kit_options) — this panel's picks are
 * not yet wired into the browser scoring calls; that wiring is the next
 * step, and until then fitness shown here is weapons alone.
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
/* equipment ability tooltip (2026-08-19): the item's actives/passives from
   the game's own craftingspelllist (parse_dumps gear_spells.json) */
function loAbilityTip(k){
  const g = (typeof GEAR_SPELLS !== "undefined" && GEAR_SPELLS[k]) || null;
  if (!g) return "";
  const names = arr => (arr || []).map(x => x[1]).join(" / ");
  const bits = [];
  if (g.a && g.a.length) bits.push("actives: " + names(g.a));
  if (g.p && g.p.length) bits.push("passives: " + names(g.p));
  return bits.length ? " — " + bits.join(" · ") : "";
}

/* Gear art is HOTLINKED, not embedded — it is ~270 of the ~400 icons and
   embedding it cost the page ~1.1 MB for a picker most sessions never open.
   Weapon art stays inlined in ICONS (on screen from the first paint, and has
   to survive file:// and offline). If ICONS happens to carry a gear key it
   wins, so nothing breaks if that policy is reverted.

   RETRY, don't remove (2026-08-20): opening a picker fires ~18 concurrent
   render-service requests and the service drops some under burst — every
   URL verified 200 individually. `onerror` used to delete the img
   permanently on the FIRST failure, which is why half the picker showed no
   art. Now it backs off and retries (0.4s/0.8s/1.6s) and only gives up
   after the third miss. */
function loArtRetry(img){
  const n = +(img.dataset.r || 0);
  if (n >= 3){ img.remove(); return; }
  img.dataset.r = n + 1;
  const src = img.src;
  img.removeAttribute("src");
  setTimeout(() => { img.src = src; }, 400 * Math.pow(2, n));
}
function loArt(key, px){
  if (typeof ICONS !== "undefined" && ICONS[key])
    return `<img src="${ICONS[key]}" width="${px}" height="${px}" alt="" loading="lazy">`;
  const item = (loGear(key) || {}).example_item;
  if (!item) return "";
  const base = (typeof RENDER_BASE !== "undefined") ? RENDER_BASE
                                                    : "https://render.albiononline.com/v1";
  return `<img src="${base}/item/${encodeURIComponent(item)}.png?size=96"
    width="${px}" height="${px}" alt="" loading="lazy" onerror="loArtRetry(this)">`;
}

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
      /* drop anything this build's catalogue does not know, rather than
         carry a key nothing can name or draw */
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
/* Displayed-build selection (changeschapter2.md §F). The index arrives
   pre-ordered by approval / patch freshness / confidence and flags canonical
   defaults with their promotion basis; at runtime we additionally require a
   matching party-size range and prefer exact-content records over explicit
   content fallbacks. NEVER variants[0] of arrival order, and a fallback is
   always visible on the returned record (fallback_from / size_fallback). */
function loadoutVariantsFor(w, ct){
  /* exact-content records first, then records whose broad content tag covers
     this template (LOADOUT_COVERS, e.g. large_scale_zvz -> castle) — each of
     those carries fallback_from so the UI can say so (§F) */
  const all = (typeof LOADOUTS !== "undefined") ? LOADOUTS : {};
  const out = (((all[ct]) || {})[w] || []).slice();
  const covers = (typeof LOADOUT_COVERS !== "undefined") ? LOADOUT_COVERS : {};
  for (const broad of Object.keys(covers)){
    if (!covers[broad].includes(ct)) continue;
    ((all[broad] || {})[w] || []).forEach(v => out.push(Object.assign({}, v, {
      fallback_from: broad,
      canonical: false,
      canonical_for_fallback: !!v.canonical,
      canonical_basis: undefined,
    })));
  }
  return out;
}

function loadoutSelect(w, ct, size){
  const variants = loadoutVariantsFor(w, ct);
  const fits = v => !v.party_size ||
    (size >= v.party_size.min && size <= v.party_size.max);
  const pick =
    variants.find(v => v.canonical && fits(v)) ||
    variants.find(v => (v.canonical || v.canonical_for_fallback) && fits(v)) ||
    variants.find(v => v.canonical || v.canonical_for_fallback) ||
    null;
  if (!pick) return null;
  return Object.assign({}, pick, {size_fallback: !fits(pick)});
}

/* The canonical reference build for a weapon under the current content, if
   the evidence layer promoted one. This is what makes an added member start
   populated instead of blank — candidates that never cleared the promotion
   gate are shown in the drawer but never drive the default kit. */
function loadoutReference(w){
  const size = (typeof SIZE !== "undefined") ? SIZE : 20;
  return loadoutSelect(w, (typeof CONTENT !== "undefined") ? CONTENT : "", size);
}

function loadoutPrefill(i){
  const ref = loadoutReference(party[i]);
  const L = LOADOUT[i] || (LOADOUT[i] = {});
  if (ref){
    Object.entries(ref.gear || {}).forEach(([slot, key]) => {
      if (!(slot in L) && loGear(key)) L[slot] = key;
    });
    /* caller sheets are 1-based ("q3" = third option); the pools are 0-based */
    LO_SPELLS.forEach(s => {
      if (!(s in L) && Number.isInteger(ref[s]) && ref[s] > 0) L[s] = ref[s] - 1;
    });
  }
  /* engine fallback (owner 2026-08-21): whatever no promoted caller build
     covers is filled by the engine — spells from the scored combo, gear
     from the comp-aware kit advisor. The kit wears the engine mark so it
     can never be mistaken for a fielded build. */
  loadoutEngineSpells(i);
  loadoutEngineGear(i);
}

/* On-open retro suggestion (owner 2026-08-21: "weapons should come with
   suggested kits" — including members added before the feature or loaded
   from share links). SAFE variant: merely looking at a kit must never
   change the party's fitness, so ref SPELLS are not applied here (a
   caller's picks could differ from the member's scored combo) — spells
   seed from the member's OWN combo and gear picks are display-only. */
function loadoutSuggest(i){
  loadoutPrefillGear(i);
  loadoutEngineSpells(i);
  loadoutEngineGear(i);
}

/* the combo the engine actually scores for member i (null -> default) */
function loComboOf(i){
  return (typeof COMBO !== "undefined" && Number.isInteger(COMBO[i]))
    ? COMBO[i] : null;
}

function loadoutEngineSpells(i){
  const w = party[i];
  if (typeof ENG === "undefined" || !ENG.comboSpells) return;
  const pools = (typeof SPELLS !== "undefined" && SPELLS[w]) || {};
  const L = LOADOUT[i] || (LOADOUT[i] = {});
  let used = false;
  for (const [slot, sid] of ENG.comboSpells(w, loComboOf(i))){
    const s = slot === "passive" ? "p" : slot;   /* pool name -> loadout key */
    if (!LO_SPELLS.includes(s) || s in L) continue;
    const pool = pools[slot] || [];
    for (let j = 0; j < pool.length; j++)
      if (pool[j][0] === sid){ L[s] = j; used = true; break; }
  }
  /* _eng is display provenance only: the permalink codec walks the fixed
     slot lists, so the mark never enters a share link */
  if (used) L._eng = 1;
}

function loadoutEngineGear(i){
  /* comp-aware kit advisor (engine kit_options; JS mirror parity-checked
     2026-08-21): each empty gear slot gets the top-ranked item for THIS
     member in THIS comp. Display-only — gear picks do not feed browser
     scoring yet. */
  const w = party[i];
  if (typeof ENG === "undefined" || !ENG.kitOptions) return;
  const L = LOADOUT[i] || (LOADOUT[i] = {});
  const empty = LO_SLOTS.filter(s => !(s in L)
    && !(s === "offhand" && w.startsWith("2H_")));  /* 2H hands are full */
  if (!empty.length) return;
  let ko;
  try {
    ko = ENG.kitOptions(w, loComboOf(i), party.filter((_, j) => j !== i));
  } catch (e) { return; }
  let used = false;
  empty.forEach(s => {
    const top = (ko.kit || {})[s];
    if (top && loGear(top.gear)){ L[s] = top.gear; used = true; }
  });
  if (used) L._eng = 1;
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
  const art = key ? loArt(key, 34) : "";
  const picking = LO_PICKING && LO_PICKING.i === i && LO_PICKING.slot === slot;
  return `<button class="lo-tile${picking ? " on" : ""}${key ? " set" : ""}"
      data-lo-pick="${i}:${slot}" title="${esc(key ? loName(key) + loAbilityTip(key) : LO_SLOT_LABEL[slot])}">
    ${art || `<span class="lo-empty"></span>`}
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
    `<button class="lo-opt${k === cur ? " on" : ""}" data-lo-set="${i}:${slot}:${k}" title="${esc(loName(k) + loAbilityTip(k))}">
      ${loArt(k, 30)}
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
    ${(LOADOUT[i] || {})._eng ? `<div class="lo-ref lo-eng" title="spell and gear picks are the engine's scored suggestions for this content and comp — change anything to make the kit your own">&#9881; engine kit — scored for this comp, not a fielded build</div>` : ""}
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
    /* Opening a kit fills any empty slots with SAFE suggestions (owner
       2026-08-21): ref gear + engine gear (display-only) + spells from
       the member's OWN scored combo — so looking at a kit still never
       changes the party's fitness (review 2026-08-18 holds). Caller-ref
       SPELL prefill stays add/forge-time only, where it is announced. */
    if (LO_OPEN !== null) loadoutSuggest(LO_OPEN);
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
    delete L._eng;   /* a hand-picked item makes the kit the player's own */
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
  delete L._eng;   /* a hand-picked spell makes the kit the player's own */
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

/* --------------------------------------------------- provenance codec
   Slot provenance (2026-08-18): 'm' = manual / live-party, 'f' = forged.
   Encoded into the permalink as a plain m/f string (`f=` param) so "reforge
   all" knows which slots the engine owns even across a shared link; links
   from before this feature decode to all-manual, which only means the first
   reforge won't rebuild them — never a wrong comp. Trailing 'm's are
   trimmed like the loadout codec trims empty members. */
function provEncode(prov, n){
  let s = "";
  for (let i = 0; i < n; i++) s += prov[i] === "f" ? "f" : "m";
  s = s.replace(/m+$/, "");
  return s;
}
function provDecode(str, n){
  const out = [];
  for (let i = 0; i < n; i++)
    out.push(str && str[i] === "f" ? "f" : "m");
  return out;
}

/* -------------------------------------------- spell picks <-> engine combos
   The bridge that makes the player's REAL Q/W/passive picks reach scoring
   (2026-08-18): picks map to the engine's curated loadout bundles via
   spell ids; slots without a curated pick fall back to the engine's default
   resolution. Gear stays display-only — no gear capabilities are curated. */

/* {engine slot name -> picked spell id} for member i, or null when the
   member has no spell picks at all. */
function loadoutPicks(i){
  const L = LOADOUT[i] || {};
  const pools = ((typeof SPELLS !== "undefined" && SPELLS[party[i]]) || {});
  const picks = {};
  let any = false;
  LO_SPELLS.forEach(s => {
    const idx = L[s];
    const pool = pools[LO_SPELL_POOL[s]] || [];
    if (Number.isInteger(idx) && pool[idx]){
      picks[LO_SPELL_POOL[s]] = pool[idx][0];
      any = true;
    }
  });
  return any ? picks : null;
}

/* Write a forged combo's spell choices back into the member's pickers, so
   the kit the user sees IS the kit the forge scored. E-slot use-variants
   have no picker (E is fixed per weapon) and are carried by the member's
   stored combo instead. */
function loadoutApplySpells(i, combo){
  if (combo === null || combo === undefined) return;
  const w = party[i];
  const pools = (typeof SPELLS !== "undefined" && SPELLS[w]) || {};
  const L = LOADOUT[i] || (LOADOUT[i] = {});
  (ENG.comboSpells(w, combo) || []).forEach(([slotName, sid]) => {
    const s = slotName === "passive" ? "p" : slotName;
    if (LO_SPELLS.indexOf(s) === -1) return;   // E is fixed, not a picker
    const pool = pools[slotName] || [];
    for (let j = 0; j < pool.length; j++){
      if (pool[j][0] === sid){ L[s] = j; break; }
    }
  });
}

/* Gear-only half of the caller-reference prefill — forged slots take their
   SPELLS from the scored combo, not the reference. */
function loadoutPrefillGear(i){
  const ref = loadoutReference(party[i]);
  if (!ref) return;
  const L = LOADOUT[i] || (LOADOUT[i] = {});
  Object.entries(ref.gear || {}).forEach(([slot, key]) => {
    if (!(slot in L) && loGear(key)) L[slot] = key;
  });
}

/* ------------------------------------------------------ combo permalink
   Explicit member combos (forge results — e.g. an E-slot use variant no
   picker can express) travel in the permalink `k=` param, base36 per
   member, `-` = none (review 2026-08-18: without this a forged E-variant
   silently reverted to the default bundle on reload, changing the score).
   Combo indexes are dataset-stable (product order over the weapon's
   loadout slots), not context-dependent, so they persist safely. */
function comboEncode(combo, n){
  const fields = [];
  for (let i = 0; i < n; i++){
    const c = combo[i];
    fields.push(Number.isInteger(c) && c >= 0 ? c.toString(36) : LO_UNSET);
  }
  while (fields.length && fields[fields.length - 1] === LO_UNSET) fields.pop();
  return fields.join(LO_SEP_FIELD);
}
function comboDecode(str, n){
  const out = [];
  const f = String(str || "").split(LO_SEP_FIELD);
  for (let i = 0; i < n; i++){
    const v = f[i];
    if (v === undefined || v === LO_UNSET){ out.push(null); continue; }
    const c = parseInt(v, 36);
    out.push(Number.isInteger(c) && c >= 0 ? c : null);
  }
  return out;
}
