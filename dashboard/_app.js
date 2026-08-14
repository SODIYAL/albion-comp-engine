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

function syncEngine(){ SIZE = Math.max(PLANNED, party.length); ENG.setContent(CONTENT, SIZE, STYLE); }

const tpl = () => DATASET.templates[CONTENT];
const REQS = () => tpl().requirements;
const FLOORS = () => tpl().hard_floors || {};
const baseSize = () => tpl().base_size || 7;
const validatedSizes = () => tpl().validated_sizes || [baseSize()];

const target = cap => ENG.target(cap);
const softCap = cap => ENG.softCap(cap);
const supply = p => ENG.supply(p);
const fitness = p => ENG.fitness(p);
const maxFitness = () => ENG.maxFitness();
const uncoveredCaps = p => ENG.uncoveredCaps(p);
const weaknesses = (p, n = 3) => ENG.weaknesses(p, n);
/* app_scoring.js term/rec field names -> the short ones this file renders */
const explain = (p, cand) => ENG.explain(p, cand).map(t => ({d: t.delta, ...t}));
const recommend = (p, n = 4) => ENG.recommend(p, n).map(r =>
  ({w: r.weapon, dFit: r.d_fitness, dSyn: r.d_synergy, meta: r.meta_prior, score: r.score}));

const capsOf = w => WEAPONS[w].capabilities || {};
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
  Denial:    ["purge","anti_zone","heal_reduction","resist_shred","energy_drain"],
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

function roleOf(w){
  return Object.entries(capsOf(w)).sort((a,b) => b[1]-a[1]).slice(0,2)
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
function facetOk(w){
  if (!FACET) return true;
  if (FACET.type === "role") return (WEAPONS[w].role_hint || "other") === FACET.v;
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
const roleCls = w => `role-${WEAPONS[w].role_hint || "other"}`;
function whySentence(party, cand){
  const terms = explain(party, cand);
  if (!party.length)
    return `Opening pick. With nothing on the board, ${nameOf(cand)} scores highest because it covers ${terms.slice(0,2).map(t => prose(t.cap)).join(" and ")} — the capabilities this template weights most heavily.`;
  const s = supply(party);
  const strong = Object.keys(REQS()).filter(c => (s[c]||0)/target(c) >= 0.85)
    .sort((a,b) => REQS()[b].weight - REQS()[a].weight).slice(0,2).map(prose);
  const lead = terms[0], rest = terms.slice(1,3).map(t => prose(t.cap));
  const f = lead && FLOORS()[lead.cap];
  const floorClause = (f && (s[lead.cap]||0) < f.floor_units && SIZE >= f.min_party_size)
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
  if (p.c && DATASET.templates[p.c]) CONTENT = p.c;
  PLANNED = (p.n && +p.n >= 2 && +p.n <= HARD_CAP) ? +p.n : baseSize();
  STYLE = (p.st && (DATASET.styles || {})[p.st]) ? p.st : "balanced";
  if (p.p) party = p.p.split(",").filter(w => WEAPONS[w]);
  syncEngine();
  return true;
}
function saveHash(){
  const h = `c=${CONTENT}&n=${PLANNED}${STYLE !== "balanced" ? "&st=" + STYLE : ""}${party.length ? "&p=" + party.join(",") : ""}`;
  history.replaceState(null, "", "#" + h);
  try { localStorage.setItem("compforge", h); } catch (e) { /* file:// may deny */ }
}
function loadStored(){
  try {
    const h = localStorage.getItem("compforge");
    if (!h) return false;
    location.hash = h;
    return loadHash();
  } catch (e) { return false; }
}

/* ---------------------------------------------------------------- render */

let party = [];
let pickFilter = "";
let treeFilter = "";
const $ = id => document.getElementById(id);

const PENDING = [["hellgate_5v5","Hellgate 5v5"], ["roads_7","Roads of Avalon"]];

function renderSetup(){
  $("content").innerHTML = Object.entries(DATASET.templates)
    .map(([k,t]) => `<option value="${k}" ${k===CONTENT?"selected":""}>${t.name} — base ${t.base_size}</option>`)
    .join("") + PENDING.filter(([k]) => !DATASET.templates[k])
    .map(([k,n]) => `<option value="${k}" disabled>${n} — template pending</option>`).join("");
  const styles = DATASET.styles || {};
  const styleKeys = STYLE_ORDER.filter(k => styles[k])
    .concat(Object.keys(styles).filter(k => STYLE_ORDER.indexOf(k) === -1));
  $("style").innerHTML = styleKeys.map(k =>
    `<option value="${k}" ${k===STYLE?"selected":""}>${esc(styles[k].name || k)}</option>`).join("");
  $("style-blurb").textContent = (styles[STYLE] || {}).blurb || "";
  $("size-input").value = PLANNED;
  const presets = [...new Set(validatedSizes().concat([baseSize()]))].sort((a,b) => a-b);
  $("size-presets").innerHTML = presets.map(n =>
    `<button class="size-btn" data-size="${n}" aria-pressed="${n===PLANNED}">${n}</button>`).join("");
  $("size-hint").textContent = party.length > PLANNED
    ? `Roster is ${party.length} — targets and floors now scale to ${SIZE}, not the planned ${PLANNED}.`
    : `Targets and floors scale to whoever shows up — ${SIZE} right now.`;
  $("size-notice").innerHTML = validatedSizes().includes(SIZE) ? "" :
    `<div class="notice"><b>Extrapolated.</b> This template is fitted and validated at size ${validatedSizes().join(", ")} only. Per-player targets are scaled linearly to ${SIZE}; flat threshold targets are unchanged. Tier-2 validation must confirm each size before this is trustworthy.</div>`;
}
function renderTally(){
  const counts = {};
  party.forEach(w => { const r = WEAPONS[w].role_hint || "other"; counts[r] = (counts[r]||0) + 1; });
  $("tally").innerHTML = party.length
    ? Object.entries(counts).sort((a,b) => b[1]-a[1])
        .map(([r,n]) => `<span class="t t-${esc(r)}" data-pfilter="${esc(r)}" role="button" tabindex="0"
           aria-pressed="${PARTY_FACET === r}"
           title="show only the ${esc(r)} slots — click again for all"><b>${n}</b> ${esc(r)}</span>`).join("")
      + `<span class="t"><b>${SIZE - party.length}</b> open</span>`
    : "";
}
function renderRoster(){
  /* contribution = fitness lost if this member left — the caller's
     "who is load-bearing" number. Lowest contributor gets flagged. */
  const base = fitness(party);
  const contrib = party.map((w, i) =>
    base - fitness(party.filter((_, j) => j !== i)));
  const minI = party.length > 2 ? contrib.indexOf(Math.min(...contrib)) : -1;
  const signed = v => (v < 0 ? "−" : "+") + Math.abs(v).toFixed(1);
  const flag = i => i !== minI ? "" : contrib[i] < 0
    ? ' · <b class="least">comp gains without it</b>'
    : ' · <b class="least">least load-bearing</b>';
  /* party facet: a display filter over the roster — slot numbers and remove
     buttons keep their true indices */
  let idxs = party.map((_, i) => i);
  if (PARTY_FACET)
    idxs = idxs.filter(i => (WEAPONS[party[i]].role_hint || "other") === PARTY_FACET);
  const rows = idxs.map(i => { const w = party[i]; return (
    `<div class="slot ${roleCls(w)}"${roleBg(w)}><span class="n mono">${String(i+1).padStart(2,"0")}</span>${icon(w, 32)}
      <span class="nm"><button class="nm-btn" data-detail="${w}">${nameOf(w)}</button>${badgeHtml(w)}
        <span class="fn">${roleOf(w)} · ${signed(contrib[i])} fit${flag(i)}</span></span>
      <button class="x" data-remove="${i}" aria-label="Remove ${nameOf(w)}">&times;</button></div>`); });
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
function filteredWeapons(){
  const q = pickFilter.trim().toLowerCase();
  return Object.keys(WEAPONS)
    .sort((a,b) => nameOf(a).localeCompare(nameOf(b)))
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
      `</div>`;
    holder.dataset.built = "1";
  }
  holder.querySelectorAll("[data-rfilter]").forEach(el => el.setAttribute("aria-pressed",
    String(!!FACET && FACET.type === "role" && FACET.v === el.dataset.rfilter)));
  holder.querySelectorAll("[data-bfilter]").forEach(el => el.setAttribute("aria-pressed",
    String(!!FACET && FACET.type === "badge" && FACET.v === el.dataset.bfilter)));
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
  $("groups").innerHTML = Object.entries(GROUPS).map(([g, caps]) => {
    const rows = caps.filter(c => REQS()[c]).map(c => {
      const have = s[c] || 0, t = target(c), soft = softCap(c);
      const f = FLOORS()[c], floorHit = f && SIZE >= f.min_party_size && have < f.floor_units;
      const over = have > soft;
      const cls = over ? "over" : have === 0 ? "none" : have >= t ? "met" : "part";
      return `<div class="cap ${floorHit ? "floor-hit" : ""}">
        <button class="cap-name" data-cap="${c}" title="${esc(prose(c))} — click for evidence">${c}${floorHit ? '<span class="tag floor">below floor</span>' : ""}${over ? '<span class="tag over">overstacked</span>' : ""}</button>
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
    const f = FLOORS()[x.cap], r = REQS()[x.cap];
    const floorHit = f && SIZE >= f.min_party_size && (s[x.cap]||0) < f.floor_units;
    const ratio = (s[x.cap]||0) / target(x.cap);
    if (floorHit || (r.weight >= 6 && ratio < 0.5)) needed.push({...x, floorHit});
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
  $("warn-slot").innerHTML = (party.length && left > 0 && left <= 2 && unc.length >= 3)
    ? `<div class="warn"><span class="t">Lookahead</span>
       <span class="b"><b>Greedy trap.</b> ${left} slot${left>1?"s":""} left but ${unc.length} high-weight capabilities still uncovered
       (<code>${unc.join(", ")}</code>). No single weapon closes all of them — expect to leave at least ${unc.length - left} unmet whatever you pick next.</span></div>`
    : "";
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
  const styleTag = STYLE !== "balanced" ? ` · ${(DATASET.styles[STYLE] || {}).name || STYLE}` : "";
  const forge = party.length < SIZE
    ? `<button class="cb-forge" id="forge">${party.length ? "forge the rest" : "forge a full comp"}</button>`
    : "";
  $("cb-next").innerHTML = `
    <div class="eyebrow">Next pick — ${slotLabel}${styleTag}</div>
    <div class="cb-row">
      ${icon(top.w, 44)}
      <span><button class="nm-btn nm" data-detail="${top.w}">${nameOf(top.w)}</button><span class="fn rl">${roleOf(top.w)} ${badgeHtml(top.w)}</span></span>
      <button class="cb-add" data-add="${top.w}">Add to party</button>
      ${forge}
    </div>`;
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
        ${usageLine(top.w)}
        ${((typeof LOADOUTS !== "undefined" && LOADOUTS[CONTENT]) || {})[top.w] ? (() => {
          const v = LOADOUTS[CONTENT][top.w][0];
          return `<div class="lo-box"><div class="who">caller loadout — ${esc(v.caller)}${v.role ? " · " + esc(v.role) : ""}</div>
            Q${v.q} ${esc(spellAt(top.w, "q", v.q))} · W${v.w} ${esc(spellAt(top.w, "w", v.w))} · P${v.p} ${esc(spellAt(top.w, "passive", v.p))}</div>`;
        })() : ""}
        <div class="terms">${terms.map(t => `<div class="term">
          <span class="d">+${t.d.toFixed(2)}</span><span class="c">${t.cap}</span>
          <span class="mv">${t.before.toFixed(0)} → ${t.after.toFixed(0)} of ${t.target.toFixed(1)}</span></div>`).join("")}</div>
        <div class="formula">
          <span class="k">score</span> = ${ENG.alpha}·Δfitness + ${ENG.beta}·Δsynergy + ${ENG.delta}·metaPrior<br>
          &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;= ${ENG.alpha}·<b>${top.dFit.toFixed(2)}</b> + ${ENG.beta}·<b>${top.dSyn.toFixed(2)}</b> + ${ENG.delta}·<b>${top.meta.toFixed(2)}</b> = <b>${top.score.toFixed(2)}</b><br>
          <span class="k">metaPrior</span> is a hand-set guard value — real win-lift arrives in Phase 3 from battle data.
        </div>
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
/* Real-usage field report (sample_battles.py): how often a weapon actually
   appeared on players in recent fights of roughly this party's size.
   Display evidence only — never feeds the scoring. */
function usageBucketName(){ return SIZE < 12 ? "small" : SIZE <= 30 ? "mid-size" : "large"; }
function usageOf(w){
  if (typeof USAGE === "undefined" || !USAGE.buckets) return null;
  const key = SIZE < 12 ? "small" : SIZE <= 30 ? "mid" : "large";
  const m = (USAGE.meta || {})[key];
  if (!m || m.players_attributed < 200) return null;   // not enough data to quote
  const n = (USAGE.buckets[key] || {})[w] || 0;
  return { pct: 100 * n / m.players_attributed, n,
           players: m.players_attributed, battles: m.battles };
}
function usageLine(w){
  const u = usageOf(w);
  if (!u) return "";
  const bucket = usageBucketName();
  const txt = u.n === 0
    ? `not seen in ${u.battles} recent ${bucket} fights`
    : `on ${u.pct.toFixed(u.pct < 1 ? 1 : 0)}% of ${u.players} players across ${u.battles} recent ${bucket} fights`;
  return `<div class="fieldnote">field report: ${txt} <span>(${esc((USAGE.generated_utc || "").slice(0, 10))}, killboard)</span></div>`;
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
function renderDetail(w){
  const d = WEAPONS[w], sp = (typeof SPELLS !== "undefined" && SPELLS[w]) || {};
  const vars = loVariants(w);
  const picks = { q: new Set(), w: new Set(), passive: new Set() };
  vars.filter(v => v.ct === CONTENT).forEach(v => {
    picks.q.add(v.q); picks.w.add(v.w); picks.passive.add(v.p);
  });
  const pool = (slot, label) => {
    const rows = (sp[slot] || []).map(([sid, nm], i) =>
      `<li class="${picks[slot] && picks[slot].has(i+1) ? "pick" : ""}">
         <span class="idx">${slot === "e" ? "E" : slot[0].toUpperCase() + (i+1)}</span>
         <span>${esc(nm)}</span>
         ${picks[slot] && picks[slot].has(i+1) ? '<span class="idx">caller pick</span>' : ""}
       </li>`).join("");
    return rows ? `<h4>${label}</h4><ul class="sp-list">${rows}</ul>` : "";
  };
  const caps = Object.entries(d.capabilities || {}).sort((a,b) => b[1]-a[1]).map(([c, v]) =>
    `<tr><td><button class="cap-name" data-cap="${c}">${c}</button></td><td class="sc">${v}</td>
     <td>${((d.evidence || {})[c] || []).map(e => `<span class="sp">${esc(e)}</span>`).join(", ")}</td></tr>`).join("");
  const lo = vars.length ? `<div class="lo-box">
      <div class="who">caller loadout${vars.length > 1 ? "s" : ""}</div>
      ${vars.map(v => `<div>${esc(v.caller)}${v.role ? " · " + esc(v.role) : ""}${v.ct !== CONTENT ? ` · <i>${esc((DATASET.templates[v.ct] || {name: v.ct}).name)}</i>` : ""} —
        Q${v.q} ${esc(spellAt(w, "q", v.q))} · W${v.w} ${esc(spellAt(w, "w", v.w))} · P${v.p} ${esc(spellAt(w, "passive", v.p))}</div>`).join("")}
    </div>` : "";
  $("drawer-title").textContent = d.display_name;
  $("drawer-body").innerHTML = `
    <div class="dt-head">${icon(w, 40)}
      <div><b>${nameOf(w)}</b>${badgeHtml(w)}<span class="fn">${esc(TREE_NAMES[TREES[w]] || TREES[w] || "")} tree · ${roleOf(w)}</span>${usageLine(w)}</div>
    </div>
    <div class="dt-grid">
      <div><h4>Capabilities — click one for party-wide evidence</h4>
        <table class="ev-tbl"><tbody>${caps}</tbody></table></div>
      <div>${pool("e", "E — the identity")}${pool("q", "Q options")}${pool("w", "W options")}${pool("passive", "Passives")}${lo}</div>
    </div>`;
  $("drawer").dataset.open = "true";
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
    : `<p class="ev-empty">No weapon in this party supplies <span class="mono">${cap}</span>. Supply is 0 of ${target(cap).toFixed(1)} units.</p>`;
  $("drawer").dataset.open = "true";
}
function renderMetaStrip(){
  const sec = $("meta-sec");
  if (typeof USAGE === "undefined" || !USAGE.buckets){ sec.hidden = true; return; }
  const key = SIZE < 12 ? "small" : SIZE <= 30 ? "mid" : "large";
  const m = (USAGE.meta || {})[key];
  if (!m || m.players_attributed < 200){ sec.hidden = true; return; }
  const rows = Object.entries(USAGE.buckets[key] || {})
    .sort((a,b) => b[1] - a[1]).slice(0, 12);
  $("meta-label").textContent =
    `This week on the killboard — ${usageBucketName()} fights (${m.battles} battles, ${m.players_attributed} players)`;
  $("meta-strip").innerHTML = rows.map(([w, n], i) =>
    `<div class="meta-row"><span class="rk">${String(i+1).padStart(2,"0")}</span>${icon(w, 20)}
      <button class="nm-btn" data-detail="${w}">${nameOf(w)}</button>
      <span class="pct">${(100 * n / m.players_attributed).toFixed(1)}%</span></div>`).join("");
  sec.hidden = false;
}
/* ------------------------------------------------ live party (companion)
   Polls the local companion app (companion/) for the real in-game party and
   maps each member's weapon (an engine unique_name) into the comp. The
   companion serves loopback-only, and browsers exempt http://localhost from
   mixed-content blocking, so the HTTPS page can read it directly. */
const COMPANION_URL = "http://localhost:53321";
let companionOn = false, companionTimer = null, companionData = null;

async function companionPoll(){
  try {
    const r = await fetch(COMPANION_URL + "/party", {cache: "no-store"});
    if (!r.ok) throw new Error("http " + r.status);
    companionData = await r.json();
    renderCompanion(true);
  } catch (e) {
    companionData = null;
    renderCompanion(false, e.message);
  }
}
function companionRoleClass(w){
  const rh = (WEAPONS[w] && WEAPONS[w].role_hint) || "";
  return rh ? `role-${rh}` : "";
}
function renderCompanion(live){
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
    status.innerHTML = `<span class="comp-dot"></span>companion not found
      <span class="sub">start <code>companion/run-companion.bat</code> as admin — retrying…</span>`;
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
  PLANNED = Math.max(PLANNED, party.length);
  PARTY_FACET = null;
  render();
}
function toggleCompanion(){
  companionOn = !companionOn;
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
  const counts = {};
  party.forEach(w => { const r = WEAPONS[w].role_hint || "other"; counts[r] = (counts[r]||0) + 1; });
  const styleBit = STYLE !== "balanced" ? ` · ${(DATASET.styles[STYLE] || {}).name || STYLE}` : "";
  const lines = [
    `**${tpl().name}${styleBit}** — ${party.length}/${SIZE} — fitness ${fitness(party).toFixed(1)}/${maxFitness().toFixed(0)}`,
    Object.entries(counts).sort((a,b) => b[1]-a[1]).map(([r,n]) => `${n} ${r}`).join(" · "),
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
  if (e.target.closest("#facet-clear")){ setFacet(null); return; }
  const det = e.target.closest("[data-detail]");
  if (det){ renderDetail(det.dataset.detail); return; }
  const add = e.target.closest("[data-add]");
  if (add){ if (party.length < HARD_CAP){
    party.push(add.dataset.add);
    PARTY_FACET = null;   /* the new member must be visible */
    render(); } return; }
  if (e.target.closest("#forge")){
    /* Greedy auto-build: repeatedly take the engine's top pick. */
    const goal = Math.min(SIZE, HARD_CAP);
    while (party.length < goal){
      const r = recommend(party, 1);
      if (!r.length) break;
      party.push(r[0].w);
    }
    PARTY_FACET = null;   /* show the whole forged comp, not a filtered view */
    render();
    return;
  }
  const rm = e.target.closest("[data-remove]");
  if (rm){ party.splice(+rm.dataset.remove, 1); render(); return; }
  if (e.target.closest("#companion-connect")){ toggleCompanion(); return; }
  if (e.target.closest("#companion-load")){ loadCompanionParty(); return; }
  if (e.target.closest("#clear")){
    /* two-step: first click arms, second within 2.2s clears — a misclick
       must never wipe a 20-slot comp */
    const b = $("clear");
    if (b.dataset.armed === "1"){
      delete b.dataset.armed; b.textContent = "clear comp";
      party = []; PARTY_FACET = null; render();
    } else {
      b.dataset.armed = "1"; b.textContent = "really clear? click again";
      setTimeout(() => { delete b.dataset.armed; b.textContent = "clear comp"; }, 2200);
    }
    return;
  }
  const sz = e.target.closest("[data-size]");
  if (sz){ PLANNED = +sz.dataset.size; render(); return; }
  if (e.target.closest("#size-minus")){ PLANNED = Math.max(2, PLANNED - 1); render(); return; }
  if (e.target.closest("#size-plus")){ PLANNED = Math.min(HARD_CAP, PLANNED + 1); render(); return; }
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
  if (e.target.id === "content"){ CONTENT = e.target.value; PLANNED = baseSize(); party = []; PARTY_FACET = null; render(); }
  if (e.target.id === "style"){ STYLE = e.target.value; render(); }
  if (e.target.id === "tree-filter"){ treeFilter = e.target.value; renderPicker(); }
  if (e.target.id === "size-input"){
    const v = Math.round(+e.target.value);
    if (v >= 2 && v <= HARD_CAP){ PLANNED = v; render(); } else { e.target.value = PLANNED; }
  }
});
document.addEventListener("input", e => {
  if (e.target.id === "pick-filter"){ pickFilter = e.target.value; renderPicker(); }
});
document.addEventListener("keydown", e => {
  if ((e.key === "Enter" || e.key === " ")
      && e.target.matches("[data-bfilter],[data-rfilter],[data-pfilter]")){
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
  if (keys.length && party.length < HARD_CAP){ party.push(keys[0]); render(); }
});
/* A pasted share-link hash applies without a reload. saveHash() uses
   replaceState, which never fires hashchange, so this cannot loop. The
   party view-filter resets — it described the previous comp. */
window.addEventListener("hashchange", () => {
  if (loadHash()){ PARTY_FACET = null; render(); }
});

$("build-stamp").textContent = `v${META.version} · ${META.weapons_curated}/${META.weapons_total} curated`;

/* Boot: a shared link restores content/size/party; otherwise seed with the
   design doc's worked example (§4.3), if those sheets exist. */
const SEED = ["2H_LONGBOW","MAIN_ARCANESTAFF_UNDEAD","2H_ICECRYSTAL_UNDEAD"].filter(w => WEAPONS[w]);
if (!loadHash() && !loadStored()) party = SEED;
renderTreeFilter();
syncEngine();
render();

/* Parity guard. PARITY_EXPECTED is injected at build time by running
   engine/engine.py over the same seed party, so this compares the client
   against the Python engine's ACTUAL output rather than a hardcoded name that
   goes stale the moment a sheet is curated. Reported in the masthead chip. */
(function parity(){
  if (typeof PARITY_EXPECTED === "undefined" || !SEED.length) return;
  const e2 = new CompEngine(DATASET, "castle_outpost", 7);
  const got = {
    fitness: +e2.fitness(SEED).toFixed(2),
    recs: e2.recommend(SEED, 4).map(r => r.weapon),
    weaknesses: e2.weaknesses(SEED).map(x => x.cap),
  };
  const ok = JSON.stringify(got) === JSON.stringify(PARITY_EXPECTED);
  (ok ? console.info : console.error)("engine parity vs engine.py:",
    ok ? "OK" : "MISMATCH", ok ? got : {got, expected: PARITY_EXPECTED});
  const chip = $("parity-chip"), dot = $("parity-dot");
  if (chip) chip.textContent = ok ? "parity vs engine.py — OK" : "PARITY MISMATCH — do not trust";
  if (dot && !ok) dot.style.background = "var(--gap)";
})();
