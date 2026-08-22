"use strict";
/* Decision-first UX layer.
   CompEngine remains the authority. This file translates its existing
   floors, weaknesses, recommendation ordering and marginal terms into the
   order a caller needs them: status -> biggest need -> next pick -> why ->
   what is still missing. */
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
      ...x,
      have:s[x.cap] || 0,
      want:target(x.cap),
      floor:floorHit(x.cap, s[x.cap] || 0),
      ratio:(s[x.cap] || 0) / Math.max(.001, target(x.cap))
    }));
    rows.sort((a,b) => Number(b.floor)-Number(a.floor)
      || b.gap-a.gap || ENG.weight(b.cap)-ENG.weight(a.cap));
    return rows;
  }

  function afterPickGaps(rec){
    const next = party.concat([rec.w]);
    /* Existing members keep their actual resolved kits. The candidate keeps
       the combo CompEngine selected for this recommendation. */
    const combos = COMBOS_CUR.concat([rec.combo === undefined ? null : rec.combo]);
    return inPickContext(() => {
      const sup = ENG.effectiveSupply(next, combos);
      return ENG.weaknesses(next, 8, combos).filter(x => x.gap >= .5).slice(0,3)
        .map(x => ({...x, have:sup[x.cap] || 0, want:ENG.target(x.cap)}));
    });
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
        ${remain}
        <button class="cb-add dl-add" data-add="${top.w}">Add ${nameOf(top.w)}</button>
      </div>`;
  }

  /* _app.js owns state and rendering. Wrap its render function so every real
     roster/content/style/loadout change refreshes this surface too. */
  const baseRender = render;
  render = function(){ baseRender(); renderDecisionLayer(); };
  renderDecisionLayer();
})();
