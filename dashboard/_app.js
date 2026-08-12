"use strict";
/* Dashboard client. Reads the injected DATASET — the same
   pipeline/out/dataset-latest.json that engine/engine.py consumes. No
   capability numbers live in this file. Regenerate with:
       py -3 pipeline/build_dashboard.py                                     */

const META = DATASET._meta;
const WEAPONS = DATASET.weapons;
const SCORING = DATASET.scoring;
const W = SCORING.weights;
const GAMMA = W.gamma, ALPHA = W.alpha, BETA = W.beta, DELTA = W.delta;
const META_PRIOR = SCORING.meta_prior || {};
const SYNERGY_PAIRS = (SCORING.capability_synergies || []).map(s => [s.a, s.b, s.bonus]);

let CONTENT = Object.keys(DATASET.templates)[0];
let SIZE = DATASET.templates[CONTENT].base_size || 7;

const tpl = () => DATASET.templates[CONTENT];
const REQS = () => tpl().requirements;
const FLOORS = () => tpl().hard_floors || {};
const baseSize = () => tpl().base_size || 7;
const validatedSizes = () => tpl().validated_sizes || [baseSize()];

const target = cap => { const r = REQS()[cap];
  return r.scales ? r.target * SIZE / baseSize() : r.target; };
const softCap = cap => { const r = REQS()[cap];
  return r.scales ? r.soft_cap * SIZE / baseSize() : r.soft_cap; };

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

/* ---------------------------------------------------------------- engine
   Mirrors engine/engine.py exactly; parity is asserted at the bottom. */

function supply(party){
  const s = {};
  for (const w of party) for (const [c,v] of Object.entries(capsOf(w))) s[c] = (s[c]||0) + v;
  return s;
}
function floorPenalty(cap, have){
  const f = FLOORS()[cap];
  if (!f || SIZE < f.min_party_size || have >= f.floor_units) return 0;
  return f.penalty_mult * REQS()[cap].weight * (f.floor_units - have) / f.floor_units;
}
function fitness(party){
  const s = supply(party); let total = 0;
  for (const [cap, r] of Object.entries(REQS())){
    const have = s[cap] || 0, t = target(cap), soft = softCap(cap);
    total += r.weight * Math.pow(Math.min(1, have/t), GAMMA);
    if (have > soft) total -= 0.5 * r.weight * (have - soft) / t;
    total -= floorPenalty(cap, have);
  }
  return total;
}
const maxFitness = () => Object.values(REQS()).reduce((a,r) => a + r.weight, 0);
function synergy(party){
  const s = supply(party);
  return SYNERGY_PAIRS.reduce((a,[x,y,b]) => a + b * Math.min(s[x]||0, s[y]||0), 0);
}
function explain(party, cand){
  const s = supply(party), terms = [];
  for (const [cap, r] of Object.entries(REQS())){
    const gain = capsOf(cand)[cap] || 0;
    if (!gain) continue;
    const have = s[cap] || 0, t = target(cap);
    let d = r.weight * (Math.pow(Math.min(1,(have+gain)/t), GAMMA) - Math.pow(Math.min(1,have/t), GAMMA));
    d += floorPenalty(cap, have) - floorPenalty(cap, have + gain);
    if (d > 0.05) terms.push({d:+d.toFixed(2), cap, before:have, after:have+gain, target:t});
  }
  return terms.sort((a,b) => b.d - a.d);
}
function recommend(party, topN = 4){
  const bf = fitness(party), bs = synergy(party);
  return Object.keys(WEAPONS).map(w => {
    const dFit = fitness(party.concat([w])) - bf, dSyn = synergy(party.concat([w])) - bs;
    const meta = META_PRIOR[w] || 0;
    return {w, dFit, dSyn, meta, score: ALPHA*dFit + BETA*dSyn + DELTA*meta};
  }).sort((a,b) => b.score - a.score).slice(0, topN);
}
function weaknesses(party, topN = 3){
  const s = supply(party);
  return Object.entries(REQS()).map(([cap, r]) => ({
    cap, gap: r.weight * (1 - Math.pow(Math.min(1,(s[cap]||0)/target(cap)), GAMMA)),
  })).sort((a,b) => b.gap - a.gap).slice(0, topN);
}
function uncoveredCaps(party){
  const s = supply(party);
  return Object.entries(REQS()).filter(([cap, r]) =>
    r.weight >= 5 && (s[cap]||0)/target(cap) < 0.5).map(([cap]) => cap);
}

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

/* ---------------------------------------------------------------- render */

let party = [];
const $ = id => document.getElementById(id);

function renderSetup(){
  $("content").innerHTML = Object.entries(DATASET.templates)
    .map(([k,t]) => `<option value="${k}" ${k===CONTENT?"selected":""}>${t.name}</option>`).join("");
  $("sizes").innerHTML = [2,3,4,5,6,7,8,9,10].map(n =>
    `<button class="size-btn" data-size="${n}" aria-pressed="${n===SIZE}">${n}</button>`).join("");
  $("size-notice").innerHTML = validatedSizes().includes(SIZE) ? "" :
    `<div class="notice"><b>Extrapolated.</b> This template is fitted and validated at size ${validatedSizes().join(", ")} only. Per-player targets are scaled linearly to ${SIZE}; flat threshold targets are unchanged. Tier-2 validation must confirm each size before this is trustworthy.</div>`;
}
function renderRoster(){
  const rows = party.map((w,i) =>
    `<div class="slot"><span class="n mono">${String(i+1).padStart(2,"0")}</span>
      <span class="nm">${nameOf(w)}<span class="fn">${roleOf(w)}</span></span>
      <button class="x" data-remove="${i}" aria-label="Remove ${nameOf(w)}">&times;</button></div>`);
  for (let i = party.length; i < SIZE; i++)
    rows.push(`<div class="slot empty"><span class="n mono">${String(i+1).padStart(2,"0")}</span>open slot</div>`);
  $("roster").innerHTML = rows.join("");
}
function renderPicker(){
  $("picker").innerHTML = Object.keys(WEAPONS)
    .sort((a,b) => nameOf(a).localeCompare(nameOf(b)))
    .map(w => `<button class="pick" data-add="${w}" ${party.length >= SIZE ? "disabled" : ""}>
      <span class="nm">${nameOf(w)}</span>
      <span class="prov ${WEAPONS[w].status === "curated" ? "curated" : "draft"}">${WEAPONS[w].status === "curated" ? "curated" : "illustrative"}</span>
    </button>`).join("");
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
function renderRec(){
  if (party.length >= SIZE){
    $("rec-slot").innerHTML = `<div class="sec-label">Recommendation</div>
      <div class="rec"><div class="rec-body"><p class="why">Party is full at ${SIZE}. Remove a slot to see what the engine would swap in.</p></div></div>`;
    return;
  }
  const recs = recommend(party, 4), top = recs[0], terms = explain(party, top.w).slice(0,4);
  $("rec-slot").innerHTML = `
    <div class="sec-label">Recommendation — slot ${party.length + 1} of ${SIZE}</div>
    <div class="rec">
      <div class="rec-top">
        <div class="rec-eyebrow">Highest marginal gain</div>
        <div class="rec-name">${nameOf(top.w)}</div>
        <div class="rec-role">${roleOf(top.w)}</div>
      </div>
      <div class="rec-body">
        <p class="why">${whySentence(party, top.w)}</p>
        <div class="terms">${terms.map(t => `<div class="term">
          <span class="d">+${t.d.toFixed(2)}</span><span class="c">${t.cap}</span>
          <span class="mv">${t.before.toFixed(0)} → ${t.after.toFixed(0)} of ${t.target.toFixed(1)}</span></div>`).join("")}</div>
        <div class="formula">
          <span class="k">score</span> = ${ALPHA}·Δfitness + ${BETA}·Δsynergy + ${DELTA}·metaPrior<br>
          &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;= ${ALPHA}·<b>${top.dFit.toFixed(2)}</b> + ${BETA}·<b>${top.dSyn.toFixed(2)}</b> + ${DELTA}·<b>${top.meta.toFixed(2)}</b> = <b>${top.score.toFixed(2)}</b><br>
          <span class="k">metaPrior</span> is a hand-set guard value — real win-lift arrives in Phase 3 from battle data.
        </div>
        <button class="add" data-add="${top.w}">Add ${nameOf(top.w)} to party</button>
        <div><div class="sec-label" style="margin-bottom:8px">Alternatives</div>
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
  renderSetup(); renderRoster(); renderPicker(); renderFitness();
  renderGroups(); renderWeaknesses(); renderWarning(); renderRec(); renderFootnote();
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
  if (e.target.closest("#drawer-close")){ $("drawer").dataset.open = "false"; return; }
  if (!e.target.closest("#drawer")) $("drawer").dataset.open = "false";
});
document.addEventListener("change", e => {
  if (e.target.id === "content"){ CONTENT = e.target.value; SIZE = baseSize(); party = []; render(); }
});
document.addEventListener("keydown", e => { if (e.key === "Escape") $("drawer").dataset.open = "false"; });

$("build-stamp").textContent = `v${META.version} · ${META.weapons_curated}/${META.weapons_total} curated`;

/* Seed with the design doc's worked example (§4.3), if those sheets exist. */
const SEED = ["2H_LONGBOW","MAIN_ARCANESTAFF_UNDEAD","2H_ICECRYSTAL_UNDEAD"].filter(w => WEAPONS[w]);
party = SEED;
render();

/* Parity guard. PARITY_EXPECTED is injected at build time by running
   engine/engine.py over the same seed party, so this compares the client
   against the Python engine's ACTUAL output rather than a hardcoded name that
   goes stale the moment a sheet is curated. */
(function parity(){
  if (typeof PARITY_EXPECTED === "undefined" || !SEED.length) return;
  const got = {
    fitness: +fitness(SEED).toFixed(2),
    recs: recommend(SEED, 4).map(r => r.w),
    weaknesses: weaknesses(SEED).map(x => x.cap),
  };
  const ok = JSON.stringify(got) === JSON.stringify(PARITY_EXPECTED);
  (ok ? console.info : console.error)("engine parity vs engine.py:",
    ok ? "OK" : "MISMATCH", ok ? got : {got, expected: PARITY_EXPECTED});
})();
