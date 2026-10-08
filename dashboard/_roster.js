"use strict";

/*
 * The engine's read of a live roster (platform phase 11). The sign-up
 * sheet shows who holds which slot; this module shows what the engine
 * makes of it: the coverage of the held roster, its biggest needs, the
 * next picks (one body ahead), the open slots of the plan with who can
 * fill them, the held seats a swap would improve, and what is
 * overstacked or duplicated. Descriptive, like every analyzer in the
 * planner: the engine ranks, this module translates.
 *
 * The engine is the planner's own (CompEngine over DATASET, the same
 * code the parity gate runs), on an instance of this module's own, so
 * nothing of the planner's state is read or written: the inputs are
 * the CTA's content, style, the weapon keys of its slots and the build
 * each slot is read in, exactly what a share link carries. A slot is
 * read in the build the CTA's saved link holds for it, as the planner
 * reads that link, else in the engine's default kit for its weapon:
 * the engine's targets are person units, and a roster read naked fell
 * short of them on every forged comp ("Tankiness — needed" at 10.0 of
 * 69.7 on a forged Blackzone Roam 20 the planner reads as covered).
 * Who signed up, what they declared and what the guild's members play
 * are shown BESIDE the engine's needs, never scored: attendance and
 * preference are no scoring input (a logged decision would be needed
 * for that).
 *
 * build.py inlines this file as its own <script> after _import.js. The
 * sheet hands its roster over as a DOM event (sheet-read) after every
 * render and on close; this module paints into the rr-* elements of the
 * sheet page, which the sign-up module never touches. It reaches no
 * table: members and their lists come through the guild module's
 * helpers, for a member of the CTA's guild. Two parts:
 *   pure    - the held party, the read, the fillers, the wording
 *             (tests/test_roster.js, the stub engine and the real one)
 *   UI      - the listener and the painter
 */


/* --------------------------------------------------------------- pure */

/* how many picks, needs and fillers the read lists */
const ROSTER_PICKS = 4;
const ROSTER_NEEDS = 6;
const ROSTER_FILLERS = 5;
const ROSTER_SWAP_OPTIONS = 3;

/* a gap below this weight is not listed (the planner's own cut) */
const ROSTER_GAP_MIN = 0.5;

/* the roster cap the engine is asked for: a CTA's slot bound (the
   database's 60, three parties of the planner's HARD_CAP) */
const ROSTER_SIZE_MAX = 60;

/* the gear slots a saved build wears, in the codec's order (the order
   the planner hands the engine), and the spell picks it stores with the
   pool each indexes */
const ROSTER_GEAR = ["head", "armor", "shoes", "cape", "offhand", "potion", "food"];
const ROSTER_SPELL_POOL = { q: "q", w: "w", p: "passive" };

const ROSTER_VERDICTS = { ok: "closes a gap", redundant: "a depth pick", negative: "costs the comp" };

const ROSTER_FILLER_HOW = { declared: "declared", main: "main", secondary: "can also play", swap: "can swap" };
const ROSTER_FILLER_ORDER = ["declared", "main", "secondary", "swap"];

/* the kill-pressure lights in the planner's names, and the fight chain's
   stage verdicts in words */
const ROSTER_KILL = [["pierce", "Pierce"], ["heal_cut", "Anti-heal"], ["burst", "Burst"]];
const ROSTER_STAGE = { strong: "strong", ok: "ok", weak: "under the bare minimum", missing: "missing", quiet: "not asked here" };


/* a capability in the planner's words: its short title, else its prose,
   else the key (the planner's tables are read when the page has them) */
function rosterCapLabel(cap) {
  const labels = typeof CAP_LABEL !== "undefined" ? CAP_LABEL : {};
  const prose = typeof CAP_PROSE !== "undefined" ? CAP_PROSE : {};
  const text = labels[cap] || prose[cap] || String(cap || "").replace(/_/g, " ");
  return text.replace(/^./, ch => ch.toUpperCase());
}


/* The roster as the engine reads it: one weapon per HELD slot, the
   slot's weapon, or the claimant's first declared weapon for a slot
   that names none. A held slot with no weapon either way is not in the
   party; a free slot never is. */
function heldParty(board) {
  const seats = [];
  for (const row of (board && board.rows) || []) {
    if (!row.claimant) continue;
    const declared = (row.claimant.weapons || []).filter(Boolean);
    const weapon = row.weapon_id || declared[0] || null;
    if (!weapon) continue;
    seats.push({ position: row.position, weapon, source: row.weapon_id ? "slot" : "declared",
                 player: row.claimant.player_name || "" });
  }
  return { party: seats.map(s => s.weapon), seats };
}


/* the plan: every slot's weapon, held or not */
function plannedParty(board) {
  return ((board && board.rows) || []).map(r => r.weapon_id).filter(Boolean);
}


/* the plan's seats: every slot naming a weapon, with its position */
function plannedSeats(board) {
  return ((board && board.rows) || []).filter(r => r.weapon_id)
    .map(r => ({ position: r.position, weapon: r.weapon_id, source: "slot" }));
}


/* A comp or a CTA read as designed, in the dialogs that edit them: no one
   holds a slot there, so every slot naming a weapon is read as held and a
   slot naming none is open. The rows carry a weapon and a role, never a
   player. */
function planBoard(slots) {
  const rows = (slots || []).map(s => ({
    position: s.position, weapon_id: s.weapon_id || null, role: s.role || null,
    claimant: s.weapon_id ? { player_name: "", weapons: [] } : null
  }));
  return { rows, reserves: [], counts: { slots: rows.length } };
}


/* What the CTA's saved link holds of the comp it was made from: the
   weapons by position (p=; an empty entry is an open slot of a link
   built from a comp's slots, which keeps every later member at its
   slot's position), each member's saved build (g=: gear and spell
   picks) and explicit combo (k=: a forge's E-slot use no picker holds).
   tables.loadout and tables.combo are the planner's codec (_loadout.js);
   without them, or without a link, nothing is saved. */
function savedComp(shareHash, tables) {
  const t = tables || {};
  const params = new URLSearchParams(String(shareHash || "").replace(/^#/, ""));
  const listed = params.get("p");
  const weapons = listed ? listed.split(",") : [];
  if (!weapons.some(Boolean) || typeof t.loadout !== "function") return { weapons: [], loadouts: [], combos: [] };
  return {
    weapons,
    loadouts: t.loadout(params.get("g") || "") || [],
    combos: typeof t.combo === "function" ? t.combo(params.get("k") || "", weapons.length) : []
  };
}


/* The build one seat is read in. A slot whose weapon is the saved comp's
   member at its position reads that member's saved build as the planner
   reads the link: its curated pieces in the codec's order (a two-handed
   weapon's off-hand left out), its explicit combo, else its picked
   spells. Any other seat (no build saved, the weapon changed, a slot
   naming none) reads the engine's default kit for its weapon, the
   doctrine kit winners wear for its seat, on the default spells.
   spells: the planner's pools (SPELLS), which the picks index. */
function slotBuild(saved, seat, engine, spells) {
  const i = seat.position - 1;
  const w = seat.weapon;
  const mine = !!saved && seat.source === "slot" && saved.weapons[i] === w;
  const L = mine ? saved.loadouts[i] : undefined;
  const k = mine ? saved.combos[i] : null;
  if (L || Number.isInteger(k)) {
    const db = engine.gear || {};
    const gears = ROSTER_GEAR.filter(s => L && L[s] && db[L[s]] && !(s === "offhand" && String(w).startsWith("2H_")))
      .map(s => L[s]);
    let combo = Number.isInteger(k) ? k : null;
    if (combo === null && L && typeof engine.comboFromPicks === "function") {
      const pools = (spells && spells[w]) || {};
      const picks = {};
      let any = false;
      for (const [field, pool] of Object.entries(ROSTER_SPELL_POOL)) {
        const list = pools[pool] || [];
        if (Number.isInteger(L[field]) && list[L[field]]) { picks[pool] = list[L[field]][0]; any = true; }
      }
      if (any) combo = engine.comboFromPicks(w, picks);
    }
    return { combo, gears: gears.length ? gears : null, from: "saved" };
  }
  const v0 = typeof engine.kitVariants === "function" ? (engine.kitVariants(w) || [])[0] : null;
  const kit = v0 && v0[1];
  return { combo: null, gears: kit && kit.length ? kit.slice() : null, from: "default" };
}


/* the content and style the engine is asked for: the CTA's when the
   dataset has them, else the first template and balanced */
function rosterContext(event, data) {
  const templates = (data && data.templates) || {};
  const styles = (data && data.styles) || {};
  const first = Object.keys(templates)[0] || null;
  const content = event && templates[event.content] ? event.content : first;
  const style = event && event.style && styles[event.style] ? event.style : "balanced";
  return { content, style, known: !!(event && templates[event.content]) };
}


/* the engine's needs of a party at its size, read in its builds: the
   gaps the planner lists, each with whether it is a hard floor unmet or
   a heavy capability under half (the planner's "needed" cut). A hard
   floor reads the weapon and spell supply alone: worn gear never buys
   floor relief (the planner's supplyFloor). */
function rosterNeeds(engine, party, top, combos, gears) {
  const supply = engine.effectiveSupply(party, combos, gears);
  const floorSupply = engine.effectiveSupply(party, combos);
  return engine.weaknesses(party, top, combos, gears).filter(x => x.gap >= ROSTER_GAP_MIN).map(x => {
    const have = supply[x.cap] || 0;
    const floor = !!engine.floorArmed(x.cap, floorSupply[x.cap] || 0);
    const ratio = x.target ? have / x.target : 1;
    return { cap: x.cap, label: rosterCapLabel(x.cap), have, target: x.target, gap: x.gap,
             floor, needed: floor || (engine.weight(x.cap) >= 6 && ratio < 0.5) };
  });
}


/* what sits past its soft cap */
function rosterOverstack(engine, party, combos, gears) {
  const supply = engine.effectiveSupply(party, combos, gears);
  const out = [];
  for (const cap of Object.keys(engine.reqs || {})) {
    const soft = engine.softCap(cap);
    const have = supply[cap] || 0;
    if (soft && have > soft) out.push({ cap, label: rosterCapLabel(cap), have, soft });
  }
  return out.sort((a, b) => (b.have / b.soft) - (a.have / a.soft));
}


/* {seat index: chest key}: the piece of each seat's build the gear table
   files under armor (the role check reads the chest a member wears) */
function rosterChests(engine, gears) {
  const db = engine.gear || {};
  const out = {};
  (gears || []).forEach((g, i) => {
    const chest = (g || []).find(k => (db[k] || {}).slot === "armor");
    if (chest) out[i] = chest;
  });
  return out;
}


/* a role's name from the role book without its parenthetical ("Main /
   Clump Healer", "Pierce"): both halves of a paired name stay, since
   "Main" alone does not say healer; a class standing in for a role
   (dps) reads as itself */
function rosterRoleName(engine, role) {
  const name = (((engine && engine.rolesBook) || {})[role] || {}).name || String(role || "");
  return name.split(" (")[0];
}


/* The planner's three descriptive reads of the held roster, in its builds
   at its size: the kill-pressure lights (pierce, anti-heal, burst against
   the content's bare minimums), the role check (who is in the comp, and
   the warnings the role book raises) and the fight chain (the stages of
   the playstyle's fight, each graded). They translate engine output and
   never score; an engine without one of them leaves it out. */
function rosterFight(engine, party, combos, gears) {
  if (!party || !party.length) return null;
  const kp = typeof engine.killPressure === "function" ? engine.killPressure(party, combos, gears) : null;
  const kill = kp ? ROSTER_KILL.map(([key, label]) => {
    const l = kp[key] || {};
    const have = l.have || 0, bar = l.bar || 0;
    return { key, label, ok: !!l.ok, have, bar, pct: bar > 0 ? Math.round(100 * have / bar) : 100 };
  }) : [];
  const adv = typeof engine.roleAdvisory === "function" ? engine.roleAdvisory(party, rosterChests(engine, gears)) : null;
  const roles = adv ? {
    tally: Object.entries(adv.tally || {}).map(([role, n]) => ({ role, name: rosterRoleName(engine, role), n })),
    flags: (adv.flags || []).map(f => ({ kind: f.kind, weapon: f.weapon || null, role: f.role || null,
                                         roleName: f.role ? rosterRoleName(engine, f.role) : "" }))
  } : null;
  const fc = typeof engine.fightChain === "function" ? engine.fightChain(party, combos, gears, null) : null;
  const chain = fc && (fc.stages || []).length ? {
    style: fc.style,
    styleName: ((((engine.data || {}).styles || {})[fc.style]) || {}).name || fc.style,
    stages: fc.stages.map(s => ({ name: s.name, verdict: s.verdict, have: s.have || 0, bar: s.bar || 0, caps: s.caps || [] }))
  } : null;
  return { kill, roles, chain };
}


/* The read: the held roster judged at its own size in its builds, the
   next picks one body ahead, the seats a swap improves, the overstack
   and the duplicate checks, the kill pressure, the role check and the
   fight chain; the plan's coverage beside it when the plan
   is bigger than what is held. tables: the planner's codec and spell
   pools ({ loadout, combo, spells }) the saved builds are read through;
   without them every seat reads the default kit. The engine is left at
   the held size. */
function rosterRead(event, board, engine, tables) {
  const ctx = rosterContext(event, engine.data);
  if (!ctx.content) return null;
  /* a key this build's dataset does not hold (a stale comp, an old profile,
     a guest's own declaration) is left out of the read and named, never
     allowed to stop it */
  const knows = w => !engine.weapons || !!engine.weapons[w];
  const heldAll = heldParty(board);
  const plannedAll = plannedSeats(board);
  const held = { party: [], seats: [] };
  heldAll.seats.forEach(s => { if (knows(s.weapon)) { held.seats.push(s); held.party.push(s.weapon); } });
  const plannedKnown = plannedAll.filter(s => knows(s.weapon));
  const planned = plannedKnown.map(s => s.weapon);
  const unknown = [...new Set(heldAll.party.concat(plannedAll.map(s => s.weapon)).filter(w => !knows(w)))].sort();
  const size = Math.min(Math.max(held.party.length, 1), ROSTER_SIZE_MAX);
  const at = n => engine.setContent(ctx.content, Math.min(Math.max(n, 1), ROSTER_SIZE_MAX), ctx.style);
  const saved = savedComp(event && event.share_hash, tables);
  const spells = tables && tables.spells;
  /* the builds are taken in the context they are judged in: the default
     kit follows the content, the size and the style */
  const buildsOf = seats => {
    const b = seats.map(s => slotBuild(saved, s, engine, spells));
    return { combos: b.map(x => x.combo), gears: b.map(x => x.gears), saved: b.filter(x => x.from === "saved").length };
  };

  at(size);
  const hb = buildsOf(held.seats);
  const fitness = held.party.length ? engine.fitness(held.party, hb.combos, hb.gears) : 0;
  const max = engine.maxFitness(held.party, hb.combos, hb.gears);
  const needs = rosterNeeds(engine, held.party, ROSTER_NEEDS, hb.combos, hb.gears);
  const over = rosterOverstack(engine, held.party, hb.combos, hb.gears);
  const duplicates = held.party.length > 1 ? engine.duplicateConflicts(held.party, hb.combos) : [];
  const swaps = held.party.length > 1 ? engine.swapReview(held.party, ROSTER_SWAP_OPTIONS, null, hb.combos, hb.gears) : [];
  const replacements = swaps.filter(s => s.redundant || s.off_comp || s.off_style).map(s => ({
    index: s.index, weapon: s.weapon, seat: held.seats[s.index] || null, verdict: s.verdict,
    offComp: !!s.off_comp, offStyle: !!s.off_style,
    options: (s.options || []).slice(0, ROSTER_SWAP_OPTIONS).map(o => ({ weapon: o.weapon, gain: o.gain }))
  }));
  const fight = rosterFight(engine, held.party, hb.combos, hb.gears);

  /* the next pick one body ahead, the held seats in the builds they were
     read in (the planner holds a member's kit while it prices a pick) */
  at(held.party.length + 1);
  const picks = engine.recommend(held.party, ROSTER_PICKS, null, hb.combos, hb.gears).map((r, i) => ({
    rank: i + 1, weapon: r.weapon, verdict: r.verdict || "ok", score: r.score,
    capsGain: r.caps_gain || 0
  }));

  let plan = null;
  if (planned.length > held.party.length) {
    at(planned.length);
    const pb = buildsOf(plannedKnown);
    const pf = engine.fitness(planned, pb.combos, pb.gears);
    const pm = engine.maxFitness(planned, pb.combos, pb.gears);
    plan = { count: planned.length, fitness: pf, max: pm, coverage: pm ? pf / pm : 0,
             needs: rosterNeeds(engine, planned, 3, pb.combos, pb.gears) };
  }
  at(size);

  return {
    content: ctx.content, style: ctx.style, knownContent: ctx.known, size,
    held: { count: held.party.length, seats: held.seats, fitness, max, coverage: max ? fitness / max : 0, saved: hb.saved },
    needs, over, duplicates, picks, replacements, plan, unknown, fight
  };
}


/* what a read is of: the content, the style, the saved link (the
   builds), the held party and the plan; a sheet change that keeps
   these keeps the read */
function rosterKey(event, board) {
  const ev = event || {};
  return [ev.content || "", ev.style || "", ev.share_hash || "", heldParty(board).party.join(","), plannedParty(board).join(",")].join("|");
}


/* the line that says which build the held slots are read in */
function rosterBuildsNote(read) {
  const n = read && read.held ? read.held.count : 0;
  if (!n) return "";
  const s = read.held.saved || 0;
  if (s === n) return n === 1 ? "The held slot is read in the build the CTA's comp saved for it." : "Every held slot is read in the build the CTA's comp saved for it.";
  if (!s) return n === 1
    ? "The held slot is read in the engine's default kit for its weapon (no build saved for it, or its weapon changed)."
    : "The held slots are read in the engine's default kit for each weapon (no build saved for them, or their weapons changed).";
  return `${s} held slot${s === 1 ? " is" : "s are"} read in the build the CTA's comp saved, ${n - s} in the engine's default kit for the weapon (no build saved, or the slot's weapon changed).`;
}


/* the open slots of the plan, each with its weapon and whether the
   engine's next picks name it */
function openSlots(board, picks) {
  const wanted = new Map((picks || []).map(p => [p.weapon, p.rank]));
  return ((board && board.rows) || []).filter(r => !r.claimant).map(r => ({
    position: r.position, weapon: r.weapon_id || null, role: r.role || null,
    pickRank: r.weapon_id && wanted.has(r.weapon_id) ? wanted.get(r.weapon_id) : null
  }));
}


/* who is not in a slot: the sheet's reserves with what they declared,
   and the guild's members not on the sheet with what they play (an
   account signs up under its character name; the match is by name,
   whatever its case) */
function rosterPool(board, members) {
  const onSheet = new Set();
  for (const row of (board && board.rows) || []) {
    if (row.claimant) onSheet.add(String(row.claimant.player_name || "").trim().toLowerCase());
  }
  const reserves = ((board && board.reserves) || []).map(s => ({
    name: s.player_name || "", declared: (s.weapons || []).filter(Boolean), swap: !!s.can_swap, reserve: true
  }));
  for (const s of reserves) onSheet.add(s.name.trim().toLowerCase());
  const others = (members || []).filter(m => {
    const names = [m.albion, m.name].map(n => String(n || "").trim().toLowerCase()).filter(Boolean);
    return !names.some(n => onSheet.has(n));
  }).map(m => ({ name: m.name || m.albion || "", main: (m.lists && m.lists.main) || [], secondary: (m.lists && m.lists.secondary) || [] }));
  return { reserves, others };
}


/* who can bring one weapon: reserves who declared it, members who list
   it as a main, then as a weapon they can also play, then reserves who
   can swap; at most ROSTER_FILLERS */
function fillersFor(weapon, pool) {
  const out = [];
  if (!weapon || !pool) return out;
  for (const r of pool.reserves || []) {
    if (r.declared.includes(weapon)) out.push({ name: r.name, how: "declared" });
  }
  for (const m of pool.others || []) {
    if (m.main.includes(weapon)) out.push({ name: m.name, how: "main" });
    else if (m.secondary.includes(weapon)) out.push({ name: m.name, how: "secondary" });
  }
  for (const r of pool.reserves || []) {
    if (!r.declared.includes(weapon) && r.swap) out.push({ name: r.name, how: "swap" });
  }
  return out.sort((a, b) => ROSTER_FILLER_ORDER.indexOf(a.how) - ROSTER_FILLER_ORDER.indexOf(b.how) || a.name.localeCompare(b.name))
    .slice(0, ROSTER_FILLERS);
}


function rosterPct(fraction) {
  return `${Math.round(Math.max(0, Math.min(1, Number(fraction) || 0)) * 100)}%`;
}


/* the line the summary shows before the read is opened */
function rosterHeadline(read, board, catalog) {
  if (!read) return "";
  const slots = (board && board.counts && board.counts.slots) || 0;
  const name = key => weaponInfo(catalog, key).name;
  if (!read.held.count) {
    const plan = read.plan ? ` · the plan covers ${rosterPct(read.plan.coverage)}` : "";
    return `no one in a slot yet${plan}` + (read.picks.length ? ` · first pick ${name(read.picks[0].weapon)}` : "");
  }
  const parts = [`${read.held.count} of ${slots} slot${slots === 1 ? "" : "s"} held`, `coverage ${rosterPct(read.held.coverage)}`];
  const need = read.needs.find(n => n.needed) || read.needs[0];
  if (need) parts.push(`biggest need ${need.label}`);
  if (read.picks.length) parts.push(`next pick ${name(read.picks[0].weapon)}`);
  return parts.join(" · ");
}


const ROSTER_DEFINITIONS = "The engine reads the weapons of the held slots at their number (a slot naming no weapon counts its player's first declared weapon), "
  + "each in the build the CTA's comp saved for its slot, else in the engine's default kit for the weapon (what winners wear in its seat); "
  + "the next pick is judged one body ahead. Kill pressure, the role check and the fight chain are the planner's descriptive reads of the held slots: they never score. "
  + "Who signed up, what they declared and what members play are shown beside the engine's needs, never scored. "
  + "The same engine and rules as the planner: open the CTA in the planner for the full read.";


/* the line a dialog's read shows before it is opened: a comp or a CTA
   read as designed, every slot naming a weapon */
function planHeadline(read, catalog) {
  if (!read) return "";
  const name = key => weaponInfo(catalog, key).name;
  const n = read.held.count;
  if (!n) return "no slot names a weapon yet" + (read.picks.length ? ` · first pick ${name(read.picks[0].weapon)}` : "");
  const parts = [`${n} weapon${n === 1 ? "" : "s"}`, `coverage ${rosterPct(read.held.coverage)}`];
  const need = read.needs.find(x => x.needed) || read.needs[0];
  if (need) parts.push(`biggest need ${need.label}`);
  if (read.picks.length) parts.push(`next pick ${name(read.picks[0].weapon)}`);
  return parts.join(" · ");
}


/* the line that says which build a dialog's slots are read in */
function planBuildsNote(read) {
  const n = read && read.held ? read.held.count : 0;
  if (!n) return "";
  const s = read.held.saved || 0;
  if (s === n) return n === 1 ? "The slot is read in the build the comp's link saved for it." : "Every slot is read in the build the comp's link saved for it.";
  if (!s) return "Every slot is read in the engine's default kit for its weapon (no build saved, or the slot's weapon changed).";
  return `${s} slot${s === 1 ? " is" : "s are"} read in the build the comp's link saved, ${n - s} in the engine's default kit for the weapon (no build saved, or the slot's weapon changed).`;
}


/* what a dialog's read says it is */
function planDefinitions(what) {
  return `The engine reads the weapons of the ${what}'s slots at their number, each in the build its saved link holds for the slot, `
    + "else in the engine's default kit for the weapon (what winners wear in its seat); the next pick is judged one body ahead. "
    + "Kill pressure, the role check and the fight chain are the planner's descriptive reads: they never score. "
    + `The same engine and rules as the planner: open the ${what} in the planner for the full read.`;
}


/* ----------------------------------------------------------------- UI */

(function rosterUI() {
  if (typeof document === "undefined") {
    return;
  }

  const $id = id => document.getElementById(id);
  const CATALOG = typeof ACCOUNT_CATALOG !== "undefined" ? ACCOUNT_CATALOG : {};
  const CONTENTS = typeof ACCOUNT_CONTENTS !== "undefined" ? ACCOUNT_CONTENTS : {};

  /* The surfaces the read paints into: the sign-up sheet's (rr-*) and the
     saved comps and CTAs dialogs' (comp-rr-*, ev-rr-*), each with its own
     last read. A dialog reads its comp or CTA as designed (planBoard);
     the words say what a surface reads. */
  const SHEET_WORDS = {
    plan: false,
    definitions: ROSTER_DEFINITIONS,
    noneHeld: "Nothing held yet: the needs read the plan once someone holds a slot.",
    allHeld: "Every slot is held.",
    swapsTwo: "Two or more held slots are needed for a swap review.",
    swapsNone: "Every held weapon still closes a gap of its own.",
    nothing: "Nothing held yet.",
    what: "CTA"
  };
  const planWords = what => ({
    plan: true,
    definitions: planDefinitions(what),
    noneHeld: "No slot names a weapon yet.",
    allHeld: "Every slot names a weapon.",
    swapsTwo: "Two or more slots naming a weapon are needed for a swap review.",
    swapsNone: "Every weapon still closes a gap of its own.",
    nothing: "No slot names a weapon yet.",
    what
  });

  function surfaceOf(prefix, words) {
    const g = s => $id(`${prefix}-${s}`);
    const els = { wrap: g("wrap"), headline: g("headline"), note: g("note"), needs: g("needs"), picks: g("picks"),
                  free: g("free"), swaps: g("swaps"), over: g("over"), fight: g("fight"), definitions: g("definitions") };
    if (!els.wrap) return null;
    els.definitions.textContent = words.definitions;
    return { els, words, last: null, lastKey: null };
  }
  const surfaces = {
    sheet: surfaceOf("rr", SHEET_WORDS),
    comp: surfaceOf("comp-rr", planWords("comp")),
    cta: surfaceOf("ev-rr", planWords("CTA"))
  };

  if (!surfaces.sheet && !surfaces.comp && !surfaces.cta) {
    return;
  }

  let engine = null;           /* this module's own CompEngine, made on the first read, one for every surface */
  let members = { guildId: null, rows: [] };   /* the CTA's guild's members with their lists (the sheet) */
  let seq = 0;

  function ownEngine() {
    if (engine) return engine;
    if (typeof CompEngine === "undefined" || typeof DATASET === "undefined") return null;
    try {
      engine = new CompEngine(DATASET, Object.keys(DATASET.templates)[0]);
    } catch (err) {
      engine = null;
    }
    return engine;
  }

  /* the planner's codec and spell pools the saved builds are read
     through (the same tables the sheet's build panel reads) */
  const tables = () => ({
    loadout: typeof loadoutDecode === "function" ? loadoutDecode : null,
    combo: typeof comboDecode === "function" ? comboDecode : null,
    spells: typeof SPELLS !== "undefined" ? SPELLS : {}
  });

  function art(key) {
    const info = weaponInfo(CATALOG, key);
    const src = (typeof ICONS !== "undefined" && ICONS[key])
      || (info.item ? `https://render.albiononline.com/v1/item/${encodeURIComponent(info.item)}.png?size=64` : "");
    if (!src) return null;
    const img = document.createElement("img");
    img.className = "pw-art";
    img.src = src;
    img.alt = "";
    img.width = 20;
    img.height = 20;
    img.loading = "lazy";
    return img;
  }

  function weaponSpan(key) {
    const span = document.createElement("span");
    span.className = "rr-weapon";
    const img = art(key);
    if (img) span.append(img);
    const info = weaponInfo(CATALOG, key);
    const name = document.createElement("span");
    name.textContent = info.known ? info.name : key;
    span.append(name);
    if (info.role) {
      const tag = document.createElement("span");
      tag.className = `pw-role ${info.role}`;
      tag.textContent = ROLE_NAMES[info.role] || info.role;
      span.append(tag);
    }
    return span;
  }

  function item(cls) {
    const li = document.createElement("li");
    if (cls) li.className = cls;
    return li;
  }

  function sub(text) {
    const s = document.createElement("span");
    s.className = "gd-sub";
    s.textContent = text;
    return s;
  }

  function none(list, text) {
    const li = item("gd-none");
    li.textContent = text;
    list.replaceChildren(li);
  }

  function fillerText(weapon, pool) {
    const who = fillersFor(weapon, pool);
    if (!who.length) return "";
    return "can bring it: " + who.map(f => `${f.name} (${ROSTER_FILLER_HOW[f.how]})`).join(", ");
  }

  function paintNeeds(sf, read) {
    const { els, words } = sf;
    if (!read.held.count) { none(els.needs, words.noneHeld); return; }
    if (!read.needs.length) { none(els.needs, "Every capability is at its typical winner's level or better."); return; }
    els.needs.replaceChildren(...read.needs.map(n => {
      const li = item(n.needed ? "rr-needed" : "");
      const name = document.createElement("span");
      name.className = "gd-name";
      name.textContent = n.label;
      li.append(name, sub(`${n.have.toFixed(1)} of ${n.target.toFixed(1)}${n.floor ? " · below the hard floor" : n.needed ? " · needed" : ""}`));
      return li;
    }));
  }

  function paintPicks(sf, read, pool) {
    const { els } = sf;
    if (!read.picks.length) { none(els.picks, "No pick to suggest."); return; }
    els.picks.replaceChildren(...read.picks.map(p => {
      const li = item(p.verdict === "ok" ? "" : "rr-depth");
      const rank = document.createElement("span");
      rank.className = "cp-pos";
      rank.textContent = String(p.rank);
      li.append(rank, weaponSpan(p.weapon));
      const tail = [ROSTER_VERDICTS[p.verdict] || p.verdict, fillerText(p.weapon, pool)].filter(Boolean).join(" · ");
      li.append(sub(tail));
      return li;
    }));
  }

  function paintFree(sf, read, board, pool) {
    const { els, words } = sf;
    const free = openSlots(board, read.picks);
    if (!free.length) { none(els.free, words.allHeld); return; }
    els.free.replaceChildren(...free.map(f => {
      const li = item(f.pickRank ? "rr-wanted" : "");
      const pos = document.createElement("span");
      pos.className = "cp-pos";
      pos.textContent = String(f.position);
      li.append(pos);
      if (f.weapon) li.append(weaponSpan(f.weapon));
      else {
        const any = document.createElement("span");
        any.className = "cp-open";
        any.textContent = "any weapon";
        li.append(any);
      }
      const tail = [f.role || "", f.pickRank ? `the engine's pick ${f.pickRank}` : "", f.weapon ? fillerText(f.weapon, pool) : ""].filter(Boolean).join(" · ");
      if (tail) li.append(sub(tail));
      return li;
    }));
  }

  function paintSwaps(sf, read) {
    const { els, words } = sf;
    if (read.held.count < 2) { none(els.swaps, words.swapsTwo); return; }
    if (!read.replacements.length) { none(els.swaps, words.swapsNone); return; }
    els.swaps.replaceChildren(...read.replacements.map(r => {
      const li = item("");
      const pos = document.createElement("span");
      pos.className = "cp-pos";
      pos.textContent = r.seat ? String(r.seat.position) : "";
      li.append(pos, weaponSpan(r.weapon));
      const why = r.offComp ? "not a comp the generation rules would build here" : r.offStyle ? `unfit for the ${words.what}'s style`
                : r.verdict === "negative" ? "costs the comp as a pick into the rest" : "its jobs are covered by the rest";
      const better = r.options.length
        ? " · better here: " + r.options.map(o => `${weaponInfo(CATALOG, o.weapon).name} (${o.gain >= 0 ? "+" : "−"}${Math.abs(o.gain).toFixed(1)})`).join(", ")
        : "";
      li.append(sub(`${r.seat && r.seat.player ? r.seat.player + " · " : ""}${why}${better}`));
      return li;
    }));
  }

  function paintOver(sf, read) {
    const { els, words } = sf;
    const rows = [];
    for (const o of read.over) {
      const li = item("rr-over");
      const name = document.createElement("span");
      name.className = "gd-name";
      name.textContent = `${o.label} overstacked`;
      li.append(name, sub(`${o.have.toFixed(1)} past a soft cap of ${o.soft.toFixed(1)}`));
      rows.push(li);
    }
    for (const d of read.duplicates) {
      const li = item(`rr-dup rr-dup-${d.severity}`);
      const name = document.createElement("span");
      name.className = "gd-name";
      name.textContent = d.severity === "high" ? "duplicate utility wasted" : d.severity === "warning" ? "duplicate utility warning"
                       : d.severity === "verify" ? "verify a duplicate" : "duplicate check";
      li.append(name, sub(`${d.reason} · ${(d.weapons || []).map(w => weaponInfo(CATALOG, w).name).join(" + ")}`));
      rows.push(li);
    }
    if (!rows.length) none(els.over, read.held.count ? "Nothing past its soft cap, no duplicate to check." : words.nothing);
    else els.over.replaceChildren(...rows);
  }

  function span(cls, text, title) {
    const s = document.createElement("span");
    if (cls) s.className = cls;
    s.textContent = text;
    if (title) s.title = title;
    return s;
  }

  /* a labelled row; its values wrap in their own column */
  function fightRow(label) {
    const row = document.createElement("div");
    row.className = "rr-fight-row";
    const vals = document.createElement("div");
    vals.className = "rr-fight-v";
    row.append(span("rr-fight-k", label), vals);
    row.vals = vals;
    return row;
  }

  function flagText(f) {
    if (f.kind === "no_engage_tank") return "no engage tank: nobody makes a clump";
    const who = f.weapon ? weaponInfo(CATALOG, f.weapon).name : "a member";
    return `${who}: the worn chest fights its ${(f.roleName || "seat").toLowerCase()} job`;
  }

  function paintFight(sf, read) {
    const { els, words } = sf;
    const f = read.fight;
    if (!read.held.count || !f) { els.fight.replaceChildren(span("gd-none", words.nothing)); return; }
    const rows = [];
    if (f.kill.length) {
      const row = fightRow("Kill pressure");
      for (const k of f.kill) {
        row.vals.append(span(`rr-light ${k.ok ? "ok" : "bad"}`, k.ok ? `${k.label} covered` : `${k.label} ${k.pct}%`,
          `${k.have.toFixed(1)} of a bare minimum of ${k.bar.toFixed(1)}`));
      }
      rows.push(row);
    }
    if (f.roles && (f.roles.tally.length || f.roles.flags.length)) {
      const row = fightRow("Roles");
      for (const t of f.roles.tally) {
        const chip = span("rr-chip", "");
        const n = document.createElement("b");
        n.textContent = String(t.n);
        chip.append(n, ` ${t.name}`);
        row.vals.append(chip);
      }
      rows.push(row);
      for (const fl of f.roles.flags) {
        const warn = fightRow("");
        warn.vals.append(span("rr-flag", `⚠ ${flagText(fl)}`));
        rows.push(warn);
      }
    }
    if (f.chain) {
      const row = fightRow(`Fight chain · ${f.chain.styleName}`);
      f.chain.stages.forEach((s, i) => {
        if (i) row.vals.append(span("rr-arrow", "→"));
        const caps = s.caps.map(rosterCapLabel).join(", ");
        row.vals.append(span(`rr-stage ${s.verdict}`, s.name, s.bar > 0
          ? `${s.name}: ${ROSTER_STAGE[s.verdict] || s.verdict} · ${s.have.toFixed(1)} of ${s.bar.toFixed(1)} (${caps})`
          : `${s.name}: ${ROSTER_STAGE.quiet}`));
      });
      rows.push(row);
    }
    if (!rows.length) rows.push(span("gd-none", "The engine reads nothing to show here."));
    els.fight.replaceChildren(...rows);
  }

  function paint(sf, read, board, event) {
    const { els, words } = sf;
    const pool = words.plan ? { reserves: [], others: [] } : rosterPool(board, members.rows);
    els.headline.textContent = words.plan ? planHeadline(read, CATALOG) : rosterHeadline(read, board, CATALOG);
    const notes = [];
    if (read.unknown && read.unknown.length) {
      notes.push(`${read.unknown.length === 1 ? "A weapon" : `${read.unknown.length} weapons`} this build does not know `
        + `${read.unknown.length === 1 ? "is" : "are"} left out of the read: ${read.unknown.join(", ")}.`);
    }
    if (!read.knownContent) {
      notes.push(event && event.content
        ? `The ${words.what}'s content is not in this build's templates; the read uses ${CONTENTS[read.content] || read.content}.`
        : `The ${words.what} names no content yet; the read uses ${CONTENTS[read.content] || read.content}.`);
    }
    const builds = words.plan ? planBuildsNote(read) : rosterBuildsNote(read);
    if (builds) notes.push(builds);
    if (read.plan) notes.push(`The plan (${read.plan.count} slots) covers ${rosterPct(read.plan.coverage)}`
      + (read.plan.needs.length ? `; its biggest needs: ${read.plan.needs.map(n => n.label).join(", ")}.` : "."));
    els.note.textContent = notes.join(" ");
    els.note.hidden = !notes.length;
    paintNeeds(sf, read);
    paintPicks(sf, read, pool);
    paintFree(sf, read, board, pool);
    paintSwaps(sf, read);
    paintOver(sf, read);
    paintFight(sf, read);
  }

  function hide(sf) {
    sf.els.wrap.hidden = true;
    sf.last = null;
    sf.lastKey = null;
  }

  /* one surface's read: computed again only when what the engine reads
     changes (the content, the style, the saved link, the weapons), so a
     mark, a move or a typed note keeps it */
  function show(sf, event, board) {
    const eng = ownEngine();
    if (!eng) { hide(sf); return null; }
    const key = rosterKey(event, board);
    let read = sf.last && sf.lastKey === key ? sf.last.read : null;
    if (!read) {
      try {
        read = rosterRead(event, board, eng, tables());
      } catch (err) {
        read = null;
      }
    }
    if (!read) { hide(sf); return null; }
    sf.last = { read, board, event };
    sf.lastKey = key;
    paint(sf, read, board, event);
    sf.els.wrap.hidden = false;
    return read;
  }

  /* the guild's members with their lists, once per guild, for a member; a
     read in flight is not started again, and a failed one is tried again
     on the next sheet read, never kept for the visit */
  let membersLoading = null;
  async function loadMembers(guildId) {
    const mySeq = ++seq;
    membersLoading = guildId;
    let rows = null;
    try {
      const list = await loadGuildMembers(guildId);
      const weapons = await loadMembersWeapons(list.map(m => m.user_id));
      rows = memberRows(list, weapons, CATALOG);
    } catch (err) {
      rows = null;
    }
    if (mySeq !== seq) return;
    membersLoading = null;
    if (rows === null) return;
    members = { guildId, rows };
    const sf = surfaces.sheet;
    if (sf && sf.last) paint(sf, sf.last.read, sf.last.board, sf.last.event);
  }

  if (surfaces.sheet) {
    document.addEventListener("sheet-read", e => {
      const sf = surfaces.sheet;
      const d = e.detail;
      if (!d || !d.slots) {
        hide(sf);
        members = { guildId: null, rows: [] };
        return;
      }
      const read = show(sf, d.event, sheetBoard(d.slots, d.signups));
      if (!read) return;
      if (d.member && d.guild && d.guild.id && members.guildId !== d.guild.id && membersLoading !== d.guild.id) {
        loadMembers(d.guild.id);
      } else if (!d.member) {
        members = { guildId: null, rows: [] };
      }
    });
  }

  /* the saved comps and CTAs dialogs hand their open comp or CTA over as a
     DOM event (plan-read) after every render of its slots, and an empty
     one when none is open: the slots' weapons and roles and the record's
     content, style and saved link, never a player */
  const planTimers = {};
  document.addEventListener("plan-read", e => {
    const d = e.detail || {};
    const sf = surfaces[d.surface];
    if (!sf || d.surface === "sheet") return;
    clearTimeout(planTimers[d.surface]);
    if (!d.event || !d.slots) { hide(sf); return; }
    /* the dialog paints first and the read follows (a roster of sixty
       takes the engine a moment); a newer hand-over replaces a pending one */
    planTimers[d.surface] = setTimeout(() => show(sf, d.event, planBoard(d.slots)), 0);
  });
})();
