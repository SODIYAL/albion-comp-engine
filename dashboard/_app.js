"use strict";
/* Dashboard client. Reads the injected DATASET — the same
   pipeline/out/dataset-latest.json that engine/engine.py consumes. No
   capability numbers live in this file, and no scoring math either: the
   engine is pipeline/app_scoring.js (inlined by the build just before this
   file), the SAME code node runs in tests/test_js_parity.py. Regenerate:
       py -3 pipeline/build_dashboard.py                                     */

const META = DATASET._meta;
const WEAPONS = DATASET.weapons;

let CONTENT = Object.keys(DATASET.templates)[0];
const ENG = new CompEngine(DATASET, CONTENT);
/* There is no fixed party size in open-world content: PLANNED is what you
   expect to field, but the roster is reality — the effective SIZE (targets,
   floors, scaling) is whichever is larger. Bring 4 or bring 40. */
let PLANNED = ENG.size;
let SIZE = PLANNED;
let STYLE = "balanced";
const HARD_CAP = 60;
const STYLE_ORDER = ["balanced", "brawl", "clap", "kite", "brawl_clap"];

function syncEngine(){
  SIZE = Math.max(PLANNED, party.length);
  ENG.setContent(CONTENT, SIZE, STYLE);
  /* member combos re-resolve after every context change: the default
     loadout depends on the styled weights, and pick-derived combos map
     through the current engine (2026-08-18) */
  COMBOS_CUR = party.map((_, i) => comboAt(i));
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
const explain = (p, cand) => ENG.explain(p, cand, p === party ? COMBOS_CUR : null)
  .map(t => ({d: t.delta, ...t}));
const recommend = (p, n = 4) => ENG.recommend(p, n, null, p === party ? COMBOS_CUR : null)
  .map(r => ({w: r.weapon, dFit: r.d_fitness, dSyn: r.d_synergy, meta: r.meta_prior,
              viab: r.viability, combo: r.combo, score: r.score}));
/* swapReview is a full-pool sweep per member (~40-100ms at 20-40 members) —
   memoized on the engine context + party + loadouts so facet clicks,
   companion polls and other no-op re-renders don't pay it again. */
const comboSig = () => COMBOS_CUR.join(",");
let swapCache = { key: null, val: [] };
function swapReviewCached(){
  const key = `${CONTENT}|${SIZE}|${STYLE}|${party.join(",")}|${comboSig()}`;
  if (swapCache.key !== key)
    swapCache = { key, val: party.length > 1 ? ENG.swapReview(party, 3, null, COMBOS_CUR) : [] };
  return swapCache.val;
}

/* fitness + effective supply for the CURRENT party, computed once per state
   (renderers used to re-derive them 3-4x per render pass) */
let calcCache = { key: null, fit: 0, sup: null };
function partyCalc(){
  const key = `${CONTENT}|${SIZE}|${STYLE}|${party.join(",")}|${comboSig()}`;
  if (calcCache.key !== key)
    calcCache = { key, fit: ENG.fitness(party, COMBOS_CUR),
                  sup: ENG.effectiveSupply(party, COMBOS_CUR) };
  return calcCache;
}

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

const GROUPS = {
  Sustain:   ["heal_burst","heal_sustain","cleanse","self_sustain"],
  Frontline: ["tankiness","engage","disengage","anti_dive","zone_control"],
  Control:   ["stun","root","silence","knockback_displace","slow","clump_create","peel"],
  Denial:    ["purge","anti_zone","heal_reduction","resist_shred","energy_drain","damage_debuff"],
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
};
const prose = c => CAP_PROSE[c] || c.replace(/_/g," ");

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
const BADGE_DEFS = [
  ["tank", ["tankiness"]],
  ["heal", ["heal_sustain", "heal_burst"]],
  ["peel", ["peel"]],
  ["cc",   ["stun", "root", "silence", "slow", "clump_create", "knockback_displace"]],
  ["aoe",  ["burst_aoe"]],
  ["st",   ["burst_st", "execute"]],
  ["dps",  ["sustained_dps"]],
];
function badgeHtml(w){
  const caps = capsOf(w);
  return BADGE_DEFS.map(([cls, keys]) => {
    const hits = keys.filter(k => (caps[k] || 0) >= 2);
    if (!hits.length) return "";
    const tip = hits.map(k => `${prose(k)} ${caps[k]}`).join(", ");
    return `<span class="bdg b-${cls}" data-bfilter="${cls}" role="button" tabindex="0"
      title="${esc(tip)} — click to list every ${cls} weapon">${cls}</span>`;
  }).join("");
}

/* Two independent chip facets:
   FACET       — filters the ADD-WEAPON picker (its own chip bar, plus any
                 capability badge clicked on a weapon anywhere)
   PARTY_FACET — filters the PARTY roster view (tally role chips); display
                 only, never touches the engine */
let FACET = null;
let PARTY_FACET = null;
const BADGE_KEYS = Object.fromEntries(BADGE_DEFS);

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
  renderPicker();
  if (FACET && scroll && !matchMedia("(prefers-reduced-motion: reduce)").matches)
    $("pick-filter").scrollIntoView({behavior: "smooth", block: "center"});
}
function roleBg(w){
  return (typeof ICONS !== "undefined" && ICONS[w])
    ? ` style="--wbg:url('${ICONS[w]}')"` : "";
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
  const floorClause = (lead && floorHit(lead.cap, s[lead.cap] || 0))
    ? ` — and at size ${SIZE} that is below the hard floor, not merely suboptimal` : "";
  return `${strong.length ? `Your party already covers ${strong.join(" and ")}` : "Your party is thin across the board"}, but has <em>${lead ? prose(lead.cap) : "gaps"}</em> at ${lead ? lead.before : 0} of ${lead ? target(lead.cap).toFixed(1) : "0"} units${floorClause}. ${nameOf(cand)} closes that${rest.length ? `, and adds ${rest.join(" and ")}` : ""}.`;
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
/* The last forge's honesty report: {feasible, filler, held} or null. */
let FORGE_NOTE = null;
let pickFilter = "";
let treeFilter = "";
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
  $("size-hint").textContent = party.length > PLANNED
    ? `Roster is ${party.length} — targets and floors now scale to ${SIZE}, not the planned ${PLANNED}.`
    : `Targets and floors scale to whoever shows up — ${SIZE} right now.`;
  $("size-notice").innerHTML =
    (tpl().max_size && SIZE > tpl().max_size
      ? `<div class="notice"><b>Over the in-game cap.</b> ${esc(tpl().name)} parties are capped at ${tpl().max_size} players in game — ${SIZE} cannot actually field. The advice below still computes, but treat it as hypothetical.</div>`
      : "")
    + (!ENG.extrapolated() ? "" :
    `<div class="notice"><b>Extrapolated.</b> This template is fitted and validated at size ${validatedSizes().join(", ")} only. Per-player targets are scaled linearly to ${SIZE}; flat threshold targets are unchanged. Tier-2 validation must confirm each size before this is trustworthy.</div>`);
}
function renderTally(){
  $("tally").innerHTML = party.length
    ? Object.entries(roleCounts()).sort((a,b) => b[1]-a[1])
        .map(([r,n]) => `<span class="t t-${esc(r)}" data-pfilter="${esc(r)}" role="button" tabindex="0"
           aria-pressed="${PARTY_FACET === r}"
           title="show only the ${esc(r)} slots — click again for all"><b>${n}</b> ${esc(r)}</span>`).join("")
      + `<span class="t"><b>${SIZE - party.length}</b> open</span>`
    : "";
}
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
    /* viability-excluded members always get their replacement advice —
       the owner rule flags them regardless of rank (2026-08-18) */
    if (m.off_comp && m.options.length){ ok.add(i); return; }
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
  const forced = m.off_comp && m.options.length;
  if (!forced && m.rank < SWAP_CFG.min_rank) return "";
  const opts = forced ? m.options
    : m.options.filter(o => o.gain >= SWAP_CFG.min_gain);
  if (!opts.length) return "";
  const pool = Object.keys(WEAPONS).length;
  const label = m.off_comp
    ? `<b class="offcomp">off-comp at this size (owner rule) — swap to</b>`
    : m.rank >= SWAP_CFG.offcomp_rank
      ? `<b class="offcomp">off-comp here — rank ${m.rank}/${pool}</b>`
      : `<span class="swap-lbl">better options</span>`;
  return `<span class="fn swap">${label} ${opts.map(o =>
    `<button class="swap-opt" data-swapat="${i}" data-swapto="${o.weapon}"
       title="swap ${nameOf(m.weapon)} for ${nameOf(o.weapon)} (+${o.gain.toFixed(1)} score)">${nameOf(o.weapon)} +${o.gain.toFixed(1)}</button>`).join(" ")}</span>`;
}
function renderRoster(){
  /* contribution = fitness lost if this member left — the caller's
     "who is load-bearing" number. Lowest contributor gets flagged. */
  const base = fitness(party);
  const contrib = party.map((w, i) =>
    base - ENG.fitness(party.filter((_, j) => j !== i),
                       COMBOS_CUR.filter((_, j) => j !== i)));
  const review = swapReviewCached();
  const hintable = swapEligible(review);
  const minI = party.length > 2 ? contrib.indexOf(Math.min(...contrib)) : -1;
  const signed = v => (v < 0 ? "−" : "+") + Math.abs(v).toFixed(1);
  const flag = i => i !== minI ? "" : contrib[i] < 0
    ? ' · <b class="least">comp gains without it</b>'
    : ' · <b class="least">least load-bearing</b>';
  /* party facet: a display filter over the roster — slot numbers and remove
     buttons keep their true indices */
  let idxs = party.map((_, i) => i);
  if (PARTY_FACET){
    idxs = idxs.filter(i => roleHint(party[i]) === PARTY_FACET);
    if (!idxs.length){
      /* removing the last member of the filtered role also removes the tally
         chip that exits the filter — a dead end. Auto-clear instead. */
      PARTY_FACET = null;
      idxs = party.map((_, i) => i);
    }
  }
  const rows = idxs.map(i => { const w = party[i]; return (
    `<div class="slot ${roleCls(w)}"${roleBg(w)}><span class="n mono">${String(i+1).padStart(2,"0")}</span>${icon(w, 32)}
      <span class="nm"><button class="nm-btn" data-detail="${w}">${nameOf(w)}</button>${badgeHtml(w)}${PROV[i] === "f" ? '<span class="prov forged" title="slot generated by the forge — reforge all rebuilds it">forged</span>' : ""}
        <span class="fn">${roleOf(w, COMBOS_CUR[i])} · ${signed(contrib[i])} fit${flag(i)}${ENG.isExcluded(w) ? ' · <b class="offcomp" title="owner rule: not a default large-group pick at this size — swap advice below">off-comp at size ' + SIZE + "</b>" : ""}</span>${hintable.has(i) ? swapHint(review[i], i) : ""}</span>
      <button class="lo-open${LO_OPEN === i ? " on" : ""}" data-lo-open="${i}"
        aria-expanded="${LO_OPEN === i}" aria-label="Loadout for ${nameOf(w)}"
        >kit${loadoutCount(i) ? `<i>${loadoutCount(i)}</i>` : ""}</button>
      <button class="x" data-remove="${i}" aria-label="Remove ${nameOf(w)}">&times;</button></div>
      ${loadoutPanel(i)}`); });
  /* duplicate-interaction notices (spec §7): what a duplicated SPELL
     actually does, from the compiled interaction records — the message
     names the exact effect, and unknown says "verify", never a penalty */
  const inotes = interactionNotices();
  if (inotes) rows.push(inotes);
  if (PARTY_FACET){
    rows.push(`<div class="slot more">${idxs.length} of ${party.length} — ${esc(PARTY_FACET)} only · click the chip again for all</div>`);
  } else {
    /* open slots collapse: one dashed "next" row, one "+N more" line */
    const open = SIZE - party.length;
    if (party.length < HARD_CAP)
      rows.push(`<div class="slot next"><span class="n mono">${String(party.length+1).padStart(2,"0")}</span>next slot — pick below</div>`);
    if (open > 1)
      rows.push(`<div class="slot more">+ ${open - 1} more open slot${open > 2 ? "s" : ""}</div>`);
  }
  $("roster").innerHTML = rows.join("");
}
const INOTE_LABEL = {high: "duplicate utility wasted",
                     warning: "duplicate utility warning",
                     info: "duplicate check", verify: "verify duplicate"};
function interactionNotices(){
  if (party.length < 2) return "";
  const conf = ENG.duplicateConflicts(party, COMBOS_CUR);
  if (!conf.length) return "";
  return conf.map(c => `<div class="slot inote int-${c.severity}">
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
    holder.innerHTML =
      `<div class="pchips"><span class="lbl2">role</span>` +
      PICKER_ROLES.map(r =>
        `<button class="pchip t-${r}" data-rfilter="${r}">${r}</button>`).join("") +
      `</div><div class="pchips"><span class="lbl2">provides</span>` +
      BADGE_DEFS.map(([cls]) =>
        `<button class="pchip b-${cls}" data-bfilter="${cls}">${cls}</button>`).join("") +
      `</div><div class="pchips"><span class="lbl2">utility</span>` +
      UTIL_DEFS.map(([cls]) =>
        `<button class="pchip u-chip" data-ufilter="${cls}">${cls}</button>`).join("") +
      `</div>`;
    holder.dataset.built = "1";
  }
  holder.querySelectorAll("[data-rfilter]").forEach(el => el.setAttribute("aria-pressed",
    String(!!FACET && FACET.type === "role" && FACET.v === el.dataset.rfilter)));
  holder.querySelectorAll("[data-bfilter]").forEach(el => el.setAttribute("aria-pressed",
    String(!!FACET && FACET.type === "badge" && FACET.v === el.dataset.bfilter)));
  holder.querySelectorAll("[data-ufilter]").forEach(el => el.setAttribute("aria-pressed",
    String(!!FACET && FACET.type === "util" && FACET.v === el.dataset.ufilter)));
}
function renderPicker(){
  const keys = filteredWeapons();
  renderPickerChips();
  $("facet-slot").innerHTML = FACET
    ? `<div class="facet"><span>showing: <b>${esc(FACET.type === "role" ? FACET.v + " weapons" : "provides " + FACET.v)}</b> — ${keys.length} match${keys.length === 1 ? "" : "es"}</span>
       <button class="fx" id="facet-clear" aria-label="Clear filter">&times; clear</button></div>`
    : "";
  $("picker").innerHTML = keys.map(w => `<button class="pick" data-add="${w}">
      ${icon(w, 26)}<span class="nm">${nameOf(w)}${badgeHtml(w)}<span class="fn">${roleOf(w)}</span></span>
      ${ENG.isExcluded(w) ? '<span class="prov draft offcomp" title="owner rule: not a default large-group pick at this size — manual add still allowed">off-comp</span>' : ""}
      ${WEAPONS[w].status === "curated" ? "" : '<span class="prov draft">illustrative</span>'}
      <span class="info" data-detail="${w}" role="button" tabindex="0" aria-label="Details for ${nameOf(w)}">i</span>
    </button>`).join("")
    || `<p class="ev-empty">Nothing matches${treeFilter ? " in this tree" : ""}${pickFilter.trim() ? ` — “${esc(pickFilter)}”` : ""}.</p>`;
}
function renderFitness(){
  const f = fitness(party), max = maxFitness();
  $("fit-num").textContent = f.toFixed(1);
  $("fit-of").textContent = `/ ${Math.round(max)}`;
  $("fit-bar").style.width = `${Math.max(0, Math.min(100, f/max*100))}%`;
}
function renderGroups(){
  const s = supply(party);
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
      const below = floorHit(c, have);
      const over = have > soft;
      const cls = over ? "over" : have === 0 ? "none" : have >= t ? "met" : "part";
      return `<div class="cap ${below ? "floor-hit" : ""}">
        <button class="cap-name" data-cap="${c}" title="${esc(prose(c))} — click for evidence">${c}${below ? '<span class="tag floor">below floor</span>' : ""}${over ? '<span class="tag over">overstacked</span>' : ""}</button>
        <span class="cap-val">${have.toFixed(0)} / ${t.toFixed(1)}</span>
        <span class="cap-bar"><i class="${cls}" style="width:${over ? 100 : Math.min(100, have/t*100)}%"></i></span>
      </div>`;
    }).join("");
    return rows ? `<div class="grp"><h3>${g}</h3>${rows}</div>` : "";
  }).join("");
}
function renderWeaknesses(){
  const s = supply(party);
  /* Split the gap list: floors and heavy under-supplied capabilities are
     NEEDED; the rest are nice-to-haves. */
  const needed = [], nice = [];
  for (const x of weaknesses(party, 8)){
    if (x.gap < 0.5) continue;
    const below = floorHit(x.cap, s[x.cap] || 0);
    const ratio = (s[x.cap]||0) / target(x.cap);
    // styled weight (ENG.weight), same scale as the engine's own
    // uncovered-caps test — raw template weight silently disagreed with the
    // greedy-trap warning under any non-balanced style
    if (below || (ENG.weight(x.cap) >= 6 && ratio < 0.5)) needed.push({...x, floorHit: below});
    else nice.push(x);
  }
  const row = (x, i, cls) =>
    `<div class="weak ${cls}"><span class="rank">${String(i+1).padStart(2,"0")}</span>
      <span class="txt">You have <b>${(s[x.cap]||0).toFixed(0)}</b> of <b>${target(x.cap).toFixed(1)}</b> units of <b>${x.cap}</b> — ${prose(x.cap)}${x.floorHit ? " <b>(below the hard floor)</b>" : ""}.</span>
      <span class="sc">−${x.gap.toFixed(1)}</span></div>`;
  $("weaknesses").innerHTML =
    `<div class="weak-sub">Needed now</div>`
    + (needed.length ? needed.slice(0,4).map((x,i) => row(x,i,"")).join("")
                     : `<p class="weak-none">Nothing critical — the core is covered.</p>`)
    + (nice.length ? `<div class="weak-sub nice">Nice to have</div>`
                   + nice.slice(0,3).map((x,i) => row(x,i,"nice")).join("") : "");
}
function renderWarning(){
  const unc = uncoveredCaps(party), left = SIZE - party.length;
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
        <span class="b"><b>Saturated tail.</b> Slot${FORGE_NOTE.filler.length > 1 ? "s" : ""} ${slotNames(FORGE_NOTE.filler)} reduce${FORGE_NOTE.filler.length > 1 ? "" : "s"} the comp score and no allowed replacement does better — the template is fully covered before size ${SIZE}. Treat ${FORGE_NOTE.filler.length > 1 ? "these slots" : "this slot"} as provisional.</span></div>`;
    if (FORGE_NOTE.held && FORGE_NOTE.held.length)
      forgeBits += `<div class="warn"><span class="t">Forge</span>
        <span class="b"><b>Constraint-held.</b> Slot${FORGE_NOTE.held.length > 1 ? "s" : ""} ${slotNames(FORGE_NOTE.held)} score${FORGE_NOTE.held.length > 1 ? "" : "s"} slightly negative but ${FORGE_NOTE.held.length > 1 ? "are" : "is"} required by the composition minimums (healers/frontline/ranged core) — expert structure the capability score alone does not see.</span></div>`;
  }
  $("warn-slot").innerHTML = greedy + forgeBits;
}
function renderCmdNext(recs){
  if (!recs){
    $("cb-next").style.removeProperty("--wbg");
    $("cb-next").innerHTML = `<div class="eyebrow">Roster cap</div>
      <div class="cb-row"><span class="cb-full">That is ${HARD_CAP} people — beyond even a castle blob. Remove someone to explore swaps.</span></div>`;
    return;
  }
  const top = recs[0];
  if (typeof ICONS !== "undefined" && ICONS[top.w])
    $("cb-next").style.setProperty("--wbg", `url('${ICONS[top.w]}')`);
  else $("cb-next").style.removeProperty("--wbg");
  const slotLabel = party.length + 1 > PLANNED
    ? `slot ${party.length + 1} — beyond planned ${PLANNED}`
    : `slot ${party.length + 1} of ${SIZE}`;
  const sn = styleName();
  const styleTag = sn ? ` · ${sn}` : "";
  /* "forge the rest" fills open slots locking every current member;
     "reforge all" (shown whenever forged slots exist — even on a full
     roster after a content/style/size change) rebuilds every generated
     slot and keeps only the manual/live ones (2026-08-18). */
  const forge = (party.length < SIZE
    ? `<button class="cb-forge" id="forge">${party.length ? "forge the rest" : "forge a full comp"}</button>`
    : "") + (PROV.some(x => x === "f")
    ? `<button class="cb-forge" id="reforge" title="rebuild every forged slot for the current content, style and size — manual picks stay">reforge all</button>`
    : "");
  $("cb-next").innerHTML = `
    <div class="eyebrow">Next pick — ${slotLabel}${styleTag}</div>
    <div class="cb-row">
      ${icon(top.w, 44)}
      <span><button class="nm-btn nm" data-detail="${top.w}">${nameOf(top.w)}</button><span class="fn rl">${roleOf(top.w)} ${badgeHtml(top.w)}</span></span>
      <button class="cb-add" data-add="${top.w}">Add to party</button>
      ${forge}
    </div>`;
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
function renderRecDetail(recs){
  if (!recs){
    $("rec-label").textContent = "Recommendation";
    $("rec-slot").innerHTML = `<div class="rec"><div class="rec-body">
      <p class="why">Party is full at ${SIZE}. Remove a slot to see what the engine would swap in.</p></div></div>`;
    return;
  }
  const top = recs[0], terms = explain(party, top.w).slice(0,4);
  $("rec-label").textContent = `Why ${WEAPONS[top.w].display_name}`;
  $("rec-slot").innerHTML = `
    <div class="rec">
      <div class="rec-body">
        <p class="why">${whySentence(party, top.w)}</p>
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
        <div><div class="sec-label" style="margin-bottom:8px">Alternatives — click to add instead</div>
          <div class="alts">${recs.slice(1).map(r => {
            const t0 = explain(party, r.w)[0];
            return `<button class="alt" data-add="${r.w}"><span class="sc">${r.score.toFixed(2)}</span>
              ${icon(r.w, 24)}<span class="nm">${nameOf(r.w)}${badgeHtml(r.w)}</span>
              <span class="rz">${t0 ? `+${t0.d.toFixed(1)} ${t0.cap}` : "no template gain"}</span></button>`;
          }).join("")}</div>
        </div>
      </div>
    </div>`;
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
/* One gate for the usage sample: the bucket key comes from the ENGINE's
   size_bucket, so the display bucket is provably the bucket the meta prior
   scores with; the min-sample rule lives here once (it was copy-pasted
   between usageOf and renderMetaStrip). */
const USAGE_BUCKET_LABEL = { small: "small", mid: "mid-size", large: "large" };
function usageStats(){
  if (typeof USAGE === "undefined" || !USAGE.buckets) return null;
  const key = ENG.sizeBucket();
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
      `<li class="${picks[slot] && picks[slot].has(i+1) ? "pick" : ""}">
         <span class="idx">${slot === "e" ? "E" : slot[0].toUpperCase() + (i+1)}</span>
         ${spellIcon(sid)}<span>${esc(nm)}</span>
         ${picks[slot] && picks[slot].has(i+1) ? '<span class="idx">caller pick</span>' : ""}
       </li>`).join("");
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
  const u = usageStats();
  if (!u){ sec.hidden = true; return; }
  /* usage keys are filtered against the dataset at build time too, but a
     stale inlined file must degrade to a shorter list, not throw in nameOf
     and kill every render after a weapon rename */
  const rows = Object.entries(USAGE.buckets[u.key] || {})
    .filter(([w]) => WEAPONS[w])
    .sort((a,b) => b[1] - a[1]).slice(0, 12);
  $("meta-label").textContent =
    `Killboard equipment prevalence — ${u.label}-size fights (${u.m.battles} battles, ${u.m.players_attributed} observed combatants; fight size, not party size)`;
  $("meta-strip").innerHTML = rows.map(([w, n], i) =>
    `<div class="meta-row"><span class="rk">${String(i+1).padStart(2,"0")}</span>${icon(w, 20)}
      <button class="nm-btn" data-detail="${w}">${nameOf(w)}</button>
      <span class="pct">${(100 * n / u.m.players_attributed).toFixed(1)}%</span></div>`).join("");
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
      <span class="cm-wpn ${k ? "" : "unknown"}">${wpn}</span></div>`;
  }).join("");
  load.hidden = false; load.disabled = known.length === 0;
}
function loadCompanionParty(){
  if (!companionData) return;
  const weapons = (companionData.members || []).map(m => m.weapon).filter(w => w && WEAPONS[w]);
  if (!weapons.length) return;
  party = weapons.slice(0, HARD_CAP);
  /* live-party members are the user's, never the forge's */
  PROV = party.map(() => "m");
  COMBO = party.map(() => null);
  FORGE_NOTE = null;
  loadoutClear();
  sortPartyByRole();
  PLANNED = Math.max(PLANNED, party.length);
  PARTY_FACET = null;
  render();
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
  renderSetup(); renderTally(); renderRoster(); renderPicker(); renderFitness();
  renderCmdNext(recs); renderGroups(); renderWeaknesses(); renderWarning();
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

document.addEventListener("click", e => {
  /* loadout layer first: its controls live inside party rows, so a later
     [data-remove]/[data-detail] match must not swallow them */
  if (loadoutHandleClick(e)){ render(); return; }
  /* chip facets first: badges/role chips nest inside add/detail buttons,
     so they must win the closest() race */
  const pf = e.target.closest("[data-pfilter]");
  if (pf){
    PARTY_FACET = PARTY_FACET === pf.dataset.pfilter ? null : pf.dataset.pfilter;
    /* update pressed states IN PLACE — rebuilding the tally would replace
       the chip mid-click and a double-click would toggle straight back off */
    document.querySelectorAll("#tally .t[data-pfilter]").forEach(el =>
      el.setAttribute("aria-pressed", String(el.dataset.pfilter === PARTY_FACET)));
    renderRoster(); return;
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
  const det = e.target.closest("[data-detail]");
  if (det){ renderDetail(det.dataset.detail); return; }
  const add = e.target.closest("[data-add]");
  if (add){ if (party.length < HARD_CAP){
    party.push(add.dataset.add);
    PROV.push("m"); COMBO.push(null); FORGE_NOTE = null;
    loadoutInsert(party.length - 1);   /* prefill from the caller reference */
    sortPartyByRole();    /* the new member lands in its role group */
    PARTY_FACET = null;   /* the new member must be visible */
    render(); } return; }
  const forgeBtn = e.target.closest("#forge") || e.target.closest("#reforge")
                || e.target.closest("#forge-rail");
  if (forgeBtn){
    /* Deterministic constrained beam search in the engine (2026-08-18) —
       greedy top-1 append + a 1-opt pass used to force-fill negative-value
       bodies and treated every forged slot as manual afterwards.
       "forge the rest" locks every current member; "reforge all" keeps
       only the manual/live slots and rebuilds the rest for the CURRENT
       content, style and size. The rail's "forge full comp" fills open
       slots, and on a fully forged roster acts as a reforge. */
    const goal = Math.min(SIZE, HARD_CAP);
    const reforgeAll = forgeBtn.id === "reforge"
      || (forgeBtn.id === "forge-rail" && party.length >= goal
          && PROV.some(x => x === "f"));
    const keep = party.map((_, i) => i)
      .filter(i => reforgeAll ? PROV[i] !== "f" : true);
    const locked = keep.map(i => party[i]);
    const lockedCombos = keep.map(i => comboAt(i));
    const lockedLoadouts = keep.map(i => LOADOUT[i]);
    const lockedProv = keep.map(i => PROV[i] || "m");
    if (locked.length >= goal && !reforgeAll){ return; }
    const lockedStored = keep.map(i => COMBO[i]);
    const r = ENG.forge(Math.max(goal, locked.length), locked, lockedCombos);
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
      /* gear from the caller reference; SPELLS from the combo the forge
         actually scored — the kit shown is the kit valued */
      loadoutPrefillGear(i);
      loadoutApplySpells(i, r.combos[i]);
    }
    FORGE_NOTE = { feasible: r.feasible, filler: r.filler, held: r.held };
    LO_OPEN = null; LO_PICKING = null;
    sortPartyByRole();    /* remaps the forge note's slot indexes too */
    PARTY_FACET = null;   /* show the whole forged comp, not a filtered view */
    render();
    return;
  }
  const rm = e.target.closest("[data-remove]");
  if (rm){
    const ri = +rm.dataset.remove;
    party.splice(ri, 1); PROV.splice(ri, 1); COMBO.splice(ri, 1);
    FORGE_NOTE = null;
    loadoutRemove(ri); render(); return;
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
      loadoutClear(); PARTY_FACET = null; render();
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
    PARTY_FACET = null; render();
  }
  if (e.target.id === "style"){ STYLE = e.target.value; FORGE_NOTE = null; render(); }
  if (e.target.id === "tree-filter"){ treeFilter = e.target.value; renderPicker(); }
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
  if (e.target.id === "pick-filter"){ pickFilter = e.target.value; renderPicker(); }
});
document.addEventListener("keydown", e => {
  if ((e.key === "Enter" || e.key === " ")
      && e.target.matches("[data-bfilter],[data-rfilter],[data-ufilter],[data-pfilter],span.info[data-detail]")){
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
    PARTY_FACET = null;   /* the new member must be visible (matches click-add) */
    loadoutInsert(party.length - 1); sortPartyByRole(); render(); }
});
/* A pasted share-link hash applies without a reload. saveHash() uses
   replaceState, which never fires hashchange, so this cannot loop. The
   party view-filter resets — it described the previous comp. */
window.addEventListener("hashchange", () => {
  if (loadHash()){ PARTY_FACET = null; render(); }
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
