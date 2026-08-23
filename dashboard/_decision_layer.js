"use strict";
/* Decision-first UX layer.
   CompEngine remains the authority. This file translates its existing
   floors, weaknesses, recommendation ordering and marginal terms into the
   order a caller needs them: status -> biggest need -> next pick -> why ->
   what is still missing.
   Plus two on-demand caller workflows (PR #6, 2026-08-22), folded shut by
   default so the party dock keeps its above-the-fold seat:
   - a player weapon pool that feeds CompEngine.recommend(pool)
   - a swap lab comparing exact roster replacements, applied through the
     dashboard's existing swap handler.
   Neither feature changes scoring. */
(function(){
  const PLAYER_POOL = new Set();
  let POOL_QUERY = "";
  let SWAP_SLOT = 0;
  let TOOLS_OPEN = false;
  function statusModel(){
    if (!party.length) return {tone:"empty", label:"Start your comp", critical:0, weak:0, excess:0};
    const s = supply(party);
    let critical = 0, weak = 0, excess = 0;
    /* Display-only triage thresholds — these classify, they never score.
       "Weak" = under 65% of target on a capability the template weights
       at 4+; revisit if template weights are retuned. */
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

  /* Comp identity (F-V3-2, 2026-08-23): what the party is BECOMING, in
     playstyle vocabulary. ENG.compIdentity is descriptive engine output —
     this renders it verbatim and adds nothing. */
  function identityLine(){
    if (!party.length || typeof ENG.compIdentity !== "function") return "";
    const id = ENG.compIdentity(party, COMBOS_CUR);
    if (!id.label) return "";
    const tag = id.style && id.strength === "leaning"
      ? `${id.label} · leaning` : id.label;
    const conf = id.conflicts.length
      ? `<small class="dl-id-conflict" title="${esc(id.conflicts[0].note)}">⚠ ${
          id.conflicts.map(c => esc(c.display_name)).join(", ")} pull${
          id.conflicts.length > 1 ? "" : "s"} against the ${
          id.conflicts[0].side === "melee" ? "ranged" : "melee"} core</small>`
      : "";
    return `<span class="dl-identity"><span class="dl-kicker">becoming</span>${esc(tag)}</span>${conf}`;
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

  function poolKeys(){
    return Array.from(PLAYER_POOL).filter(w => WEAPONS[w] && !WEAPONS[w].removed);
  }

  function playerPoolRecs(){
    const keys = poolKeys();
    if (!keys.length || party.length >= HARD_CAP) return [];
    return inPickContext(() => ENG.recommend(party, keys.length, keys, COMBOS_CUR))
      .map(r => ({w:r.weapon, score:r.score, combo:r.combo}));
  }

  function poolSearchResults(){
    const q = POOL_QUERY.trim().toLowerCase();
    if (!q) return [];
    return Object.keys(WEAPONS)
      .filter(w => !WEAPONS[w].removed && !PLAYER_POOL.has(w))
      .filter(w => (WEAPONS[w].display_name || w).toLowerCase().includes(q)
                || w.toLowerCase().includes(q))
      .sort((a,b) => (WEAPONS[a].display_name || a).localeCompare(WEAPONS[b].display_name || b))
      .slice(0,8);
  }

  /* Swaps keep the party size, so every evaluation here runs in the ROSTER
     context — no inPickContext (matches the engine's own swap_review). */
  function slotRanking(i){
    if (!party.length || i < 0 || i >= party.length) return null;
    const cur = party[i];
    let keys = poolKeys().filter(w => w !== cur);
    if (!keys.length){
      /* no pool: reuse the memoized full-pool sweep the roster popovers
         already pay for, instead of a second 40-100ms sweep per render */
      const review = swapReviewCached()[i];
      if (!review) return null;
      return {cur, curScore:review.score,
              rows:review.options.map(x => ({w:x.weapon, score:x.score, gain:x.gain}))};
    }
    const rest = party.slice(0,i).concat(party.slice(i+1));
    const restCombos = COMBOS_CUR.slice(0,i).concat(COMBOS_CUR.slice(i+1));
    const current = ENG.recommend(rest, 1, [cur], restCombos)[0];
    const ranked = ENG.recommend(rest, keys.length, keys, restCombos)
      .filter(r => r.weapon !== cur);
    return {cur, curScore:current ? current.score : 0,
            rows:ranked.map(r => ({w:r.weapon, score:r.score,
              gain:r.score-(current ? current.score : 0), combo:r.combo}))};
  }

  function swapImpact(i, cand){
    if (!party[i] || !WEAPONS[cand]) return null;
    const rest = party.slice(0,i).concat(party.slice(i+1));
    const restCombos = COMBOS_CUR.slice(0,i).concat(COMBOS_CUR.slice(i+1));
    const rr = ENG.recommend(rest, 1, [cand], restCombos)[0];
    if (!rr) return null;
    const np = party.slice(); np[i] = cand;
    const nc = COMBOS_CUR.slice(); nc[i] = rr.combo;
    const before = supply(party);
    const after = ENG.effectiveSupply(np, nc);
    const capRows = Object.keys(REQS()).map(cap => ({
      cap, d:(after[cap]||0)-(before[cap]||0)
    })).filter(x => Math.abs(x.d) > .05)
      .sort((a,b) => Math.abs(b.d)*ENG.weight(b.cap)-Math.abs(a.d)*ENG.weight(a.cap));
    const newFit = ENG.fitness(np, nc);
    return {delta:newFit-fitness(party), caps:capRows.slice(0,5),
            newWeak:ENG.weaknesses(np, 1, nc)[0]};
  }

  function renderPlayerTools(host){
    const keys = poolKeys();
    const search = poolSearchResults();
    const recs = playerPoolRecs();
    const best = recs[0] || null;
    if (SWAP_SLOT >= party.length) SWAP_SLOT = Math.max(0, party.length-1);
    const swap = party.length ? slotRanking(SWAP_SLOT) : null;

    const chips = keys.length ? keys.map(w =>
      `<button class="dl-pool-chip" data-pool-remove="${w}" title="remove from this player's pool">${icon(w,24)}<span>${nameOf(w)}</span><b>×</b></button>`).join("")
      : `<span class="dl-tool-note">Add the weapons this player can actually play.</span>`;

    const searchRows = search.map(w =>
      `<button class="dl-search-row" data-pool-add="${w}">${icon(w,28)}<span>${nameOf(w)}</span><small>${esc(roleLabel(roleHint(w)))}</small></button>`).join("");

    const poolRank = best ? `<div class="dl-pool-best">
      <span class="dl-kicker">Best from this player's pool</span>
      <div class="dl-pool-hero">${icon(best.w,44)}<strong>${nameOf(best.w)}</strong><b>+${best.score.toFixed(2)}</b></div>
      <p>${whySentence(party, best.w)}</p>
      <button class="cb-add" data-add="${best.w}">Add ${nameOf(best.w)}</button>
      ${recs.length > 1 ? `<div class="dl-mini-rank">${recs.slice(1,5).map((r,i) =>
        `<span>${i+2}. ${nameOf(r.w)} <b>${r.score >= 0 ? "+" : ""}${r.score.toFixed(2)}</b></span>`).join("")}</div>` : ""}
    </div>` : `<div class="dl-pool-best empty"><span class="dl-kicker">Best available</span><strong>Build this player's pool first</strong><p>Once you select their weapons, Comp Forge ranks only those choices for the next slot.</p></div>`;

    let swapHtml = `<div class="dl-tool-note">${party.length
      ? "Swap comparison needs a second member — or a player pool to draw candidates from."
      : "Add a party member to compare replacements."}</div>`;
    if (swap){
      const slotOpts = party.map((w,i) =>
        `<option value="${i}" ${i === SWAP_SLOT ? "selected" : ""}>${i+1}. ${esc(WEAPONS[w].display_name || w)}</option>`).join("");
      const rows = swap.rows.slice(0,5).map(r => {
        const imp = swapImpact(SWAP_SLOT, r.w);
        const fit = imp ? `${imp.delta >= 0 ? "+" : ""}${imp.delta.toFixed(1)} fitness` : "";
        const cap = imp && imp.caps[0] ? `${imp.caps[0].d >= 0 ? "+" : ""}${imp.caps[0].d.toFixed(1)} ${esc(capLabel(imp.caps[0].cap))}` : "";
        const weak = imp && imp.newWeak ? `next gap: ${esc(capLabel(imp.newWeak.cap))}` : "core gaps covered";
        return `<div class="dl-swap-row">
          <div class="dl-swap-main">${icon(r.w,38)}<div><strong>${nameOf(r.w)}</strong><span>${fit}${cap ? ` · ${cap}` : ""}</span><small>${weak}</small></div></div>
          <div class="dl-swap-actions"><b class="${r.gain >= 0 ? "up" : "down"}">${r.gain >= 0 ? "+" : ""}${r.gain.toFixed(2)} slot score</b>
          <button data-swapat="${SWAP_SLOT}" data-swapto="${r.w}">Apply swap</button></div>
        </div>`;
      }).join("");
      swapHtml = `<label class="dl-slot-label">Compare slot <select id="dl-swap-slot">${slotOpts}</select></label>
        <div class="dl-current">Current: ${icon(swap.cur,28)} <strong>${nameOf(swap.cur)}</strong><span>slot score ${swap.curScore.toFixed(2)}</span></div>
        <div class="dl-swap-list">${rows || `<span class="dl-tool-note">Nothing in the pool beats keeping this slot as-is${keys.length ? "" : " — no better options at this content and size"}.</span>`}</div>`;
    }

    /* the fold lives AFTER the wheel stage in the DOM: on the hero grid it
       auto-places below the party strip (keeping the one-screen budget),
       and on stacked layouts it reads as the section after the stage */
    const old = document.getElementById("dl-tools-fold");
    if (old) old.remove();
    const fold = document.createElement("details");
    fold.className = "dl-tools-fold";
    fold.id = "dl-tools-fold";
    fold.dataset.toolsFold = "1";
    if (TOOLS_OPEN) fold.open = true;
    fold.innerHTML = `<summary>Caller tools — player pool · swap impact${keys.length ? `<span class="cnt">${keys.length} in pool</span>` : ""}</summary>
    <div class="dl-tools"><div class="dl-tool-card">
      <div class="dl-tool-head"><div><span class="dl-kicker">Player weapon pool</span><h3>What can this player play?</h3></div>${keys.length ? `<button class="dl-clear-pool" id="dl-clear-pool">clear ${keys.length}</button>` : ""}</div>
      <div class="dl-pool-chips">${chips}</div>
      <div class="dl-pool-search"><input id="dl-pool-search" value="${esc(POOL_QUERY)}" placeholder="Search weapons to add…" autocomplete="off">${searchRows ? `<div class="dl-search-results">${searchRows}</div>` : ""}</div>
      ${poolRank}
    </div>
    <div class="dl-tool-card">
      <div class="dl-tool-head"><div><span class="dl-kicker">Swap impact</span><h3>What changes if this slot swaps?</h3></div></div>
      ${swapHtml}
    </div></div>`;
    const stage = document.querySelector(".wheelstage");
    if (stage) stage.after(fold); else host.appendChild(fold);
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
      renderPlayerTools(host);
      return;
    }

    if (!top){
      host.innerHTML = `<div class="dl-status ${state.tone} dl-empty"><div><span class="dl-kicker">Comp status</span><strong>${state.label}</strong><small>${state.critical} critical · ${state.weak} weak${state.excess ? ` · ${state.excess} overstacked` : ""}</small>${identityLine()}</div><span class="dl-fit">${pct.toFixed(0)}%<small>fitness</small></span></div>`;
      renderPlayerTools(host);
      return;
    }

    const terms = explain(party, top.w).slice(0,3);
    const remaining = afterPickGaps(top);
    /* need + pick are ONE card (owner 2026-08-22): the biggest need is the
       question, the pick is the answer — the need renders as the card's
       header line, runner-up gaps as inline chips. The reclaimed column
       goes to the wheel. */
    const alsoThin = needs.slice(1, 4);
    const needline = need ? `<div class="dl-needline${need.floor ? " critical" : ""}">
      <div class="dl-nl-main"><span class="dl-kicker">Biggest need${need.floor ? " · hard floor" : ""}</span>
        <strong>${esc(capLabel(need.cap))}</strong>
        <span class="dl-nd-sub">${+need.have.toFixed(1)} / ${need.want.toFixed(1)} covered</span></div>
      ${alsoThin.length ? `<div class="dl-nd-chips"><span class="dl-kicker">also thin</span>${
        alsoThin.map(x => `<span title="${+x.have.toFixed(1)} / ${x.want.toFixed(1)} covered">${esc(capLabel(x.cap))}</span>`).join("")}${
        needs.length > 4 ? `<em>+${needs.length - 4} more</em>` : ""}</div>` : ""}
    </div>` : `<div class="dl-needline ready">
      <div class="dl-nl-main"><span class="dl-kicker">Diagnosis</span>
        <strong>Core requirements covered</strong>
        <span class="dl-nd-sub">The next slot improves depth instead of repairing a load-bearing hole.</span></div>
    </div>`;

    const gains = terms.map(t => `<li><b>+${t.d.toFixed(1)}</b> ${esc(capLabel(t.cap))}<span>${t.before.toFixed(0)} → ${t.after.toFixed(0)} / ${t.target.toFixed(1)}</span></li>`).join("");
    const remain = remaining.length ? `<div class="dl-remain"><span class="dl-kicker">Still weak after this pick</span>${remaining.map(x => `<span title="${x.have.toFixed(0)} / ${x.want.toFixed(1)}">${esc(capLabel(x.cap))}</span>`).join("")}</div>` : `<div class="dl-remain clear"><span class="dl-kicker">After this pick</span><span>Core gaps are covered.</span></div>`;
    /* observed killboard context (PR #5 integration): _app.js owns the
       cohort math; the note appears only when cohorts echo this pick */
    const observed = (typeof observedLine === "function") ? observedLine(top.w) : "";
    /* alternatives, rehomed (2026-08-22): the hidden flank carried the
       click-to-add alternatives — a single take-it-or-leave-it pick is
       not a recommendation surface, so the runners-up live here now */
    const alts = (recs || []).slice(1, 4);
    const altsHtml = alts.length ? `<div class="dl-alts"><span class="dl-kicker">instead — click to add</span><div class="dl-alt-row">${
      alts.map(r => {
        const t0 = explain(party, r.w)[0];
        return `<button class="dl-alt" data-add="${r.w}" title="${t0 ? `+${t0.d.toFixed(1)} ${esc(capLabel(t0.cap))} — ` : ""}click to add">${icon(r.w, 24)}
          <span class="dl-alt-nm">${nameOf(r.w)}</span>
          <span class="dl-alt-sc">${r.score.toFixed(2)}</span></button>`;
      }).join("")}</div></div>` : "";

    host.innerHTML = `
      <div class="dl-status ${state.tone}">
        <div><span class="dl-kicker">Comp status</span><strong>${state.label}</strong><small>${state.critical} critical · ${state.weak} weak${state.excess ? ` · ${state.excess} overstacked` : ""}</small>${identityLine()}</div>
        <span class="dl-fit">${pct.toFixed(0)}%<small>fitness</small></span>
      </div>
      <div class="dl-pick">
        ${needline}
        <div class="dl-pick-head"><span class="dl-kicker">Best next pick · slot ${Math.min(party.length + 1, HARD_CAP)}</span><span class="dl-score">+${top.score.toFixed(2)} comp score</span></div>
        <div class="dl-weapon">${icon(top.w,72)}<div><button class="nm-btn" data-detail="${top.w}">${nameOf(top.w)}</button><span>${esc(roleOf(top.w, top.combo))}</span></div></div>
        <p>${whySentence(party, top.w)}</p>
        <ul class="dl-gains">${gains}</ul>
        ${observed}
        ${remain}
        <button class="cb-add dl-add" data-add="${top.w}">Add ${nameOf(top.w)}</button>
        ${altsHtml}
      </div>`;
    renderPlayerTools(host);
  }

  /* Caller-tools state lives outside _app.js render (pool edits and slot
     picks re-render this layer only; roster changes come through render). */
  document.addEventListener("input", e => {
    if (e.target && e.target.id === "dl-pool-search"){
      POOL_QUERY = e.target.value;
      renderDecisionLayer();
      const el = document.getElementById("dl-pool-search");
      if (el){ el.focus(); el.setSelectionRange(el.value.length, el.value.length); }
    }
  });
  document.addEventListener("change", e => {
    if (e.target && e.target.id === "dl-swap-slot"){
      SWAP_SLOT = +e.target.value; renderDecisionLayer();
    }
  });
  document.addEventListener("click", e => {
    const add = e.target.closest && e.target.closest("[data-pool-add]");
    if (add){ PLAYER_POOL.add(add.dataset.poolAdd); POOL_QUERY = ""; renderDecisionLayer(); return; }
    const rm = e.target.closest && e.target.closest("[data-pool-remove]");
    if (rm){ PLAYER_POOL.delete(rm.dataset.poolRemove); renderDecisionLayer(); return; }
    if (e.target.closest && e.target.closest("#dl-clear-pool")){ PLAYER_POOL.clear(); renderDecisionLayer(); }
  });
  /* toggle doesn't bubble, but it does capture — keep the fold's open state
     across the innerHTML rebuilds every re-render performs */
  document.addEventListener("toggle", e => {
    if (e.target && e.target.dataset && e.target.dataset.toolsFold) TOOLS_OPEN = e.target.open;
  }, true);

  /* _app.js owns state and rendering. Wrap its render function so every real
     roster/content/style/loadout change refreshes this surface too. */
  const baseRender = render;
  render = function(){ baseRender(); renderDecisionLayer(); };
  renderDecisionLayer();
})();
