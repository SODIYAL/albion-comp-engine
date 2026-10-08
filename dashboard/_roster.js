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
 * the CTA's content, style and the weapon keys of its slots, exactly
 * what a share link carries. Who signed up, what they declared and what
 * the guild's members play are shown BESIDE the engine's needs, never
 * scored: attendance and preference are no scoring input (a logged
 * decision would be needed for that).
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

const ROSTER_VERDICTS = { ok: "closes a gap", redundant: "a depth pick", negative: "costs the comp" };

const ROSTER_FILLER_HOW = { declared: "declared", main: "main", secondary: "can also play", swap: "can swap" };
const ROSTER_FILLER_ORDER = ["declared", "main", "secondary", "swap"];


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


/* the engine's needs of a party at its size: the gaps the planner
   lists, each with whether it is a hard floor unmet or a heavy
   capability under half (the planner's "needed" cut) */
function rosterNeeds(engine, party, top) {
  const supply = engine.effectiveSupply(party);
  return engine.weaknesses(party, top).filter(x => x.gap >= ROSTER_GAP_MIN).map(x => {
    const have = supply[x.cap] || 0;
    const floor = !!engine.floorArmed(x.cap, have);
    const ratio = x.target ? have / x.target : 1;
    return { cap: x.cap, label: rosterCapLabel(x.cap), have, target: x.target, gap: x.gap,
             floor, needed: floor || (engine.weight(x.cap) >= 6 && ratio < 0.5) };
  });
}


/* what sits past its soft cap */
function rosterOverstack(engine, party) {
  const supply = engine.effectiveSupply(party);
  const out = [];
  for (const cap of Object.keys(engine.reqs || {})) {
    const soft = engine.softCap(cap);
    const have = supply[cap] || 0;
    if (soft && have > soft) out.push({ cap, label: rosterCapLabel(cap), have, soft });
  }
  return out.sort((a, b) => (b.have / b.soft) - (a.have / a.soft));
}


/* The read: the held roster judged at its own size, the next picks one
   body ahead, the seats a swap improves, the overstack and the
   duplicate checks; the plan's coverage beside it when the plan is
   bigger than what is held. The engine is left at the held size. */
function rosterRead(event, board, engine) {
  const ctx = rosterContext(event, engine.data);
  if (!ctx.content) return null;
  /* a key this build's dataset does not hold (a stale comp, an old profile,
     a guest's own declaration) is left out of the read and named, never
     allowed to stop it */
  const knows = w => !engine.weapons || !!engine.weapons[w];
  const heldAll = heldParty(board);
  const plannedAll = plannedParty(board);
  const held = { party: [], seats: [] };
  heldAll.seats.forEach(s => { if (knows(s.weapon)) { held.seats.push(s); held.party.push(s.weapon); } });
  const planned = plannedAll.filter(knows);
  const unknown = [...new Set(heldAll.party.concat(plannedAll).filter(w => !knows(w)))].sort();
  const size = Math.min(Math.max(held.party.length, 1), ROSTER_SIZE_MAX);
  const at = n => engine.setContent(ctx.content, Math.min(Math.max(n, 1), ROSTER_SIZE_MAX), ctx.style);

  at(size);
  const fitness = held.party.length ? engine.fitness(held.party) : 0;
  const max = engine.maxFitness(held.party);
  const needs = rosterNeeds(engine, held.party, ROSTER_NEEDS);
  const over = rosterOverstack(engine, held.party);
  const duplicates = held.party.length > 1 ? engine.duplicateConflicts(held.party) : [];
  const swaps = held.party.length > 1 ? engine.swapReview(held.party, ROSTER_SWAP_OPTIONS) : [];
  const replacements = swaps.filter(s => s.redundant || s.off_comp || s.off_style).map(s => ({
    index: s.index, weapon: s.weapon, seat: held.seats[s.index] || null, verdict: s.verdict,
    offComp: !!s.off_comp, offStyle: !!s.off_style,
    options: (s.options || []).slice(0, ROSTER_SWAP_OPTIONS).map(o => ({ weapon: o.weapon, gain: o.gain }))
  }));

  at(held.party.length + 1);
  const picks = engine.recommend(held.party, ROSTER_PICKS).map((r, i) => ({
    rank: i + 1, weapon: r.weapon, verdict: r.verdict || "ok", score: r.score,
    capsGain: r.caps_gain || 0
  }));

  let plan = null;
  if (planned.length > held.party.length) {
    at(planned.length);
    const pf = engine.fitness(planned);
    const pm = engine.maxFitness(planned);
    plan = { count: planned.length, fitness: pf, max: pm, coverage: pm ? pf / pm : 0,
             needs: rosterNeeds(engine, planned, 3) };
  }
  at(size);

  return {
    content: ctx.content, style: ctx.style, knownContent: ctx.known, size,
    held: { count: held.party.length, seats: held.seats, fitness, max, coverage: max ? fitness / max : 0 },
    needs, over, duplicates, picks, replacements, plan, unknown
  };
}


/* what a read is of: the content, the style, the held party and the
   plan; a sheet change that keeps these keeps the read */
function rosterKey(event, board) {
  const ev = event || {};
  return [ev.content || "", ev.style || "", heldParty(board).party.join(","), plannedParty(board).join(",")].join("|");
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


const ROSTER_DEFINITIONS = "The engine reads the weapons of the held slots at their number (a slot naming no weapon counts its player's first declared weapon); "
  + "the next pick is judged one body ahead. Who signed up, what they declared and what members play are shown beside the engine's needs, never scored. "
  + "The same engine and rules as the planner: open the CTA in the planner for the full read.";


/* ----------------------------------------------------------------- UI */

(function rosterUI() {
  if (typeof document === "undefined") {
    return;
  }

  const $id = id => document.getElementById(id);
  const wrap = $id("rr-wrap");

  if (!wrap) {
    return;
  }

  const CATALOG = typeof ACCOUNT_CATALOG !== "undefined" ? ACCOUNT_CATALOG : {};
  const CONTENTS = typeof ACCOUNT_CONTENTS !== "undefined" ? ACCOUNT_CONTENTS : {};

  const el = {
    headline: $id("rr-headline"),
    note: $id("rr-note"),
    needs: $id("rr-needs"),
    picks: $id("rr-picks"),
    free: $id("rr-free"),
    swaps: $id("rr-swaps"),
    over: $id("rr-over"),
    definitions: $id("rr-definitions")
  };
  el.definitions.textContent = ROSTER_DEFINITIONS;

  let engine = null;           /* this module's own CompEngine, made on the first read */
  let members = { guildId: null, rows: [] };   /* the CTA's guild's members with their lists */
  let last = null;             /* the last read, repainted when the members arrive */
  let lastKey = null;          /* what the last read was of: the read is reused while it holds */
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

  function paintNeeds(read) {
    if (!read.held.count) { none(el.needs, "Nothing held yet: the needs read the plan once someone holds a slot."); return; }
    if (!read.needs.length) { none(el.needs, "Every capability is at its typical winner's level or better."); return; }
    el.needs.replaceChildren(...read.needs.map(n => {
      const li = item(n.needed ? "rr-needed" : "");
      const name = document.createElement("span");
      name.className = "gd-name";
      name.textContent = n.label;
      li.append(name, sub(`${n.have.toFixed(1)} of ${n.target.toFixed(1)}${n.floor ? " · below the hard floor" : n.needed ? " · needed" : ""}`));
      return li;
    }));
  }

  function paintPicks(read, pool) {
    if (!read.picks.length) { none(el.picks, "No pick to suggest."); return; }
    el.picks.replaceChildren(...read.picks.map(p => {
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

  function paintFree(read, board, pool) {
    const free = openSlots(board, read.picks);
    if (!free.length) { none(el.free, "Every slot is held."); return; }
    el.free.replaceChildren(...free.map(f => {
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

  function paintSwaps(read) {
    if (read.held.count < 2) { none(el.swaps, "Two or more held slots are needed for a swap review."); return; }
    if (!read.replacements.length) { none(el.swaps, "Every held weapon still closes a gap of its own."); return; }
    el.swaps.replaceChildren(...read.replacements.map(r => {
      const li = item("");
      const pos = document.createElement("span");
      pos.className = "cp-pos";
      pos.textContent = r.seat ? String(r.seat.position) : "";
      li.append(pos, weaponSpan(r.weapon));
      const why = r.offComp ? "not a comp the generation rules would build here" : r.offStyle ? "unfit for the CTA's style"
                : r.verdict === "negative" ? "costs the comp as a pick into the rest" : "its jobs are covered by the rest";
      const better = r.options.length
        ? " · better here: " + r.options.map(o => `${weaponInfo(CATALOG, o.weapon).name} (${o.gain >= 0 ? "+" : "−"}${Math.abs(o.gain).toFixed(1)})`).join(", ")
        : "";
      li.append(sub(`${r.seat && r.seat.player ? r.seat.player + " · " : ""}${why}${better}`));
      return li;
    }));
  }

  function paintOver(read) {
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
    if (!rows.length) none(el.over, read.held.count ? "Nothing past its soft cap, no duplicate to check." : "Nothing held yet.");
    else el.over.replaceChildren(...rows);
  }

  function paint(read, board) {
    const pool = rosterPool(board, members.rows);
    el.headline.textContent = rosterHeadline(read, board, CATALOG);
    const notes = [];
    if (read.unknown && read.unknown.length) {
      notes.push(`${read.unknown.length === 1 ? "A weapon" : `${read.unknown.length} weapons`} this build does not know `
        + `${read.unknown.length === 1 ? "is" : "are"} left out of the read: ${read.unknown.join(", ")}.`);
    }
    if (!read.knownContent) notes.push(`The CTA's content is not in this build's templates; the read uses ${CONTENTS[read.content] || read.content}.`);
    if (read.plan) notes.push(`The plan (${read.plan.count} slots) covers ${rosterPct(read.plan.coverage)}`
      + (read.plan.needs.length ? `; its biggest needs: ${read.plan.needs.map(n => n.label).join(", ")}.` : "."));
    el.note.textContent = notes.join(" ");
    el.note.hidden = !notes.length;
    paintNeeds(read);
    paintPicks(read, pool);
    paintFree(read, board, pool);
    paintSwaps(read);
    paintOver(read);
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
    if (last) paint(last.read, last.board);
  }

  document.addEventListener("sheet-read", e => {
    const d = e.detail;
    if (!d || !d.slots) {
      wrap.hidden = true;
      last = null;
      lastKey = null;
      members = { guildId: null, rows: [] };
      return;
    }
    const eng = ownEngine();
    if (!eng) { wrap.hidden = true; return; }
    const board = sheetBoard(d.slots, d.signups);
    /* a mark or a move changes the sheet, not what the engine reads: the
       read is computed again only when the roster's weapons change */
    const key = rosterKey(d.event, board);
    let read = last && lastKey === key ? last.read : null;
    if (!read) {
      try {
        read = rosterRead(d.event, board, eng);
      } catch (err) {
        read = null;
      }
    }
    if (!read) { wrap.hidden = true; last = null; lastKey = null; return; }
    last = { read, board };
    lastKey = key;
    if (d.member && d.guild && d.guild.id && members.guildId !== d.guild.id && membersLoading !== d.guild.id) {
      loadMembers(d.guild.id);
    } else if (!d.member) {
      members = { guildId: null, rows: [] };
    }
    paint(read, board);
    wrap.hidden = false;
  });
})();
