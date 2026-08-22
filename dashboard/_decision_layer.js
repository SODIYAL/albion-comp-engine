"use strict";
/* Decision-first UX + display-only killboard context.
   CompEngine remains the authority. Killboard observations never change a
   score or recommendation; they are a separate evidence channel. */
(function(){
  function statusModel(){
    if (!party.length) return {tone:"empty", label:"Start your comp", critical:0, weak:0, excess:0};
    const s = supply(party);
    let critical = 0, weak = 0, excess = 0;
    for (const cap of Object.keys(REQS())){
      const have = s[cap] || 0;
      const want = Math.max(.001, target(cap) || 0);
      if (floorHit(cap, have)) critical++;
      else if (have / want < .65 && ENG.weight(cap) >= 4) weak++;
      if (have > softCap(cap)) excess++;
    }
    const label = critical ? "Critical gaps" : weak >= 2 ? "Needs work" : weak ? "Nearly ready" : "Core covered";
    const tone = critical ? "critical" : weak ? "warning" : "ready";
    return {tone, label, critical, weak, excess};
  }

  function diagnosisRows(){
    if (!party.length) return [];
    const s = supply(party);
    const rows = weaknesses(party, 12).filter(x => x.gap >= .5).map(x => ({
      ...x, have:s[x.cap] || 0, want:target(x.cap),
      floor:floorHit(x.cap, s[x.cap] || 0),
      ratio:(s[x.cap] || 0) / Math.max(.001, target(x.cap))
    }));
    rows.sort((a,b) => Number(b.floor)-Number(a.floor)
      || b.gap-a.gap || ENG.weight(b.cap)-ENG.weight(a.cap));
    return rows;
  }

  function afterPickGaps(rec){
    const next = party.concat([rec.w]);
    const combos = COMBOS_CUR.concat([rec.combo === undefined ? null : rec.combo]);
    return inPickContext(() => {
      const sup = ENG.effectiveSupply(next, combos);
      return ENG.weaknesses(next, 8, combos).filter(x => x.gap >= .5).slice(0,3)
        .map(x => ({...x, have:sup[x.cap] || 0, want:ENG.target(x.cap)}));
    });
  }

  /* ---------------- observed organization-cohort evidence ----------------
     sample_battles.py only groups actors when the kill feed states the same
     Alliance/Guild identity. These are NOT parties and NOT win-rate samples.
     We therefore call the result "observed together", never "teammates" or
     "successful comps". */
  function cohortContext(){
    if (typeof USAGE === "undefined" || !USAGE.cohorts) return null;
    const key = ENG.sizeBucket();
    const rows = (USAGE.cohorts[key] || []).filter(c => Array.isArray(c.weapons) && c.weapons.length >= 2);
    if (rows.length < 8) return null;
    return {key, rows, label:(typeof USAGE_BUCKET_LABEL !== "undefined" && USAGE_BUCKET_LABEL[key]) || key};
  }

  function cohortAffinity(){
    const ctx = cohortContext();
    if (!ctx || !party.length) return null;
    const selected = [...new Set(party)];
    const selectedSet = new Set(selected);
    const N = ctx.rows.length;
    const count = {};
    const baskets = ctx.rows.map(c => new Set(c.weapons.filter(w => WEAPONS[w])));
    baskets.forEach(s => s.forEach(w => { count[w] = (count[w] || 0) + 1; }));

    const minOverlap = Math.min(2, selected.length);
    const matched = {};
    const overlapHist = {};
    baskets.forEach(s => {
      const overlap = selected.reduce((n,w) => n + (s.has(w) ? 1 : 0), 0);
      if (overlap < minOverlap) return;
      overlapHist[overlap] = (overlapHist[overlap] || 0) + 1;
      s.forEach(w => {
        if (selectedSet.has(w)) return;
        const m = matched[w] || (matched[w] = {cohorts:0, overlapSum:0, pairCount:0, liftSum:0, liftN:0});
        m.cohorts++; m.overlapSum += overlap;
      });
    });

    Object.keys(matched).forEach(w => {
      selected.forEach(a => {
        if (!count[a] || !count[w]) return;
        let both = 0;
        baskets.forEach(s => { if (s.has(a) && s.has(w)) both++; });
        if (!both) return;
        const lift = both * N / (count[a] * count[w]);
        matched[w].pairCount += both;
        matched[w].liftSum += lift;
        matched[w].liftN++;
      });
      matched[w].lift = matched[w].liftN ? matched[w].liftSum / matched[w].liftN : 0;
      matched[w].avgOverlap = matched[w].cohorts ? matched[w].overlapSum / matched[w].cohorts : 0;
      matched[w].base = count[w] || 0;
    });

    const candidates = Object.entries(matched).map(([w,m]) => ({w,...m}))
      .filter(x => x.cohorts >= 2)
      .sort((a,b) => b.cohorts-a.cohorts || b.lift-a.lift || b.avgOverlap-a.avgOverlap);
    return {ctx, selected, N, count, candidates, overlapHist, minOverlap};
  }

  function observedFor(w){
    const a = cohortAffinity();
    if (!a) return null;
    const row = a.candidates.find(x => x.w === w);
    if (!row) return null;
    return {...row, total:a.N, label:a.ctx.label, minOverlap:a.minOverlap};
  }

  function observedLine(w){
    const o = observedFor(w);
    if (!o) return "";
    const lift = o.lift >= 1.15 ? `${o.lift.toFixed(1)}× pair affinity` : "no strong pair lift";
    return `<div class="dl-observed"><span class="dl-kicker">Observed killboard context · display only</span>
      <b>${o.cohorts} organization cohort${o.cohorts === 1 ? "" : "s"}</b> also fielded ${nameOf(w)} while showing at least ${o.minOverlap} of your selected weapons · ${lift}
      <small>same stated Alliance/Guild in a ${esc(o.label)}-size fight; not reconstructed party membership, win rate, or scoring input</small></div>`;
  }

  function renderDecisionLayer(){
    const host = document.getElementById("decision-layer");
    if (!host) return;
    const state = statusModel();
    const needs = diagnosisRows();
    const need = needs[0] || null;
    const recs = RECS_CUR;
    const top = recs && recs[0];
    const f = party.length ? fitness(party) : null;
    const max = maxFitness();
    const pct = f === null ? 0 : Math.max(0, Math.min(100, f / Math.max(1,max) * 100));

    if (!party.length){
      host.innerHTML = `<div class="dl-status dl-empty">
        <div><span class="dl-kicker">Build a party</span><strong>What should your next player bring?</strong>
        <p>Choose the content and playstyle, then add the weapons you already have. Comp Forge will diagnose the gaps before suggesting the next slot.</p></div>
        <span class="dl-fit">—<small>fitness</small></span>
      </div>`;
      return;
    }

    if (!top){
      host.innerHTML = `<div class="dl-status ${state.tone} dl-empty"><div><span class="dl-kicker">Comp status</span><strong>${state.label}</strong><small>${state.critical} critical · ${state.weak} weak${state.excess ? ` · ${state.excess} overstacked` : ""}</small></div><span class="dl-fit">${pct.toFixed(0)}%<small>fitness</small></span></div>`;
      return;
    }

    const terms = explain(party, top.w).slice(0,3);
    const remaining = afterPickGaps(top);
    const needHtml = need ? `<div class="dl-need ${need.floor ? "critical" : ""}">
      <span class="dl-kicker">Biggest need${need.floor ? " · hard floor" : ""}</span>
      <strong>${esc(capLabel(need.cap))}</strong>
      <span>${need.have.toFixed(0)} / ${need.want.toFixed(1)} covered${needs.length > 1 ? ` · ${needs.length - 1} other gap${needs.length > 2 ? "s" : ""}` : ""}</span>
    </div>` : `<div class="dl-need ready"><span class="dl-kicker">Diagnosis</span><strong>Core requirements covered</strong><span>The next slot improves depth instead of repairing a load-bearing hole.</span></div>`;

    const gains = terms.map(t => `<li><b>+${t.d.toFixed(1)}</b> ${esc(capLabel(t.cap))}<span>${t.before.toFixed(0)} → ${t.after.toFixed(0)} / ${t.target.toFixed(1)}</span></li>`).join("");
    const remain = remaining.length ? `<div class="dl-remain"><span class="dl-kicker">Still weak after this pick</span>${remaining.map(x => `<span title="${x.have.toFixed(0)} / ${x.want.toFixed(1)}">${esc(capLabel(x.cap))}</span>`).join("")}</div>` : `<div class="dl-remain clear"><span class="dl-kicker">After this pick</span><span>Core gaps are covered.</span></div>`;

    host.innerHTML = `
      <div class="dl-status ${state.tone}">
        <div><span class="dl-kicker">Comp status</span><strong>${state.label}</strong><small>${state.critical} critical · ${state.weak} weak${state.excess ? ` · ${state.excess} overstacked` : ""}</small></div>
        <span class="dl-fit">${pct.toFixed(0)}%<small>fitness</small></span>
      </div>
      ${needHtml}
      <div class="dl-pick">
        <div class="dl-pick-head"><span class="dl-kicker">Best next pick · slot ${Math.min(party.length + 1, HARD_CAP)}</span><span class="dl-score">+${top.score.toFixed(2)} comp score</span></div>
        <div class="dl-weapon">${icon(top.w,72)}<div><button class="nm-btn" data-detail="${top.w}">${nameOf(top.w)}</button><span>${esc(roleOf(top.w, top.combo))}</span></div></div>
        <p>${whySentence(party, top.w)}</p>
        <ul class="dl-gains">${gains}</ul>
        ${observedLine(top.w)}
        ${remain}
        <button class="cb-add dl-add" data-add="${top.w}">Add ${nameOf(top.w)}</button>
      </div>`;
  }

  /* Replace generic popularity with contextual observations when the newly
     generated cohort data is present. Old samples still fall back cleanly. */
  const baseMetaStrip = renderMetaStrip;
  renderMetaStrip = function(){
    const a = cohortAffinity();
    if (!a || !a.candidates.length){ baseMetaStrip(); return; }
    const sec = document.getElementById("meta-sec");
    const label = document.getElementById("meta-label");
    const strip = document.getElementById("meta-strip");
    const rows = a.candidates.slice(0,12);
    label.textContent = `Observed with your weapons — ${a.ctx.label}-size fights (${a.N} organization cohorts; display only)`;
    strip.innerHTML = rows.map((r,i) => {
      const affinity = r.lift >= 1.15 ? `${r.lift.toFixed(1)}× affinity` : "baseline pairing";
      return `<div class="meta-row meta-aff"><span class="rk">${String(i+1).padStart(2,"0")}</span>${icon(r.w,20)}
        <button class="nm-btn" data-detail="${r.w}">${nameOf(r.w)}</button>
        <span class="pct">${r.cohorts} cohorts · ${affinity}</span></div>`;
    }).join("") + `<div class="ka-note">Matches require ≥${a.minOverlap} selected weapon${a.minOverlap === 1 ? "" : "s"} in the same observed Alliance/Guild cohort. This is not party reconstruction or effectiveness data and never changes recommendation scores.</div>`;
    sec.hidden = false;
  };

  const baseRender = render;
  render = function(){ baseRender(); renderDecisionLayer(); };
  renderMetaStrip();
  renderDecisionLayer();
})();
