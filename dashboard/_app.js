"use strict";
/* Dashboard client. Reads the injected DATASET — the same
   pipeline/out/dataset-latest.json that engine/engine.py consumes. No
   capability numbers live in this file, and no scoring math either: the
   engine is engine/app_scoring.js (inlined by the build just before this
   file), the SAME code node runs in tests/test_js_parity.py. Regenerate:
       py -3 dashboard/build.py                                              */

const META = DATASET._meta;
const WEAPONS = DATASET.weapons;

let CONTENT = Object.keys(DATASET.templates)[0];
const ENG = new CompEngine(DATASET, CONTENT);
/* There is no fixed party size in open-world content, and attendance is
   FLUID (owner ruling 2026-08-21): the party is judged at the ROSTER you
   actually have — targets, floors and scaling follow whoever showed up.
   PLANNED is what you expect to field: it drives how many slots the forge
   fills and the cap warnings, never the judgment. Next-pick advice runs
   ONE AHEAD (roster+1), so a threshold that arms at the next body — the
   roads heal floor at 5 — is anticipated while you are choosing, not
   after the 5th DPS already joined. */
let PLANNED = ENG.size;
let SIZE = PLANNED;
let STYLE = "balanced";
const HARD_CAP = 60;
const STYLE_ORDER = ["balanced", "brawl", "clap", "kite", "brawl_clap", "clap_kite"];

const PLAN = () => Math.max(PLANNED, party.length);
const pickSize = () => Math.min(Math.max(party.length + 1, 1), HARD_CAP);
/* run fn under the ONE-AHEAD context (candidate evaluation), then restore
   the roster-judged context — every board number stays roster-sized */
function inPickContext(fn){
  ENG.setContent(CONTENT, pickSize(), STYLE);
  try { return fn(); } finally { ENG.setContent(CONTENT, SIZE, STYLE); }
}

function syncEngine(){
  SIZE = Math.max(party.length, 1);
  ENG.setContent(CONTENT, SIZE, STYLE);
  /* member combos re-resolve after every context change: the default
     loadout depends on the styled weights, and pick-derived combos map
     through the current engine (2026-08-18) */
  COMBOS_CUR = party.map((_, i) => comboAt(i));
  /* equipped gear reaches scoring (dressed forge Task 1, 2026-08-27):
     the engine has scored full builds since the 2026-08-20 gear layer —
     the page's fitness call just never passed them. Gear edits re-render,
     and render() lands here, so this stays fresh. */
  GEARS_CUR = party.map((_, i) =>
    gearsFromLoadout(typeof LOADOUT !== "undefined" ? LOADOUT[i] : null));
}
/* LOADOUT entry -> engine gears list: CURATED pieces only (uncurated
   picker items carry no capabilities and would churn the cache key),
   fixed slot order, null when nothing curated is equipped. `gearDb`
   is injectable for the node test; the page uses the engine's curated
   catalog. */
function gearsFromLoadout(lo, gearDb){
  const db = gearDb || ENG.gear;
  if (!lo) return null;
  const out = [];
  const slots = ["head", "armor", "shoes", "cape", "offhand", "potion", "food"];
  for (let i = 0; i < slots.length; i++)
    if (lo[slots[i]] && db[lo[slots[i]]]) out.push(lo[slots[i]]);
  return out.length ? out : null;
}
/* The loadout combo actually scored for member i: an explicit stored combo
   (a forge result) wins; otherwise the member's real Q/W/passive picks map
   to curated bundles; otherwise null = the engine's static default. */
function comboAt(i){
  if (COMBO[i] !== undefined && COMBO[i] !== null) return COMBO[i];
  const picks = loadoutPicks(i);
  return picks ? ENG.comboFromPicks(party[i], picks) : null;
}

const tpl = () => DATASET.templates[CONTENT];
const REQS = () => tpl().requirements;
const FLOORS = () => tpl().hard_floors || {};
const baseSize = () => tpl().base_size || 7;
const validatedSizes = () => tpl().validated_sizes || [baseSize()];

const target = cap => ENG.target(cap);
const softCap = cap => ENG.softCap(cap);
/* EFFECTIVE supply (after the mechanics multipliers) — the numbers scoring
   actually uses. Displaying raw sheet units next to effective-supply gap
   scores let a bar read "met" while the weakness list still charged a gap
   for the same capability (review 2026-08-15). Raw sheet numbers stay
   visible per-weapon in the detail drawer. */
/* Every scoring call for THE party passes the members' resolved combos
   (COMBOS_CUR) — the user's spell picks and forged loadouts reach the
   engine; ad-hoc parties (contribution what-ifs) pass their own slices. */
const supply = p => p === party ? partyCalc().sup : ENG.effectiveSupply(p);
const fitness = p => p === party ? partyCalc().fit : ENG.fitness(p);
const maxFitness = () => ENG.maxFitness();
const uncoveredCaps = p => ENG.uncoveredCaps(p, p === party ? COMBOS_CUR : null);
const weaknesses = (p, n = 3) => ENG.weaknesses(p, n, p === party ? COMBOS_CUR : null);
/* app_scoring.js term/rec field names -> the short ones this file renders */
const explain = (p, cand) => inPickContext(() =>
  ENG.explain(p, cand, p === party ? COMBOS_CUR : null,
              p === party ? GEARS_CUR : null))
  .map(t => ({d: t.delta, ...t}));
/* every candidate surface prices picks against the party AS EQUIPPED
   (dressed forge 2026-08-27): the loaded comp's gear reaches the same
   _evalPick the score uses, and each suggestion carries the kit its
   marginal assumed */
const recommend = (p, n = 4) => inPickContext(() =>
  ENG.recommend(p, n, null, p === party ? COMBOS_CUR : null,
                p === party ? GEARS_CUR : null))
  .map(r => ({w: r.weapon, dFit: r.d_fitness, dSyn: r.d_synergy, meta: r.meta_prior,
              viab: r.viability, combo: r.combo, kit: r.kit, score: r.score,
              verdict: r.verdict, capsGain: r.caps_gain}));
/* Signed pick decomposition (engine pickReport): the "why not" behind a
   pick — saturated caps, over-stack costs, duplicate penalty, count-once
   spell losses. Descriptive engine output; this file only renders it. */
const pickReport = (p, cand) => inPickContext(() =>
  ENG.pickReport(p, cand, p === party ? COMBOS_CUR : null,
                 p === party ? GEARS_CUR : null));
/* swapReview is a full-pool sweep per member (~40-100ms at 20-40 members) —
   memoized on the engine context + party + loadouts so facet clicks,
   companion polls and other no-op re-renders don't pay it again. */
const comboSig = () => COMBOS_CUR.join(",");
const gearSig = () => GEARS_CUR.map(g => g ? g.join("+") : "-").join(",");
let swapCache = { key: null, val: [] };
function swapReviewCached(){
  const key = `${CONTENT}|${SIZE}|${STYLE}|${party.join(",")}|${comboSig()}|${gearSig()}`;
  if (swapCache.key !== key)
    swapCache = { key, val: party.length > 1
      ? ENG.swapReview(party, 3, null, COMBOS_CUR, GEARS_CUR) : [] };
  return swapCache.val;
}

/* fitness + effective supply for the CURRENT party, computed once per state
   (renderers used to re-derive them 3-4x per render pass). supFloor is the
   WEAPON+LOADOUT supply — the basis Option C hard floors read (owner ruling
   2026-08-27): floor tags must quote it or display would disagree with
   scoring. */
let calcCache = { key: null, fit: 0, sup: null, supFloor: null };
function partyCalc(){
  const key = `${CONTENT}|${SIZE}|${STYLE}|${party.join(",")}|${comboSig()}|${gearSig()}`;
  if (calcCache.key !== key)
    calcCache = { key, fit: ENG.fitness(party, COMBOS_CUR, GEARS_CUR),
                  sup: ENG.effectiveSupply(party, COMBOS_CUR, GEARS_CUR),
                  supFloor: ENG.effectiveSupply(party, COMBOS_CUR) };
  return calcCache;
}
/* ad-hoc parties are naked, so their dressed and floor supplies coincide */
const supplyFloor = p => p === party ? partyCalc().supFloor : ENG.effectiveSupply(p);

const capsOf = w => WEAPONS[w].capabilities || {};
/* one home for the role-hint default and the below-floor predicate — the
   latter delegates to the engine so display can never disagree with scoring */
const roleHint = w => WEAPONS[w].role_hint || "other";
/* roster role order — tanks first, then supports, damage (melee, range),
   healers: the order real caller sheets read in (Timothy's blap, the
   Deadlyhooker parties). The roster is ALWAYS kept in this order: every
   path that changes its membership (add, swap, forge, companion load,
   permalink load) runs sortPartyByRole(). */
const ROLE_SORT = { tank: 0, support: 1, melee: 2, range: 3, healer: 4 };
function sortPartyByRole(){
  /* One stable permutation over ALL parallel slot state — party, forged/
     manual provenance, stored combos, loadouts — plus every live index
     that points at a slot (open kit panel, gear picker, forge-note
     filler/held). Scoring, permalinks and codecs are order-independent,
     so only the presentation moves. Stable within a role: equal-role
     members keep their relative order, so re-sorting a sorted roster is a
     no-op and members never shuffle gratuitously. */
  const order = party.map((_, i) => i).sort((a, b) => {
    const ra = ROLE_SORT[roleHint(party[a])];
    const rb = ROLE_SORT[roleHint(party[b])];
    return (ra === undefined ? 9 : ra) - (rb === undefined ? 9 : rb)
           || a - b;
  });
  if (order.every((v, i) => v === i)) return;   /* already in role order */
  party = order.map(i => party[i]);
  PROV = order.map(i => PROV[i]);
  COMBO = order.map(i => COMBO[i]);
  LOADOUT = order.map(i => LOADOUT[i]);
  if (LO_OPEN !== null) LO_OPEN = order.indexOf(LO_OPEN);
  if (LO_PICKING) LO_PICKING.i = order.indexOf(LO_PICKING.i);
  if (FORGE_NOTE){
    const remap = idxs => (idxs || []).map(x => order.indexOf(x))
      .sort((a, b) => a - b);
    FORGE_NOTE = { feasible: FORGE_NOTE.feasible,
                   filler: remap(FORGE_NOTE.filler),
                   held: remap(FORGE_NOTE.held) };
  }
}
const floorHit = (cap, have) => ENG.floorArmed(cap, have);
function roleCounts(){
  const counts = {};
  party.forEach(w => { const r = roleHint(w); counts[r] = (counts[r]||0) + 1; });
  return counts;
}
const styleName = () =>
  STYLE !== "balanced" ? (DATASET.styles[STYLE] || {}).name || STYLE : "";
/* Display names and evidence IDs originate in ao-bin-dumps (an external game-data
   repo), so they are escaped before ever reaching innerHTML. */
const esc = s => String(s).replace(/[&<>"']/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const nameOf = w => esc(WEAPONS[w].display_name || w);
/* In-game item renders (fetch_icons.py manifest, © Sandbox Interactive).
   Missing entries — e.g. Black Hands, absent from the render service — get
   a quiet placeholder square. */
const icon = (w, s) => (typeof ICONS !== "undefined" && ICONS[w])
  ? `<img class="icon" src="${ICONS[w]}" width="${s}" height="${s}" alt="" loading="lazy">`
  : `<span class="icon ph" style="width:${s}px;height:${s}px"></span>`;

const ROLE_LABELS = {
  tank: "Tank", melee: "Melee", range: "Ranged",
  healer: "Healer", support: "Support",
};
const roleLabel = r => ROLE_LABELS[r] || r.replace(/_/g, " ");
/* Generated role/effect art is injected by dashboard/build.py beside the
   weapon icon manifest. Empty fallback is intentional: every icon-only
   control also carries an accessible text name, and the builder fails early
   if one of the committed assets is missing. */
function semanticIcon(key, extraClass = ""){
  const src = (typeof SEMANTIC_ICONS !== "undefined" && SEMANTIC_ICONS[key]) || "";
  return src
    ? `<img class="sem-icon${extraClass ? " " + extraClass : ""}" src="${src}"
         alt="" aria-hidden="true" draggable="false">`
    : "";
}

const GROUPS = {
  Sustain:   ["heal_burst","heal_sustain","cleanse","self_sustain"],
  Frontline: ["tankiness","engage","disengage","anti_dive","zone_control"],
  Control:   ["stun","root","silence","interrupt","knockback_displace","slow","clump_create","peel"],
  Denial:    ["purge","anti_zone","heal_reduction","resist_shred","energy_drain","damage_debuff","max_health_cut"],
  Damage:    ["burst_st","burst_aoe","sustained_dps","execute"],
  Tempo:     ["mobility","catch","buff_allies"],
};

/* ------------------------------------------------------------------ copy */

const CAP_PROSE = {
  heal_sustain:"sustained healing", heal_burst:"burst healing", cleanse:"cleanse",
  tankiness:"frontline that survives focus", engage:"a way to initiate",
  disengage:"a way to get out", zone_control:"space denial", stun:"stuns",
  root:"roots", silence:"silences", slow:"slows", clump_create:"stacking enemies for AoE",
  peel:"backline protection", purge:"buff removal", heal_reduction:"healing reduction",
  anti_zone:"clearing enemy ground zones",
  resist_shred:"resistance shred", energy_drain:"energy pressure",
  burst_st:"single-target burst", burst_aoe:"AoE burst", sustained_dps:"sustained damage",
  execute:"execute pressure", mobility:"mobility", catch:"chase-down", buff_allies:"ally buffs",
  self_sustain:"self-sustain", anti_dive:"anti-dive", knockback_displace:"enemy displacement",
  /* taxonomy ruling 2026-08-21: %-max-health cuts are their own capability —
     an enabler, not damage; execute stays for low-HP payoffs / kill rewards */
  max_health_cut:"max-health cut",
  /* interrupt taxonomy 2026-08-21: stopping a cast mid-channel is its own
     thing, not silence — Badon's cloud, Snare Charge, Forbidden Stab */
  interrupt:"cast interrupts",
};
const prose = c => CAP_PROSE[c] || c.replace(/_/g," ");
/* User-facing short titles (owner 2026-08-21): headline surfaces speak
   player, never engine — no snake_case keys, no awkward wordings. The
   full prose stays one hover away in tooltips. */
const CAP_LABEL = {
  tankiness:"Frontline", heal_sustain:"Sustain healing", heal_burst:"Burst healing",
  cleanse:"Cleanse", self_sustain:"Self-sustain",
  engage:"Engage", disengage:"Disengage", anti_dive:"Anti-dive",
  zone_control:"Zone control", stun:"Stuns", root:"Roots", silence:"Silences",
  slow:"Slows", clump_create:"Clump", knockback_displace:"Displace", peel:"Peel",
  purge:"Purge", anti_zone:"Zone clear", heal_reduction:"Anti-heal",
  resist_shred:"Shred", energy_drain:"Energy drain", damage_debuff:"Damage debuff",
  max_health_cut:"Health cut", burst_st:"Single burst", burst_aoe:"AoE burst",
  sustained_dps:"Sustained DPS", execute:"Execute", mobility:"Mobility",
  catch:"Catch", buff_allies:"Ally buffs", interrupt:"Interrupts",
  ranged_presence:"Ranged presence",
};
const capLabel = c => CAP_LABEL[c] ||
  prose(c).replace(/^./, ch => ch.toUpperCase());

function roleOf(w, combo){
  /* Role label from the SCORED loadout (2026-08-18): the top capabilities
     of the combo the engine actually resolves for this content — a Cursed
     Staff whose scored kit is sustain-dps utility no longer wears its two
     highest RAW capabilities (burst_st) as a label. Pass a member's combo
     for their actual kit; omit for the content default. */
  const extra = ENG.memberExtra(w, combo === undefined ? null : combo);
  return Object.entries(extra).sort((a,b) => b[1]-a[1]).slice(0,2)
    .map(e => prose(e[0])).join(" · ");
}

/* Capability badges — visual cues for what a weapon PROVIDES. A chip shows
   only at defining strength (score >= 2): score-1 effects are minor by the
   magnitude rule (HANDOFF) and would drown the signal. Tooltip carries the
   component scores. */
/* chip: the short name worn on the picker's filter chips — label stays the
   full name for tooltips, badges and screen readers */
const BADGE_DEFS = [
  {id:"tank", label:"Tankiness",              chip:"tanky",    icon:"tank",   caps:["tankiness"]},
  {id:"heal", label:"Healing",                chip:"healing",  icon:"healer", caps:["heal_sustain", "heal_burst"]},
  {id:"peel", label:"Peel / ally protection", chip:"peel",     icon:"peel",   caps:["peel"]},
  {id:"cc",   label:"Crowd control",           chip:"cc",       icon:"cc",     caps:["stun", "root", "silence", "slow", "clump_create", "knockback_displace"]},
  {id:"aoe",  label:"Area damage",             chip:"aoe",      icon:"aoe",    caps:["burst_aoe"]},
  {id:"st",   label:"Single-target burst",     chip:"burst",    icon:"st",     caps:["burst_st", "execute"]},
  {id:"dps",  label:"Sustained damage",        chip:"dps",      icon:"dps",    caps:["sustained_dps"]},
];
const BADGE_BY_ID = Object.fromEntries(BADGE_DEFS.map(d => [d.id, d]));
function badgeHtml(w){
  const caps = capsOf(w);
  return BADGE_DEFS.map(({id, label, icon, caps: keys}) => {
    const hits = keys.filter(k => (caps[k] || 0) >= 2);
    if (!hits.length) return "";
    const tip = hits.map(k => `${prose(k)} ${caps[k]}`).join(", ");
    return `<span class="bdg b-${id}" data-bfilter="${id}" role="button" tabindex="0"
      aria-label="${esc(label)}: ${esc(tip)}. Click to filter weapons"
      title="${esc(label)} — ${esc(tip)} — click to filter">${semanticIcon(icon)}<span class="sr-only">${esc(label)}</span></span>`;
  }).join("");
}

/* The ADD-WEAPON picker's chip facet (its own chip bar, plus any
   capability badge clicked on a weapon anywhere). The old PARTY_FACET
   roster filter retired with the party strip (2026-08-27). */
let FACET = null;
/* mobile pass 2026-08-21: which member's popover is open as a bottom
   sheet (touch has no hover) — display state only, never in the hash */
let SHEET_OPEN = null;
const BADGE_KEYS = Object.fromEntries(BADGE_DEFS.map(d => [d.id, d.caps]));

/* ---- PvP interaction records (pipeline/build_interactions.py -> dataset).
   Spell-keyed: duplicate semantics, reflect/cleanse/purge per component, CC
   classes — with chapter-2 confidence provenance. Display + analysis here;
   the only scoring coupling lives inside app_scoring.js (verified
   nonstacking_caps). `unknown` renders as unknown, never hidden. */
const INTERACTIONS = (typeof DATASET !== "undefined" && DATASET.interactions) || {};
const INTERACTIONS_BY_WEAPON = (() => {
  const out = {};
  for (const sid of Object.keys(INTERACTIONS).sort())
    (INTERACTIONS[sid].weapons || []).forEach(w => (out[w] = out[w] || []).push(sid));
  return out;
})();
/* human-readable tooltips for the duplicate enum (spec §14) */
const DUP_TIP = {
  full: "Two copies receive essentially full independent value.",
  damage_only: "Both players can deal their normal damage, but one or more utility effects from the ability do not stack.",
  refresh: "Reapplying this effect refreshes its duration instead of creating a second independent effect.",
  override: "A new application replaces the existing version of the same effect.",
  shared_stack: "Multiple players feed the same stack counter on the target rather than maintaining independent copies.",
  unique_effect_only: "The same named effect does not stack with itself; a differently named effect on the same stat can coexist.",
  partial: "Different parts of this ability follow different stacking or interaction rules (or are not uniformly verified).",
  does_not_stack: "Duplicate applications provide no overlapping effect for this component.",
  unknown: "Duplicate behavior is not verified by the game data — treated as unknown, never guessed.",
};
function intBadgeTip(b){
  if (b.indexOf("DUPLICATE:") === 0)
    return DUP_TIP[b.slice(10).toLowerCase()] || b;
  if (b === "NON-REFLECTABLE")
    return "The game's own spell description states this damage cannot be reflected.";
  if (b === "PARTIAL REFLECT")
    return "Some components are non-reflectable; others differ or are unverified — see the component list.";
  return b.charAt(0) + b.slice(1).toLowerCase();
}
/* utility / interaction filter chips (spec §13). Capability chips use the
   1-point utility threshold (purge/cleanse slots are 1-2 pointers);
   interaction chips read the compiled records. */
const UTIL_DEFS = [
  ["purge", w => (capsOf(w).purge || 0) >= 1],
  ["cleanse", w => (capsOf(w).cleanse || 0) >= 1],
  ["anti-heal", w => (capsOf(w).heal_reduction || 0) >= 1],
  ["pierce", w => (capsOf(w).resist_shred || 0) >= 1],
  ["displace", w => (capsOf(w).knockback_displace || 0) >= 1],
  ["no-reflect", w => (INTERACTIONS_BY_WEAPON[w] || [])
    .some(sid => INTERACTIONS[sid].reflect === "non_reflectable")],
  ["dup-verified", w => (INTERACTIONS_BY_WEAPON[w] || [])
    .some(sid => INTERACTIONS[sid].confidence === "verified"
              && (INTERACTIONS[sid].duplicate === "full"
                  || INTERACTIONS[sid].duplicate === "shared_stack"))],
];
const UTIL_FN = Object.fromEntries(UTIL_DEFS);
function facetOk(w){
  if (!FACET) return true;
  if (FACET.type === "role") return roleHint(w) === FACET.v;
  if (FACET.type === "util") return (UTIL_FN[FACET.v] || (() => false))(w);
  return (BADGE_KEYS[FACET.v] || []).some(k => (capsOf(w)[k] || 0) >= 2);
}
function setFacet(f, scroll){
  FACET = (f && FACET && FACET.type === f.type && FACET.v === f.v) ? null : f;
  renderWheel(RECS_CUR);
  if (FACET && scroll && !matchMedia("(prefers-reduced-motion: reduce)").matches)
    $("wheel").scrollIntoView({behavior: "smooth", block: "center"});
}
const roleCls = w => `role-${roleHint(w)}`;
function whySentence(party, cand){
  const terms = explain(party, cand);
  if (!party.length)
    return `Opening pick. With nothing on the board, ${nameOf(cand)} scores highest because it covers ${terms.slice(0,2).map(t => prose(t.cap)).join(" and ")} — the capabilities this template weights most heavily.`;
  const s = supply(party);
  const strong = Object.keys(REQS()).filter(c => (s[c]||0)/target(c) >= 0.85)
    .sort((a,b) => REQS()[b].weight - REQS()[a].weight).slice(0,2).map(prose);
  const lead = terms[0], rest = terms.slice(1,3).map(t => prose(t.cap));
  /* Option C: floor state reads the weapon+loadout supply, never gear */
  const sfl = supplyFloor(party);
  const floorClause = (lead && floorHit(lead.cap, sfl[lead.cap] || 0))
    ? ` — and at size ${SIZE} that is below the hard floor, not merely suboptimal` : "";
  /* +…toFixed(1): kit-effectiveness scaling makes supply fractional —
     without rounding this printed "at 7.730833333333333 of 7.9 units" */
  return `${strong.length ? `Your party already covers ${strong.join(" and ")}` : "Your party is thin across the board"}, but has <em>${lead ? prose(lead.cap) : "gaps"}</em> at ${lead ? +lead.before.toFixed(1) : 0} of ${lead ? target(lead.cap).toFixed(1) : "0"} units${floorClause}. ${nameOf(cand)} closes that${rest.length ? `, and adds ${rest.join(" and ")}` : ""}.`;
}

/* ------------------------------------------------------- shareable state */

function loadHash(){
  const h = location.hash.replace(/^#/, "");
  if (!h) return false;
  const p = {};
  h.split("&").forEach(kv => { const i = kv.indexOf("=");
    if (i > 0) p[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1)); });
  /* junk hashes (#foo) are not state — returning true for them would
     suppress the localStorage restore and the seed party */
  if (!("c" in p) && !("n" in p) && !("st" in p) && !("p" in p)) return false;
  if (p.c && DATASET.templates[p.c]) CONTENT = p.c;
  const n = parseInt(p.n, 10);   // integers only — +"0x10"/+"7.5" slipped through
  PLANNED = (n >= 2 && n <= HARD_CAP) ? n : baseSize();
  STYLE = (p.st && (DATASET.styles || {})[p.st]) ? p.st : "balanced";
  /* a link WITHOUT p= is a shared empty comp — clear, don't keep the old
     party (saveHash omits p= when empty, so restore must mirror that).
     g / f / k decode POSITIONALLY against the ORIGINAL p= list, so unknown
     weapon keys are dropped from all four arrays TOGETHER — filtering the
     party alone used to shift loadouts and forged flags onto the wrong
     members (review 2026-08-18). Cap at HARD_CAP like every roster path. */
  const rawParty = p.p ? p.p.split(",") : [];
  const rawLoadout = p.g ? loadoutDecode(p.g) : [];
  const rawProv = provDecode(p.f || "", rawParty.length);
  /* `k` (2026-08-18) carries explicit member combos (forge results whose
     E-slot use variant no spell picker can express). Optional like g/f. */
  const rawCombo = comboDecode(p.k || "", rawParty.length);
  party = []; LOADOUT = []; PROV = []; COMBO = [];
  rawParty.forEach((w, i) => {
    if (!WEAPONS[w] || party.length >= HARD_CAP) return;
    party.push(w);
    LOADOUT[party.length - 1] = rawLoadout[i];
    PROV[party.length - 1] = rawProv[i];
    COMBO[party.length - 1] = rawCombo[i];
  });
  FORGE_NOTE = null;
  LO_OPEN = null; LO_PICKING = null; LO_FILTER = "";
  sortPartyByRole();   /* restored comps read in role order too */
  syncEngine();
  return true;
}
function saveHash(){
  /* every optional param is omitted when empty, so a plain comp's link is
     byte-for-byte what it was before these features existed */
  const g = loadoutEncode();
  const f = provEncode(PROV, party.length);
  const k = comboEncode(COMBO, party.length);
  const h = `c=${CONTENT}&n=${PLANNED}${STYLE !== "balanced" ? "&st=" + STYLE : ""}${party.length ? "&p=" + party.join(",") : ""}${g ? "&g=" + g : ""}${f ? "&f=" + f : ""}${k ? "&k=" + k : ""}`;
  history.replaceState(null, "", "#" + h);
  try { localStorage.setItem("compforge", h); } catch (e) { /* file:// may deny */ }
}
function loadStored(){
  try {
    const h = localStorage.getItem("compforge");
    if (!h) return false;
    /* replaceState, NOT location.hash: assigning the hash is a navigation —
       it pushes a history entry (Back then lands on a hashless URL that
       disagrees with the rendered state) and fires an async hashchange that
       double-renders the boot. */
    history.replaceState(null, "", "#" + h);
    return loadHash();
  } catch (e) { return false; }
}

/* ---------------------------------------------------------------- render */

let party = [];
/* Slot provenance (2026-08-18): 'm' manual / live-party, 'f' forged. "Forge
   the rest" locks every current member; "reforge all" rebuilds only the 'f'
   slots. Without this, a slot the engine created was permanently treated as
   the user's the moment the handler returned. */
let PROV = [];
/* Explicit per-member combo overrides (forge results — e.g. an E-slot use
   variant no picker can express). null/undefined = derive from picks. */
let COMBO = [];
/* Resolved combos for the current party — recomputed in syncEngine. */
let COMBOS_CUR = [];
let GEARS_CUR = [];
/* The last forge's honesty report: {feasible, filler, held} or null. */
let FORGE_NOTE = null;
let pickFilter = "";
let treeFilter = "";
/* Forge-wheel state: the focused weapon rides at 12 o'clock. Roster changes
   re-aim the wheel at the engine's top pick (render() owns that); pure
   browsing (drag / scroll / arrows / filters) never fights the user. */
let WHEEL_FOCUS_W = null;
let RECS_CUR = null;   /* last recommendations, so filter handlers can
                          re-render the wheel without re-running the engine */
const $ = id => document.getElementById(id);

const PENDING = [["hellgate_5v5","Hellgate 5v5"]];

function renderSetup(){
  /* the option lists are static per page load — build once, then only set
     .value (rewriting a focused <select>'s options mid-interaction is
     fragile, and it was churned on every render) */
  const content = $("content"), styleSel = $("style");
  if (!content.dataset.built){
    content.innerHTML = Object.entries(DATASET.templates)
      .map(([k,t]) => `<option value="${k}">${esc(t.name)} — base ${t.base_size}</option>`)
      .join("") + PENDING.filter(([k]) => !DATASET.templates[k])
      .map(([k,n]) => `<option value="${k}" disabled>${n} — template pending</option>`).join("");
    content.dataset.built = "1";
  }
  content.value = CONTENT;
  const styles = DATASET.styles || {};
  if (!styleSel.dataset.built){
    const styleKeys = STYLE_ORDER.filter(k => styles[k])
      .concat(Object.keys(styles).filter(k => STYLE_ORDER.indexOf(k) === -1));
    styleSel.innerHTML = styleKeys.map(k =>
      `<option value="${k}">${esc(styles[k].name || k)}</option>`).join("");
    styleSel.dataset.built = "1";
  }
  styleSel.value = STYLE;
  $("style-blurb").textContent = (styles[STYLE] || {}).blurb || "";
  $("size-input").value = PLANNED;
  const presets = [...new Set(validatedSizes().concat([baseSize()]))].sort((a,b) => a-b);
  $("size-presets").innerHTML = presets.map(n =>
    `<button class="size-btn" data-size="${n}" aria-pressed="${n===PLANNED}">${n}</button>`).join("");
  $("size-hint").textContent = party.length
    ? `Judged as the ${SIZE} you actually have — the forge fills toward ${PLAN()}.`
    : `Targets and floors scale to whoever actually shows up; the forge fills toward ${PLAN()}.`;
  $("size-notice").innerHTML =
    (tpl().max_size && Math.max(SIZE, PLAN()) > tpl().max_size
      ? `<div class="notice"><b>Over the in-game cap.</b> ${esc(tpl().name)} parties are capped at ${tpl().max_size} players in game — ${Math.max(SIZE, PLAN())} cannot actually field. The advice below still computes, but treat it as hypothetical.</div>`
      : "")
    + (!ENG.extrapolated() ? "" :
    `<div class="notice"><b>Extrapolated.</b> This template is fitted and validated at size ${validatedSizes().join(", ")} only. Per-player targets are scaled linearly to ${SIZE}; flat threshold targets are unchanged. Tier-2 validation must confirm each size before this is trustworthy.</div>`);
  /* phone setup summary bar: one line that says what's set */
  const sumEl = $("msetup-sum");
  if (sumEl){
    const ct = content.selectedOptions[0]
      ? content.selectedOptions[0].textContent : CONTENT;
    sumEl.textContent = `${ct} · ${styleName() || STYLE} · ${PLAN()}`;
  }
}
/* The old role-tally chip row (and its roster facet filter) retired with
   the party strip (owner 2026-08-27) — the comp board's column headers
   carry the same counts, permanently visible and grouped. */
/* Per-member swap advice (engine swapReview): a member's weapon is valued as
   if being picked into the rest of the party and ranked against every
   alternative. Hints show only when they're worth acting on — a decent pick
   (top ~10% rank) or marginal gains stay silent, so a 3-man missing "ideal"
   pieces isn't nagged; a genuinely off-comp weapon at this content + size
   gets multiple concrete options, clickable to swap in place. */
/* Verdict thresholds live in the DATA layer (templates/scoring.yaml
   swap_advisor block) like every other PROVISIONAL tunable, so the expert
   pass can find them; the fallback only covers a pre-block dataset. */
const SWAP_CFG = (DATASET.scoring || {}).swap_advisor
  || { min_rank: 15, min_gain: 1.0, offcomp_rank: 60 };
/* A party-wide gap (say, no healer yet) makes EVERY member's best
   alternative the same role, and rank measures the shared gap, not
   individual misfit — naive gating would nag the whole roster with the
   same "go healer" hint (the next-pick panel already owns that gap). So
   each suggested ROLE keeps its hint only on the member who'd convert
   cheapest (largest gain); everyone else stays quiet. Members whose top
   options point at different roles are genuinely individual advice and
   all keep their hints. */
function swapEligible(review){
  const claim = {};
  const ok = new Set();
  review.forEach((m, i) => {
    if (!m) return;
    /* viability-excluded, style-unfit and cost-gated members always get
       their replacement advice — owner rules flag them regardless of rank
       (2026-08-18; style gate 2026-08-23; cost gate 2026-08-23) */
    if ((m.off_comp || m.off_style || m.off_budget) && m.options.length){ ok.add(i); return; }
    if (m.rank < SWAP_CFG.min_rank) return;
    const top = m.options.find(o => o.gain >= SWAP_CFG.min_gain);
    if (!top) return;
    const role = roleHint(top.weapon);
    if (!claim[role] || top.gain > claim[role].gain) claim[role] = { i, gain: top.gain };
  });
  Object.values(claim).forEach(c => ok.add(c.i));
  return ok;
}
function swapHint(m, i){
  if (!m) return "";
  const forced = (m.off_comp || m.off_style || m.off_budget) && m.options.length;
  if (!forced && m.rank < SWAP_CFG.min_rank) return "";
  const opts = forced ? m.options
    : m.options.filter(o => o.gain >= SWAP_CFG.min_gain);
  if (!opts.length) return "";
  const pool = Object.keys(WEAPONS).length;
  const label = m.off_comp
    ? `<b class="offcomp">off-comp at this size (owner rule) — swap to</b>`
    : m.off_style
      ? `<b class="offcomp">off-style for ${esc(styleName() || STYLE)} at this size — swap to</b>`
      : m.off_budget
      ? `<b class="offcomp">crystal regear cost — a rich-group pick below 30 (owner rule) — swap to</b>`
      : m.rank >= SWAP_CFG.offcomp_rank
      ? `<b class="offcomp">off-comp here — rank ${m.rank}/${pool}</b>`
      : `<span class="swap-lbl">better options</span>`;
  return `<span class="fn swap">${label} ${opts.map(o =>
    `<button class="swap-opt" data-swapat="${i}" data-swapto="${o.weapon}"
       title="swap ${nameOf(m.weapon)} for ${nameOf(o.weapon)} (+${o.gain.toFixed(1)} score)">${nameOf(o.weapon)} +${o.gain.toFixed(1)}</button>`).join(" ")}</span>`;
}
/* THE member popover — served identically in the party strip and the
   wheel's comp board. ctx carries the per-render roster analysis
   (contribution, swap review, hintability, least-load-bearing index). */
function memberPop(i, ctx){
  const w = party[i];
  const signed = v => (v < 0 ? "−" : "+") + Math.abs(v).toFixed(1);
  const flag = i !== ctx.minI ? "" : ctx.contrib[i] < 0
    ? ' · <b class="least">comp gains without it</b>'
    : ' · <b class="least">least load-bearing</b>';
  return `<div class="dm-pop" role="group" aria-label="Slot ${i+1} — ${nameOf(w)}">
    <div class="dm-nm"><button class="nm-btn" data-detail="${w}">${nameOf(w)}</button>${badgeHtml(w)}${PROV[i] === "f" ? '<span class="prov forged" title="slot generated by the forge — reforge all rebuilds it">forged</span>' : ""}</div>
    <span class="fn">${roleOf(w, COMBOS_CUR[i])} · ${signed(ctx.contrib[i])} fit${flag}${ENG.isExcluded(w) ? ' · <b class="offcomp" title="owner rule: not a default large-group pick at this size — swap advice below">off-comp at size ' + SIZE + "</b>" : ""}${ctx.review[i] && ctx.review[i].redundant && !ENG.isExcluded(w) ? ' · <b class="redund" title="redundancy warning (display only, never a score change): valued as a pick into the rest of the party, this member closes no capability gap — its jobs are already covered without it">jobs covered without it</b>' : ""}</span>
    ${ctx.hintable.has(i) ? swapHint(ctx.review[i], i) : ""}
    <div class="dm-actions">
      <button class="lo-open${LO_OPEN === i ? " on" : ""}" data-lo-open="${i}"
        aria-expanded="${LO_OPEN === i}" aria-label="Loadout for ${nameOf(w)}"
        >kit${(LOADOUT[i] || {})._eng ? '<span class="lo-eng-mark" title="engine kit — scored defaults, not a fielded build">&#9881;</span>' : ""}${loadoutCount(i) ? `<i>${loadoutCount(i)}</i>` : ""}</button>
      <button class="dm-act" data-detail="${w}">dossier</button>
      <button class="dm-act dm-x" data-remove="${i}" aria-label="Remove ${nameOf(w)}">remove</button>
    </div>
  </div>`;
}
/* The wheel's comp board (owner 2026-08-27): the roster as four main-role
   columns, each member a full dm tile with the SAME popover and actions as
   the party strip — this board is on course to replace that strip. Built
   during renderRoster (the render that runs exactly when roster state
   changes) and cached, so wheel spins never pay for the roster analysis. */
let BOARD_HTML = "", NOTES_HTML = "";
function buildCompBoard(ctx){
  if (!party.length || typeof ENG.roleAdvisory !== "function") return "";
  const chests = {};
  party.forEach((w, i) => {
    const L = (typeof LOADOUT !== "undefined" && LOADOUT[i]) || null;
    if (L && L.armor) chests[i] = L.armor;
  });
  const adv = ENG.roleAdvisory(party, chests);
  if (!adv || !adv.members.length) return "";
  const book = ENG.rolesBook || {};
  const fine = id => id ? ((book[id] || {}).name || id).split(" / ")[0].split(" (")[0] : "";
  /* four MAIN columns only (owner: "only show main roles like tank
     support dps and healers") — the fine played role rides each tile */
  const CLS = { frontline: ["Tank", "var(--role-tank)", 0],
                support:   ["Support", "var(--role-support)", 1],
                dps:       ["DPS", "var(--role-melee)", 2],
                healer:    ["Healer", "var(--role-healer)", 3] };
  const cols = new Map();
  adv.members.forEach((m, i) => {
    const cls = (m.role && (book[m.role] || {}).class) || m.class || "dps";
    const [name, color, ord] = CLS[cls] || ["Other", "var(--ink-3)", 4];
    let c = cols.get(cls);
    if (!c){ c = { name, color, ord, ms: [] }; cols.set(cls, c); }
    c.ms.push({ i, role: fine(m.role) });
  });
  const sorted = [...cols.values()].sort((a, b) => a.ord - b.ord);
  /* the strip's open-slot affordance lives on as its own dashed column */
  const open = Math.max(0, PLAN() - party.length);
  const openCol = party.length < HARD_CAP ? `
    <div class="wf-col wf-col-open">
      <span class="wf-col-h">${open} open</span>
      <div class="dm-card wf-mcard next" title="next slot — pick on the wheel">
        <span class="n mono">${String(party.length + 1).padStart(2, "0")}</span><span class="dm-plus">+</span>
      </div>
    </div>` : "";
  /* the member sheet's scrim (≤960 — touch taps open a bottom sheet) */
  const scrim = SHEET_OPEN !== null
    ? `<button class="dm-scrim" data-sheet-close aria-label="Close member details"></button>` : "";
  return `<div class="wf-comp">${sorted.map(c => `
    <div class="wf-col" style="--rc:${c.color}">
      <span class="wf-col-h">${c.ms.length}× ${esc(c.name)}</span>
      ${c.ms.map(({ i, role }) =>
        `<div class="dm wf-dm ${roleCls(party[i])}${SHEET_OPEN === i ? " sheet-open" : ""}">
          <button class="dm-card wf-mcard" data-member="${i}" aria-label="${esc(nameOf(party[i]))} — slot ${i + 1}, details">
            ${icon(party[i], 44)}<span class="wf-mnm">${esc(nameOf(party[i]))}${role ? `<small>${esc(role)}</small>` : ""}</span><span class="n mono">${String(i + 1).padStart(2, "0")}</span>
          </button>
          ${memberPop(i, ctx)}
        </div>`).join("")}
    </div>`).join("")}${openCol}${scrim}</div>`;
}
function renderRoster(){
  /* The party's ONE dock is the wheel's comp board (owner 2026-08-27: "this
     is meant to replace the party section below" — the old strip is gone).
     This render computes the roster analysis, caches the board, and caches
     the notes rail; renderWheelFoot injects both.
     contribution = fitness lost if this member left — the caller's
     "who is load-bearing" number. Lowest contributor gets flagged. */
  const base = fitness(party);
  const contrib = party.map((w, i) =>
    base - ENG.fitness(party.filter((_, j) => j !== i),
                       COMBOS_CUR.filter((_, j) => j !== i),
                       GEARS_CUR.filter((_, j) => j !== i)));
  const review = swapReviewCached();
  const hintable = swapEligible(review);
  const minI = party.length > 2 ? contrib.indexOf(Math.min(...contrib)) : -1;
  if (SHEET_OPEN !== null && !(SHEET_OPEN < party.length)) SHEET_OPEN = null;
  BOARD_HTML = buildCompBoard({ contrib, review, hintable, minI });
  /* below the board: duplicate-interaction notices (spec §7 — the message
     names the exact effect, and unknown says "verify", never a penalty)
     and the open kit editor, full width */
  const notes = [];
  const inotes = interactionNotices();
  if (inotes) notes.push(inotes);
  if (LO_OPEN !== null && party[LO_OPEN] !== undefined)
    notes.push(`<div class="kit-head fn">kit — ${nameOf(party[LO_OPEN])} · slot ${String(LO_OPEN + 1).padStart(2,"0")}</div>`
      + loadoutPanel(LO_OPEN));
  NOTES_HTML = notes.join("");
}
const INOTE_LABEL = {high: "duplicate utility wasted",
                     warning: "duplicate utility warning",
                     info: "duplicate check", verify: "verify duplicate"};
function interactionNotices(){
  if (party.length < 2) return "";
  const conf = ENG.duplicateConflicts(party, COMBOS_CUR);
  if (!conf.length) return "";
  return conf.map(c => `<div class="inote int-${c.severity}">
    <b>${esc(INOTE_LABEL[c.severity] || c.severity)}</b> — ${esc(c.reason)}
    <span class="fn">${c.weapons.map(nameOf).join(" + ")} · ${esc(c.confidence)}</span></div>`).join("");
}
const TREE_NAMES = {
  arcanestaff:"Arcane", axe:"Axe", bow:"Bow", crossbow:"Crossbow",
  cursestaff:"Curse", dagger:"Dagger", firestaff:"Fire", froststaff:"Frost",
  hammer:"Hammer", holystaff:"Holy", knuckles:"War Gloves", mace:"Mace",
  naturestaff:"Nature", quarterstaff:"Quarterstaff",
  shapeshifterstaff:"Shapeshifter", spear:"Spear", sword:"Sword",
};
function renderTreeFilter(){
  const present = [...new Set(Object.values(TREES))];
  const opts = present.map(t => [t, TREE_NAMES[t] || t])
    .sort((a,b) => a[1].localeCompare(b[1]))
    .map(([t,n]) => `<option value="${t}">${n}</option>`).join("");
  $("tree-filter").innerHTML = `<option value="">All weapon trees</option>` + opts;
}
/* WEAPONS is static per page load — sort once, not per keystroke (the old
   per-render sort ran ~2,000 escape-regex + localeCompare calls each pass) */
/* Game-retired weapons are dropped from the picker: they stay in WEAPONS so
   an old permalink still loads and scores, but must never be offered. */
const WEAPONS_BY_NAME = Object.keys(WEAPONS).filter(w => !WEAPONS[w].removed)
  .sort((a,b) => nameOf(a).localeCompare(nameOf(b)));
function filteredWeapons(){
  const q = pickFilter.trim().toLowerCase();
  return WEAPONS_BY_NAME
    .filter(w => (!treeFilter || TREES[w] === treeFilter)
              && facetOk(w)
              && (!q || (WEAPONS[w].display_name || w).toLowerCase().includes(q)));
}
const PICKER_ROLES = ["tank", "melee", "range", "healer", "support"];
function renderPickerChips(){
  /* built once; afterwards only pressed states change — replacing the chip
     node mid-click would let a double-click toggle the facet back off */
  const holder = $("picker-chips");
  if (!holder.dataset.built){
    /* collapsed filter groups: a compact trigger per group, chips fly out
       on hover / focus so the rows stop spending hero-section height */
    const fly = (label, type, chips) =>
      `<div class="pgroup"><button class="pgroup-t" data-pg="${type}" type="button"
        aria-haspopup="true" title="${label} filters">${label}<span class="pg-caret">&#9662;</span></button>
        <div class="pc-fly"><div class="pc-row">${chips}</div></div></div>`;
    holder.innerHTML =
      fly("role", "role", PICKER_ROLES.map(r => {
        const label = roleLabel(r);
        return `<button class="pchip t-${r}" data-rfilter="${r}"
          aria-label="${esc(label)} role" title="${esc(label)} role">${semanticIcon(r)}${esc(label)}</button>`;
      }).join("")) +
      fly("provides", "badge", BADGE_DEFS.map(({id, label, chip, icon}) =>
        `<button class="pchip b-${id}" data-bfilter="${id}"
          aria-label="${esc(label)}" title="${esc(label)}">${semanticIcon(icon)}${esc(chip)}</button>`).join("")) +
      fly("utility", "util", UTIL_DEFS.map(([cls]) =>
        `<button class="pchip u-chip" data-ufilter="${cls}">${cls}</button>`).join(""));
    holder.dataset.built = "1";
  }
  holder.querySelectorAll("[data-rfilter]").forEach(el => el.setAttribute("aria-pressed",
    String(!!FACET && FACET.type === "role" && FACET.v === el.dataset.rfilter)));
  holder.querySelectorAll("[data-bfilter]").forEach(el => el.setAttribute("aria-pressed",
    String(!!FACET && FACET.type === "badge" && FACET.v === el.dataset.bfilter)));
  holder.querySelectorAll("[data-ufilter]").forEach(el => el.setAttribute("aria-pressed",
    String(!!FACET && FACET.type === "util" && FACET.v === el.dataset.ufilter)));
  /* the trigger glows while its group holds the active facet, so the
     collapsed row still tells you a filter is on */
  holder.querySelectorAll(".pgroup-t").forEach(t => t.setAttribute("aria-pressed",
    String(!!FACET && FACET.type === t.dataset.pg)));
}
/* ------------------------------------------------------- the forge wheel
   The picker as a wheel: filtered weapons ride the rim, the focused one
   sits under the brass notch at 12 o'clock, and the hub shows it over the
   party's role rings. Rim cards are DIFFED by weapon key, never rebuilt —
   updating each card's --a angle lets CSS transitions carry them around
   the rim instead of snapping. */
/* degrees between rim cards — wider on phones so touch-sized cards never
   overlap on the smaller radius (mobile pass 2026-08-21). Owner 2026-08-27:
   3 per side at a wider step so the fewer, larger cards stay readable. */
const wheelStepDeg = () => matchMedia("(max-width:640px)").matches ? 40 : 31;
const WHEEL_WINDOW = 3;    /* cards rendered each side of the focus */

function wheelFocusIdx(keys, recs){
  /* keep the user's focus when it survives the filter; otherwise aim at
     the best engine pick present, else the first card */
  let i = WHEEL_FOCUS_W ? keys.indexOf(WHEEL_FOCUS_W) : -1;
  if (i === -1 && recs)
    for (const r of recs){ i = keys.indexOf(r.w); if (i !== -1) break; }
  if (i === -1 && keys.length) i = 0;
  WHEEL_FOCUS_W = i === -1 ? null : keys[i];
  return i;
}
function renderWheelRing(keys, idx){
  const ring = $("wheel-ring");
  const want = new Map();   /* weapon -> signed offset from focus */
  const L = keys.length;
  if (idx !== -1 && L){
    const v = Math.min(L, WHEEL_WINDOW * 2 + 1);
    const lo = -Math.floor((v - 1) / 2);
    for (let k = 0; k < v; k++)
      want.set(keys[((idx + lo + k) % L + L) % L], lo + k);
  }
  [...ring.children].forEach(el => { if (!want.has(el.dataset.wfocus)) el.remove(); });
  const have = new Map([...ring.children].map(el => [el.dataset.wfocus, el]));
  want.forEach((o, w) => {
    let el = have.get(w);
    if (!el){
      el = document.createElement("button");
      el.className = "wseg";
      el.dataset.wfocus = w;
      el.id = "wseg-" + w;
      el.setAttribute("role", "option");
      el.tabIndex = -1;
      el.title = `${WEAPONS[w].display_name || w} — click to focus`;
      el.innerHTML = `${icon(w, 54)}<span class="ws-nm">${nameOf(w)}</span>`;
      /* spawn one step beyond the final angle so the entry animates inward */
      el.style.setProperty("--a", `${(o + Math.sign(o || 1)) * wheelStepDeg()}deg`);
      el.style.setProperty("--fade", "0");
      ring.appendChild(el);
      void el.offsetWidth;
    }
    el.style.setProperty("--a", `${o * wheelStepDeg()}deg`);
    el.style.setProperty("--fade", String(Math.max(.3, 1 - Math.abs(o) * .15)));
    el.classList.toggle("on", o === 0);
    el.setAttribute("aria-selected", String(o === 0));
  });
  $("wheel").setAttribute("aria-activedescendant",
    idx === -1 ? "" : "wseg-" + WHEEL_FOCUS_W);
}
/* Ring data is engine truth, never invented: the outer brass ring is the
   party filling toward SIZE; the role rings are the forge's own composition
   minima for this content + size (the constraint band — a display-only read;
   scoring paths never come through here). No band, no role rings. */
function hubRingData(){
  const rings = [{label:"party", have:party.length, want:PLAN(), color:"var(--brass)"}];
  const band = ENG._band;
  if (band){
    const counts = {};
    party.forEach(w => { const c = ENG.roleOf(w); counts[c] = (counts[c] || 0) + 1; });
    [["healer","var(--role-healer)"], ["frontline","var(--role-tank)"],
     ["support","var(--role-support)"], ["dps","var(--role-range)"]]
      .forEach(([k, color]) => {
        const rule = band[k];
        if (rule && typeof rule === "object" && rule.min)
          rings.push({label:k, have:counts[k] || 0, want:rule.min, color});
      });
  }
  return rings;
}
function renderHubRings(rings){
  let r = 94;
  $("hub-rings").innerHTML = rings.map(g => {
    const v = Math.max(0, Math.min(100, 100 * g.have / g.want));
    const seg = `
      <circle class="ring-track" cx="100" cy="100" r="${r}"></circle>
      <circle class="ring-fill${g.have >= g.want ? " done" : ""}${v <= 0 ? " empty" : ""}"
        cx="100" cy="100" r="${r}" pathLength="100"
        stroke-dasharray="${v.toFixed(2)} ${(100 - v).toFixed(2)}"
        style="stroke:${g.color}; color:${g.color}">
        <title>${esc(g.label)}: ${g.have} of ${g.want}</title></circle>`;
    /* rings pack edge-to-edge (stroke 6.5 + hairline) — the saved radial
       depth widens the hub body for the name, cap icons and actions */
    r -= 7;
    return seg;
  }).join("");
}
/* capability → semantic icon for the hub's glance row. Caps without a
   glyph fall back to a small text chip so nothing is silently dropped;
   the full prose stays in the tooltip either way. */
const CAP_ICON = {
  tankiness:"tank", anti_dive:"antidive",
  heal_burst:"healer", heal_sustain:"healer", self_sustain:"healer", cleanse:"healer",
  peel:"peel", buff_allies:"support",
  stun:"cc", root:"cc", silence:"cc", slow:"cc", clump_create:"cc",
  knockback_displace:"cc", interrupt:"interrupt",
  burst_aoe:"aoe", zone_control:"aoe", anti_zone:"aoe",
  burst_st:"st", execute:"st", catch:"st",
  sustained_dps:"dps",
  engage:"melee", ranged_presence:"range",
  mobility:"mobility", disengage:"disengage",
  resist_shred:"shred", heal_reduction:"antiheal", purge:"purge",
  damage_debuff:"weaken", max_health_cut:"hpcut",
};
function hubCapsHtml(w){
  /* Ordered the way the owner reads a weapon (2026-08-21 ruling): what
     the E does comes first, then Q, then W — within one slot, the
     biggest effect leads. Sub-unit slot contributions (< 1.0 effective)
     don't claim a slot, so an E's incidental dribble can't outrank a
     Q's real job; caps granted only by always-on bundles trail. Weapons
     without loadout slots fall back to pure magnitude order. Values and
     units come from the same effective caps roleOf read — display only.
     Two caps sharing a glyph (zone_control + anti_zone → ripples) merge
     into one chip whose tooltip lists both; tooltips name the slot. */
  const eff = ENG.memberExtra(w, null);
  const PRI = { e:0, q:1, w:2, r:3, passive:4 };
  const claim = {};                 /* cap → {p, slot} best claiming slot */
  const le = ENG._loadoutEff(w);
  const ch = ENG.comboChoices(w, null);
  const sp = ENG.comboSpells(w, null);
  ch.forEach(([oi, bi], i) => {
    const slot = (sp[i] || [])[0];
    const p = PRI[slot] !== undefined ? PRI[slot] : 5;
    const bundle = (le.slots[oi] || [])[bi] || {};
    for (const c in bundle)
      if (bundle[c] >= 1.0 && (!(c in claim) || p < claim[c].p))
        claim[c] = { p, slot };
  });
  const top = Object.entries(eff).filter(([, v]) => v > 0)
    .sort((a, b) => {
      const pa = claim[a[0]] ? claim[a[0]].p : 6;
      const pb = claim[b[0]] ? claim[b[0]].p : 6;
      return pa - pb || b[1] - a[1];
    }).slice(0, 3);
  const label = k => prose(k) + (claim[k] && claim[k].slot !== "passive"
    ? ` · ${claim[k].slot.toUpperCase()}` : "");
  const byIcon = new Map();   /* icon key → [cap labels], insertion-ordered */
  const out = [];
  for (const [k] of top){
    const ic = CAP_ICON[k];
    if (!ic){ out.push({txt:prose(k), tip:label(k)}); continue; }
    if (byIcon.has(ic)) byIcon.get(ic).push(label(k));
    else { const caps = [label(k)]; byIcon.set(ic, caps); out.push({ic, caps}); }
  }
  return out.map(e => e.txt !== undefined
    ? `<span class="hub-cap hub-cap-txt" title="${esc(e.tip)}">${esc(e.txt)}</span>`
    : `<span class="hub-cap" title="${esc(e.caps.join(" · "))}">${semanticIcon(e.ic)}</span>`
  ).join("");
}
/* the hub wears its weapon's element: tree name → aura key, painted by
   CSS as a breathing glow behind the art */
function auraOf(w){
  const t = (TREES[w] || "").toLowerCase();
  if (t.includes("fire")) return "fire";
  if (t.includes("frost")) return "frost";
  if (t.includes("holy")) return "holy";
  if (t.includes("nature")) return "nature";
  if (t.includes("cursed")) return "shadow";
  if (t.includes("arcane")) return "arcane";
  return "steel";
}
function renderHub(keys, idx, recs){
  const body = $("hub-body");
  const hub = body.parentElement;   /* .wheel-hub — carries the aura */
  if (recs === null){
    delete hub.dataset.aura;
    body.innerHTML = `<div class="hub-empty">That is ${HARD_CAP} people — beyond even a castle blob. Remove someone to explore swaps.</div>`;
    return;
  }
  if (idx === -1){
    delete hub.dataset.aura;
    body.innerHTML = `<div class="hub-empty">Nothing matches${treeFilter ? " in this tree" : ""}${pickFilter.trim() ? ` — “${esc(pickFilter)}”` : ""}. Clear a filter to respin.</div>`;
    return;
  }
  const w = keys[idx];
  hub.dataset.aura = auraOf(w);
  /* score the focused weapon exactly as recommend() would — a one-candidate
     pool eval, so any card on the rim carries its true marginal score */
  let r = (recs || []).find(x => x.w === w);
  if (!r){
    const rr = inPickContext(() =>
      ENG.recommend(party, 1, [w], COMBOS_CUR, GEARS_CUR));
    r = rr.length ? {w, score: rr[0].score} : null;
  }
  const isTop = !!(recs && recs.length && recs[0].w === w);
  const marks = (isTop ? ' · <b>engine pick</b>' : "")
    + (ENG.isExcluded(w) ? ' · <i class="offcomp">off-comp</i>' : "")
    + (WEAPONS[w].status === "curated" ? "" : " · illustrative");
  body.innerHTML = `
    <div class="hub-art-slot">${icon(w, 54)}</div>
    <button class="nm-btn hub-nm" data-detail="${w}" title="open the dossier">${nameOf(w)}</button>
    <span class="hub-caps">${hubCapsHtml(w)}</span>
    <span class="hub-score mono">${r ? (r.score >= 0 ? "+" : "−") + Math.abs(r.score).toFixed(2) : "—"}${marks}</span>
    <button class="cb-add hub-add" data-add="${w}">Add to comp</button>`;
}
function renderWheelFoot(keys, recs, rings){
  const sn = styleName();
  const slotLabel = recs === null
    ? `roster cap — ${HARD_CAP}`
    : party.length + 1 > PLANNED
      ? `slot ${party.length + 1} — beyond planned ${PLANNED}`
      : `slot ${party.length + 1} of ${PLAN()}`;
  /* same commands as ever: "forge the rest" locks current members,
     "reforge all" rebuilds only the generated slots (2026-08-18) */
  const forge = recs === null ? "" : (party.length < PLAN()
    ? `<button class="cb-forge" id="forge">${party.length ? "forge the rest" : "forge a full comp"}</button>`
    : "") + (PROV.some(x => x === "f")
    ? `<button class="cb-forge" id="reforge" title="rebuild every forged slot for the current content, style and size — manual picks stay">reforge all</button>`
    : "");
  /* the comp board replaces the ring tallies once members exist; the brass
     party count moves up beside the wheel count. BOARD_HTML is built by
     renderRoster (which runs on every roster-state change), so wheel spins
     reuse it for free. */
  const board = BOARD_HTML;
  $("wheel-foot").innerHTML = `
    ${WHEEL_FOCUS_W && recs !== null && party.length < HARD_CAP
      ? `<button class="cb-add wf-add-mobile" data-add="${WHEEL_FOCUS_W}">Add ${esc(nameOf(WHEEL_FOCUS_W))}</button>`
      : ""}
    <div class="wf-row">
      <span class="eyebrow">Next pick — ${slotLabel}${sn ? " · " + esc(sn) : ""}</span>
      <span class="wf-count">${keys.length} weapon${keys.length === 1 ? "" : "s"} on the wheel</span>
      ${board ? `<span class="wf-ring" style="color:var(--brass)">party <b>${party.length}/${PLAN()}</b></span>` : ""}
    </div>
    ${board || `<div class="wf-row"><span class="wf-rings">${rings.map(g =>
      `<span class="wf-ring" style="color:${g.color}">${esc(g.label)} <b>${g.have}/${g.want}</b></span>`).join("")}</span></div>`}
    ${NOTES_HTML ? `<div class="roster-notes wf-notes">${NOTES_HTML}</div>` : ""}
    ${forge ? `<div class="wf-row"><span class="wf-actions">${forge}</span></div>` : ""}`;
}
function renderWheel(recs){
  renderPickerChips();
  const keys = filteredWeapons();
  const facetText = !FACET ? "" : FACET.type === "role"
    ? `${roleLabel(FACET.v)} weapons`
    : FACET.type === "badge"
      ? `provides ${(BADGE_BY_ID[FACET.v] || {label:FACET.v}).label.toLowerCase()}`
      : `utility: ${FACET.v}`;
  $("facet-slot").innerHTML = FACET
    ? `<div class="facet"><span>showing: <b>${esc(facetText)}</b> — ${keys.length} match${keys.length === 1 ? "" : "es"}</span>
       <button class="fx" id="facet-clear" aria-label="Clear filter">&times; clear</button></div>`
    : "";
  const idx = wheelFocusIdx(keys, recs);
  const rings = hubRingData();
  renderWheelRing(keys, idx);
  renderHubRings(rings);
  renderHub(keys, idx, recs);
  renderWheelFoot(keys, recs, rings);
}
function wheelStep(d){
  const keys = filteredWeapons();
  if (!keys.length) return;
  let i = WHEEL_FOCUS_W ? keys.indexOf(WHEEL_FOCUS_W) : -1;
  i = i === -1 ? 0 : ((i + d) % keys.length + keys.length) % keys.length;
  WHEEL_FOCUS_W = keys[i];
  renderWheel(RECS_CUR);
}
function renderFitness(){
  /* an EMPTY roster measures negative (the armed hard floors have nobody
     covering them — engine math, golden T16), but showing a failing grade
     for a comp that doesn't exist yet reads as a bug. Neutral display until
     the first member; partial comps keep the negative number on purpose —
     there it is the floor signal working. */
  if (!party.length){
    $("fit-num").textContent = "—";
    $("fit-of").textContent = "add members";
    $("fit-bar").style.width = "0%";
    return;
  }
  const f = fitness(party), max = maxFitness();
  $("fit-num").textContent = f.toFixed(1);
  $("fit-of").textContent = `/ ${Math.round(max)}`;
  $("fit-bar").style.width = `${Math.max(0, Math.min(100, f/max*100))}%`;
}
function renderGroups(){
  const s = supply(party);
  /* Option C: the bars keep quoting the DRESSED supply (coverage), but
     the below-floor predicate reads the weapon+loadout basis the engine's
     structural floors use */
  const sfl = supplyFloor(party);
  /* any requirement cap missing from the hardcoded GROUPS map lands in an
     "Other" group instead of silently vanishing from the board — the
     taxonomy grows (anti_zone, damage_debuff, self_sustain all post-date
     the map) and a forgotten entry hid the cap with zero errors */
  const grouped = new Set(Object.values(GROUPS).flat());
  const other = Object.keys(REQS()).filter(c => !grouped.has(c));
  const groups = other.length ? {...GROUPS, Other: other} : GROUPS;
  $("groups").innerHTML = Object.entries(groups).map(([g, caps]) => {
    const rows = caps.filter(c => REQS()[c]).map(c => {
      const have = s[c] || 0, t = target(c), soft = softCap(c);
      const below = floorHit(c, sfl[c] || 0);
      const over = have > soft;
      const cls = over ? "over" : have === 0 ? "none" : have >= t ? "met" : "part";
      /* styles multiply a capability's WEIGHT, never its target — surface
         that emphasis here so switching playstyles visibly (and truthfully)
         changes the board: ×1.6 = this style values the cap more, ×0.7 less */
      const baseW = REQS()[c].weight || 0;
      const styledW = ENG.weight(c);
      const mult = baseW ? styledW / baseW : 1;
      const styleTag = Math.abs(mult - 1) < 0.01 ? "" :
        `<span class="tag ${mult > 1 ? "style-up" : "style-down"}" title="this playstyle ${mult > 1 ? "raises" : "lowers"} ${c}'s weight (${baseW} → ${styledW.toFixed(1)}); targets never change with style — style changes what the engine emphasises, not what keeps a party alive">×${mult.toFixed(mult >= 1 ? 1 : 2)}</span>`;
      return `<div class="cap ${below ? "floor-hit" : ""}">
        <button class="cap-name" data-cap="${c}" title="${esc(prose(c))} — click for evidence">${c}${below ? '<span class="tag floor">below floor</span>' : ""}${over ? '<span class="tag over">overstacked</span>' : ""}${styleTag}</button>
        <span class="cap-val">${have.toFixed(0)} / ${t.toFixed(1)}</span>
        <span class="cap-bar"><i class="${cls}" style="width:${over ? 100 : Math.min(100, have/t*100)}%"></i></span>
      </div>`;
    }).join("");
    return rows ? `<div class="grp"><h3>${g}</h3>${rows}</div>` : "";
  }).join("");
}
function renderWeaknesses(){
  const s = supply(party);
  const sfl = supplyFloor(party);   /* Option C floor basis */
  /* Split the gap list: floors and heavy under-supplied capabilities are
     NEEDED; the rest are nice-to-haves. */
  const needed = [], nice = [];
  for (const x of weaknesses(party, 8)){
    if (x.gap < 0.5) continue;
    const below = floorHit(x.cap, sfl[x.cap] || 0);
    const ratio = (s[x.cap]||0) / target(x.cap);
    // styled weight (ENG.weight), same scale as the engine's own
    // uncovered-caps test — raw template weight silently disagreed with the
    // greedy-trap warning under any non-balanced style
    if (below || (ENG.weight(x.cap) >= 6 && ratio < 0.5)) needed.push({...x, floorHit: below});
    else nice.push(x);
  }
  /* the fix, not the units (owner 2026-08-21): each gap leads with the
     weapons that close it — click to add. Ranked by the flat sheet score
     for that capability (the same display layer the dossier shows);
     excluded weapons never suggested; duplicates allowed (real comps
     stack healers). Numbers demoted to a small have/target aside. */
  const capSuppliers = (cap, k = 3) => Object.entries(DATASET.weapons)
    .filter(([w, d]) => d.status === "curated" && !d.removed
                        && (d.capabilities || {})[cap] && !ENG.isExcluded(w))
    .sort((a, b) => (b[1].capabilities[cap] - a[1].capabilities[cap])
                    || a[0].localeCompare(b[0]))
    .slice(0, k).map(([w]) => w);
  /* image-first, player-voiced cards (owner 2026-08-21): the fix leads at
     full size, the gap wears its short title (full prose in the tooltip),
     and priority is carried by order alone — no rank numerals, no keys */
  const row = (x, i, cls) => {
    const picks = capSuppliers(x.cap).map(w =>
      `<button class="weak-add" data-add="${w}" title="Add ${esc(DATASET.weapons[w].display_name)} — ${esc(capLabel(x.cap))} ${DATASET.weapons[w].capabilities[x.cap]}/7">${icon(w, 40)}</button>`).join("");
    return `<div class="weak ${cls}">
      <span class="weak-picks">${picks}</span>
      <span class="weak-main">
        <span class="weak-name" title="${esc(prose(x.cap))}">${esc(capLabel(x.cap))}</span>
        <span class="weak-have">${(s[x.cap]||0).toFixed(0)} / ${target(x.cap).toFixed(1)}</span>
        ${x.floorHit ? `<span class="weak-floor">below the hard floor</span>` : ""}
      </span></div>`;
  };
  $("weaknesses").innerHTML =
    `<div class="weak-sub">Needed now</div>`
    + (needed.length ? needed.slice(0,4).map((x,i) => row(x,i,"")).join("")
                     : `<p class="weak-none">Nothing critical — the core is covered.</p>`)
    + (nice.length ? `<div class="weak-sub nice">Nice to have</div>`
                   + nice.slice(0,3).map((x,i) => row(x,i,"nice")).join("") : "");
}
function renderWarning(){
  const unc = uncoveredCaps(party), left = Math.max(0, PLAN() - party.length);
  const greedy = (party.length && left > 0 && left <= 2 && unc.length >= 3)
    ? `<div class="warn"><span class="t">Lookahead</span>
       <span class="b"><b>Greedy trap.</b> ${left} slot${left>1?"s":""} left but ${unc.length} high-weight capabilities still uncovered
       (<code>${unc.join(", ")}</code>). No single weapon closes all of them — expect to leave at least ${unc.length - left} unmet whatever you pick next.</span></div>`
    : "";
  /* The forge's honesty report (2026-08-18): an infeasible constraint set
     or a slot the objective dislikes is SAID, never silently absorbed. */
  let forgeBits = "";
  if (FORGE_NOTE){
    const slotNames = idx => idx.map(i =>
      `${String(i + 1).padStart(2, "0")} ${party[i] ? nameOf(party[i]) : ""}`).join(", ");
    if (!FORGE_NOTE.feasible)
      forgeBits += `<div class="warn"><span class="t">Forge</span>
        <span class="b"><b>Infeasible.</b> The composition constraints for this content and size could not all be met from the allowed weapon pool — the roster below is partial/provisional. Loosen the locked picks or change the size.</span></div>`;
    if (FORGE_NOTE.filler && FORGE_NOTE.filler.length)
      forgeBits += `<div class="warn"><span class="t">Forge</span>
        <span class="b"><b>Saturated tail.</b> Slot${FORGE_NOTE.filler.length > 1 ? "s" : ""} ${slotNames(FORGE_NOTE.filler)} reduce${FORGE_NOTE.filler.length > 1 ? "" : "s"} the comp score and no allowed replacement does better — the template is fully covered before size ${PLAN()}. Treat ${FORGE_NOTE.filler.length > 1 ? "these slots" : "this slot"} as provisional.</span></div>`;
    if (FORGE_NOTE.held && FORGE_NOTE.held.length)
      forgeBits += `<div class="warn"><span class="t">Forge</span>
        <span class="b"><b>Constraint-held.</b> Slot${FORGE_NOTE.held.length > 1 ? "s" : ""} ${slotNames(FORGE_NOTE.held)} score${FORGE_NOTE.held.length > 1 ? "" : "s"} slightly negative but ${FORGE_NOTE.held.length > 1 ? "are" : "is"} required by the composition minimums (healers/frontline/ranged core) — expert structure the capability score alone does not see.</span></div>`;
  }
  $("warn-slot").innerHTML = greedy + forgeBits;
}
/* Names for the spells a scored combo equips — the loadout the engine
   ACTUALLY valued, shown with the recommendation (2026-08-18). */
function scoredKitLine(w, combo){
  const pools = (typeof SPELLS !== "undefined" && SPELLS[w]) || {};
  const parts = (ENG.comboSpells(w, combo) || []).map(([slot, sid]) => {
    const pool = pools[slot] || [];
    let nm = sid;
    for (const e of pool) if (e[0] === sid){ nm = e[1]; break; }
    return `${slot === "passive" ? "P" : slot.toUpperCase()} ${esc(nm)}`;
  });
  return parts.length
    ? `<div class="fieldnote">scored loadout: ${parts.join(" · ")} — the marginal terms below are THIS kit, one spell per slot</div>`
    : "";
}
/* the math disclosure keeps its state across re-renders — a reader who
   opened it mid-comparison shouldn't have it snap shut on every pick */
let MATH_OPEN = false;
function renderRecDetail(recs){
  if (!recs){
    $("rec-label").textContent = "Recommendation";
    $("rec-slot").innerHTML = `<div class="rec"><div class="rec-body">
      <p class="why">Party is full at ${SIZE}. Remove a slot to see what the engine would swap in.</p></div></div>`;
    return;
  }
  const top = recs[0], terms = explain(party, top.w).slice(0,4);
  /* one-ahead residual gaps (PR #5): what stays thin AFTER this pick joins,
     in the same resolved-loadout context the recommendation used */
  const after = inPickContext(() => {
    const next = party.concat([top.w]);
    const combos = COMBOS_CUR.concat([top.combo === undefined ? null : top.combo]);
    const sup = ENG.effectiveSupply(next, combos);
    return ENG.weaknesses(next, 8, combos).filter(x => x.gap >= 0.5).slice(0, 3)
      .map(x => ({...x, have: sup[x.cap] || 0, want: ENG.target(x.cap)}));
  });
  const afterHtml = `<div class="after-pick"><span class="ap-k">after this pick</span>${
    after.length
      ? after.map(x => `<span class="ap-gap" title="${x.have.toFixed(0)} / ${x.want.toFixed(1)} covered">${esc(capLabel(x.cap))}</span>`).join("")
      : `<span class="ap-ok">core gaps covered</span>`}</div>`;
  $("rec-label").textContent = `Why ${WEAPONS[top.w].display_name}`;
  $("rec-slot").innerHTML = `
    <div class="rec">
      <div class="rec-body">
        <p class="why">${whySentence(party, top.w)}</p>
        ${observedLine(top.w)}
        ${afterHtml}
        <div><div class="sec-label" style="margin-bottom:8px">Alternatives — click to add instead</div>
          <div class="alts">${recs.slice(1).map(r => {
            const t0 = explain(party, r.w)[0];
            /* two-line card: the name owns a full row (score beside it),
               badges flow horizontally beneath with the gain right-aligned */
            return `<button class="alt" data-add="${r.w}">${icon(r.w, 40)}
              <span class="alt-main">
                <span class="alt-top"><span class="nm">${nameOf(r.w)}</span><span class="sc">${r.score.toFixed(2)}</span></span>
                <span class="alt-sub">${badgeHtml(r.w)}<span class="rz" title="${t0 ? esc(prose(t0.cap)) : ""}">${t0 ? `+${t0.d.toFixed(1)} ${esc(capLabel(t0.cap))}` : "no template gain"}</span></span>
              </span></button>`;
          }).join("")}</div>
        </div>
        <details class="rec-math"${MATH_OPEN ? " open" : ""}>
          <summary>the math — scored loadout, marginal terms, formula</summary>
          <div class="math-body">
        ${scoredKitLine(top.w, top.combo)}
        ${usageLine(top.w)}
        ${(() => {
          /* §F selection, never variants[0]; §G provenance on every
             displayed reference build */
          const v = (typeof loadoutSelect !== "undefined")
            ? loadoutSelect(top.w, CONTENT, SIZE) : null;
          return v ? `<div class="lo-box"><div class="who">reference build — ${esc(v.caller)}${v.role ? " · " + esc(v.role) : ""}</div>
            ${loLine(top.w, v)}
            <div class="fieldnote">${loProvenance(v)}</div></div>` : "";
        })()}
        <div class="terms">${terms.map(t => `<div class="term">
          <span class="d">+${t.d.toFixed(2)}</span><span class="c">${t.cap}</span>
          <span class="mv">${t.before.toFixed(0)} → ${t.after.toFixed(0)} of ${t.target.toFixed(1)}</span></div>`).join("")}</div>
        ${(() => {
          /* the score is the EXACT compScore delta: base blend + the prior
             and duplication terms. adj = viability tier − duplicate cost,
             shown when it moves the number (2026-08-18). */
          const blend = ENG.alpha * top.dFit + ENG.beta * top.dSyn + ENG.delta * top.meta;
          const adj = top.score - blend;
          const adjBit = Math.abs(adj) > 0.005
            ? ` ${adj >= 0 ? "+" : "−"} <b>${Math.abs(adj).toFixed(2)}</b><span class="k"> priors</span>` : "";
          return `<div class="formula">
          <span class="k">score</span> = ${ENG.alpha}·Δfitness + ${ENG.beta}·Δsynergy + ${ENG.delta}·metaPrior ± viability/duplication<br>
          &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;= ${ENG.alpha}·<b>${top.dFit.toFixed(2)}</b> + ${ENG.beta}·<b>${top.dSyn.toFixed(2)}</b> + ${ENG.delta}·<b>${top.meta.toFixed(2)}</b>${adjBit} = <b>${top.score.toFixed(2)}</b><br>
          <span class="k">score</span> is the exact change to the party's comp score if this pick joins with the loadout above. <span class="k">metaPrior</span> and the viability tier are hand-curated guard values — real win-lift arrives in Phase 3 from battle data.
        </div>`;
        })()}
          </div>
        </details>
      </div>
    </div>`;
  const mathEl = $("rec-slot").querySelector(".rec-math");
  if (mathEl) mathEl.addEventListener("toggle", () => { MATH_OPEN = mathEl.open; });
}
function renderFootnote(){
  const c = party.filter(w => WEAPONS[w].status === "curated").length;
  $("footnote").innerHTML = `Dataset <code>v${META.version}</code> — <code>${META.weapons_curated} curated</code>, <code>${META.weapons_illustrative} illustrative</code> of ${META.weapons_total} weapons; evidence lint <code>${META.lint_passed ? "passed" : "FAILED"}</code>, release_clean <code>${META.release_clean}</code>.
    This party: ${c} curated, ${party.length - c} illustrative.
    Curated sheets cite an equippable spell for every nonzero score. Illustrative sheets carry design-doc §2.3 placeholder numbers and are <b>not</b> evidence-checked — they exist to keep the engine runnable during curation. Click any capability for its evidence chain.
    Item renders from the official Albion Online Render Service, © Sandbox Interactive GmbH — this tool is unofficial and not affiliated.`;
}
/* FIGHT-SIZE EQUIPMENT PREVALENCE (sample_battles.py, §E): how often a
   weapon appeared on observed combatants in recent fights of roughly the
   size this party would find itself in. The killboard states only the total
   fight size — party size, side size and selected abilities are UNKNOWN and
   never inferred; prevalence is not effectiveness, and none of this feeds
   the scoring. */
/* One gate for the usage sample; the min-sample rule lives here once (it
   was copy-pasted between usageOf and renderMetaStrip). The bucket keys to
   the size this comp is FOR — PLAN(), not the roster judged so far: a
   20-man plan with 3 members picked must quote large-fight evidence, not
   small ganks, or the cohort strip stays invisible for the whole planning
   phase. (The old rule displayed ENG.sizeBucket() to provably match the
   meta prior's bucket — dead since H18: the shipped prior is the hand-set
   flat map, never bucketed.) Participant axis = 2 x party size, mirroring
   engine size_bucket. */
const USAGE_BUCKET_LABEL = { small: "small", mid: "mid-size", large: "large" };
function usageBucket(){
  const n = 2 * PLAN();
  return n < 12 ? "small" : n <= 30 ? "mid" : "large";
}
function usageStats(){
  if (typeof USAGE === "undefined" || !USAGE.buckets) return null;
  const key = usageBucket();
  const m = (USAGE.meta || {})[key];
  if (!m || m.players_attributed < 200) return null;   // not enough data to quote
  return { key, label: USAGE_BUCKET_LABEL[key], m };
}
function usageOf(w){
  const u = usageStats();
  if (!u) return null;
  const n = (USAGE.buckets[u.key] || {})[w] || 0;
  return { pct: 100 * n / u.m.players_attributed, n,
           players: u.m.players_attributed, battles: u.m.battles,
           inBattles: ((USAGE.buckets_battles || {})[u.key] || {})[w] || 0,
           label: u.label };
}
/* ---------------- observed organization cohorts (PR #5, 2026-08-22) ----
   sample_battles.py groups actors ONLY when the kill feed states the same
   Alliance/Guild identity; ambiguous players are excluded. Cohorts are NOT
   parties, sides, or win-rate samples — the copy says "observed together",
   never "teammates" or "successful". The page embeds only the anonymous
   weapon baskets (dashboard/build.py strips org ids and battle ids). Display
   evidence only; nothing here can touch a score. */
function cohortContext(){
  if (typeof USAGE === "undefined" || !USAGE.cohort_baskets) return null;
  const key = usageBucket();
  const rows = (USAGE.cohort_baskets[key] || [])
    .filter(ws => Array.isArray(ws) && ws.length >= 2);
  if (rows.length < 8) return null;   /* too thin to quote */
  return { key, rows, label: USAGE_BUCKET_LABEL[key] || key };
}
function cohortAffinity(){
  const ctx = cohortContext();
  if (!ctx || !party.length) return null;
  const selected = [...new Set(party)];
  const selectedSet = new Set(selected);
  const N = ctx.rows.length;
  const baskets = ctx.rows.map(ws => new Set(ws.filter(w => WEAPONS[w])));
  const count = {};
  baskets.forEach(s => s.forEach(w => { count[w] = (count[w] || 0) + 1; }));
  /* a one-weapon party matches on 1 overlap; from two unique weapons on,
     require >=2 so a match means the cohort echoed a PAIR you field */
  const minOverlap = Math.min(2, selected.length);
  const matched = {};
  baskets.forEach(s => {
    const overlap = selected.reduce((n, w) => n + (s.has(w) ? 1 : 0), 0);
    if (overlap < minOverlap) return;
    s.forEach(w => {
      if (selectedSet.has(w)) return;
      const m = matched[w] || (matched[w] = {cohorts: 0, overlapSum: 0,
                                             liftSum: 0, liftN: 0});
      m.cohorts++; m.overlapSum += overlap;
    });
  });
  Object.keys(matched).forEach(w => {
    /* popularity-corrected pair lift: P(a&w) / (P(a)P(w)) averaged over
       the selected weapons — 1.0 = pairs no more than chance */
    selected.forEach(a => {
      if (!count[a] || !count[w]) return;
      let both = 0;
      baskets.forEach(s => { if (s.has(a) && s.has(w)) both++; });
      if (!both) return;
      matched[w].liftSum += both * N / (count[a] * count[w]);
      matched[w].liftN++;
    });
    matched[w].lift = matched[w].liftN ? matched[w].liftSum / matched[w].liftN : 0;
    matched[w].base = count[w] || 0;
  });
  const candidates = Object.entries(matched).map(([w, m]) => ({w, ...m}))
    .filter(x => x.cohorts >= 2)
    .sort((a, b) => b.cohorts - a.cohorts || b.lift - a.lift);
  return { ctx, selected, N, candidates, minOverlap };
}
/* Partial-roster neighbours (roadmap item 6, 2026-08-24 — the
   KILLBOARD_AFFINITY.md "next step": show a few anonymized observed
   organization ROSTERS that overlap the selected weapons, not only the
   per-candidate aggregation above). Same rules as cohortAffinity: the
   anonymous baskets only, bucket keyed to the plan, a neighbour must
   share >=2 of the selected weapons, language stays "observed together".
   Ranked by shared count, then Jaccard similarity over unique weapons,
   then original basket order (deterministic). Display evidence only —
   nothing here can touch a score, a suggestion pool, or the forge. */
function cohortNeighbours(){
  const ctx = cohortContext();
  if (!ctx) return null;
  const selected = [...new Set(party)].filter(w => WEAPONS[w]);
  if (selected.length < 2) return null;   /* a PAIR is the minimum roster shape worth echoing */
  const selectedSet = new Set(selected);
  const rows = [];
  ctx.rows.forEach((ws, i) => {
    const basket = [...new Set(ws.filter(w => WEAPONS[w]))];
    const shared = basket.filter(w => selectedSet.has(w)).length;
    if (shared < 2) return;
    const union = selected.length + basket.length - shared;
    rows.push({ i, basket, shared,
                jaccard: union ? shared / union : 0,
                others: basket.filter(w => !selectedSet.has(w)) });
  });
  if (!rows.length) return null;
  rows.sort((a, b) => b.shared - a.shared || b.jaccard - a.jaccard || a.i - b.i);
  return { ctx, selected, matched: rows.length, rows: rows.slice(0, 3) };
}
/* Recurring observed families (roadmap item 7, 2026-08-24): mined offline
   by pipeline/build_cohort_families.py — an anchor PAIR that recurs across
   orgs and battles, plus the weapons frequently observed alongside (their
   shares). The page renders the committed artifact verbatim and marks
   which pieces the current roster already carries. Anchor-pair families,
   not roster clustering, BY FINDING: the baskets are partial observations
   (most hold 2-5 weapons of a 20-man lineup), so whole-roster distance
   clustering separates observation noise — see the builder's docstring.
   Display evidence only; nothing here touches a score. */
function familyRows(){
  if (typeof FAMILIES === "undefined") return null;
  const rows = FAMILIES[usageBucket()] || [];
  if (!rows.length) return null;
  const selected = new Set([...new Set(party)].filter(w => WEAPONS[w]));
  return rows.map(f => {
    const all = f.anchor.concat((f.cast || []).map(c => c.weapon));
    const mine = all.filter(w => selected.has(w));
    return { ...f, mine, anchored: f.anchor.every(w => selected.has(w)) };
  });
}
function familiesHtml(withNote){
  const rows = familyRows();
  if (!rows) return "";
  const note = withNote
    ? `<div class="ka-note">Anchor pairs observed together across distinct Alliance/Guild cohorts and battles; percentages are how often a weapon was observed with that anchor. Observation counts, not parties or win rates; never changes a score.</div>`
    : "";
  return `<div class="ka-fam"><span class="ka-nb-label">Recurring observed cores — ${esc(USAGE_BUCKET_LABEL[usageBucket()] || usageBucket())} fights</span>${
    rows.map(f => `<div class="fam-row${f.anchored ? " mine" : ""}">
      <span class="fam-anchor">${f.anchor.map(w =>
        `<button class="nb-w${f.mine.includes(w) ? " match" : ""}" data-detail="${w}" title="${esc(nameOf(w))} — family anchor">${icon(w, 26)}</button>`).join("")}</span>
      <span class="fam-meta">${f.cohorts} cohorts · ${f.orgs} orgs · ${f.battles} battles · ${f.lift}× lift${f.anchored ? ' · <b class="fam-yours">anchor in your roster</b>' : ""}</span>
      ${f.anchored ? "" : `<button class="fam-load" data-family-load="${f.anchor.join(",")}" title="add this core's anchor pair to the comp as manual picks — the engine scores them like any manual choice, and the forge can complete the rest">add core</button>`}
      ${(f.cast || []).length ? `<span class="fam-cast"><i>with</i>${f.cast.map(c =>
        `<button class="nb-w${f.mine.includes(c.weapon) ? " match" : ""}" data-detail="${c.weapon}" title="${esc(nameOf(c.weapon))} — observed with this core in ${Math.round(100 * c.share)}% of its cohorts">${icon(c.weapon, 20)}</button>`).join("")}</span>` : ""}
    </div>`).join("")}${note}</div>`;
}
/* Observed effect quotas (increment 3b, owner-ruled 2026-08-26: "yes —
   advise quotas"). EFFECT_QUOTAS carries how many carriers of each typed
   gear effect (Demon/Judicator/Guardian/Royal/Hellion chests) the
   near-complete observed rosters field per 20 — mined from the
   reference-build evidence layer, scaled to PLAN(). Rows compare against
   the chests this roster's loadouts actually carry; members without gear
   set are counted honestly as unknown, and no shortfall is claimed while
   any chest is unknown. Observed evidence: advice only, never a score. */
function effectQuotaRows(){
  if (typeof EFFECT_QUOTAS === "undefined" || !EFFECT_QUOTAS) return null;
  const plan = PLAN();
  if (plan < (EFFECT_QUOTAS.min_size || 15)) return null;
  const effs = EFFECT_QUOTAS.effects || {};
  const keys = Object.keys(effs).sort();
  if (!keys.length) return null;
  let unset = 0;
  const carried = {};
  (party || []).forEach((_, i) => {
    const L = (typeof LOADOUT !== "undefined" && LOADOUT[i]) || null;
    if (!L || !L.armor){ unset++; return; }
    for (const k of keys){
      if ((effs[k].items || []).indexOf(L.armor) >= 0)
        carried[k] = (carried[k] || 0) + 1;
    }
  });
  return keys.map(k => {
    const e = effs[k];
    const want = Math.round(e.typical * plan / 2) / 10;
    return { effect: k, name: e.name, have: carried[k] || 0,
             want, fielded: e.fielded, unset,
             short: unset === 0 && (carried[k] || 0) < Math.floor(want) };
  });
}
function effectQuotasHtml(){
  const rows = effectQuotaRows();
  if (!rows) return "";
  const unset = rows[0].unset;
  return `<div class="ka-fam"><span class="ka-nb-label">Observed effect quotas — carriers per ${PLAN()}</span>
    <div class="fam-row"><span class="fam-meta">${rows.map(r => {
      const line = `${esc(r.name)}: yours ×${r.have} · observed ~${r.want}`;
      return `<span title="${esc(r.name)} — near-complete observed rosters field ~${r.want} carrier${r.want === 1 ? "" : "s"} at this size (fielded in ${Math.round(100 * r.fielded)}% of rosters)">${
        r.short ? `<b class="offcomp">${line}</b>` : line}</span>`;
    }).join(" · ")}</span></div>
    ${unset ? `<div class="ka-note">${unset} member${unset === 1 ? "" : "s"} without gear set — their chests are unknown, not counted as missing.</div>` : ""}
    <div class="ka-note">Carrier counts from near-complete observed rosters (reference-build evidence). Advice only; never changes a score.</div></div>`;
}
function observedLine(w){
  const a = cohortAffinity();
  if (!a) return "";
  const o = a.candidates.find(x => x.w === w);
  if (!o) return "";
  const lift = o.lift >= 1.15 ? `${o.lift.toFixed(1)}× pair affinity` : "no strong pair lift";
  return `<div class="obs-note"><span class="obs-k">observed killboard context · display only</span>
    <b>${o.cohorts}</b> organization cohort${o.cohorts === 1 ? "" : "s"} also fielded ${nameOf(w)} alongside ${a.minOverlap === 1 ? "your weapon" : "at least 2 of your weapons"} · ${lift}
    <small>same stated Alliance/Guild in one ${esc(a.ctx.label)} fight — not party membership, win rate, or a scoring input</small></div>`;
}
function usageLine(w){
  const u = usageOf(w);
  if (!u) return "";
  /* fight-size prevalence, battle-level count alongside the player share —
     one fight's players are correlated, not independent samples (§E) */
  const txt = u.n === 0
    ? `not seen in ${u.battles} recent ${u.label}-size fights`
    : `on ${u.pct.toFixed(u.pct < 1 ? 1 : 0)}% of ${u.players} observed combatants` +
      `${u.inBattles ? ` (in ${u.inBattles} of ${u.battles} fights)` : ` across ${u.battles} fights`}`;
  return `<div class="fieldnote">equipment prevalence, ${esc(u.label)}-size fights — ${txt}
    <span>(${esc((USAGE.generated_utc || "").slice(0, 10))}, killboard; fight size ≠ party size; not a build recommendation)</span></div>`;
}

/* ------------------------------------------------------ weapon dossier
   Live art: when online, the dossier hot-loads the official full-res
   render + spell icons (render.albiononline.com, the sanctioned community
   CDN); offline or blocked, onerror quietly falls back to the inlined
   icon / hides the spell icon. Item ids and spell UniqueNames are
   repo-controlled strings, safe in URLs. */
const RENDER_BASE = "https://render.albiononline.com/v1";
function heroArt(w, size){
  const item = typeof ITEMS !== "undefined" && ITEMS[w];
  const fallback = icon(w, size);
  if (!item) return fallback;
  return `<span class="hero-art" style="width:${size}px;height:${size}px">${fallback}
    <img src="${RENDER_BASE}/item/${item}.png?size=217&quality=4" width="${size}" height="${size}"
      alt="" loading="lazy" onerror="this.remove()"></span>`;
}
const spellIcon = sid =>
  `<img class="sp-ic" src="${RENDER_BASE}/spell/${sid}.png?size=40" width="20" height="20"
     alt="" loading="lazy" onerror="this.remove()">`;

/* Content affinity: how this weapon rates as the OPENING pick into an
   empty party, per content template (balanced style, base size) — the
   apples-to-apples "where does this weapon live" comparison. Computed once
   from the same engine that powers everything else, so it can never
   disagree with the planner. */
let AFFINITY = null;
function affinity(){
  if (AFFINITY) return AFFINITY;
  AFFINITY = {};
  for (const c of Object.keys(DATASET.templates)){
    const e2 = new CompEngine(DATASET, c);
    const rows = e2.recommend([], Object.keys(WEAPONS).length);
    const top = rows[0].score || 1;
    const m = {};
    rows.forEach((r, i) => { m[r.weapon] = { rank: i + 1, score: r.score, top }; });
    AFFINITY[c] = m;
  }
  return AFFINITY;
}
function affinityRows(w){
  const a = affinity();
  return Object.entries(DATASET.templates).map(([c, t]) => {
    const e = a[c][w] || { rank: 0, score: 0, top: 1 };
    const pct = Math.max(2, Math.round(100 * Math.max(0, e.score) / e.top));
    const tier = e.rank <= 12 ? "prime" : e.rank <= 45 ? "solid" : e.rank <= 90 ? "situational" : "fringe";
    return `<div class="aff ${c === CONTENT ? "here" : ""}">
      <span class="aff-name">${esc(t.name)}</span>
      <span class="aff-rank mono" title="opening-pick rank of ${Object.keys(WEAPONS).length} weapons">#${e.rank}</span>
      <span class="aff-tier ${tier}">${tier}</span>
      <span class="aff-bar"><i style="width:${pct}%"></i></span>
    </div>`;
  }).join("");
}
/* field reports across every fight-size bucket, not just the current one */
function usageAllBuckets(w){
  if (typeof USAGE === "undefined" || !USAGE.buckets) return "";
  const rows = ["small", "mid", "large"].map(k => {
    const m = (USAGE.meta || {})[k];
    if (!m || m.players_attributed < 200) return "";
    const n = (USAGE.buckets[k] || {})[w] || 0;
    const pct = 100 * n / m.players_attributed;
    return `<div class="ub"><span class="ub-k">${USAGE_BUCKET_LABEL[k]}</span>
      <span class="ub-bar"><i style="width:${Math.min(100, pct * 8)}%"></i></span>
      <span class="ub-v mono">${n ? pct.toFixed(1) + "%" : "—"}</span></div>`;
  }).join("");
  return rows ? `<h4>Equipment prevalence — share of observed combatants, by fight size</h4>
    <div class="ub-rows">${rows}</div>
    <div class="ub-note">killboard sample; fight size ≠ party size; prevalence ≠ effectiveness; display only — never feeds the scoring</div>` : "";
}

function loVariants(w){
  /* caller loadouts for this weapon: current content first, then others */
  const out = [];
  for (const [ct, m] of Object.entries(typeof LOADOUTS !== "undefined" ? LOADOUTS : {}))
    (m[w] || []).forEach(v => out.push({...v, ct}));
  return out.sort((a,b) => (a.ct === CONTENT ? -1 : 0) - (b.ct === CONTENT ? -1 : 0));
}
function spellAt(w, slot, idx){
  const pool = ((typeof SPELLS !== "undefined" && SPELLS[w]) || {})[slot] || [];
  const e = pool[idx - 1];
  return e ? e[1] : `#${idx}`;
}
function spellNameById(w, slot, sid){
  const pool = ((typeof SPELLS !== "undefined" && SPELLS[w]) || {})[slot] || [];
  const hit = pool.find(p => p[0] === sid);
  return hit ? hit[1] : sid;
}
/* one renderer for the "Q# name · W# name · P# name" build line — resolved
   spell UniqueNames are authoritative; the source's raw 1-based index is
   display data; a field the source never stated renders as UNKNOWN, never
   silently as option 1 (§C). */
const loLine = (w, v) => ["q", "w", "passive"].map(slot => {
  const label = slot === "passive" ? "P" : slot.toUpperCase();
  const idx = {q: v.q, w: v.w, passive: v.p}[slot];
  const sid = (v.spells || {})[slot];
  if (Number.isInteger(idx)) return `${label}${idx} ${esc(spellAt(w, slot, idx))}`;
  if (sid) return `${label} ${esc(spellNameById(w, slot, sid))}`;
  return `${label} <i class="lo-unknown">unknown</i>`;
}).join(" · ");
/* provenance line for a displayed build (§G): source, revision/date, patch,
   party size, approval + canonical basis, explicit fallbacks, confidence by
   dimension, unresolved fields. */
function loProvenance(v){
  const bits = [];
  if (v.source && (v.source.kind || v.source.author))
    bits.push(esc([v.source.kind, v.source.author &&
      `“${v.source.author}”`].filter(Boolean).join(" ")));
  if (v.published) bits.push(esc(String(v.published)));
  if (v.patch) bits.push(`patch ${esc(String(v.patch))}`);
  if (v.party_size)
    bits.push(`party ${v.party_size.min}${v.party_size.max !== v.party_size.min
      ? "–" + v.party_size.max : ""}`);
  if (v.approval)
    bits.push(esc(v.approval) + (v.canonical
      ? ` · canonical (${esc(v.canonical_basis || "")})`
      : v.canonical_for_fallback ? " · canonical in its own content" : ""));
  if (v.fallback_from) bits.push(`<b>fallback from ${esc(v.fallback_from)}</b>`);
  if (v.size_fallback) bits.push("<b>size range differs from this party</b>");
  const conf = Object.entries(v.confidence || {})
    .filter(([, x]) => typeof x === "number")
    .map(([k, x]) => `${esc(k.replace(/_/g, " "))} ${x}`);
  if (conf.length) bits.push(`confidence: ${conf.join(", ")}`);
  const unk = (v.unknowns || []).concat(v.quarantined_fields || []);
  if (unk.length) bits.push(`unresolved: ${esc(unk.join(", "))}`);
  return bits.join(" · ");
}
/* ---- item stats bank (pipeline/fetch_item_stats.py) --------------------
   The game's own numbers. These are BASE values: the dumps are tier-invariant
   per line and the in-game figure is base x f(itempower, quality, enchant), a
   curve the dumps do not carry — so the item-power ladder is shown next to
   them rather than folded into them. Reference only; scoring never reads it. */
const STAT_LABEL = {
  attackdamage:"Attack damage", attackspeed:"Attack speed", attackrange:"Range",
  attacktype:"Attack type", twohanded:"Two-handed", abilitypower:"Ability power",
  activespellslots:"Active spell slots", passivespellslots:"Passive slots",
  physicalarmor:"Physical armor", magicresistance:"Magic resistance",
  crowdcontrolresistance:"CC resistance", hitpointsmax:"Max health",
  hitpointsregenerationbonus:"Health regen", energymax:"Max energy",
  energyregenerationbonus:"Energy regen", energycostreduction:"Energy cost −",
  movespeed:"Move speed", movespeedbonus:"Move speed +",
  attackspeedbonus:"Attack speed +", magiccooldownreduction:"Cooldown −",
  magiccasttimereduction:"Cast time −", healbonus:"Heal bonus",
  healmodifier:"Heal modifier", threatbonus:"Threat", maxload:"Max load",
  masterymodifier:"Mastery", focusfireprotectionpenetration:"Focus-fire pen",
  physicalspelldamagebonus:"Phys spell dmg +", magicspelldamagebonus:"Magic spell dmg +",
  physicalattackdamagebonus:"Phys attack dmg +", magicattackdamagebonus:"Magic attack dmg +",
  bonusccdurationvsplayers:"CC duration vs players", bonusdefensevsplayers:"Defense vs players",
  weight:"Weight", durability:"Durability", nutrition:"Nutrition",
  dummyitempower:"Item power", consumespell:"Effect spell",
};
const statLabel = k => STAT_LABEL[k] || k.replace(/([a-z])([A-Z])/g, "$1 $2");
function statsBlock(key){
  const e = (typeof ITEM_STATS !== "undefined" && ITEM_STATS[key]) || null;
  if (!e) return "";
  const rows = Object.entries(e.stats || {})
    .map(([k, v]) => `<tr><td>${esc(statLabel(k))}</td><td class="sc">${esc(String(v))}</td></tr>`);
  /* a stat that genuinely differs per tier is shown as its range, not averaged */
  Object.entries(e.by_tier || {}).forEach(([k, per]) => {
    const vals = Object.values(per);
    rows.push(`<tr><td>${esc(statLabel(k))}</td><td class="sc">${esc(String(vals[0]))} – ${esc(String(vals[vals.length-1]))}
      <span class="st-note">by tier</span></td></tr>`);
  });
  if (!rows.length) return "";
  const ip = Object.entries(e.ip || {}).map(([t, v]) => `T${t} <b>${v}</b>`).join(" · ");
  return `<h4>Game stats <span class="h4-note">(base values — in game these scale with item power)</span></h4>
    <table class="ev-tbl st-tbl"><tbody>${rows.join("")}</tbody></table>
    ${ip ? `<div class="st-ip">item power — ${ip}</div>` : ""}`;
}
function renderDetail(w){
  if (DETAIL_W !== w) DETAIL_SPELL = null;   /* new weapon, fold open panels */
  DETAIL_W = w;
  const d = WEAPONS[w], sp = (typeof SPELLS !== "undefined" && SPELLS[w]) || {};
  const vars = loVariants(w);
  const picks = { q: new Set(), w: new Set(), passive: new Set() };
  vars.filter(v => v.ct === CONTENT).forEach(v => {
    if (Number.isInteger(v.q)) picks.q.add(v.q);
    if (Number.isInteger(v.w)) picks.w.add(v.w);
    if (Number.isInteger(v.p)) picks.passive.add(v.p);
  });
  const pool = (slot, label) => {
    const rows = (sp[slot] || []).map(([sid, nm], i) =>
      `<li class="sp-row ${picks[slot] && picks[slot].has(i+1) ? "pick" : ""}${DETAIL_SPELL === sid ? " open" : ""}"
           data-spellinfo="${sid}" role="button" tabindex="0"
           aria-expanded="${DETAIL_SPELL === sid}"
           title="click for this ability's effects, numbers and PvP interactions">
         <span class="idx">${slot === "e" ? "E" : slot[0].toUpperCase() + (i+1)}</span>
         ${spellIcon(sid)}<span>${esc(nm)}</span>
         ${picks[slot] && picks[slot].has(i+1) ? '<span class="idx">caller pick</span>' : ""}
       </li>${DETAIL_SPELL === sid ? `<li class="sp-detail">${spellFactsBlock(sid)}</li>` : ""}`).join("");
    return rows ? `<h4>${label}</h4><ul class="sp-list">${rows}</ul>` : "";
  };
  const caps = Object.entries(d.capabilities || {}).sort((a,b) => b[1]-a[1]).map(([c, v]) =>
    `<tr><td><button class="cap-name" data-cap="${c}">${c}</button></td><td class="sc">${v}</td>
     <td>${((d.evidence || {})[c] || []).map(e => `<span class="sp">${esc(e)}</span>`).join(", ")}</td></tr>`).join("");
  /* fallback copies of the same build under other contents would repeat
     here — list each build once, under its home content */
  const homeVars = vars.filter(v => !v.fallback_from);
  const lo = homeVars.length ? `<div class="lo-box">
      <div class="who">recorded builds</div>
      ${homeVars.map(v => `<div>${esc(v.caller)}${v.role ? " · " + esc(v.role) : ""}${v.ct !== CONTENT ? ` · <i>${esc((DATASET.templates[v.ct] || {name: v.ct}).name)}</i>` : ""} —
        ${loLine(w, v)}
        <div class="fieldnote">${loProvenance(v)}</div></div>`).join("")}
    </div>` : "";
  $("drawer-title").textContent = d.display_name;
  $("drawer-body").innerHTML = `
    <div class="dt-head">${heroArt(w, 84)}
      <div class="dt-id">
        <b>${nameOf(w)}</b>${badgeHtml(w)}
        <span class="fn">${esc(TREE_NAMES[TREES[w]] || TREES[w] || "")} tree · ${roleOf(w)}</span>
        ${usageLine(w)}
      </div>
    </div>
    <div class="dt-grid dossier">
      <div>
        <h4>Where it lives — opening-pick rank per content
          <span class="h4-note">(balanced · base size · of ${Object.keys(WEAPONS).length} weapons)</span></h4>
        <div class="aff-rows">${affinityRows(w)}</div>
        ${usageAllBuckets(w)}
        <h4>Capabilities — click one for party-wide evidence</h4>
        <table class="ev-tbl"><tbody>${caps}</tbody></table>
      </div>
      <div>${pool("e", "E — the identity")}${pool("q", "Q options")}${pool("w", "W options")}${pool("passive", "Passives")}${interactionBlock(w)}${lo}${statsBlock(w)}</div>
    </div>`;
  $("drawer").dataset.open = "true";
}
/* Per-ability facts panel (2026-08-19): every effect the game data states
   for a spell — typed effects from the structured effect layer, the
   resolved description carrying the game's own numbers (damage, CC
   durations, radii), cooldown/range facts, and the PvP interaction record
   (reflect / party stacking). BASE-value honesty: in-game numbers scale
   with item power and the scaling curve is not in the public game files,
   so the panel says so instead of inventing it. */
let DETAIL_W = null, DETAIL_SPELL = null;
function spellFactsBlock(sid){
  const f = (typeof SPELL_FACTS !== "undefined" && SPELL_FACTS[sid]) || null;
  if (!f) return `<div class="fn">no game-data facts recorded for this ability</div>`;
  const facts = [];
  if (f.cd !== undefined && +f.cd > 0) facts.push(`cooldown ${f.cd}s`);
  if (f.cr !== undefined && +f.cr > 0) facts.push(`cast range ${f.cr}m`);
  if (f.r !== undefined) facts.push(`radius ${f.r}m`);
  if (f.mt !== undefined) facts.push(`max targets ${f.mt}`);
  if (f.ct !== undefined && +f.ct > 0) facts.push(`cast time ${f.ct}s`);
  const fx = (f.fx || []).map(t => {
    const cut = t.indexOf(">");
    const eff = cut < 0 ? t : t.slice(0, cut);
    const tgt = cut < 0 ? "" : t.slice(cut + 1);
    return `<span class="fx-chip" title="typed effect extracted from the game's structured spell data">${esc(eff)}${tgt ? " → " + esc(tgt) : ""}</span>`;
  }).join("");
  const rec = (typeof INTERACTIONS !== "undefined") ? INTERACTIONS[sid] : null;
  const inter = rec
    ? `<div class="sp-inter">${(rec.badges || []).map(b =>
        `<span class="bdg b-int" title="${esc(intBadgeTip(b))}">${esc(b)}</span>`).join(" ")}
       <span class="prov${rec.confidence === "verified" ? "" : " draft"}"
         title="${esc(rec.source || "no source recorded")}">${esc(rec.confidence)}</span>
       <span class="fn">reflect / party-stacking components in “PvP interactions” below</span></div>`
    : `<div class="fn">no curated PvP interaction record yet — duplicate and reflect behavior is unknown, never guessed</div>`;
  return `<div class="sp-facts">
    ${facts.length ? `<div class="sp-fline mono">${facts.join(" · ")}</div>` : ""}
    ${fx ? `<div class="sp-fx">${fx}</div>` : ""}
    ${f.d ? `<div class="sp-desc">${esc(f.d)}</div>` : ""}
    ${inter}
    <div class="fn">numbers are the game’s own BASE values — in-game damage and durations scale with item power; the scaling curve is not in the public game files, so it is shown as base rather than invented</div>
  </div>`;
}
/* PvP interactions section of the dossier (spec §6): per-spell badges with
   human-readable tooltips, a confidence chip carrying the source citation,
   and the component-level detail. Unknown is shown as unknown. */
function interactionBlock(w){
  const sids = INTERACTIONS_BY_WEAPON[w] || [];
  if (!sids.length) return "";
  const rows = sids.map(sid => {
    const rec = INTERACTIONS[sid];
    const badges = (rec.badges || []).map(b =>
      `<span class="bdg b-int" title="${esc(intBadgeTip(b))}">${esc(b)}</span>`).join("");
    const comps = (rec.components || []).map(c => {
      const bits = [c.kind + (c.cc_type ? ` (${c.cc_type})` : "")];
      if (c.reflect && c.reflect !== "not_applicable") bits.push(`reflect: ${c.reflect}`);
      if (c.cleanse && c.cleanse !== "not_applicable") bits.push(`cleanse: ${c.cleanse}`);
      if (c.purge && c.purge !== "not_applicable") bits.push(`purge: ${c.purge}`);
      if (c.duplicate) bits.push(`duplicate: ${c.duplicate}`);
      return `<li><b>${esc(c.id)}</b> — ${esc(bits.join(" · "))}${c.notes ? ` <i>${esc(c.notes)}</i>` : ""}</li>`;
    }).join("");
    return `<div class="int-row">
      <div>${spellIcon(sid)}<b>${esc(rec.name || sid)}</b> ${badges}
        <span class="prov${rec.confidence === "verified" ? "" : " draft"}"
          title="${esc(rec.source || "no source recorded")}">${esc(rec.confidence)}</span></div>
      ${rec.effect_name ? `<div class="fn">${esc(rec.effect_name)}</div>` : ""}
      ${comps ? `<ul class="sp-list int-comps">${comps}</ul>` : ""}
    </div>`;
  }).join("");
  return `<h4>PvP interactions <span class="h4-note">(duplicate / reflect / cleanse semantics — “unknown” means the game data does not say)</span></h4>${rows}`;
}
function renderEvidence(cap){
  const rows = party.filter(w => capsOf(w)[cap]).map(w => {
    const ev = (WEAPONS[w].evidence || {})[cap];
    return `<tr><td>${icon(w, 20)} ${nameOf(w)}</td><td class="sc">${capsOf(w)[cap]}</td>
      <td>${ev && ev.length ? ev.map(e => `<span class="sp">${esc(e)}</span>`).join(", ")
            : '<span class="pend">no evidence — illustrative sheet, blocks release</span>'}</td>
      <td class="mono" style="font-size:11px;color:var(--ink-3)">${w}</td></tr>`;
  });
  $("drawer-title").textContent = cap;
  $("drawer-body").innerHTML = rows.length
    ? `<table class="ev-tbl"><thead><tr><th>Weapon</th><th>Score</th><th>Evidence spell</th><th>Item key</th></tr></thead><tbody>${rows.join("")}</tbody></table>`
    : `<p class="ev-empty">No weapon in this party supplies <span class="mono">${esc(cap)}</span>. Supply is 0 of ${target(cap).toFixed(1)} units.</p>`;
  $("drawer").dataset.open = "true";
}
function renderMetaStrip(){
  const sec = $("meta-sec");
  /* contextual mode (PR #5): with cohort data and a party, the strip shows
     what was OBSERVED WITH the selected weapons instead of raw popularity;
     old samples and thin data fall back to the prevalence strip below */
  const a = cohortAffinity();
  const nb = cohortNeighbours();
  if (a && (a.candidates.length || nb)){
    const rows = a.candidates.slice(0, 12);
    $("meta-label").textContent =
      `Observed with your weapons — ${a.ctx.label} fights (${a.N} organization cohorts; display only)`;
    /* neighbour rosters (roadmap item 6): the observed baskets themselves,
       shared picks highlighted, the rest clickable as dossier links —
       "observed together", never "party" or "winning comp" */
    const nbHtml = !nb ? "" : `<div class="ka-nb">
      <span class="ka-nb-label">Observed rosters most like yours — ${nb.matched} cohort${nb.matched === 1 ? "" : "s"} share${nb.matched === 1 ? "s" : ""} ≥2 of your ${nb.selected.length} weapons</span>
      ${nb.rows.map(r => {
        /* baskets are unordered sets — shared picks lead, and a huge
           alliance basket caps at 14 icons with an honest "+N more" (the
           full basket is evidence, not a recommended roster to copy) */
        const shown = r.basket.filter(w => nb.selected.includes(w))
          .concat(r.others).slice(0, 14);
        const more = r.basket.length - shown.length;
        return `<div class="nb-row"><span class="nb-ov" title="${r.shared} of your ${nb.selected.length} unique weapons appear in this observed cohort of ${r.basket.length} (${Math.round(100 * r.jaccard)}% roster similarity)">${r.shared}/${nb.selected.length}</span>${
          shown.map(w => nb.selected.includes(w)
            ? `<span class="nb-w match" title="${esc(nameOf(w))} — also in your roster">${icon(w, 22)}</span>`
            : `<button class="nb-w" data-detail="${w}" title="${esc(nameOf(w))} — fielded by this cohort, not in your roster">${icon(w, 22)}</button>`).join("")
        }${more > 0 ? `<span class="nb-more">+${more} more</span>` : ""}</div>`;
      }).join("")}</div>`;
    $("meta-strip").innerHTML = rows.map((r, i) => {
      const aff = r.lift >= 1.15 ? `${r.lift.toFixed(1)}× affinity` : "baseline pairing";
      return `<div class="meta-row meta-aff"><span class="rk">${String(i+1).padStart(2,"0")}</span>${icon(r.w, 20)}
        <button class="nm-btn" data-detail="${r.w}">${nameOf(r.w)}</button>
        <span class="pct">${r.cohorts} cohorts · ${aff}</span></div>`;
    }).join("") + nbHtml + familiesHtml(false) + effectQuotasHtml() + `<div class="ka-note">Matches need ${a.minOverlap === 1 ? "your weapon" : "≥2 of your weapons"} in the same observed Alliance/Guild cohort. Family percentages are observation shares. Not party reconstruction or effectiveness data; never changes a score.</div>`;
    sec.hidden = false;
    return;
  }
  const u = usageStats();
  if (!u){ sec.hidden = true; return; }
  /* usage keys are filtered against the dataset at build time too, but a
     stale inlined file must degrade to a shorter list, not throw in nameOf
     and kill every render after a weapon rename */
  const rows = Object.entries(USAGE.buckets[u.key] || {})
    .filter(([w]) => WEAPONS[w])
    .sort((a,b) => b[1] - a[1]).slice(0, 12);
  $("meta-label").textContent =
    `Killboard equipment prevalence — ${u.label} fights (${u.m.battles} battles, ${u.m.players_attributed} observed combatants; fight size, not party size)`;
  $("meta-strip").innerHTML = rows.map(([w, n], i) =>
    `<div class="meta-row"><span class="rk">${String(i+1).padStart(2,"0")}</span>${icon(w, 20)}
      <button class="nm-btn" data-detail="${w}">${nameOf(w)}</button>
      <span class="pct">${(100 * n / u.m.players_attributed).toFixed(1)}%</span></div>`).join("")
    + familiesHtml(true) + effectQuotasHtml();
  sec.hidden = false;
}
/* ------------------------------------------------ live party (companion)
   Polls the local companion app (companion/) for the real in-game party and
   maps each member's weapon (an engine unique_name) into the comp. The
   companion serves loopback-only, and browsers exempt http://localhost from
   mixed-content blocking, so the HTTPS page can read it directly. */
const COMPANION_URL = "http://localhost:53321";
let companionOn = false, companionTimer = null, companionData = null;
let companionSig = null;

async function companionPoll(){
  if (document.hidden) return;   // no point polling a tab nobody sees
  try {
    const r = await fetch(COMPANION_URL + "/party", {cache: "no-store"});
    if (!r.ok) throw new Error("http " + r.status);
    const j = await r.json();
    /* skip the DOM rebuild when the party payload is unchanged (the ts
       field ticks every response, so compare the content, not the text) */
    const sig = JSON.stringify({ self: j.self, members: j.members });
    companionData = j;
    if (sig === companionSig) return;
    companionSig = sig;
    syncLiveComp();
    renderCompanion(true);
  } catch (e) {
    companionData = null;
    companionSig = null;
    renderCompanion(false, e.message);
  }
}
function companionRoleClass(w){
  const rh = (WEAPONS[w] && WEAPONS[w].role_hint) || "";
  return rh ? `role-${rh}` : "";
}
function renderCompanion(live, err){
  const box = $("companion"), status = $("companion-status");
  const members = $("companion-members"), load = $("companion-load"), connect = $("companion-connect");
  box.dataset.live = live ? "true" : "false";
  if (!companionOn){
    status.hidden = true; members.innerHTML = ""; load.hidden = true;
    connect.textContent = "connect live party";
    return;
  }
  connect.textContent = "disconnect";
  status.hidden = false;
  if (!live){
    /* the raw error distinguishes "not running" from a browser-side block
       (CORS / local-network permission) — without it every failure reads as
       "start the exe" even when the exe is fine */
    status.innerHTML = `<span class="comp-dot"></span>companion not reachable
      <span class="sub">${err ? esc(err) + " — " : ""}start <code>companion/run-companion.bat</code> as admin; if it IS running, check for a local-network permission prompt in the address bar — retrying…</span>`;
    members.innerHTML = ""; load.hidden = true;
    return;
  }
  const mem = companionData.members || [];
  const known = mem.filter(m => m.weapon && WEAPONS[m.weapon]);
  status.innerHTML = `<span class="comp-dot"></span>connected — ${mem.length} in party${companionData.self ? ` · you: ${esc(companionData.self)}` : ""}
    <span class="sub">${known.length} with a known weapon${mem.length > known.length ? `; ${mem.length - known.length} out of zone / unmapped` : ""}</span>`;
  members.innerHTML = mem.map(m => {
    const k = m.weapon && WEAPONS[m.weapon];
    const wpn = k ? nameOf(m.weapon) : (m.weapon ? esc(m.weapon) : "— out of zone —");
    return `<div class="comp-m ${k ? companionRoleClass(m.weapon) : ""}"><span class="cm-role"></span>
      <span class="cm-name">${esc(m.name)}</span>
      <span class="cm-wpn ${k ? "" : "unknown"}">${k ? icon(m.weapon, 26) : ""}<span>${wpn}</span></span></div>`;
  }).join("");
  load.hidden = false; load.disabled = known.length === 0;
  const syncWrap = $("companion-sync-wrap");
  if (syncWrap){
    syncWrap.hidden = LIVE_GUIDS === null;   /* appears after the first load */
    const cb = $("companion-sync");
    if (cb) cb.checked = LIVE_SYNC;
  }
}
/* ---- live sync (2026-08-23, owner: "it should be as current as possible")
   After a load, companion updates keep flowing into the comp on every poll:
   a member's weapon swap updates their slot in place, a newly visible
   weapon fills in, and the member's REAL Q/W picks (spell UniqueNames off
   the wire) map into the loadout picker so the comp scores their actual
   kit. Members are tracked by guid -> what they last contributed, so the
   role re-sort permutation needs no new parallel array, and a slot the
   user manually removed simply stops matching and stays gone. */
let LIVE_SYNC = false;
let LIVE_GUIDS = null;   /* guid -> {w, q, w2}: weapon + q/w spell ids */

function liveSpellPicks(w, spells){
  /* companion spell names -> picker indices (q/w only: the passive is not
     on the wire and the E rides the weapon). Unknown names map to nothing
     — the engine's default combo covers the gap. */
  if (!spells || typeof SPELLS === "undefined" || !SPELLS[w]) return null;
  const out = {};
  for (const slot of ["q", "w"]){
    const sid = spells[slot];
    const pool = SPELLS[w][slot] || [];
    const idx = sid ? pool.findIndex(e => e[0] === sid) : -1;
    if (idx >= 0) out[slot] = idx;
  }
  return Object.keys(out).length ? out : null;
}
const liveSig = m => ({ w: m.weapon,
                        q: (m.spells || {}).q || null,
                        w2: (m.spells || {}).w || null });

function syncLiveComp(){
  if (!LIVE_SYNC || !LIVE_GUIDS || !companionData) return;
  let changed = false;
  for (const m of (companionData.members || [])){
    if (!m.guid || !m.weapon || !WEAPONS[m.weapon]) continue;
    const sig = liveSig(m), prev = LIVE_GUIDS[m.guid];
    if (prev && prev.w === sig.w && prev.q === sig.q && prev.w2 === sig.w2)
      continue;
    const picks = liveSpellPicks(m.weapon, m.spells);
    if (prev && WEAPONS[prev.w]){
      /* the member swapped weapons or picks: update their slot in place
         (same state resets as the central data-swapat handler; no kit
         prefill — the real kit is what just arrived) */
      const i = party.findIndex((pw, ix) => pw === prev.w && PROV[ix] === "m");
      if (i !== -1){
        party[i] = m.weapon;
        COMBO[i] = null;
        LOADOUT[i] = picks || undefined;
        changed = true;
      }
    } else if (party.length < HARD_CAP){
      /* newly visible (or newly joined) member: fill them in */
      party.push(m.weapon); PROV.push("m"); COMBO.push(null);
      LOADOUT[party.length - 1] = picks || undefined;
      changed = true;
    }
    LIVE_GUIDS[m.guid] = sig;
  }
  if (changed){
    FORGE_NOTE = null; SHEET_OPEN = null;
    sortPartyByRole();
    PLANNED = Math.max(PLANNED, party.length);
    render();
  }
}

function loadCompanionParty(){
  if (!companionData) return;
  const live = (companionData.members || [])
    .filter(m => m.weapon && WEAPONS[m.weapon]).slice(0, HARD_CAP);
  if (!live.length) return;
  party = live.map(m => m.weapon);
  /* live-party members are the user's, never the forge's */
  PROV = party.map(() => "m");
  COMBO = party.map(() => null);
  FORGE_NOTE = null;
  loadoutClear();
  /* the members' REAL q/w picks score the comp from the first render */
  live.forEach((m, i) => {
    const picks = liveSpellPicks(m.weapon, m.spells);
    if (picks) LOADOUT[i] = picks;
  });
  LIVE_GUIDS = {};
  live.forEach(m => { if (m.guid) LIVE_GUIDS[m.guid] = liveSig(m); });
  LIVE_SYNC = true;
  sortPartyByRole();
  PLANNED = Math.max(PLANNED, party.length);
  render();
  renderCompanion(true);
}
function toggleCompanion(){
  companionOn = !companionOn;
  /* reset the skip-unchanged signature on every toggle: after a manual
     disconnect/reconnect the first poll must re-render the connected state
     even when the party payload is identical to before */
  companionSig = null;
  if (companionOn){ companionPoll(); companionTimer = setInterval(companionPoll, 5000); }
  else { clearInterval(companionTimer); companionTimer = null; companionData = null; renderCompanion(false); }
}

function render(){
  syncEngine(); saveHash();
  const recs = party.length < HARD_CAP ? recommend(party, 4) : null;
  RECS_CUR = recs;
  /* every roster/context change re-aims the wheel at the engine's pick;
     browsing between changes belongs to the user (wheelStep) */
  if (recs && recs.length) WHEEL_FOCUS_W = recs[0].w;
  renderSetup(); renderRoster(); renderFitness();
  renderWheel(recs); renderGroups(); renderWeaknesses(); renderWarning();
  renderRecDetail(recs); renderMetaStrip(); renderFootnote();
}

function compText(){
  const sn = styleName();
  const lines = [
    `**${tpl().name}${sn ? " · " + sn : ""}** — ${party.length}/${SIZE} — fitness ${fitness(party).toFixed(1)}/${maxFitness().toFixed(0)}`,
    Object.entries(roleCounts()).sort((a,b) => b[1]-a[1]).map(([r,n]) => `${n} ${r}`).join(" · "),
    "",
  ];
  party.forEach((w,i) => lines.push(
    `${String(i+1).padStart(2,"0")}  ${WEAPONS[w].display_name}  (${roleOf(w)})`));
  const s = supply(party);
  const gaps = weaknesses(party, 3).filter(x => x.gap >= 0.5)
    .map(x => `${x.cap} ${(s[x.cap]||0).toFixed(0)}/${target(x.cap).toFixed(0)}`);
  if (gaps.length) lines.push("", `still needs: ${gaps.join(", ")}`);
  lines.push("", location.href);
  return lines.join("\n");
}
function flashBtn(id, text, back){
  $(id).textContent = text;
  setTimeout(() => { $(id).textContent = back; }, 1400);
}

/* Collapsible setup rail: state on .shell[data-rail], persisted so the
   layout choice survives reloads. Display only. */
const RAIL_KEY = "compforge.rail";
function setRail(min){
  $("shell").dataset.rail = min ? "min" : "";
  $("rail-toggle").setAttribute("aria-expanded", String(!min));
  try { localStorage.setItem(RAIL_KEY, min ? "min" : ""); } catch (e) { /* private mode */ }
}

document.addEventListener("click", e => {
  /* loadout layer first: its controls live inside party rows, so a later
     [data-remove]/[data-detail] match must not swallow them */
  if (loadoutHandleClick(e)){ render(); return; }
  /* member bottom sheet (≤960 only — desktop keeps the hover popover).
     data-member sits on the CARD; the popover is its sibling, so taps on
     the sheet's own kit/dossier/remove buttons never re-toggle it */
  const mem = e.target.closest("[data-member]");
  if (mem && matchMedia("(max-width:960px)").matches){
    const i = +mem.dataset.member;
    SHEET_OPEN = SHEET_OPEN === i ? null : i;
    /* the board lives in the wheel foot now — refresh it with cached recs */
    renderRoster(); renderWheel(RECS_CUR); return;
  }
  if (e.target.closest("[data-sheet-close]")){
    SHEET_OPEN = null; renderRoster(); renderWheel(RECS_CUR); return;
  }
  const bf = e.target.closest("[data-bfilter]");
  if (bf){ setFacet({type: "badge", v: bf.dataset.bfilter},
                    !bf.closest("#picker-chips")); return; }
  const rf = e.target.closest("[data-rfilter]");
  if (rf){ setFacet({type: "role", v: rf.dataset.rfilter},
                    !rf.closest("#picker-chips")); return; }
  const uf = e.target.closest("[data-ufilter]");
  if (uf){ setFacet({type: "util", v: uf.dataset.ufilter},
                    !uf.closest("#picker-chips")); return; }
  if (e.target.closest("#facet-clear")){ setFacet(null); return; }
  const sw = e.target.closest("[data-swapat]");
  if (sw){
    const si = +sw.dataset.swapat;
    party[si] = sw.dataset.swapto;
    COMBO[si] = null;      /* the new weapon resolves its own loadout */
    LOADOUT[si] = undefined;   /* old spell-pick indices would misread
                                  against the new weapon's pools */
    loadoutPrefill(si);    /* same start as a fresh add: caller reference */
    PROV[si] = "m";        /* an explicit user choice is manual, even in a
                              formerly forged slot */
    FORGE_NOTE = null;
    sortPartyByRole();     /* the swap may have changed the slot's role */
    render(); return;
  }
  /* rim card click = focus it (adding stays a deliberate hub action) */
  const wf = e.target.closest("[data-wfocus]");
  if (wf){ WHEEL_FOCUS_W = wf.dataset.wfocus; renderWheel(RECS_CUR); return; }
  const spi = e.target.closest("[data-spellinfo]");
  if (spi){
    DETAIL_SPELL = DETAIL_SPELL === spi.dataset.spellinfo
      ? null : spi.dataset.spellinfo;
    if (DETAIL_W) renderDetail(DETAIL_W);
    return;
  }
  const det = e.target.closest("[data-detail]");
  if (det){ renderDetail(det.dataset.detail); return; }
  const add = e.target.closest("[data-add]");
  if (add){ if (party.length < HARD_CAP){
    party.push(add.dataset.add);
    PROV.push("m"); COMBO.push(null); FORGE_NOTE = null;
    loadoutInsert(party.length - 1);   /* prefill from the caller reference */
    sortPartyByRole();    /* the new member lands in its role group */
    render(); } return; }
  const fl = e.target.closest("[data-family-load]");
  if (fl){
    /* observed-core loader (2026-08-24): the family's anchor pair joins as
       MANUAL picks through the same mutation path as data-add — the engine
       scores them like any manual choice (off-style / redundancy flags
       apply as usual) and the forge completes the rest. Observed data
       PROPOSES a starting point; the engine still disposes. Copies already
       in the roster are not duplicated. */
    let added = false;
    fl.dataset.familyLoad.split(",").forEach(w => {
      if (!WEAPONS[w] || party.length >= HARD_CAP || party.includes(w)) return;
      party.push(w); PROV.push("m"); COMBO.push(null);
      loadoutInsert(party.length - 1);
      added = true;
    });
    if (added){
      FORGE_NOTE = null; sortPartyByRole(); render();
    }
    return;
  }
  const forgeBtn = e.target.closest("#forge") || e.target.closest("#reforge")
                || e.target.closest("#forge-rail") || e.target.closest("#forge-rail-mini");
  if (forgeBtn){
    /* Deterministic constrained beam search in the engine (2026-08-18) —
       greedy top-1 append + a 1-opt pass used to force-fill negative-value
       bodies and treated every forged slot as manual afterwards.
       "forge the rest" locks every current member; "reforge all" keeps
       only the manual/live slots and rebuilds the rest for the CURRENT
       content, style and size. The rail's "forge full comp" fills open
       slots, and on a fully forged roster acts as a reforge. */
    const goal = Math.min(PLAN(), HARD_CAP);
    const reforgeAll = forgeBtn.id === "reforge"
      || ((forgeBtn.id === "forge-rail" || forgeBtn.id === "forge-rail-mini")
          && party.length >= goal && PROV.some(x => x === "f"));
    const keep = party.map((_, i) => i)
      .filter(i => reforgeAll ? PROV[i] !== "f" : true);
    const locked = keep.map(i => party[i]);
    const lockedCombos = keep.map(i => comboAt(i));
    const lockedLoadouts = keep.map(i => LOADOUT[i]);
    const lockedProv = keep.map(i => PROV[i] || "m");
    if (locked.length >= goal && !reforgeAll){ return; }
    const lockedStored = keep.map(i => COMBO[i]);
    /* Forge under the TARGET-size context (2026-08-24 fix): the engine is
       normally judged at roster size (owner ruling 2026-08-21), but every
       generation gate — single-target-E, cost, style, healer, per-weapon
       dup allowances, size physics — keys off the size being BUILT. A
       2-member roster forging to 20 used to run the whole search under
       trio rules, so ST-E dps and gang-only picks generated into ZvZ
       comps (surfaced by the observed-core loader; every Python/test
       forge constructs the engine at target size, which is why 21/21
       forge + parity stayed green over it). Restore mirrors inPickContext;
       render()'s syncEngine re-judges the new roster anyway. */
    const forgeSize = Math.max(goal, locked.length);
    let r;
    ENG.setContent(CONTENT, forgeSize, STYLE);
    try { r = ENG.forge(forgeSize, locked, lockedCombos); }
    finally { ENG.setContent(CONTENT, SIZE, STYLE); }
    party = r.party.slice();
    /* locked members keep only their EXPLICIT stored combos — pick-derived
       resolutions must keep re-resolving under future context changes
       (review 2026-08-18) */
    COMBO = lockedStored.slice();
    LOADOUT = lockedLoadouts.slice();
    PROV = lockedProv.slice();
    for (let i = locked.length; i < party.length; i++){
      PROV[i] = "f";
      COMBO[i] = r.combos[i];
      LOADOUT[i] = undefined;
      /* the kit the forge actually VALUED lands first (dressed forge
         2026-08-27: r.gears[i] is the chosen doctrine-kit variant, part
         of the score) marked as engine picks; the caller reference then
         fills only the slots the search left unset; SPELLS from the
         combo the forge scored — the kit shown is the kit valued */
      if (r.gears && r.gears[i] && r.gears[i].length){
        const L = (LOADOUT[i] = { _eng: 1 });
        for (const k of r.gears[i]){
          const g = ENG.gear[k];
          if (g && g.slot) L[g.slot] = k;
        }
      }
      loadoutPrefillGear(i);
      loadoutApplySpells(i, r.combos[i]);
    }
    FORGE_NOTE = { feasible: r.feasible, filler: r.filler, held: r.held };
    LO_OPEN = null; LO_PICKING = null;
    sortPartyByRole();    /* remaps the forge note's slot indexes too */
    render();
    /* the forge flourish: the wheel spins and settles on the engine's next
       pick. Purely visual — reduced-motion kills it via the global rule. */
    const wheelEl = $("wheel");
    wheelEl.classList.remove("spun");
    void wheelEl.offsetWidth;
    wheelEl.classList.add("spun");
    return;
  }
  const rm = e.target.closest("[data-remove]");
  if (rm){
    const ri = +rm.dataset.remove;
    party.splice(ri, 1); PROV.splice(ri, 1); COMBO.splice(ri, 1);
    FORGE_NOTE = null; SHEET_OPEN = null;
    loadoutRemove(ri); render(); return;
  }
  if (e.target.closest("#rail-toggle")){ setRail(true); return; }
  if (e.target.closest("#rail-expand") || e.target.closest("#rail-expand-setup")){
    setRail(false); return; }
  if (e.target.closest("#msetup")){
    /* phone setup summary bar: expands/collapses the full setup controls */
    const s = $("shell"), open = s.dataset.msetup === "open";
    if (open) delete s.dataset.msetup; else s.dataset.msetup = "open";
    $("msetup").setAttribute("aria-expanded", String(!open));
    return;
  }
  if (e.target.closest("#companion-connect")){ toggleCompanion(); return; }
  if (e.target.closest("#companion-load")){ loadCompanionParty(); return; }
  if (e.target.closest("#clear")){
    /* two-step: first click arms, second within 2.2s clears — a misclick
       must never wipe a 20-slot comp */
    const b = $("clear");
    if (b.dataset.armed === "1"){
      delete b.dataset.armed; b.textContent = "clear comp";
      party = []; PROV = []; COMBO = []; FORGE_NOTE = null;
      loadoutClear(); render();
    } else {
      b.dataset.armed = "1"; b.textContent = "really clear? click again";
      setTimeout(() => { delete b.dataset.armed; b.textContent = "clear comp"; }, 2200);
    }
    return;
  }
  const sz = e.target.closest("[data-size]");
  if (sz){ PLANNED = +sz.dataset.size; FORGE_NOTE = null; render(); return; }
  if (e.target.closest("#size-minus")){ PLANNED = Math.max(2, PLANNED - 1); FORGE_NOTE = null; render(); return; }
  if (e.target.closest("#size-plus")){ PLANNED = Math.min(HARD_CAP, PLANNED + 1); FORGE_NOTE = null; render(); return; }
  const cap = e.target.closest("[data-cap]");
  if (cap){ renderEvidence(cap.dataset.cap); return; }
  if (e.target.closest("#share")){
    saveHash();
    if (navigator.clipboard && navigator.clipboard.writeText)
      navigator.clipboard.writeText(location.href).then(() =>
        flashBtn("share", "copied", "copy share link"));
    return;
  }
  if (e.target.closest("#export")){
    if (navigator.clipboard && navigator.clipboard.writeText)
      navigator.clipboard.writeText(compText()).then(() =>
        flashBtn("export", "copied", "copy comp text"));
    return;
  }
  if (e.target.closest("#drawer-close")){ $("drawer").dataset.open = "false"; return; }
  if (!e.target.closest("#drawer")) $("drawer").dataset.open = "false";
});
document.addEventListener("change", e => {
  if (loadoutHandleChange(e)){
    /* a user spell pick takes over the member's loadout: drop any stored
       forge combo so scoring follows the picker (2026-08-18) */
    const sel = e.target.closest("[data-lo-spell]");
    if (sel) COMBO[+sel.dataset.loSpell.split(":")[0]] = null;
    render(); return;
  }
  if (e.target.id === "content"){
    CONTENT = e.target.value; PLANNED = baseSize();
    /* manual/live members SURVIVE a content switch (2026-08-18); slots the
       forge generated were built for the OLD template and are dropped —
       "reforge all" or "forge the rest" rebuilds them for the new one. */
    const keep = party.map((_, i) => i).filter(i => PROV[i] !== "f");
    party = keep.map(i => party[i]);
    LOADOUT = keep.map(i => LOADOUT[i]);
    COMBO = keep.map(i => COMBO[i]);
    PROV = keep.map(() => "m");
    FORGE_NOTE = null; LO_OPEN = null; LO_PICKING = null;
    render();
  }
  if (e.target.id === "style"){ STYLE = e.target.value; FORGE_NOTE = null; render(); }
  if (e.target.id === "companion-sync"){
    LIVE_SYNC = e.target.checked;
    if (LIVE_SYNC) syncLiveComp();
  }
  if (e.target.id === "tree-filter"){ treeFilter = e.target.value; renderWheel(RECS_CUR); }
  if (e.target.id === "size-input"){
    const v = Math.round(+e.target.value);
    if (v >= 2 && v <= HARD_CAP){ PLANNED = v; FORGE_NOTE = null; render(); }
    else { e.target.value = PLANNED; }
  }
});
document.addEventListener("input", e => {
  if (loadoutHandleInput(e)){
    /* the filter box lives inside the party list, so render() replaces the
       node the user is typing in — put the caret back where it was */
    const at = e.target.selectionStart;
    render();
    const box = $("lo-filter");
    if (box){ box.focus(); try { box.setSelectionRange(at, at); } catch (err) { /* type=search */ } }
    return;
  }
  if (e.target.id === "pick-filter"){ pickFilter = e.target.value; renderWheel(RECS_CUR); }
});
document.addEventListener("keydown", e => {
  if ((e.key === "Enter" || e.key === " ")
      && e.target.matches("[data-bfilter],[data-rfilter],[data-ufilter],[data-pfilter],[data-spellinfo],span.info[data-detail]")){
    /* the picker's "i" detail control is a focusable role=button SPAN inside
       the add-weapon button — without this it is announced as a button but
       Enter/Space do nothing (and would otherwise trigger the outer add) */
    e.preventDefault(); e.target.click(); return;
  }
  if (e.key === "Escape"){ $("drawer").dataset.open = "false"; return; }
  /* "/" jumps to the weapon filter from anywhere outside a text field */
  if (e.key === "/" && !e.target.closest("input,select,textarea")){
    e.preventDefault(); $("pick-filter").focus();
  }
});
/* Enter in the filter adds the top match — repeatable for duplicate picks */
$("pick-filter").addEventListener("keydown", e => {
  if (e.key !== "Enter") return;
  const keys = filteredWeapons();
  if (keys.length && party.length < HARD_CAP){
    party.push(keys[0]); PROV.push("m"); COMBO.push(null); FORGE_NOTE = null;
    loadoutInsert(party.length - 1); sortPartyByRole(); render(); }
});
/* ---- wheel inputs: scroll, arrow keys, and drag all rotate the rim ---- */
(function wheelInputs(){
  const el = $("wheel");
  el.addEventListener("wheel", e => {
    e.preventDefault();
    stopFling();
    wheelStep((e.deltaY || e.deltaX) > 0 ? 1 : -1);
  }, {passive: false});
  el.addEventListener("keydown", e => {
    if (e.key === "ArrowRight" || e.key === "ArrowDown"){ e.preventDefault(); stopFling(); wheelStep(1); }
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp"){ e.preventDefault(); stopFling(); wheelStep(-1); }
    else if (e.key === "Home" || e.key === "End"){
      e.preventDefault();
      const keys = filteredWeapons();
      if (keys.length){
        WHEEL_FOCUS_W = keys[e.key === "Home" ? 0 : keys.length - 1];
        renderWheel(RECS_CUR);
      }
    } else if ((e.key === "Enter" || e.key === " ") && !e.target.closest("button")){
      e.preventDefault();
      const btn = $("hub-body").querySelector("[data-add]");
      if (btn) btn.click();
    }
  });
  /* drag-to-rotate with casino momentum (owner 2026-08-21): track the
     pointer's angle around the wheel center; every step-angle crossed
     shifts the focus one card (clockwise drag brings the 11-o'clock card
     under the notch, focus − 1). Releasing with speed FLINGS the wheel:
     the measured angular velocity decays exponentially, stepping cards as
     degrees accumulate — steps are batched per frame, so a hard spin
     still costs one render per frame. Grabbing the wheel (or scrolling /
     arrow keys) stops the spin; reduced-motion users get no fling. */
  let dragBase = null, lastA = null, dragTotal = 0, flingTimer = 0;
  const samples = [];   /* [time, cumulative degrees] within ~120ms */
  const angleOf = e => {
    /* the semicircle box is not square: the virtual wheel center sits one
       half-WIDTH below the top (the ring is a --wd circle anchored there) */
    const b = el.getBoundingClientRect();
    return Math.atan2(e.clientY - (b.top + b.width / 2),
                      e.clientX - (b.left + b.width / 2)) * 180 / Math.PI;
  };
  const stopFling = () => {
    if (flingTimer){ clearTimeout(flingTimer); flingTimer = 0; }
  };
  const fling = v0 => {
    /* v0 in deg/ms; tau sets the coast length — a strong flick travels
       roughly v0*tau degrees (a dozen-plus cards) before settling.
       Timer-driven, not rAF: the loop paints nothing itself (the card
       glide is CSS transitions) — it only has to fire steps on time,
       and rAF starves when frames coalesce. */
    let v = Math.max(-2.5, Math.min(2.5, v0));
    let acc = 0, last = performance.now();
    const tau = 450;
    const tick = () => {
      const now = performance.now();
      const dt = Math.min(48, Math.max(1, now - last)); last = now;
      acc += v * dt;
      v *= Math.exp(-dt / tau);
      const stepDeg = wheelStepDeg();
      const steps = Math.trunc(acc / stepDeg);
      if (steps){ acc -= steps * stepDeg; wheelStep(-steps); }
      flingTimer = Math.abs(v) > 0.02 ? setTimeout(tick, 16) : 0;
    };
    flingTimer = setTimeout(tick, 16);
  };
  el.addEventListener("pointerdown", e => {
    stopFling();   /* grabbing a spinning wheel stops it, wherever you touch */
    if (e.target.closest(".wheel-hub") || e.target.closest("button")) return;
    dragBase = angleOf(e); lastA = dragBase;
    dragTotal = 0; samples.length = 0;
    samples.push([performance.now(), 0]);
    el.setPointerCapture(e.pointerId);
  });
  el.addEventListener("pointermove", e => {
    if (dragBase === null) return;
    const a = angleOf(e);
    let da = a - lastA;
    if (da > 180) da -= 360;
    if (da < -180) da += 360;
    lastA = a; dragTotal += da;
    const now = performance.now();
    samples.push([now, dragTotal]);
    while (samples.length > 2 && now - samples[0][0] > 120) samples.shift();
    let d = a - dragBase;
    if (d > 180) d -= 360;
    if (d < -180) d += 360;
    const stepDeg = wheelStepDeg();
    const steps = Math.trunc(d / stepDeg);
    if (steps){ dragBase += steps * stepDeg; wheelStep(-steps); }
  });
  ["pointerup", "pointercancel"].forEach(t =>
    el.addEventListener(t, e => {
      if (dragBase === null) return;
      dragBase = null;
      if (t === "pointercancel") return;
      if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      const now = performance.now();
      const [t0, a0] = samples[0] || [now, dragTotal];
      const dt = now - t0;
      const v = dt > 15 ? (dragTotal - a0) / dt : 0;
      if (Math.abs(v) > 0.25) fling(v);
    }));
  /* one-shot cleanup for the forge spin class */
  el.addEventListener("animationend", () => el.classList.remove("spun"));
})();
/* A pasted share-link hash applies without a reload. saveHash() uses
   replaceState, which never fires hashchange, so this cannot loop. The
   party view-filter resets — it described the previous comp. */
window.addEventListener("hashchange", () => {
  if (loadHash()){ render(); }
});

$("build-stamp").textContent = `v${META.version} · ${META.weapons_curated}/${META.weapons_total} curated`;

/* Boot: a shared link restores content/size/party; otherwise seed with the
   design doc's worked example (§4.3). The seed comes from the build-time
   parity fixture, so the client and the fixture provably score the SAME
   party — three hardcoded copies used to have to agree by eyeball, and one
   drifting meant a false "PARITY MISMATCH" banner. */
const SEED = ((typeof PARITY_EXPECTED !== "undefined" && PARITY_EXPECTED.party) || [])
  .filter(w => WEAPONS[w]);
if (!loadHash() && !loadStored()){
  party = SEED; PROV = party.map(() => "m");
  sortPartyByRole();
}
try { if (localStorage.getItem(RAIL_KEY) === "min") setRail(true); } catch (e) { /* private mode */ }
renderTreeFilter();
syncEngine();
render();

/* Parity guard. PARITY_EXPECTED is injected at build time by running
   engine/engine.py over the same seed party, so this compares the client
   against the Python engine's ACTUAL output rather than a hardcoded name that
   goes stale the moment a sheet is curated. Reported in the masthead chip. */
(function parity(){
  if (typeof PARITY_EXPECTED === "undefined" || !SEED.length) return;
  const e2 = new CompEngine(DATASET, PARITY_EXPECTED.content || "castle_outpost",
                            PARITY_EXPECTED.size || 7);
  const got = {
    fitness: e2.fitness(SEED),
    recs: e2.recommend(SEED, 4).map(r => r.weapon),
    weaknesses: e2.weaknesses(SEED).map(x => x.cap),
  };
  /* tolerance compare like the test suite — rounding both sides to 2dp
     could flip a healthy build to "do not trust" on an exact rounding tie */
  const ok = Math.abs(got.fitness - PARITY_EXPECTED.fitness) < 1e-9
    && JSON.stringify(got.recs) === JSON.stringify(PARITY_EXPECTED.recs)
    && JSON.stringify(got.weaknesses) === JSON.stringify(PARITY_EXPECTED.weaknesses);
  (ok ? console.info : console.error)("engine parity vs engine.py:",
    ok ? "OK" : "MISMATCH", ok ? got : {got, expected: PARITY_EXPECTED});
  const chip = $("parity-chip"), dot = $("parity-dot");
  if (chip) chip.textContent = ok ? "parity vs engine.py — OK" : "PARITY MISMATCH — do not trust";
  if (dot && !ok) dot.style.background = "var(--gap)";
})();
