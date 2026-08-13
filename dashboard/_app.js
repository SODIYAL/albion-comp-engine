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
let SIZE = ENG.size;

function syncEngine(){ ENG.setContent(CONTENT, SIZE); }

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
  SIZE = (p.n && +p.n >= 2 && +p.n <= 60) ? +p.n : baseSize();
  if (p.p) party = p.p.split(",").filter(w => WEAPONS[w]);
  syncEngine();
  return true;
}
function saveHash(){
  history.replaceState(null, "",
    `#c=${CONTENT}&n=${SIZE}${party.length ? "&p=" + party.join(",") : ""}`);
}

/* ---------------------------------------------------------------- render */

let party = [];
let pickFilter = "";
const $ = id => document.getElementById(id);

/* Content decides the sensible party sizes; validated + base always present. */
function sizeOptions(){
  const preset = baseSize() <= 10 ? [2,3,4,5,6,7,8,9,10] : [10,12,15,20,25,30];
  return [...new Set(preset.concat(validatedSizes(), [baseSize()]))].sort((a,b) => a-b);
}

const PENDING = [["hellgate_5v5","Hellgate 5v5"], ["roads_7","Roads of Avalon"]];

function renderSetup(){
  $("content").innerHTML = Object.entries(DATASET.templates)
    .map(([k,t]) => `<option value="${k}" ${k===CONTENT?"selected":""}>${t.name} — ${t.base_size} players</option>`)
    .join("") + PENDING.filter(([k]) => !DATASET.templates[k])
    .map(([k,n]) => `<option value="${k}" disabled>${n} — template pending</option>`).join("");
  $("sizes").innerHTML = sizeOptions().map(n =>
    `<button class="size-btn" data-size="${n}" aria-pressed="${n===SIZE}">${n}</button>`).join("");
  $("size-notice").innerHTML = validatedSizes().includes(SIZE) ? "" :
    `<div class="notice"><b>Extrapolated.</b> This template is fitted and validated at size ${validatedSizes().join(", ")} only. Per-player targets are scaled linearly to ${SIZE}; flat threshold targets are unchanged. Tier-2 validation must confirm each size before this is trustworthy.</div>`;
}
function renderTally(){
  const counts = {};
  party.forEach(w => { const r = WEAPONS[w].role_hint || "other"; counts[r] = (counts[r]||0) + 1; });
  $("tally").innerHTML = party.length
    ? Object.entries(counts).sort((a,b) => b[1]-a[1])
        .map(([r,n]) => `<span class="t"><b>${n}</b> ${esc(r)}</span>`).join("")
      + `<span class="t"><b>${SIZE - party.length}</b> open</span>`
    : "";
}
function renderRoster(){
  const rows = party.map((w,i) =>
    `<div class="slot"><span class="n mono">${String(i+1).padStart(2,"0")}</span>
      <span class="nm">${nameOf(w)}<span class="fn">${roleOf(w)}</span></span>
      <button class="x" data-remove="${i}" aria-label="Remove ${nameOf(w)}">&times;</button></div>`);
  /* open slots collapse: one dashed "next" row, one "+N more" line */
  const open = SIZE - party.length;
  if (open > 0)
    rows.push(`<div class="slot next"><span class="n mono">${String(party.length+1).padStart(2,"0")}</span>next slot — pick below</div>`);
  if (open > 1)
    rows.push(`<div class="slot more">+ ${open - 1} more open slot${open > 2 ? "s" : ""}</div>`);
  $("roster").innerHTML = rows.join("");
}
function filteredWeapons(){
  const q = pickFilter.trim().toLowerCase();
  return Object.keys(WEAPONS)
    .sort((a,b) => nameOf(a).localeCompare(nameOf(b)))
    .filter(w => !q || (WEAPONS[w].display_name || w).toLowerCase().includes(q));
}
function renderPicker(){
  const keys = filteredWeapons();
  $("picker").innerHTML = keys.map(w => `<button class="pick" data-add="${w}" ${party.length >= SIZE ? "disabled" : ""}>
      <span class="nm">${nameOf(w)}<span class="fn">${roleOf(w)}</span></span>
      ${WEAPONS[w].status === "curated" ? "" : '<span class="prov draft">illustrative</span>'}
    </button>`).join("")
    || `<p class="ev-empty">Nothing matches “${esc(pickFilter)}”.</p>`;
}
function renderFitness(){
  const f = fitness(party), max = maxFitness();
  $("fit-num").textContent = f.toFixed(1);
  $("fit-of").textContent = `/ ${max}`;
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
        <button class="cap-name" data-cap="${c}">${c}${floorHit ? '<span class="tag floor">below floor</span>' : ""}${over ? '<span class="tag over">overstacked</span>' : ""}</button>
        <span class="cap-val">${have.toFixed(0)} / ${t.toFixed(1)}</span>
        <span class="cap-bar"><i class="${cls}" style="width:${over ? 100 : Math.min(100, have/t*100)}%"></i></span>
      </div>`;
    }).join("");
    return rows ? `<div class="grp"><h3>${g}</h3>${rows}</div>` : "";
  }).join("");
}
function renderWeaknesses(){
  const s = supply(party);
  $("weaknesses").innerHTML = weaknesses(party).map((x,i) =>
    `<div class="weak"><span class="rank">${String(i+1).padStart(2,"0")}</span>
      <span class="txt">You have <b>${(s[x.cap]||0).toFixed(0)}</b> of <b>${target(x.cap).toFixed(1)}</b> units of <b>${x.cap}</b> — ${prose(x.cap)}.</span>
      <span class="sc">−${x.gap.toFixed(1)}</span></div>`).join("");
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
    $("cb-next").innerHTML = `<div class="eyebrow">Party full</div>
      <div class="cb-row"><span class="cb-full">All ${SIZE} slots filled. Remove someone to explore swaps.</span></div>`;
    return;
  }
  const top = recs[0];
  $("cb-next").innerHTML = `
    <div class="eyebrow">Next pick — slot ${party.length + 1} of ${SIZE}</div>
    <div class="cb-row">
      <span><span class="nm">${nameOf(top.w)}</span><span class="fn rl">${roleOf(top.w)}</span></span>
      <button class="cb-add" data-add="${top.w}">Add to party</button>
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
              <span class="nm">${nameOf(r.w)}</span>
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
    Curated sheets cite an equippable spell for every nonzero score. Illustrative sheets carry design-doc §2.3 placeholder numbers and are <b>not</b> evidence-checked — they exist to keep the engine runnable during curation. Click any capability for its evidence chain.`;
}
function renderEvidence(cap){
  const rows = party.filter(w => capsOf(w)[cap]).map(w => {
    const ev = (WEAPONS[w].evidence || {})[cap];
    return `<tr><td>${nameOf(w)}</td><td class="sc">${capsOf(w)[cap]}</td>
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
function render(){
  syncEngine(); saveHash();
  const recs = party.length < SIZE ? recommend(party, 4) : null;
  renderSetup(); renderTally(); renderRoster(); renderPicker(); renderFitness();
  renderCmdNext(recs); renderGroups(); renderWeaknesses(); renderWarning();
  renderRecDetail(recs); renderFootnote();
}

document.addEventListener("click", e => {
  const add = e.target.closest("[data-add]");
  if (add && !add.disabled){ if (party.length < SIZE){ party.push(add.dataset.add); render(); } return; }
  const rm = e.target.closest("[data-remove]");
  if (rm){ party.splice(+rm.dataset.remove, 1); render(); return; }
  const sz = e.target.closest("[data-size]");
  if (sz){ SIZE = +sz.dataset.size; if (party.length > SIZE) party.length = SIZE; render(); return; }
  const cap = e.target.closest("[data-cap]");
  if (cap){ renderEvidence(cap.dataset.cap); return; }
  if (e.target.closest("#share")){
    saveHash();
    if (navigator.clipboard && navigator.clipboard.writeText)
      navigator.clipboard.writeText(location.href).then(() => {
        $("share").textContent = "copied";
        setTimeout(() => { $("share").textContent = "copy share link"; }, 1400);
      });
    return;
  }
  if (e.target.closest("#drawer-close")){ $("drawer").dataset.open = "false"; return; }
  if (!e.target.closest("#drawer")) $("drawer").dataset.open = "false";
});
document.addEventListener("change", e => {
  if (e.target.id === "content"){ CONTENT = e.target.value; SIZE = baseSize(); party = []; render(); }
});
document.addEventListener("input", e => {
  if (e.target.id === "pick-filter"){ pickFilter = e.target.value; renderPicker(); }
});
document.addEventListener("keydown", e => {
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
  if (keys.length && party.length < SIZE){ party.push(keys[0]); render(); }
});
/* A pasted share-link hash applies without a reload. saveHash() uses
   replaceState, which never fires hashchange, so this cannot loop. */
window.addEventListener("hashchange", () => { if (loadHash()) render(); });

$("build-stamp").textContent = `v${META.version} · ${META.weapons_curated}/${META.weapons_total} curated`;

/* Boot: a shared link restores content/size/party; otherwise seed with the
   design doc's worked example (§4.3), if those sheets exist. */
const SEED = ["2H_LONGBOW","MAIN_ARCANESTAFF_UNDEAD","2H_ICECRYSTAL_UNDEAD"].filter(w => WEAPONS[w]);
if (!loadHash()) party = SEED;
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
