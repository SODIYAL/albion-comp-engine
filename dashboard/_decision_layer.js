"use strict";
/* Decision-first UX pass.
   This module deliberately does not touch CompEngine scoring. It translates
   existing fitness, floor, weakness, recommendation and explanation output
   into a caller-first summary: status -> biggest need -> best next pick.
   Loaded after _app.js by build_ux_preview.py for branch review. */
(function(){
  function statusModel(){
    if (!party.length) return {tone:"empty", label:"Start your comp", critical:0, weak:0, excess:0};
    const s = supply(party);
    let critical = 0, weak = 0, excess = 0;
    for (const cap of Object.keys(REQS())){
      const have = s[cap] || 0;
      const want = target(cap) || 1;
      if (floorHit(cap, have)) critical++;
      else if (have / want < .65 && ENG.weight(cap) >= 4) weak++;
      if (have > softCap(cap)) excess++;
    }
    const label = critical ? "Critical gaps" : weak >= 2 ? "Needs work" : weak ? "Nearly ready" : "Core covered";
    const tone = critical ? "critical" : weak ? "warning" : "ready";
    return {tone, label, critical, weak, excess};
  }

  function topNeed(){
    if (!party.length) return null;
    const s = supply(party);
    const rows = weaknesses(party, 12).filter(x => x.gap >= .5).map(x => ({
      ...x,
      have:s[x.cap] || 0,
      want:target(x.cap),
      floor:floorHit(x.cap, s[x.cap] || 0),
      ratio:(s[x.cap] || 0) / Math.max(.001, target(x.cap))
    }));
    rows.sort((a,b) => Number(b.floor)-Number(a.floor) || b.gap-a.gap || ENG.weight(b.cap)-ENG.weight(a.cap));
    return rows[0] || null;
  }

  function afterPickGaps(w){
    const next = party.concat([w]);
    const sup = inPickContext(() => ENG.effectiveSupply(next));
    return inPickContext(() => ENG.weaknesses(next, 6)).filter(x => x.gap >= .5).slice(0,3)
      .map(x => ({...x, have:sup[x.cap] || 0, want:inPickContext(() => ENG.target(x.cap))}));
  }

  function renderDecisionLayer(){
    const host = document.getElementById("decision-layer");
    if (!host) return;
    const state = statusModel();
    const need = topNeed();
    const recs = RECS_CUR;
    const top = recs && recs[0];
    const f = party.length ? fitness(party) : null;
    const max = maxFitness();
    const pct = f === null ? 0 : Math.max(0, Math.min(100, f / Math.max(1,max) * 100));

    if (!top){
      host.innerHTML = `<div class="dl-status ${state.tone}"><div><span class="dl-kicker">Comp status</span><strong>${state.label}</strong></div><span class="dl-fit">${f === null ? "—" : pct.toFixed(0)+"%"} fit</span></div>`;
      return;
    }

    const terms = explain(party, top.w).slice(0,3);
    const remaining = afterPickGaps(top.w);
    const needHtml = need ? `<div class="dl-need ${need.floor ? "critical" : ""}">
      <span class="dl-kicker">Biggest need${need.floor ? " · hard floor" : ""}</span>
      <strong>${esc(capLabel(need.cap))}</strong>
      <span>${need.have.toFixed(0)} / ${need.want.toFixed(1)} covered</span>
    </div>` : `<div class="dl-need ready"><span class="dl-kicker">Diagnosis</span><strong>Core requirements covered</strong><span>Next pick improves depth rather than repairing a critical hole.</span></div>`;

    const gains = terms.map(t => `<li><b>+${t.d.toFixed(1)}</b> ${esc(capLabel(t.cap))}<span>${t.before.toFixed(0)} → ${t.after.toFixed(0)}</span></li>`).join("");
    const remain = remaining.length ? `<div class="dl-remain"><span class="dl-kicker">Still weak after this pick</span>${remaining.map(x => `<span>${esc(capLabel(x.cap))}</span>`).join("")}</div>` : `<div class="dl-remain clear"><span class="dl-kicker">After this pick</span><span>Core gaps are covered.</span></div>`;

    host.innerHTML = `
      <div class="dl-status ${state.tone}">
        <div><span class="dl-kicker">Comp status</span><strong>${state.label}</strong><small>${state.critical} critical · ${state.weak} weak${state.excess ? ` · ${state.excess} overstacked` : ""}</small></div>
        <span class="dl-fit">${pct.toFixed(0)}% <small>fitness</small></span>
      </div>
      ${needHtml}
      <div class="dl-pick">
        <div class="dl-pick-head"><span class="dl-kicker">Best next pick</span><span class="dl-score">+${top.score.toFixed(2)} comp score</span></div>
        <div class="dl-weapon">${icon(top.w,72)}<div><button class="nm-btn" data-detail="${top.w}">${nameOf(top.w)}</button><span>${esc(roleOf(top.w, top.combo))}</span></div></div>
        <p>${whySentence(party, top.w)}</p>
        <ul class="dl-gains">${gains}</ul>
        ${remain}
        <button class="cb-add dl-add" data-add="${top.w}">Add ${nameOf(top.w)}</button>
      </div>`;
  }

  /* _app.js owns render(). Wrap it rather than duplicating engine state. */
  const baseRender = render;
  render = function(){ baseRender(); renderDecisionLayer(); };
  renderDecisionLayer();
})();
