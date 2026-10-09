"use strict";

/*
 * History (platform phase 9): facts over a guild's completed CTAs, read
 * from the attendance record. The database computes them on read
 * (guild_history, as the caller: a member sees the guild's CTAs and
 * their records, anyone else empty facts); this module shows them: the
 * guild's totals, each player's record (CTAs, attended, no-shows,
 * cancellations, reserves, unmarked, show rate, what they played), the
 * weapons fielded, and each completed CTA's counts.
 *
 * The measures, defined (supabase/migrations guild_history):
 *   show rate   attended / (attended + no-show); an unmarked record is
 *               neither and is counted apart, never guessed
 *   fill        the slots held at the end / the roster's slots
 *   played      the weapon of the slot held when the CTA completed,
 *               over attended records alone
 *   regular     REGULAR_MIN_ATTENDED attended or more, at a show rate
 *               of REGULAR_MIN_RATE or more (a curation judgment,
 *               stated beside the list)
 * None of these is a skill rating, and none is offered as one.
 *
 * The facts cover a period: the last 30 days, the last 90 days or all
 * time (HISTORY_WINDOWS). A period counts the completed CTAs that started
 * in it; the database reads every fact from those CTAs alone, so each
 * measure keeps its definition over any period, and the dialog says which
 * period it reads. A season (a start and an end) is a later period.
 *
 * build.py inlines this file as its own <script> after _signup.js. It
 * reads no planner state and never calls the engine: roles are read
 * through the catalog (one role read). Three parts, as in _profile.js:
 *   helpers - the only code that talks to window.DB (guild_history)
 *   pure    - rates, rows, filters, the periods, error wording
 *             (tests/test_history.js)
 *   UI      - the history dialog the account menu opens
 */


/* ------------------------------------------------------------ helpers */

/* the facts over one guild's completed CTAs: those that started at `since`
   or after, or every one (no since: the call names the guild alone) */
async function loadGuildHistory(guildId, since) {
  const args = { guild_id: guildId };
  if (since) args.since = since;
  const { data, error } = await window.DB.rpc("guild_history", args);

  if (error) {
    throw error;
  }

  return data || { totals: {}, ctas: [], players: [], weapons: [] };
}


/* --------------------------------------------------------------- pure */

/* a regular: attended this many completed CTAs, at this show rate or
   better (curation judgment) */
const REGULAR_MIN_ATTENDED = 3;
const REGULAR_MIN_RATE = 0.75;

/* how many of a player's weapons the table lists */
const HISTORY_PLAYS_SHOWN = 3;

/* The periods the facts cover: the last 30 days, the last 90 days, all
   time (the default, every completed CTA). A period counts the completed
   CTAs that started in it; every measure keeps its definition over any
   period. A season (a start and an end) is a later period. */
const HISTORY_WINDOWS = [
  { key: "30d", days: 30, label: "Last 30 days" },
  { key: "90d", days: 90, label: "Last 90 days" },
  { key: "all", days: null, label: "All time" }
];
const HISTORY_WINDOW_DEFAULT = "all";
const HISTORY_WINDOW_KEY = "history-window";


/* the period a key names; the default for a key it does not know */
function historyWindow(key) {
  return HISTORY_WINDOWS.find(w => w.key === key) || HISTORY_WINDOWS.find(w => w.key === HISTORY_WINDOW_DEFAULT);
}


/* the instant a period starts, as the ISO time guild_history compares a
   CTA's start with; null for all time. `now` is injectable for the test. */
function historySince(key, now) {
  const w = historyWindow(key);
  if (!w.days) return null;
  const t = now instanceof Date ? now.getTime() : (now ? new Date(now).getTime() : Date.now());
  return new Date(t - w.days * 86400000).toISOString();
}


/* the line that says which period the facts read */
function historyWindowNote(key, since, now) {
  const w = historyWindow(key);
  if (!w.days) return "Every completed CTA the guild has run.";
  const day = historyDateLabel(since, now);
  return `Completed CTAs that started in the ${w.label.toLowerCase()}${day ? `, since ${day}` : ""}.`;
}


/* attended / (attended + no-show); null when nothing is marked */
function showRate(attended, noShow) {
  const a = Number(attended) || 0;
  const n = a + (Number(noShow) || 0);
  return n ? a / n : null;
}


function ratePct(rate) {
  return rate == null || Number.isNaN(Number(rate)) ? "—" : `${Math.round(Number(rate) * 100)}%`;
}


function isRegular(player) {
  const rate = player.show_rate == null ? showRate(player.attended, player.no_show) : Number(player.show_rate);
  return (Number(player.attended) || 0) >= REGULAR_MIN_ATTENDED && rate != null && rate >= REGULAR_MIN_RATE;
}


/* the players as the table shows them: attended first, then CTAs, then
   name; each with its rate, its regular mark and what it played, the
   weapons named and given roles through the catalog */
function playerRows(players, catalog) {
  return (players || []).map(p => {
    const plays = (p.weapons || []).slice(0, HISTORY_PLAYS_SHOWN).map(w => {
      const info = weaponInfo(catalog, w.weapon_id);
      return { key: w.weapon_id, name: info.known ? info.name : w.weapon_id, role: info.role, n: Number(w.n) || 0 };
    });
    const roles = [];
    for (const play of plays) {
      if (play.role && !roles.includes(play.role)) roles.push(play.role);
    }
    return Object.assign({}, p, {
      rate: p.show_rate == null ? showRate(p.attended, p.no_show) : Number(p.show_rate),
      regular: isRegular(p),
      plays,
      roles: ROLE_ORDER.filter(r => roles.includes(r))
    });
  }).sort((a, b) => (b.attended || 0) - (a.attended || 0) || (b.ctas || 0) - (a.ctas || 0) || String(a.name).localeCompare(String(b.name)));
}


/* the rows whose name holds the query (any case); all of them for none */
function filterPlayers(rows, query) {
  const q = String(query || "").trim().toLowerCase();
  if (!q) return rows || [];
  return (rows || []).filter(r => String(r.name || "").toLowerCase().includes(q));
}


/* the weapons fielded, most played first, named through the catalog */
function weaponRows(weapons, catalog) {
  return (weapons || []).map(w => {
    const info = weaponInfo(catalog, w.weapon_id);
    return { key: w.weapon_id, name: info.known ? info.name : w.weapon_id, role: info.role, n: Number(w.n) || 0, players: Number(w.players) || 0 };
  }).sort((a, b) => b.n - a.n || a.name.localeCompare(b.name));
}


/* the completed CTAs, latest first, each with its fill */
function ctaRows(ctas) {
  return (ctas || []).map(c => Object.assign({}, c, {
    fill: c.slots ? (Number(c.claimed) || 0) / Number(c.slots) : null
  })).sort((a, b) => String(b.starts_at || "").localeCompare(String(a.starts_at || "")));
}


/* A table cell's date: the day alone in the reader's own zone ("Fri 3 Oct",
   the year once it is not this one), so the row stays one short line; the
   full local time with its UTC goes in the cell's title. `now` is
   injectable for the test. */
function historyDateLabel(iso, now) {
  const d = new Date(iso || "");
  if (Number.isNaN(d.getTime())) return "";
  const how = { weekday: "short", day: "numeric", month: "short" };
  if (d.getFullYear() !== (now || new Date()).getFullYear()) how.year = "numeric";
  return d.toLocaleDateString(undefined, how);
}


/* The facts as a sheet (the export, platform phase 10): the players,
   one row each with the weapons played as "Longbow ×3; Hallowfall ×1",
   or the completed CTAs. The same measures as the tables. */
function historySheetRows(kind, facts, catalog) {
  if (kind === "ctas") {
    const rows = [["CTA", "Content", "Planned", "Starts (UTC)", "Slots", "Claimed", "Fill", "Attended", "No-show", "Unmarked", "Cancelled", "Reserve"]];
    for (const c of ctaRows(facts && facts.ctas)) {
      rows.push([c.name, c.content || "", c.planned_size || "", c.starts_at || "", c.slots || 0, c.claimed || 0,
                 c.fill == null ? "" : ratePct(c.fill), c.attended || 0, c.no_show || 0, c.unmarked || 0, c.cancelled || 0, c.reserve || 0]);
    }
    return rows;
  }
  const rows = [["Player", "Account", "CTAs", "Attended", "No-show", "Cancelled", "Reserve", "Unmarked", "Show rate", "Regular",
                 "Last attended", "First seen", "Played"]];
  for (const p of playerRows(facts && facts.players, catalog)) {
    rows.push([p.name, p.account ? "yes" : "guest", p.ctas || 0, p.attended || 0, p.no_show || 0, p.cancelled || 0, p.reserve || 0,
               p.unmarked || 0, p.rate == null ? "" : ratePct(p.rate), p.regular ? "yes" : "", p.last_attended || "", p.first_seen || "",
               (p.weapons || []).map(w => `${weaponInfo(catalog, w.weapon_id).name} ×${w.n}`).join("; ")]);
  }
  return rows;
}


/* the totals as numbers, rates included */
function historyTotals(totals) {
  const t = totals || {};
  const n = k => Number(t[k]) || 0;
  return {
    ctas: n("ctas"), records: n("records"), attended: n("attended"), no_show: n("no_show"),
    unmarked: n("unmarked"), cancelled: n("cancelled"), reserve: n("reserve"),
    rate: t.show_rate == null ? showRate(t.attended, t.no_show) : Number(t.show_rate),
    fill: t.fill == null ? null : Number(t.fill)
  };
}


const HISTORY_MSG = {
  network: PROFILE_MSG.network,
  signedOut: "Log in to see a guild's history.",
  session: PROFILE_MSG.session,
  missing: "History is not available yet: the account database has not been updated for this page. Try again later.",
  unknown: PROFILE_MSG.unknown
};


function historyErrorKind(err) {
  const code = String((err && err.code) || "");
  const message = String((err && err.message) || "");

  if (authErrorKind(err) === "network") return "network";
  if (code === "not_signed_in") return "signedOut";
  if (/^PGRST30\d$/.test(code) || /jwt expired/i.test(message)) return "session";
  if (code === "PGRST202" || code === "PGRST205" || code === "42883" || code === "42P01") return "missing";

  return "unknown";
}


function historyErrorMessage(err) {
  const kind = historyErrorKind(err);
  const message = String((err && err.message) || "").trim();

  if (kind === "unknown" && message) {
    return `Something went wrong: ${message}`;
  }

  return HISTORY_MSG[kind];
}


/* ----------------------------------------------------------------- UI */

(function historyUI() {
  if (typeof document === "undefined") {
    return;
  }

  const $id = id => document.getElementById(id);
  const dialog = $id("history-dialog");

  if (!dialog || typeof dialog.showModal !== "function" || !window.Account) {
    return;
  }

  const CATALOG = typeof ACCOUNT_CATALOG !== "undefined" ? ACCOUNT_CATALOG : {};
  const CONTENTS = typeof ACCOUNT_CONTENTS !== "undefined" ? ACCOUNT_CONTENTS : {};

  const el = {
    error: $id("hs-error"),
    notice: $id("hs-notice"),
    live: $id("hs-live"),
    guild: $id("hs-guild"),
    window: $id("hs-window"),
    windowNote: $id("hs-window-note"),
    totals: $id("hs-totals"),
    empty: $id("hs-empty"),
    body: $id("hs-body"),
    search: $id("hs-search"),
    players: $id("hs-players"),
    playersNote: $id("hs-players-note"),
    weapons: $id("hs-weapons"),
    ctas: $id("hs-ctas"),
    definitions: $id("hs-definitions"),
    exportPlayers: $id("hs-export-players"),
    exportCtas: $id("hs-export-ctas")
  };

  let account = window.Account.current();
  let guilds = [];
  let facts = null;
  let rows = [];
  let openSeq = 0;
  let state = "ready";       /* the read: "loading" until the service answers, "failed" when it did not */
  let windowKey = storedWindow();   /* the period the facts cover, remembered per browser */

  const showError = message => acctMessage(el.error, el.notice, "error", message);
  const clearMessages = () => acctMessage(el.error, el.notice, null, "");
  const announce = text => { el.live.textContent = text; };
  const guildId = () => el.guild.value || null;

  el.definitions.textContent = `Show rate is attended over attended plus no-show; an unmarked record counts as neither. `
    + `Fill is the slots held at the end over the roster's slots. Played is the slot's weapon at completion, over attended records. `
    + `A regular attended ${REGULAR_MIN_ATTENDED} or more at ${Math.round(REGULAR_MIN_RATE * 100)}% or better. `
    + `A period counts the completed CTAs that started in it, and every fact is read from those alone. None of this is a skill rating.`;

  el.window.replaceChildren(...HISTORY_WINDOWS.map(w => {
    const o = document.createElement("option");
    o.value = w.key;
    o.textContent = w.label;
    return o;
  }));
  el.window.value = windowKey;

  function storedWindow() {
    try {
      const key = window.localStorage.getItem(HISTORY_WINDOW_KEY);
      return historyWindow(key).key;
    } catch (err) {
      return HISTORY_WINDOW_DEFAULT;
    }
  }

  function renderGuilds() {
    el.guild.replaceChildren(...guilds.map(({ guild, role }) => {
      const o = document.createElement("option");
      o.value = guild.id;
      o.textContent = `${guild.name} (${GUILD_ROLE_NAMES[role] || role})`;
      return o;
    }));
    el.guild.disabled = !guilds.length;
  }

  function cell(text, cls) {
    const td = document.createElement("td");
    if (cls) td.className = cls;
    td.textContent = text;
    return td;
  }

  /* a date cell: the day in the cell, the full local time with its UTC
     in the title */
  function whenCell(iso) {
    const td = cell(iso ? historyDateLabel(iso) || "—" : "—", "hs-when");
    if (iso) td.title = eventTimeLabel(iso, true);
    return td;
  }

  function roleTag(role) {
    const tag = document.createElement("span");
    tag.className = `pw-role ${role}`;
    tag.textContent = ROLE_NAMES[role] || role;
    return tag;
  }

  function stat(label, value) {
    const box = document.createElement("span");
    box.className = "gd-cov";
    const b = document.createElement("b");
    b.textContent = String(value);
    box.append(b, ` ${label}`);
    return box;
  }

  function renderTotals() {
    const t = historyTotals(facts && facts.totals);
    el.totals.replaceChildren(
      stat("completed CTAs", t.ctas),
      stat("records", t.records),
      stat("attended", t.attended),
      stat("no-show", t.no_show),
      stat("show rate", ratePct(t.rate)),
      stat("unmarked", t.unmarked),
      stat("fill", ratePct(t.fill)));
  }

  function renderPlayers() {
    const shown = filterPlayers(rows, el.search.value);
    el.players.replaceChildren(...shown.map(p => {
      const tr = document.createElement("tr");
      if (p.regular) tr.className = "hs-regular";
      const name = document.createElement("td");
      const n = document.createElement("span");
      n.className = "gd-name";
      n.textContent = p.name;
      name.append(n);
      const sub = document.createElement("span");
      sub.className = "gd-sub";
      sub.textContent = [p.regular ? "regular" : "", p.account ? "" : "guest",
                         p.cancelled ? `${p.cancelled} cancelled` : "", p.reserve ? `${p.reserve} reserve` : "",
                         p.unmarked ? `${p.unmarked} unmarked` : ""].filter(Boolean).join(" · ");
      name.append(sub);
      const plays = document.createElement("td");
      plays.className = "hs-plays";
      for (const play of p.plays) {
        const chip = document.createElement("span");
        chip.className = "hs-play";
        chip.textContent = `${play.name} ×${play.n}`;
        if (play.role) chip.append(roleTag(play.role));
        plays.append(chip);
      }
      if (!p.plays.length) plays.append(document.createTextNode("—"));
      tr.append(name, cell(String(p.ctas), "hs-num"), cell(String(p.attended), "hs-num"), cell(String(p.no_show), "hs-num"),
                cell(ratePct(p.rate), "hs-num"), whenCell(p.last_attended), plays);
      return tr;
    }));
    el.playersNote.textContent = rows.length ? (shown.length ? "" : "No player by that name.") : "No records yet: complete a CTA and mark its attendance.";
    el.playersNote.hidden = !el.playersNote.textContent;
  }

  function renderWeapons() {
    const list = weaponRows(facts && facts.weapons, CATALOG);
    el.weapons.replaceChildren(...list.map(w => {
      const li = document.createElement("li");
      li.className = "gd-weapon";
      const name = document.createElement("span");
      name.textContent = `${w.name} ×${w.n}`;
      li.append(name);
      if (w.role) li.append(roleTag(w.role));
      const who = document.createElement("span");
      who.className = "gd-sub";
      who.textContent = `${w.players} player${w.players === 1 ? "" : "s"}`;
      li.append(who);
      return li;
    }));
    if (!list.length) {
      const li = document.createElement("li");
      li.className = "gd-none";
      li.textContent = "Nothing played yet.";
      el.weapons.append(li);
    }
  }

  function renderCtas() {
    const list = ctaRows(facts && facts.ctas);
    el.ctas.replaceChildren(...list.map(c => {
      const tr = document.createElement("tr");
      const name = document.createElement("td");
      const n = document.createElement("span");
      n.className = "gd-name";
      n.textContent = c.name;
      name.append(n);
      const sub = document.createElement("span");
      sub.className = "gd-sub";
      sub.textContent = `${CONTENTS[c.content] || c.content} · ${c.planned_size} planned`;
      name.append(sub);
      tr.append(name, whenCell(c.starts_at),
                cell(`${c.claimed}/${c.slots} (${ratePct(c.fill)})`, "hs-num"),
                cell(String(c.attended), "hs-num"), cell(String(c.no_show), "hs-num"), cell(String(c.unmarked), "hs-num"));
      return tr;
    }));
  }

  function paint() {
    const has = !!(facts && historyTotals(facts.totals).ctas);
    el.empty.hidden = has || !guildId();
    el.body.hidden = !has;
    /* the totals sit outside the body: a guild without facts, or one still
       loading, never shows the last guild's */
    if (!has) el.totals.replaceChildren();
    /* an unanswered read says so: "No completed CTA yet" and "Join or create
       a guild" are the service's answers, never the wait for them */
    if (state !== "ready") {
      el.empty.textContent = state === "loading" ? "Loading the guild's history…"
                                                 : "The history did not load. Close this dialog and open it again to retry.";
      el.empty.hidden = false;
      return;
    }
    if (!guildId()) {
      el.empty.textContent = "Join or create a guild to see its history.";
      el.empty.hidden = false;
      return;
    }
    const period = historyWindow(windowKey);
    el.empty.textContent = period.days
      ? `No completed CTA started in the ${period.label.toLowerCase()}. Choose a longer period, or All time.`
      : "No completed CTA yet. Facts appear once a CTA is completed and its attendance marked.";
    if (!has) return;
    renderTotals();
    renderPlayers();
    renderWeapons();
    renderCtas();
  }

  el.search.addEventListener("input", renderPlayers);

  /* the facts as CSV files (the export); a period's file names it */
  const guildName = () => {
    const g = guilds.find(x => x.guild.id === guildId());
    return g ? g.guild.name : "guild";
  };
  const periodName = () => {
    const period = historyWindow(windowKey);
    return period.days ? ` ${period.label.toLowerCase()}` : "";
  };
  el.exportPlayers.addEventListener("click", () => {
    if (!facts) return;
    acctDownloadText(acctFilename(`${guildName()} players${periodName()}`, "csv"), acctCsvText(historySheetRows("players", facts, CATALOG)), "text/csv");
    announce("Players exported as CSV.");
  });
  el.exportCtas.addEventListener("click", () => {
    if (!facts) return;
    acctDownloadText(acctFilename(`${guildName()} CTAs${periodName()}`, "csv"), acctCsvText(historySheetRows("ctas", facts, CATALOG)), "text/csv");
    announce("CTAs exported as CSV.");
  });

  /* the period: a choice reads the facts again and is remembered */
  el.window.addEventListener("change", () => {
    windowKey = historyWindow(el.window.value).key;
    try { window.localStorage.setItem(HISTORY_WINDOW_KEY, windowKey); } catch (err) { /* the choice lasts the visit */ }
    reload();
  });

  async function reload() {
    const seq = ++openSeq;
    const period = historyWindow(windowKey);
    const since = historySince(period.key);
    facts = null;
    rows = [];
    state = guildId() ? "loading" : "ready";
    /* the dialog says which period it reads, before and after the answer */
    el.windowNote.textContent = guildId() ? historyWindowNote(period.key, since) : "";
    el.totals.setAttribute("aria-label", period.days ? `Totals over completed CTAs, ${period.label.toLowerCase()}` : "Totals over completed CTAs");
    clearMessages();
    paint();
    if (!guildId()) return;

    try {
      facts = await loadGuildHistory(guildId(), since);
    } catch (err) {
      if (seq !== openSeq) return;
      state = "failed";
      paint();
      showError(historyErrorMessage(err));
      return;
    }
    if (seq !== openSeq) return;

    state = "ready";
    rows = playerRows(facts.players, CATALOG);
    paint();
    announce(`${historyTotals(facts.totals).ctas} completed CTAs, ${period.label.toLowerCase()}.`);
  }

  el.guild.addEventListener("change", reload);

  async function openHistory() {
    if (!account.user) return;

    clearMessages();
    facts = null;
    rows = [];
    guilds = [];
    state = "loading";
    el.search.value = "";
    el.window.value = windowKey;
    el.windowNote.textContent = "";
    renderGuilds();
    paint();
    if (!dialog.open) dialog.showModal();

    const seq = ++openSeq;
    try {
      guilds = await loadMyGuilds();
    } catch (err) {
      if (seq !== openSeq) return;
      state = "failed";
      paint();
      showError(guildErrorMessage(err));
      return;
    }
    if (seq !== openSeq) return;

    renderGuilds();
    await reload();
  }

  acctWireDialog(dialog);
  $id("hs-close").addEventListener("click", () => dialog.close());


  /* ---- identity ---- */

  window.Account.subscribe(state => {
    const was = account.user ? account.user.id : null;
    account = state;

    if (dialog.open && (!state.user || state.user.id !== was)) {
      dialog.close();
    }
  });

  window.Account.registerView("history", openHistory);
})();
