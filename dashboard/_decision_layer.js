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
    const sfl = supplyFloor(party);   /* Option C floor basis */
    let critical = 0, weak = 0, excess = 0;
    /* Display-only triage thresholds — these classify, they never score.
       "Weak" = under 65% of target on a capability the template weights
       at 4+; revisit if template weights are retuned. */
    for (const cap of Object.keys(REQS())){
      const have = s[cap] || 0;
      const want = Math.max(.001, target(cap) || 0);
      if (floorHit(cap, sfl[cap] || 0)) critical++;
      else if (have / want < .65 && ENG.weight(cap) >= 4) weak++;
      if (have > softCap(cap)) excess++;
    }
    const label = critical ? "Critical gaps" : weak >= 2 ? "Needs work" : weak ? "Nearly ready" : "Core covered";
    const tone = critical ? "critical" : weak ? "warning" : "ready";
    return {tone, label, critical, weak, excess};
  }

  /* ================= COMP-STATUS RADAR (owner 2026-08-26) =================
     The status card IS the diagram: one axis per capability GROUP (the same
     taxonomy the deep board's renderGroups uses, "Other" guard included),
     plotted as supply vs template target, with everything textual living in
     hover popups. The center shows what the comp is BECOMING (comp_identity
     verbatim: playstyle glyph, dashed ring while "leaning", solid when
     strong); its popup carries status triage, fitness, kill pressure, and
     the role advisory. Pure display translation of existing engine output —
     nothing here scores (F-V3-2, R5). */
  const DL_ICONS = {
    plus:      "M12 4v16M4 12h16",
    shield:    "M12 3l7 3v5.5c0 4.8-3.2 7.8-7 9.5-3.8-1.7-7-4.7-7-9.5V6z",
    link:      "M10.5 13.5a4.5 4.5 0 0 0 6.4.4l2.6-2.6a4.5 4.5 0 0 0-6.4-6.4l-1.5 1.5M13.5 10.5a4.5 4.5 0 0 0-6.4-.4l-2.6 2.6a4.5 4.5 0 0 0 6.4 6.4l1.5-1.5",
    ban:       "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM5.8 5.8l12.4 12.4",
    crosshair: "M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM12 1v5M12 18v5M1 12h5M18 12h5",
    bolt:      "M13 2L4.5 13.5H10L9 22l8.5-11.5H12z",
    dot:       "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
    /* playstyle glyphs for the identity center */
    brawl:     "M2 12h8M6.5 8.5L10 12l-3.5 3.5M22 12h-8M17.5 8.5L14 12l3.5 3.5",
    clap:      "M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.8 2.8M18 6l-2.8 2.8M6 18l2.8-2.8M18 18l-2.8 2.8",
    kite:      "M4 20c6-1 12-7 14-14M18 6l.7-3.3L15.4 3M13 13l5 5",
    brawl_clap:"M2 12h7M6 9l3 3-3 3M17 6v3M17 15v3M11 12h3M20 12h3M13.5 8.5l2 2M20.5 8.5l-2 2M13.5 15.5l2-2M20.5 15.5l-2-2",
    clap_kite: "M4 20c5-1 10-5.5 12.5-11M8 7v3M8 16v3M2 11.5h3M11 11.5h3M4.2 7.7l2 2M11.8 7.7l-2 2",
    split:     "M10 12H2M5.5 8.5L2 12l3.5 3.5M14 12h8M18.5 8.5L22 12l-3.5 3.5",
    forming:   "M5 12h.01M12 12h.01M19 12h.01",
    bomb:      "M14 10a7 7 0 1 1-8 8 7 7 0 0 1 8-8zM14 10l3-3M17 7l-1-1M17 7l1 1M19 3l.01.01M22 6l.01.01",
  };
  const DL_ICON_FILL = {bolt: true, dot: true};
  /* Categorical group colors: the app's role palette re-stepped where the
     colorblind validator demanded (Control teal, not peel-cyan — too close
     to Frontline blue), validated on the panel surface incl. the wrap pair.
     Fixed assignment, never cycled. */
  const DL_GROUP_META = {
    Sustain:   {col: "#1FAE58", icon: "plus"},
    Frontline: {col: "#4D8DFF", icon: "shield"},
    Control:   {col: "#17A386", icon: "link"},
    Denial:    {col: "#C08800", icon: "ban"},
    Damage:    {col: "#E00063", icon: "crosshair"},
    Tempo:     {col: "#E85D12", icon: "bolt"},
    Other:     {col: "#757A92", icon: "dot"},
  };
  /* shared popup: content lives in DL_TIPS (rebuilt every render —
     indices are re-stamped with the markup), elements carry data-dltip */
  let DL_TIPS = [];
  function dlTip(){
    let t = document.getElementById("dl-tip");
    if (!t){ t = document.createElement("div"); t.id = "dl-tip"; document.body.appendChild(t); }
    return t;
  }
  function dlTipMove(ev){
    const t = dlTip(), pad = 14, w = t.offsetWidth, h = t.offsetHeight;
    let x = ev.clientX + pad, y = ev.clientY + pad;
    if (x + w > innerWidth - 8)  x = ev.clientX - w - pad;
    if (y + h > innerHeight - 8) y = ev.clientY - h - pad;
    t.style.left = x + "px"; t.style.top = y + "px";
  }
  document.addEventListener("pointerover", e => {
    const h = e.target.closest && e.target.closest("[data-dltip]");
    const t = dlTip();
    if (h && DL_TIPS[+h.dataset.dltip]){
      t.innerHTML = DL_TIPS[+h.dataset.dltip];
      t.style.display = "block"; dlTipMove(e);
    } else t.style.display = "none";
  });
  document.addEventListener("pointermove", e => {
    if (dlTip().style.display === "block") dlTipMove(e);
  });
  function tipRef(html){ DL_TIPS.push(html); return DL_TIPS.length - 1; }

  function dlIcon(x, y, size, key, col){
    return `<g transform="translate(${x - size/2},${y - size/2}) scale(${size/24})"><path d="${DL_ICONS[key]}" fill="${DL_ICON_FILL[key] ? col : "none"}" stroke="${col}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></g>`;
  }

  /* THE RULER (owner 2026-08-27: "we should never ever be above 100 for
     anything but this 0-100 has to be based on ground facts"): 100% = the
     comp-fitted CEILING — the soft cap, fitted at 1.15x the MOST any good
     comp fields (2026-08-21 recalibration). The ceiling is style-neutral,
     so playstyle tradeoffs read directly: a real brawl ball pushes toward
     100% Frontline while sitting low on ranged Damage, a clap the
     opposite — "these tradeoffs are what define the playstyle". Per-cap
     supply is counted up to its own soft cap, so coverage can never
     exceed 100 and one overstacked capability can't mask its siblings'
     gaps; beyond-ceiling stacking shows as the purple marker, never as a
     bigger number. Each axis carries a brass TICK at the target minimum
     (Σ target / Σ soft). */
  function radarAxes(){
    const s = supply(party);
    const sfl = supplyFloor(party);   /* Option C floor basis (owner
      2026-08-27): coverage quotes the DRESSED supply, but the below-floor
      predicate reads the weapon+loadout basis the structural floors use */
    const grouped = new Set(Object.values(GROUPS).flat());
    const other = Object.keys(REQS()).filter(c => !grouped.has(c));
    const groups = other.length ? {...GROUPS, Other: other} : GROUPS;
    const axes = [];
    for (const [g, caps] of Object.entries(groups)){
      const rows = caps.filter(c => REQS()[c]).map(c => {
        const have = s[c] || 0, t = target(c), soft = softCap(c);
        return {cap: c, have, t, soft, floor: floorHit(c, sfl[c] || 0),
                over: have > soft, optional: !!REQS()[c].optional};
      /* An OPTIONAL capability the comp fields none of is not a gap (owner
         2026-08-28) — it leaves the axis entirely, exactly as it leaves
         max_fitness. Brought, it counts normally. */
      }).filter(r => !(r.optional && r.have <= 0));
      if (!rows.length) continue;
      const tSum = rows.reduce((a, r) => a + Math.max(0, r.t), 0);
      const softSum = rows.reduce((a, r) => a + Math.max(0, r.soft), 0);
      if (tSum <= 0 || softSum <= 0) continue;
      const hSum = rows.reduce((a, r) => a + Math.min(r.have, r.soft), 0);
      axes.push({g, rows, cov: hSum / softSum, tick: Math.min(1, tSum / softSum),
                 floor: rows.some(r => r.floor), over: rows.some(r => r.over),
                 meta: DL_GROUP_META[g] || DL_GROUP_META.Other});
    }
    return axes;
  }
  function groupTipHtml(a){
    const st = a.floor ? '<span class="dlt-bad">below a hard floor</span>'
      : a.over ? '<span class="dlt-over">stacked past what any good comp fields</span>'
      : a.cov >= a.tick ? '<span class="dlt-ok">target met</span>'
      : '<span class="dlt-dim">below target</span>';
    const rows = a.rows.map(r =>
      `<div class="dlt-line"><span>${esc(capLabel(r.cap))}${r.floor ? ' <b class="dlt-bad">⚑ floor</b>' : r.over ? ' <b class="dlt-over">▲</b>' : ""}</span><span>${r.have.toFixed(1)} / ${r.t.toFixed(1)} · cap ${r.soft.toFixed(1)}</span></div>`).join("");
    return `<div class="dlt-head">${esc(a.g)} — ${Math.round(a.cov * 100)}% of ceiling</div>${st}${rows}`
      + `<div class="dlt-note">100% = the most any good comp fields (comp-fitted soft cap); the brass tick marks the target minimum</div>`;
  }
  function centerTipHtml(state, id, pct, f, max){
    let h = `<div class="dlt-head">${esc(state.label)}</div>`
      + `<div class="dlt-line"><span>triage</span><span>${state.critical} critical · ${state.weak} weak · ${state.excess} overstacked</span></div>`
      + `<div class="dlt-line"><span>fitness</span><span>${pct.toFixed(0)}% · ${f.toFixed(1)} / ${max.toFixed(0)}</span></div>`;
    if (id && id.label)
      h += `<div class="dlt-line"><span>becoming</span><span>${esc(id.label)}${id.strength ? ` · ${id.strength}` : ""}</span></div>`;
    if (id) id.conflicts.forEach(c => {
      h += `<div class="dlt-warn">⚠ ${esc(c.display_name)}: ${c.kind === "unfit"
        ? "unfit for this playstyle at this size"
        : `pulls against the ${c.side === "melee" ? "ranged" : "melee"} core`}</div>`;
    });
    if (typeof ENG.killPressure === "function"){
      const kp = ENG.killPressure(party, COMBOS_CUR);
      if (kp){
        const bit = (k, lbl) => {
          const l = kp[k];
          const p = l.bar > 0 ? Math.round(100 * l.have / l.bar) : 100;
          return l.ok ? `<b class="dlt-ok">✓ ${lbl}</b>` : `<b class="dlt-bad">✗ ${lbl} ${p}%</b>`;
        };
        h += `<div class="dlt-line"><span>kill pressure</span><span>${bit("pierce", "pierce")} ${bit("heal_cut", "heal-cut")} ${bit("burst", "burst")}</span></div>`;
      }
    }
    const adv = roleAdvisory();
    if (adv){
      const label = k => (((ENG.rolesBook || {})[k]) || {}).name || k;
      const short = k => label(k).split(" / ")[0].split(" (")[0];
      const tally = Object.entries(adv.tally).map(([k, n]) => `${n}× ${esc(short(k))}`).join(" · ");
      if (tally) h += `<div class="dlt-line"><span>roles</span><span>${tally}</span></div>`;
      const fns = {};
      adv.members.forEach(m => (m.functions || []).forEach(c => { fns[c] = (fns[c] || 0) + 1; }));
      const fnTxt = Object.entries(fns).map(([k, n]) => `${n}× ${esc(short(k))}`).join(" · ");
      if (fnTxt) h += `<div class="dlt-line"><span>functions</span><span>${fnTxt}</span></div>`;
      adv.flags.forEach(f2 => {
        h += `<div class="dlt-warn">⚠ ${f2.kind === "no_engage_tank"
          ? "no engage tank — nobody makes a clump"
          : `${esc(nameOf(f2.weapon))}: worn chest fights its ${esc(label(f2.role).toLowerCase())} job`}</div>`;
      });
    }
    h += `<div class="dlt-note">descriptive — identity, kill pressure and roles never score</div>`;
    return h;
  }
  function roleAdvisory(){
    if (!party.length || typeof ENG.roleAdvisory !== "function") return null;
    const chests = {};
    party.forEach((w, i) => {
      const L = (typeof LOADOUT !== "undefined" && LOADOUT[i]) || null;
      if (L && L.armor) chests[i] = L.armor;
    });
    const adv = ENG.roleAdvisory(party, chests);
    return adv && (adv.flags.length || Object.keys(adv.tally).length) ? adv : null;
  }
  function identityCenter(id){
    /* glyph + short label for the hollow center */
    if (!id || !id.label) return {glyph: "forming", name: "FORMING", sub: "", firm: false};
    if (id.archetype === "bomb_squad") return {glyph: "bomb", name: "BOMB SQUAD", sub: id.strength || "", firm: id.strength === "strong"};
    if (id.style){
      const nm = ((DATASET.styles || {})[id.style] || {}).name || id.style;
      return {glyph: DL_ICONS[id.style] ? id.style : "dot", name: nm.toUpperCase(),
              sub: id.strength || "", firm: id.strength === "strong"};
    }
    if (id.label.indexOf("split") === 0) return {glyph: "split", name: "SPLIT", sub: "", firm: false};
    return {glyph: "forming", name: "FORMING", sub: "", firm: false};
  }
  function statusRadar(state){
    DL_TIPS = [];
    const axes = radarAxes();
    const N = axes.length;
    if (!N) return "";
    const W = 320, H = 252, cx = 160, cy = 126, R = 82;
    const ang = i => -Math.PI / 2 + i * 2 * Math.PI / N;
    const px = (a, r) => (cx + r * Math.cos(a)).toFixed(1);
    const py = (a, r) => (cy + r * Math.sin(a)).toFixed(1);
    const rOf = cov => R * Math.max(0, Math.min(cov, 1));
    const ringPts = f => axes.map((_, i) => `${px(ang(i), rOf(f))},${py(ang(i), rOf(f))}`).join(" ");
    let s = `<svg class="dl-radar" viewBox="0 0 ${W} ${H}" role="img" aria-label="Capability-group coverage versus the comp-fitted ceiling — hover the icons for detail">`;
    for (const f of [0.25, 0.5, 0.75])
      s += `<polygon points="${ringPts(f)}" fill="none" stroke="var(--rule)"/>`;
    s += `<polygon points="${ringPts(1)}" fill="none" stroke="var(--rule-2)" opacity=".9"/>`;
    axes.forEach((a, i) => {
      s += `<line x1="${cx}" y1="${cy}" x2="${px(ang(i), R)}" y2="${py(ang(i), R)}" stroke="var(--rule)" opacity=".7"/>`;
      /* the target minimum: a brass tick across the spoke */
      const rT = rOf(a.tick), k = 4.5;
      const txc = cx + rT * Math.cos(ang(i)), tyc = cy + rT * Math.sin(ang(i));
      s += `<line x1="${(txc + k * Math.sin(ang(i))).toFixed(1)}" y1="${(tyc - k * Math.cos(ang(i))).toFixed(1)}" x2="${(txc - k * Math.sin(ang(i))).toFixed(1)}" y2="${(tyc + k * Math.cos(ang(i))).toFixed(1)}" stroke="var(--brass-deep)" stroke-width="1.6"/>`;
    });
    const pts = axes.map((a, i) => [px(ang(i), rOf(a.cov)), py(ang(i), rOf(a.cov))]);
    s += `<polygon points="${pts.map(p => p.join(",")).join(" ")}" fill="rgba(35,191,110,.20)" stroke="var(--ok)" stroke-width="1.8" stroke-linejoin="round"/>`;
    axes.forEach((a, i) => {
      const tip = tipRef(groupTipHtml(a));
      const vc = a.floor ? "var(--gap)" : a.over ? "var(--over)" : "var(--ok-bright)";
      s += `<circle cx="${pts[i][0]}" cy="${pts[i][1]}" r="4" fill="${vc}" stroke="var(--panel-lo)" stroke-width="2" data-dltip="${tip}"/>`;
      const ix = +px(ang(i), R + 25), iy = +py(ang(i), R + 25) - 4;
      s += `<g data-dltip="${tip}" class="dl-radar-hit">${dlIcon(ix, iy, 21, a.meta.icon, a.meta.col)}`
        + `<text x="${ix}" y="${iy + 20}" text-anchor="middle" class="dlr-pct"${a.floor ? ' fill="var(--gap)"' : a.over ? ' fill="var(--over)"' : ""}>${Math.round(a.cov * 100)}%</text></g>`;
    });
    /* identity center */
    const id = (typeof ENG.compIdentity === "function") ? ENG.compIdentity(party, COMBOS_CUR) : null;
    const c = identityCenter(id);
    /* mirror the identity verdict into the status bar — the same
       identityCenter() value the hollow center draws, so the two can never
       disagree, and no extra engine call is made */
    const sbi = document.getElementById("sb-identity");
    if (sbi) sbi.innerHTML = `<b class="${c.firm ? "firm" : ""}">${esc(c.name)}</b>`
      + (c.sub ? `<span>${esc(c.sub.toUpperCase())}</span>` : "");
    const f = fitness(party), max = maxFitness();
    const pct = Math.max(0, Math.min(100, f / Math.max(1, max) * 100));
    const ctip = tipRef(centerTipHtml(state, id, pct, f, max));
    const adv = roleAdvisory();
    const hasWarn = (id && id.conflicts.length) || (adv && adv.flags.length);
    const nameSize = c.name.length > 7 ? 7 : 8.5;
    s += `<g data-dltip="${ctip}" class="dl-radar-hit">`
      + `<circle cx="${cx}" cy="${cy}" r="33" fill="var(--panel-lo)" stroke="var(--brass-deep)" stroke-width="1.3"${c.firm ? "" : ' stroke-dasharray="4 4"'}/>`
      + dlIcon(cx, cy - 9, 17, c.glyph, "var(--brass)")
      + `<text x="${cx}" y="${cy + 12}" text-anchor="middle" class="dlr-id" font-size="${nameSize}">${esc(c.name)}</text>`
      + (c.sub ? `<text x="${cx}" y="${cy + 22}" text-anchor="middle" class="dlr-sub">${esc(c.sub.toUpperCase())}</text>` : "")
      + (hasWarn ? `<text x="${cx + 25}" y="${cy - 22}" text-anchor="middle" class="dlr-warn">⚠</text>` : "")
      + `</g>`;
    s += `</svg>`;
    return s;
  }

  /* Fight chain (roadmap item 1, 2026-08-23): the fight as the caller's
     playstyle sequences it, stage by stage — ENG.fightChain rendered
     verbatim, gradings from the comp-fitted targets, display only.
     2026-08-24: stages are clickable — the fold lists WHICH equipped
     spells supply each stage (engine `sources`, the same resolved
     loadouts scoring sums), and the improves line names its terms so a
     stage that wins on summed caps is reconcilable with the gain tiles. */
  let CHAIN_OPEN = null;
  function chainSpellName(src){
    if (!src.spell) return "kit";
    const pool = ((typeof SPELLS !== "undefined" && SPELLS[src.weapon]) || {})[src.slot] || [];
    for (const e of pool) if (e[0] === src.spell) return e[1];
    return src.spell;
  }
  function chainSources(stage){
    if (!stage.sources || !stage.sources.length)
      return `<div class="dl-ch-fold"><span class="dl-kicker">${esc(stage.name)}</span><em>no equipped spell supplies this stage yet</em></div>`;
    /* group identical (cap, weapon, slot, spell) rows — a 20-man line of
       Heavy Maces reads "8× Shriek", not eight rows */
    const byCap = new Map();
    stage.sources.forEach(s => {
      const key = `${s.cap}|${s.weapon}|${s.slot}|${s.spell}`;
      const m = byCap.get(s.cap) || byCap.set(s.cap, new Map()).get(s.cap);
      const g = m.get(key);
      if (g) g.n++; else m.set(key, {n: 1, src: s});
    });
    const capLines = stage.caps.map(cap => {
      const m = byCap.get(cap);
      if (!m) return `<div class="dl-ch-src"><b>${esc(capLabel(cap))}</b><em>nothing equipped supplies this</em></div>`;
      const parts = Array.from(m.values()).map(({n, src}) => {
        const slot = src.slot === null ? "kit" : src.slot === "passive" ? "P" : src.slot.toUpperCase();
        return `<span title="${esc(nameOf(src.weapon))} — ${slot} ${esc(chainSpellName(src))}: ${+src.units.toFixed(1)} unit${src.units.toFixed(1) === "1.0" ? "" : "s"} each">${n > 1 ? n + "× " : ""}${icon(src.weapon, 16)}${slot === "kit" ? "" : ` ${slot}`} ${esc(chainSpellName(src))}</span>`;
      });
      return `<div class="dl-ch-src"><b>${esc(capLabel(cap))}</b>${parts.join('<i class="dl-ch-dot">·</i>')}</div>`;
    });
    return `<div class="dl-ch-fold"><span class="dl-kicker">${esc(stage.name)} — the buttons this stage is made of</span>${capLines.join("")}</div>`;
  }
  function chainLine(top){
    if (!party.length || typeof ENG.fightChain !== "function") return "";
    const fc = ENG.fightChain(party, COMBOS_CUR, null, top ? top.w : null);
    if (!fc) return "";
    const styleNm = (DATASET.styles[fc.style] || {}).name || fc.style;
    const seg = fc.stages.map(s =>
      `<button class="dl-ch ${s.verdict}${CHAIN_OPEN === s.name ? " open" : ""}" data-chain-stage="${esc(s.name)}" title="${esc(s.name)}: ${s.verdict}${
        s.bar > 0
          ? ` — ${+s.have.toFixed(1)} of ${+s.bar.toFixed(1)} needed (${s.caps.map(c => esc(capLabel(c))).join(", ")})`
          : " — not demanded by this content"} — click to see which spells">${esc(s.name)}</button>`
    ).join(`<span class="dl-ch-arrow">→</span>`);
    const openStage = CHAIN_OPEN !== null
      ? fc.stages.find(s => s.name === CHAIN_OPEN) : null;
    /* name the terms only when they add information — a single term whose
       label echoes the stage name ("Clump (+12.1 Clump)") says nothing */
    const it = (fc.improves && fc.improves.terms) || [];
    const impTerms = (it.length > 1
        || (it.length === 1 && capLabel(it[0].cap).toLowerCase()
            !== String(fc.improves.stage).toLowerCase()))
      ? ` <small>(${it.map(t => `+${t.gain.toFixed(1)} ${esc(capLabel(t.cap))}`).join(", ")})</small>`
      : "";
    const imp = (fc.improves && top)
      ? `<span class="dl-ch-imp">this pick strengthens <b>${esc(fc.improves.stage)}</b>${impTerms}</span>`
      : "";
    return `<div class="dl-chain"><span class="dl-kicker" title="the fight as ${esc(styleNm)} sequences it — graded against the comp-fitted targets; display only">fight chain · ${esc(styleNm)}</span><div class="dl-ch-row">${seg}</div>${openStage ? chainSources(openStage) : ""}${imp}</div>`;
  }

  /* Negative recommendations / redundancy warnings (roadmap item 3,
     2026-08-24): the "why not" behind the pick — ENG.pickReport is the
     SIGNED decomposition of the same exact marginal the score already is
     (its terms reconstruct the score at 1e-9, parity-pinned). This
     renders it verbatim: saturated capabilities, over-stack costs, the
     duplicate-copy penalty, verified count-once spell losses. Display
     only — the engine's Q18 investigation rejected a scoring-side
     redundancy penalty; the marginal already collapses, this SAYS so. */
  function whyNotBlock(rec){
    if (!rec || typeof ENG.pickReport !== "function") return "";
    const r = pickReport(party, rec.w);
    const lines = [];
    if (r.verdict !== "ok")
      r.caps.filter(x => x.saturated).slice(0, 3).forEach(x => {
        lines.push(`<li>${esc(capLabel(x.cap))} already ${+x.before.toFixed(1)} / ${x.target.toFixed(1)} — this adds ${x.delta > 0.05 ? "depth, not coverage" : "nothing"}</li>`);
      });
    const over = r.caps.reduce((t, x) => t + x.overstack_cost, 0);
    if (over > 0.05) lines.push(`<li>−${over.toFixed(1)} over-stack cost past the soft cap</li>`);
    if (r.dup_penalty > 0) lines.push(`<li>−${r.dup_penalty.toFixed(1)} duplicate-copy penalty (free allowance used)</li>`);
    r.nonstack.forEach(n => {
      const lost = Object.keys(n.lost).map(c => `${esc(capLabel(c))} ${n.lost[c].toFixed(1)}`).join(", ");
      lines.push(`<li>${esc(n.name)} counts once for the party — a duplicate loses ${lost}</li>`);
    });
    if (!lines.length) return "";
    const head = r.verdict === "negative"
      ? "Warning — this pick costs more than it adds"
      : r.verdict === "redundant"
        ? "Depth pick — the comp is saturated, it closes no gap"
        : "What it does not add";
    return `<div class="dl-whynot ${r.verdict}"><span class="dl-kicker">${head}</span><ul>${lines.join("")}</ul></div>`;
  }

  function diagnosisRows(){
    if (!party.length) return [];
    const s = supply(party);
    const sfl = supplyFloor(party);   /* Option C floor basis */
    const rows = weaknesses(party, 12).filter(x => x.gap >= .5).map(x => ({
      ...x,
      have:s[x.cap] || 0,
      want:target(x.cap),
      floor:floorHit(x.cap, sfl[x.cap] || 0),
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

    /* the fold lives in the left-edge tools panel (2026-09-02): it is an
       interactive workflow, not glance-info, so it costs the grid nothing */
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
    const panel = document.getElementById("tools-panel-body");
    if (panel) panel.appendChild(fold);
    else host.appendChild(fold);
  }

  function renderDecisionLayer(){
    const host = document.getElementById("decision-layer");
    if (!host) return;
    /* statusRadar() refills this; on an empty comp it never runs, so clear
       first rather than leaving a stale verdict in the status bar */
    const sbi0 = document.getElementById("sb-identity");
    if (sbi0) sbi0.innerHTML = "";
    const state = statusModel();
    const needs = diagnosisRows();
    const need = needs[0] || null;
    const recs = RECS_CUR;
    const top = recs && recs[0];

    if (!party.length){
      host.innerHTML = `<div class="dl-status dl-empty">
        <div><span class="dl-kicker">Build a party</span><strong>What should your next player bring?</strong>
        <p>Choose the content and playstyle, then add the weapons you already have. Comp Forge will diagnose the gaps before suggesting the next slot.</p></div>
      </div>`;
      renderPlayerTools(host);
      return;
    }

    if (!top){
      host.innerHTML = `<div class="dl-status ${state.tone}"><div class="sec-label">Comp status</div>${statusRadar(state)}</div>`;
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
        const dim = r.verdict && r.verdict !== "ok";
        return `<button class="dl-alt${dim ? " dl-alt-dim" : ""}" data-add="${r.w}" title="${dim ? (r.verdict === "negative" ? "warning: costs more than it adds — " : "depth only, closes no gap — ") : ""}${t0 ? `+${t0.d.toFixed(1)} ${esc(capLabel(t0.cap))} — ` : ""}click to add">${icon(r.w, 24)}
          <span class="dl-alt-nm">${nameOf(r.w)}</span>
          <span class="dl-alt-sc">${dim ? "◦ " : ""}${r.score.toFixed(2)}</span></button>`;
      }).join("")}</div></div>` : "";

    host.innerHTML = `
      <div class="dl-status ${state.tone}"><div class="sec-label">Comp status</div>${statusRadar(state)}</div>
      <div class="dl-pick">
        ${needline}
        ${chainLine(top)}
        <div class="dl-pick-head"><span class="dl-kicker">Best next pick · slot ${Math.min(party.length + 1, HARD_CAP)}</span><span class="dl-score${top.verdict && top.verdict !== "ok" ? " dl-score-dim" : ""}">${top.score >= 0 ? "+" : ""}${top.score.toFixed(2)} comp score${top.verdict === "redundant" ? " · depth only" : top.verdict === "negative" ? " · net cost" : ""}</span></div>
        <div class="dl-weapon">${icon(top.w,72)}<div><button class="nm-btn" data-detail="${top.w}">${nameOf(top.w)}</button><span>${esc(roleOf(top.w, top.combo))}</span></div></div>
        <p>${whySentence(party, top.w)}</p>
        <ul class="dl-gains">${gains}</ul>
        ${observed}
        ${remain}
        ${whyNotBlock(top)}
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
    const ch = e.target.closest && e.target.closest("[data-chain-stage]");
    if (ch){
      CHAIN_OPEN = CHAIN_OPEN === ch.dataset.chainStage ? null : ch.dataset.chainStage;
      renderDecisionLayer(); return;
    }
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
