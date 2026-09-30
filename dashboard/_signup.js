"use strict";

/*
 * Sign-up (platform phase 5): the sheet of a CTA. A player with the CTA's
 * link claims a slot or signs up as a reserve, declares the weapons they
 * bring, their item power, whether they can swap, and a note. Two kinds of
 * player use one sheet: an account (named after its character, one
 * sign-up per CTA under its id) and a guest (a name they type; their
 * sign-up is keyed by the hash of a claim token this browser keeps in
 * localStorage, so this browser alone edits or cancels it, and an account
 * created here later adopts it).
 *
 * The link is index.html?cta=<share code>. The code is the key: the
 * database reads it from the statement (event_by_code, sign_up,
 * cancel_sign_up run as the caller, signed in or not) and its policies
 * decide what comes back. build.py inlines this file as its own <script>
 * after _events.js. It reads no planner state and never calls the engine;
 * an event opens in the planner through the share hash, as a comp does.
 *
 * The caller runs the sheet from the same dialog (phase 6): a caller,
 * officer or admin of the CTA's guild moves players between slots and
 * the reserves (a held slot swaps), removes sign-ups, adds a player by
 * name, changes a slot's weapon and moves the status, until the CTA is
 * completed. The database decides; the client offers what the policies
 * allow (callerPowers).
 *
 * The sheet is live (phase 7): after every write the database sends
 * 'changed' on the CTA's Realtime topic (cta:<code>; the payload names
 * the table and the operation, nothing else) and the sheet re-reads
 * itself through event_by_code. The channel only reports; the policies
 * still decide what is read.
 *
 * The sheet carries the record (phase 8): attendance, kept apart from
 * the sign-up. A player confirms their own sign-up before the CTA
 * completes; the caller marks attended and no-show any time, one by
 * one or everyone in a slot at once; a cancellation and a settled
 * reserve stay on the record; the sheet shows the marks.
 *
 * Three parts, as in _profile.js:
 *   helpers - the only code that talks to window.DB (event_by_code,
 *             sign_up, cancel_sign_up; the caller's move_signup,
 *             add_player, a removal, a slot's weapon; the channel; the
 *             record's confirm_sign_up, mark_attendance,
 *             mark_all_attended)
 *   pure    - the link and the code, the claim token, the board (slots
 *             with their claimants, the reserves, what is free),
 *             validation, the payload, error wording (tests/test_signup.js)
 *   UI      - the sheet dialog, opened by the link or from the CTAs dialog
 */


/* ------------------------------------------------------------ helpers */

/* the CTA a code names: its guild, slots, sign-ups and the caller's own
   sign-up (by account, or by the guest token) */
async function loadSheet(code, token) {
  const { data, error } = await window.DB.rpc("event_by_code", { code, token: token || null });

  if (error) {
    throw error;
  }

  return data;
}


/* the caller's sign-up on the CTA, made or changed (sign_up) */
async function submitSignUp(code, token, signup) {
  const { data, error } = await window.DB.rpc("sign_up", {
    code, token: token || null, signup: signupPayload(signup)
  });

  if (error) {
    throw error;
  }

  return data;
}


/* the caller's sign-up gone; false when there was none */
async function cancelSignUp(code, token) {
  const { data, error } = await window.DB.rpc("cancel_sign_up", { code, token: token || null });

  if (error) {
    throw error;
  }

  return data === true;
}


/* ---- the caller's helpers (phase 6): the caller roles, until completed ---- */

/* a player to a slot (swapping with its holder), or to the reserves */
async function moveSignup(signupId, position) {
  const { data, error } = await window.DB.rpc("move_signup", {
    signup_id: signupId, target: position === "" || position == null ? null : Number(position)
  });

  if (error) {
    throw error;
  }

  return data;
}


/* a player the caller writes onto the sheet, by name */
async function addPlayer(eventId, player) {
  const { data, error } = await window.DB.rpc("add_player", {
    event_id: eventId, player: signupPayload(player)
  });

  if (error) {
    throw error;
  }

  return data;
}


/* a sign-up removed by the caller (or the player: their own) */
async function removeSignup(signupId) {
  const { data, error } = await window.DB
    .from("signups")
    .delete()
    .eq("id", signupId)
    .select("id");

  if (error) {
    throw error;
  }

  if (!data || !data.length) {
    throw guildRefusal();
  }

  return data[0];
}


/* a slot's weapon (null: any weapon) */
async function setSlotWeapon(eventId, position, weaponId) {
  const { data, error } = await window.DB
    .from("event_slots")
    .update({ weapon_id: weaponId || null })
    .eq("event_id", eventId)
    .eq("position", position)
    .select("position");

  if (error) {
    throw error;
  }

  if (!data || !data.length) {
    throw guildRefusal();
  }

  return data[0];
}


/* ---- the live sheet (phase 7) ---- */

/* The CTA's channel: after every write to the sheet the database sends
   'changed' on cta:<code> (a trigger; the payload names the table and
   the operation, nothing else), and the client re-reads the sheet
   through event_by_code, so what it sees is still what the policies
   allow. Returns the function that leaves the channel. */
function watchSheet(code, onChange, onState) {
  const channel = window.DB.channel(sheetTopic(code));
  channel.on("broadcast", { event: "changed" }, message => onChange((message && message.payload) || {}));
  channel.subscribe(status => { if (onState) onState(status); });
  return () => { window.DB.removeChannel(channel); };
}


/* ---- the record (phase 8) ---- */

/* the player's own record: signed_up <-> confirmed, before completion */
async function confirmSignUp(code, token, confirmed) {
  const { data, error } = await window.DB.rpc("confirm_sign_up", { code, token: token || null, confirmed: !!confirmed });

  if (error) {
    throw error;
  }

  return data;
}


/* the caller's mark on one record (any listed status, any time) */
async function markAttendance(attendanceId, status) {
  const { data, error } = await window.DB.rpc("mark_attendance", { attendance_id: attendanceId, mark: status });

  if (error) {
    throw error;
  }

  return data;
}


/* everyone still signed up or confirmed in a slot attended; how many */
async function markAllAttended(eventId) {
  const { data, error } = await window.DB.rpc("mark_all_attended", { event_id: eventId });

  if (error) {
    throw error;
  }

  return Number(data) || 0;
}


/* --------------------------------------------------------------- pure */

/* The database's bounds (supabase/migrations signups;
   tests/test_supabase_schema.py pins that they agree). The name bound is
   ACCOUNT_NAME_MAX; the weapon key form is the profile's WEAPON_KEY_RE;
   the share code form is the guild code's (JOIN_CODE_RE). */
const SIGNUP_WEAPONS_MAX = 10;
const SIGNUP_IP_MIN = 0;
const SIGNUP_IP_MAX = 3000;
const SIGNUP_NOTE_MAX = 200;
const SIGNUPS_MAX = 120;

/* the claim token: 16 random bytes as hex, kept per CTA in localStorage */
const CLAIM_TOKEN_RE = /^[a-f0-9]{32}$/;
const SIGNUP_PARAM = "cta";

/* what a sheet says about a CTA that is not open */
const SHEET_STATUS_MSG = {
  draft: "Sign-up has not opened yet. Check back once the caller opens it.",
  open: "",
  locked: "The roster is locked: no new sign-ups or changes. You can still cancel yours.",
  completed: "This CTA is completed. Its sheet is kept as it ended."
};


function newClaimToken(bytes) {
  return Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
}


function claimTokenKey(code) {
  return `cta-claim:${cleanJoinCode(code)}`;
}


/* the share code in a page address (?cta=...), or null */
function codeFromSearch(search) {
  const params = new URLSearchParams(String(search || "").replace(/^\?/, ""));
  const code = cleanJoinCode(params.get(SIGNUP_PARAM) || "");
  return JOIN_CODE_RE.test(code) ? code : null;
}


/* the link to a CTA's sheet: this page, the code as its one parameter */
function signupLink(code, href) {
  const base = String(href || "").replace(/[?#].*$/, "");
  return `${base}?${SIGNUP_PARAM}=${cleanJoinCode(code)}`;
}


/* The board: each slot with its claimant, the reserves (sign-ups without a
   slot), the free positions, and the counts. */
function sheetBoard(slots, signups) {
  const byPos = new Map();
  for (const s of signups || []) {
    if (s.position != null && !byPos.has(s.position)) byPos.set(s.position, s);
  }

  const rows = normalizeSlots(slots).map(slot => Object.assign({}, slot, { claimant: byPos.get(slot.position) || null }));
  const reserves = (signups || []).filter(s => s.position == null)
    .sort((a, b) => String(a.created_at || "").localeCompare(String(b.created_at || "")));
  const free = rows.filter(r => !r.claimant).map(r => r.position);

  return {
    rows,
    reserves,
    free,
    counts: { slots: rows.length, claimed: rows.length - free.length, free: free.length, reserves: reserves.length }
  };
}


/* the rules the database holds, as sentences; `allowed` is the set of
   positions this player may name (the free ones and their own) */
function validateSignup({ playerName, position, itemPower, weapons, note }, { guest, allowed }) {
  const errors = {};

  if (guest) {
    if (!String(playerName || "").trim()) {
      errors.playerName = "Enter the name the caller will see.";
    } else if (nameLength(playerName) > ACCOUNT_NAME_MAX) {
      errors.playerName = `Use at most ${ACCOUNT_NAME_MAX} characters.`;
    }
  }

  if (position !== "" && position != null) {
    const n = Number(position);
    if (!Number.isInteger(n) || !(allowed || new Set()).has(n)) {
      errors.position = "That slot is taken. Pick a free one, or sign up as a reserve.";
    }
  }

  if (itemPower !== "" && itemPower != null) {
    const ip = Number(itemPower);
    if (!Number.isInteger(ip) || ip < SIGNUP_IP_MIN || ip > SIGNUP_IP_MAX) {
      errors.itemPower = `Item power is a whole number up to ${SIGNUP_IP_MAX}.`;
    }
  }

  const list = weapons || [];
  if (list.length > SIGNUP_WEAPONS_MAX) {
    errors.weapons = `Declare at most ${SIGNUP_WEAPONS_MAX} weapons.`;
  } else if (list.some(k => !WEAPON_KEY_RE.test(k)) || new Set(list).size !== list.length) {
    errors.weapons = "A weapon is not a weapon of the list, or is listed twice.";
  }

  if (nameLength(note || "") > SIGNUP_NOTE_MAX) {
    errors.note = `Use at most ${SIGNUP_NOTE_MAX} characters.`;
  }

  return errors;
}


/* the sign_up payload */
function signupPayload({ position, playerName, itemPower, canSwap, weapons, note }) {
  const pos = position === "" || position == null ? null : Number(position);
  const ip = itemPower === "" || itemPower == null ? null : Number(itemPower);
  return {
    position: Number.isInteger(pos) ? pos : null,
    player_name: String(playerName || "").trim(),
    item_power: Number.isInteger(ip) ? ip : null,
    can_swap: !!canSwap,
    weapons: (weapons || []).slice(0, SIGNUP_WEAPONS_MAX),
    note: String(note || "").trim()
  };
}


/* a player's profile lists as the weapons a sign-up declares: main first,
   then can-also-play, at most the bound */
function weaponsFromLists(lists) {
  const seen = new Set();
  const out = [];
  for (const key of [...((lists && lists.main) || []), ...((lists && lists.secondary) || [])]) {
    if (seen.has(key) || out.length >= SIGNUP_WEAPONS_MAX) continue;
    seen.add(key);
    out.push(key);
  }
  return out;
}


/* what the caller's role does with the sheet: the policies' caller
   roles, until the CTA is completed; the status moves are the guard's */
function callerPowers(myRole, status) {
  const write = compPowers(myRole).write;
  return {
    manage: write && !!status && status !== "completed",
    moves: eventPowers(myRole, { status }).moves
  };
}


/* where a sign-up can be moved: the reserves, every other slot (a held
   one is a swap with its holder) */
function moveTargets(board, signup, catalog) {
  const own = signup && signup.position != null ? signup.position : null;
  const targets = [{ value: "", label: own == null ? "Reserve (here)" : "To the reserves" }];
  for (const row of board.rows) {
    if (row.position === own) continue;
    const weapon = row.weapon_id ? weaponInfo(catalog, row.weapon_id).name : "any weapon";
    targets.push({
      value: String(row.position),
      label: `${row.position} · ${weapon}` + (row.claimant ? ` · swap with ${row.claimant.player_name}` : "")
    });
  }
  return targets;
}


/* the catalog as a slot's weapon list, one group per role (the catalog's
   role class: one role read), names in order */
function weaponOptions(catalog) {
  const groups = ROLE_ORDER.map(role => ({ role, name: ROLE_NAMES[role], weapons: [] }));
  const other = { role: "other", name: "Other", weapons: [] };
  for (const [key, entry] of Object.entries(catalog || {})) {
    if (!entry || entry.removed) continue;
    const group = groups.find(g => g.role === entry.role) || other;
    group.weapons.push({ key, name: entry.name || key });
  }
  for (const group of groups.concat(other)) group.weapons.sort((a, b) => a.name.localeCompare(b.name));
  return groups.concat(other).filter(g => g.weapons.length);
}


/* the CTA's channel topic: the code is the key, as everywhere on the sheet */
function sheetTopic(code) {
  return `cta:${cleanJoinCode(code)}`;
}


/* what the sheet says about its channel (the Realtime client's states) */
const LIVE_STATE_MSG = {
  SUBSCRIBED: "live",
  CHANNEL_ERROR: "not live: refresh to update",
  TIMED_OUT: "not live: refresh to update",
  CLOSED: ""
};


/* how long the sheet waits after a message before re-reading, so a swap
   (several rows, several messages) reads once */
const LIVE_SETTLE_MS = 250;


/* The record's statuses (supabase/migrations attendance;
   tests/test_supabase_schema.py pins that they agree) and the marks a
   caller's list offers: cancelled and reserve are the record's own
   findings, shown, not chosen. */
const ATTENDANCE_STATUSES = ["signed_up", "confirmed", "attended", "no_show", "cancelled", "reserve"];
const ATTENDANCE_NAMES = { signed_up: "signed up", confirmed: "confirmed", attended: "attended", no_show: "no-show", cancelled: "cancelled", reserve: "reserve" };
const ATTENDANCE_MARKS = ["signed_up", "confirmed", "attended", "no_show"];


/* how many records stand in each status */
function attendanceSummary(records) {
  const out = { total: 0 };
  for (const status of ATTENDANCE_STATUSES) out[status] = 0;
  for (const r of records || []) {
    if (!Object.prototype.hasOwnProperty.call(out, r.status)) continue;
    out[r.status] += 1;
    out.total += 1;
  }
  return out;
}


/* the records with no live claim behind them (a cancellation, a
   settled reserve), latest first */
function historyRows(records) {
  return (records || []).filter(r => !r.signup_id)
    .sort((a, b) => String(b.marked_at || "").localeCompare(String(a.marked_at || "")) || a.player_name.localeCompare(b.player_name));
}


/* what the record offers: a caller marks (any time), marks everyone
   once the CTA is completed; a player confirms their own sign-up before
   completion */
function markPowers(myRole, status, mine) {
  const write = compPowers(myRole).write;
  return {
    mark: write,
    all: write && status === "completed",
    confirm: !!mine && !!status && status !== "completed"
  };
}


const SIGNUP_MSG = {
  network: PROFILE_MSG.network,
  session: PROFILE_MSG.session,
  missing: "Sign-up is not available yet: the account database has not been updated for this page. Try again later.",
  noEvent: "No CTA has this link. Ask the caller for a fresh one.",
  closed: "Sign-up is not open for this CTA.",
  taken: "That slot was just taken. Pick another, or sign up as a reserve.",
  noSlot: "That slot is no longer on the roster. Pick another.",
  needsName: "Enter the name the caller will see.",
  needsCharacter: "Name your character in the profile first, or enter a name here.",
  needsToken: "This browser holds no claim for this CTA. Sign up again to make one.",
  full: `This CTA takes at most ${SIGNUPS_MAX} sign-ups.`,
  badWeapon: "A declared weapon is not a weapon of the list, or is listed twice.",
  refused: "The server refused the change. Reload the sheet and try again.",
  invalid: "The server refused a value. Check the name, item power, weapons and note, then try again.",
  unknown: PROFILE_MSG.unknown
};


function signupErrorKind(err) {
  const code = String((err && err.code) || "");
  const message = String((err && err.message) || "");

  if (authErrorKind(err) === "network") return "network";
  if (/^PGRST30\d$/.test(code) || /jwt expired/i.test(message)) return "session";
  if (code === "PGRST202" || code === "PGRST205" || code === "42883" || code === "42P01") return "missing";
  if (code === "P0002") return "noEvent";
  if (code === "55000") return "closed";
  if (code === "23505") return "taken";
  if (code === "23503") return "noSlot";
  if (code === "23502" && /character/i.test(message)) return "needsCharacter";
  if (code === "23502") return "needsName";
  if (code === "42501" && /claim token/i.test(message)) return "needsToken";
  if (code === "23514" && /at most \d+ sign-ups/i.test(message)) return "full";
  if (code === "23514" && /weapon/i.test(message)) return "badWeapon";
  if (code === "42501") return "refused";
  if (code === "23514" || code === "22023" || code === "22001" || code === "22P02" || code === "22003") return "invalid";

  return "unknown";
}


function signupErrorMessage(err) {
  const kind = signupErrorKind(err);
  const message = String((err && err.message) || "").trim();

  if (kind === "unknown" && message) {
    return `Something went wrong: ${message}`;
  }

  return SIGNUP_MSG[kind];
}


/* ----------------------------------------------------------------- UI */

(function signupUI() {
  if (typeof document === "undefined") {
    return;
  }

  const $id = id => document.getElementById(id);
  const dialog = $id("signup-dialog");

  if (!dialog || typeof dialog.showModal !== "function" || !window.Account) {
    return;
  }

  const CATALOG = typeof ACCOUNT_CATALOG !== "undefined" ? ACCOUNT_CATALOG : {};
  const CONTENTS = typeof ACCOUNT_CONTENTS !== "undefined" ? ACCOUNT_CONTENTS : {};

  const el = {
    kicker: $id("su-kicker"),
    title: $id("su-title"),
    when: $id("su-when"),
    status: $id("su-status"),
    notes: $id("su-notes"),
    error: $id("su-error"),
    notice: $id("su-notice"),
    live: $id("su-live"),
    counts: $id("su-counts"),
    board: $id("su-board"),
    reserves: $id("su-reserves"),
    reservesWrap: $id("su-reserves-wrap"),
    closed: $id("su-closed"),
    form: $id("su-form"),
    who: $id("su-who"),
    nameWrap: $id("su-name-wrap"),
    name: $id("su-name"),
    slot: $id("su-slot"),
    weapons: $id("su-weapons"),
    weaponAdd: $id("su-weapon-add"),
    weaponResults: $id("su-weapon-results"),
    weaponsErr: $id("su-weapons-err"),
    ip: $id("su-ip"),
    swap: $id("su-swap"),
    note: $id("su-note"),
    submit: $id("su-submit"),
    cancel: $id("su-cancel"),
    refresh: $id("su-refresh"),
    open: $id("su-open"),
    link: $id("su-link"),
    liveState: $id("su-live-state"),
    confirm: $id("su-confirm"),
    historyWrap: $id("su-history-wrap"),
    history: $id("su-history"),
    markAll: $id("su-mark-all"),
    callerWrap: $id("su-caller"),
    callerMoves: $id("su-caller-moves"),
    addForm: $id("su-add-form"),
    addName: $id("su-add-name"),
    addSlot: $id("su-add-slot"),
    add: $id("su-add")
  };

  const FIELDS = { playerName: el.name, position: el.slot, itemPower: el.ip, note: el.note };

  let account = window.Account.current();
  let code = null;             /* the CTA on the sheet */
  let sheet = null;            /* event_by_code's answer */
  let weapons = [];            /* the weapons declared, as edited */
  let myRole = null;           /* the caller's role in the CTA's guild, when signed in */
  let roleGuild = null;        /* the guild that role was read for */
  let caller = callerPowers(null, null);
  let marks = markPowers(null, null, null);
  let busy = false;
  let openSeq = 0;
  let booted = false;
  let leave = null;            /* leaves the CTA's channel */
  let liveTimer = null;

  const showError = message => acctMessage(el.error, el.notice, "error", message);
  const showNotice = message => acctMessage(el.error, el.notice, "notice", message);
  const clearMessages = () => acctMessage(el.error, el.notice, null, "");
  const announce = text => { el.live.textContent = text; };
  const isGuest = () => !account.user;

  /* the claim token this browser holds for the CTA; made on the first
     sign-up */
  function readToken() {
    try { const t = localStorage.getItem(claimTokenKey(code)); return CLAIM_TOKEN_RE.test(t || "") ? t : null; }
    catch (err) { return null; }
  }

  function ensureToken() {
    let token = readToken();
    if (token) return token;
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    token = newClaimToken(bytes);
    try { localStorage.setItem(claimTokenKey(code), token); } catch (err) { /* a private window: the claim lasts the session */ }
    return token;
  }

  function forgetToken() {
    try { localStorage.removeItem(claimTokenKey(code)); } catch (err) { /* nothing kept */ }
  }


  /* ---- the board ---- */

  function roleTag(role) {
    const tag = document.createElement("span");
    tag.className = `pw-role ${role}`;
    tag.textContent = ROLE_NAMES[role] || role;
    return tag;
  }

  function weaponCell(key) {
    const wrap = document.createElement("span");
    wrap.className = "su-weapon";
    if (!key) {
      const open = document.createElement("span");
      open.className = "cp-open";
      open.textContent = "any weapon";
      wrap.append(open);
      return wrap;
    }
    const info = weaponInfo(CATALOG, key);
    const src = (typeof ICONS !== "undefined" && ICONS[key])
      || (info.item ? `https://render.albiononline.com/v1/item/${encodeURIComponent(info.item)}.png?size=64` : "");
    if (src) {
      const img = document.createElement("img");
      img.className = "pw-art";
      img.src = src;
      img.alt = "";
      img.width = 22;
      img.height = 22;
      img.loading = "lazy";
      wrap.append(img);
    }
    const name = document.createElement("span");
    name.textContent = info.known ? info.name : key;
    wrap.append(name);
    if (info.role) wrap.append(roleTag(info.role));
    return wrap;
  }

  function playerCell(s, mine) {
    const td = document.createElement("td");
    td.className = "su-player";
    if (!s) {
      const free = document.createElement("span");
      free.className = "su-free";
      free.textContent = "free";
      td.append(free);
      return td;
    }
    const name = document.createElement("span");
    name.className = "gd-name";
    name.textContent = s.player_name + (mine ? " (you)" : "");
    td.append(name);
    if (s.attendance && s.attendance !== "signed_up") td.append(attendanceTag(s.attendance));
    const sub = document.createElement("span");
    sub.className = "gd-sub";
    const parts = [];
    if (s.item_power) parts.push(`${s.item_power} IP`);
    if (s.can_swap) parts.push("can swap");
    if (!s.account) parts.push("guest");
    if (s.note) parts.push(s.note);
    sub.textContent = parts.join(" · ");
    td.append(sub);
    if (s.weapons && s.weapons.length) {
      const list = document.createElement("span");
      list.className = "su-declared";
      list.textContent = s.weapons.map(k => weaponInfo(CATALOG, k).name).join(", ");
      td.append(list);
    }
    return td;
  }

  function renderBoard() {
    const ev = sheet.event;
    const board = sheetBoard(sheet.slots, sheet.signups);
    const mineId = sheet.mine && sheet.mine.id;

    el.kicker.textContent = sheet.guild ? `${sheet.guild.name}${sheet.guild.albion_server ? " · " + (ALBION_SERVERS[sheet.guild.albion_server] || sheet.guild.albion_server) : ""}` : "CTA";
    el.title.textContent = ev.name;
    el.when.textContent = [eventTimeLabel(ev.starts_at), ev.mass_at ? `mass ${eventTimeLabel(ev.mass_at)}` : "",
                           `${CONTENTS[ev.content] || ev.content} · ${ev.planned_size} planned`].filter(Boolean).join(" · ");
    el.status.textContent = EVENT_STATUS_NAMES[ev.status] || ev.status;
    el.status.dataset.status = ev.status;
    el.notes.textContent = ev.notes || "";
    el.notes.hidden = !ev.notes;

    const att = attendanceSummary(sheet.attendance);
    el.counts.textContent = `${board.counts.claimed} of ${board.counts.slots} slot${board.counts.slots === 1 ? "" : "s"} claimed`
      + (board.counts.reserves ? `, ${board.counts.reserves} reserve${board.counts.reserves === 1 ? "" : "s"}` : "")
      + (ev.status === "completed"
         ? ` · attended ${att.attended} · no-show ${att.no_show}` + (att.reserve ? ` · reserve ${att.reserve}` : "")
         : (att.confirmed ? ` · ${att.confirmed} confirmed` : ""));

    caller = callerPowers(myRole, ev.status);
    marks = markPowers(myRole, ev.status, sheet.mine);

    el.board.replaceChildren(...board.rows.map(row => {
      const tr = document.createElement("tr");
      if (row.claimant && row.claimant.id === mineId) tr.className = "su-mine";
      const pos = document.createElement("td");
      pos.className = "cp-pos";
      pos.textContent = String(row.position);
      const weapon = document.createElement("td");
      weapon.className = "cp-weapon";
      weapon.append(caller.manage ? slotWeaponSelect(row) : weaponCell(row.weapon_id));
      const role = document.createElement("td");
      role.className = "su-role";
      role.textContent = [row.role, row.note].filter(Boolean).join(" · ");
      const player = playerCell(row.claimant, row.claimant && row.claimant.id === mineId);
      if (caller.manage && row.claimant) player.append(manageControls(board, row.claimant));
      if (marks.mark && row.claimant && row.claimant.attendance_id) player.append(markSelect(row.claimant.attendance_id, row.claimant.attendance));
      tr.append(pos, weapon, role, player);
      return tr;
    }));

    el.reservesWrap.hidden = !board.reserves.length;
    el.reserves.replaceChildren(...board.reserves.map(s => {
      const li = document.createElement("li");
      li.className = s.id === mineId ? "su-mine" : "";
      li.append(playerCell(s, s.id === mineId).firstChild, document.createTextNode(
        [s.item_power ? ` · ${s.item_power} IP` : "", s.can_swap ? " · can swap" : "", s.account ? "" : " · guest",
         s.weapons && s.weapons.length ? ` · ${s.weapons.map(k => weaponInfo(CATALOG, k).name).join(", ")}` : "",
         s.note ? ` · ${s.note}` : ""].join("")));
      if (caller.manage) li.append(manageControls(board, s));
      if (marks.mark && s.attendance_id) li.append(markSelect(s.attendance_id, s.attendance));
      return li;
    }));

    /* the record's rows with no claim behind them */
    const history = historyRows(sheet.attendance);
    el.historyWrap.hidden = !history.length;
    el.history.replaceChildren(...history.map(r => {
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.className = "gd-name";
      name.textContent = r.player_name;
      li.append(name, attendanceTag(r.status));
      const sub = document.createElement("span");
      sub.className = "gd-sub";
      sub.textContent = [r.position != null ? `slot ${r.position}` : "", r.weapon_id ? weaponInfo(CATALOG, r.weapon_id).name : "", r.account ? "" : "guest"].filter(Boolean).join(" · ");
      li.append(sub);
      if (marks.mark) li.append(markSelect(r.id, r.status));
      return li;
    }));

    renderCaller(board);

    /* the slot choice: the free slots and the player's own */
    const own = sheet.mine && sheet.mine.position != null ? sheet.mine.position : null;
    const options = [["", "Reserve (no slot)"]].concat(board.rows
      .filter(r => !r.claimant || r.position === own)
      .map(r => [String(r.position), `${r.position} · ${r.weapon_id ? weaponInfo(CATALOG, r.weapon_id).name : "any weapon"}${r.role ? " · " + r.role : ""}`]));
    const chosen = el.slot.value;
    el.slot.replaceChildren(...options.map(([value, label]) => {
      const o = document.createElement("option");
      o.value = value;
      o.textContent = label;
      return o;
    }));
    el.slot.value = options.some(([v]) => v === chosen) ? chosen : (own != null ? String(own) : "");

    el.open.disabled = !sheet.slots.some(s => s.weapon_id) && !ev.share_hash;
    el.link.textContent = signupLink(code, typeof location !== "undefined" ? location.href : "");
  }


  /* ---- the form ---- */

  function renderForm() {
    const ev = sheet.event;
    const open = ev.status === "open";
    const mine = sheet.mine;

    el.closed.textContent = SHEET_STATUS_MSG[ev.status] || "";
    el.closed.hidden = open;
    el.form.hidden = !open && !mine;

    el.nameWrap.hidden = !isGuest();
    el.who.textContent = isGuest()
      ? "You are signing up as a guest: this browser keeps your claim, so only it can change or cancel your sign-up. Log in to keep your history."
      : `Signing up as ${(account.profile && (account.profile.albion_name || account.profile.display_name)) || account.user.email}.`;

    for (const input of [el.name, el.slot, el.weaponAdd, el.ip, el.swap, el.note]) input.disabled = !open;
    el.submit.hidden = !open;
    el.submit.textContent = mine ? "Update sign-up" : "Sign up";
    el.cancel.hidden = !mine || ev.status === "completed";
    el.confirm.hidden = !marks.confirm;
    el.confirm.textContent = mine && mine.attendance === "confirmed" ? "Unconfirm" : "Confirm I'm coming";
    el.confirm.dataset.confirmed = mine && mine.attendance === "confirmed" ? "yes" : "no";
    renderWeapons(open);
  }

  function fillForm() {
    const mine = sheet.mine;
    el.name.value = mine ? mine.player_name : (el.name.value || "");
    el.slot.value = mine && mine.position != null ? String(mine.position) : "";
    el.ip.value = mine && mine.item_power != null ? String(mine.item_power) : "";
    el.swap.checked = !!(mine && mine.can_swap);
    el.note.value = mine ? (mine.note || "") : "";
    weapons = mine ? (mine.weapons || []).slice() : weapons;
  }

  function renderWeapons(open) {
    el.weapons.replaceChildren(...weapons.map(key => {
      const li = document.createElement("li");
      li.className = "gd-weapon" + (weaponInfo(CATALOG, key).known ? "" : " unknown");
      li.append(weaponCell(key));
      if (open) {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "pw-remove";
        b.dataset.suRemove = key;
        b.setAttribute("aria-label", `remove ${weaponInfo(CATALOG, key).name}`);
        b.textContent = "×";
        li.append(b);
      }
      return li;
    }));
    el.weaponAdd.disabled = !open || weapons.length >= SIGNUP_WEAPONS_MAX;
    el.weaponAdd.placeholder = weapons.length >= SIGNUP_WEAPONS_MAX ? `at most ${SIGNUP_WEAPONS_MAX}` : "add a weapon you bring";
  }

  el.weapons.addEventListener("click", e => {
    const b = e.target.closest("[data-su-remove]");
    if (!b || busy) return;
    weapons = weapons.filter(k => k !== b.dataset.suRemove);
    renderWeapons(true);
    announce(`${weaponInfo(CATALOG, b.dataset.suRemove).name} removed.`);
  });

  function showResults() {
    const hits = weaponSearch(el.weaponAdd.value, CATALOG, new Set(weapons));
    el.weaponResults.replaceChildren(...hits.map(hit => {
      const li = document.createElement("li");
      li.setAttribute("role", "option");
      li.dataset.suPick = hit.key;
      li.append(weaponCell(hit.key));
      return li;
    }));
    el.weaponResults.hidden = !hits.length;
    el.weaponAdd.setAttribute("aria-expanded", String(!!hits.length));
  }

  function pick(key) {
    if (!key || weapons.includes(key) || weapons.length >= SIGNUP_WEAPONS_MAX) return;
    weapons.push(key);
    el.weaponAdd.value = "";
    el.weaponResults.hidden = true;
    el.weaponAdd.setAttribute("aria-expanded", "false");
    el.weaponsErr.textContent = "";
    renderWeapons(true);
    announce(`${weaponInfo(CATALOG, key).name} added.`);
    el.weaponAdd.focus();
  }

  el.weaponAdd.addEventListener("input", showResults);
  el.weaponAdd.addEventListener("focus", showResults);
  el.weaponAdd.addEventListener("keydown", e => {
    if (e.key === "Enter") {
      e.preventDefault();
      const first = el.weaponResults.querySelector("[data-su-pick]");
      if (first) pick(first.dataset.suPick);
    } else if (e.key === "Escape") {
      el.weaponResults.hidden = true;
      el.weaponAdd.setAttribute("aria-expanded", "false");
    }
  });
  el.weaponResults.addEventListener("mousedown", e => {
    const li = e.target.closest("[data-su-pick]");
    if (li) { e.preventDefault(); pick(li.dataset.suPick); }
  });
  el.weaponAdd.addEventListener("blur", () => setTimeout(() => {
    el.weaponResults.hidden = true;
    el.weaponAdd.setAttribute("aria-expanded", "false");
  }, 120));

  el.form.addEventListener("submit", async e => {
    e.preventDefault();
    if (busy || !sheet || sheet.event.status !== "open") return;
    clearMessages();

    const board = sheetBoard(sheet.slots, sheet.signups);
    const allowed = new Set(board.free);
    if (sheet.mine && sheet.mine.position != null) allowed.add(sheet.mine.position);
    const typed = { playerName: el.name.value, position: el.slot.value, itemPower: el.ip.value, canSwap: el.swap.checked, weapons, note: el.note.value };
    const errors = validateSignup(typed, { guest: isGuest(), allowed });
    el.weaponsErr.textContent = errors.weapons || "";
    const first = acctFlagFields(FIELDS, errors);
    if (first) { first.focus(); return; }
    if (errors.weapons) { el.weaponAdd.focus(); return; }

    busy = true;
    acctBusy(el.submit, "Saving…");
    const token = isGuest() ? ensureToken() : readToken();

    try {
      const mine = await submitSignUp(code, token, typed);
      await reload(true);
      showNotice(mine.position != null ? `You hold slot ${mine.position}.` : "You are signed up as a reserve.");
      announce("Sign-up saved.");
    } catch (err) {
      showError(signupErrorMessage(err));
      if (signupErrorKind(err) === "taken" || signupErrorKind(err) === "noSlot") await reload(true);
    } finally {
      busy = false;
      acctIdle(el.submit);
    }
  });

  el.cancel.addEventListener("click", async () => {
    if (busy || !sheet || !sheet.mine) return;
    if (!window.confirm("Cancel your sign-up for this CTA?")) return;

    busy = true;
    acctBusy(el.cancel, "Cancelling…");

    try {
      const gone = await cancelSignUp(code, readToken());
      if (isGuest()) forgetToken();
      weapons = [];
      await reload(true);
      showNotice(gone ? "Your sign-up was cancelled." : "You had no sign-up on this CTA.");
    } catch (err) {
      showError(signupErrorMessage(err));
    } finally {
      busy = false;
      acctIdle(el.cancel);
    }
  });

  el.refresh.addEventListener("click", () => { if (!busy) reload(false); });

  el.open.addEventListener("click", () => {
    if (!sheet) return;
    const hash = templateHash(sheet.event, sheet.slots);
    dialog.close();
    location.hash = hash;
    announce(`${sheet.event.name} opened in the planner.`);
  });

  el.link.addEventListener("click", () => {
    const text = el.link.textContent;
    if (navigator.clipboard && text) {
      navigator.clipboard.writeText(text).then(() => showNotice("Link copied."), () => showNotice(text));
    }
  });


  /* ---- the caller's controls (phase 6) ---- */

  const WEAPON_GROUPS = weaponOptions(CATALOG);

  function slotWeaponSelect(row) {
    const select = document.createElement("select");
    select.className = "su-slot-weapon";
    select.dataset.suSlotWeapon = String(row.position);
    select.setAttribute("aria-label", `slot ${row.position}: weapon`);
    const any = document.createElement("option");
    any.value = "";
    any.textContent = "any weapon";
    select.append(any);
    for (const group of WEAPON_GROUPS) {
      const og = document.createElement("optgroup");
      og.label = group.name;
      for (const w of group.weapons) {
        const o = document.createElement("option");
        o.value = w.key;
        o.textContent = w.name;
        og.append(o);
      }
      select.append(og);
    }
    if (row.weapon_id && !CATALOG[row.weapon_id]) {
      const o = document.createElement("option");
      o.value = row.weapon_id;
      o.textContent = `${row.weapon_id} (unknown weapon)`;
      select.append(o);
    }
    select.value = row.weapon_id || "";
    return select;
  }

  function manageControls(board, s) {
    const wrap = document.createElement("span");
    wrap.className = "su-manage";
    const move = document.createElement("select");
    move.className = "su-move";
    move.dataset.suMove = s.id;
    move.setAttribute("aria-label", `move ${s.player_name}`);
    for (const t of moveTargets(board, s, CATALOG)) {
      const o = document.createElement("option");
      o.value = t.value;
      o.textContent = t.label;
      move.append(o);
    }
    move.value = s.position != null ? String(s.position) : "";
    if (s.position != null) {
      /* the held slot is not a target: the first option says where the player is */
      const here = document.createElement("option");
      here.value = String(s.position);
      here.textContent = `Slot ${s.position} (here)`;
      move.prepend(here);
      move.value = String(s.position);
    }
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "gd-btn danger";
    remove.dataset.suDrop = s.id;
    remove.dataset.suName = s.player_name;
    remove.setAttribute("aria-label", `remove ${s.player_name}`);
    remove.textContent = "×";
    wrap.append(move, remove);
    return wrap;
  }

  function renderCaller(board) {
    el.callerWrap.hidden = !caller.manage && !caller.moves.length && !marks.all;
    el.markAll.hidden = !marks.all;
    el.callerMoves.replaceChildren(...caller.moves.map(to => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "gd-btn";
      b.dataset.suStatus = to;
      b.textContent = EVENT_MOVE_LABELS[to] || to;
      return b;
    }));
    el.addForm.hidden = !caller.manage;
    const chosen = el.addSlot.value;
    el.addSlot.replaceChildren(...[["", "Reserve (no slot)"]].concat(board.rows.filter(r => !r.claimant)
      .map(r => [String(r.position), `${r.position} · ${r.weapon_id ? weaponInfo(CATALOG, r.weapon_id).name : "any weapon"}`]))
      .map(([value, label]) => {
        const o = document.createElement("option");
        o.value = value;
        o.textContent = label;
        return o;
      }));
    el.addSlot.value = [...el.addSlot.options].some(o => o.value === chosen) ? chosen : "";
  }

  async function act(button, label, work, done) {
    if (busy) return;
    busy = true;
    if (button) acctBusy(button, label);
    try {
      const result = await work();
      await reload(true);
      if (done) showNotice(done(result));
    } catch (err) {
      showError(signupErrorMessage(err));
      if (["taken", "noSlot", "refused"].includes(signupErrorKind(err))) await reload(true);
    } finally {
      busy = false;
      if (button) acctIdle(button);
    }
  }

  el.board.addEventListener("change", e => {
    const t = e.target;
    if (t.dataset.suMove !== undefined) {
      const id = t.dataset.suMove;
      const name = (sheet.signups.find(s => s.id === id) || {}).player_name || "the player";
      act(null, "", () => moveSignup(id, t.value), r => r.position != null ? `${name} now holds slot ${r.position}.` : `${name} is a reserve.`);
    } else if (t.dataset.suSlotWeapon !== undefined) {
      const position = Number(t.dataset.suSlotWeapon);
      act(null, "", () => setSlotWeapon(sheet.event.id, position, t.value),
          () => `Slot ${position}: ${t.value ? weaponInfo(CATALOG, t.value).name : "any weapon"}.`);
    }
  });
  el.reserves.addEventListener("change", e => {
    const t = e.target;
    if (t.dataset.suMove === undefined) return;
    const id = t.dataset.suMove;
    const name = (sheet.signups.find(s => s.id === id) || {}).player_name || "the player";
    act(null, "", () => moveSignup(id, t.value), r => r.position != null ? `${name} now holds slot ${r.position}.` : `${name} is a reserve.`);
  });
  for (const list of [el.board, el.reserves]) {
    list.addEventListener("click", e => {
      const b = e.target.closest("[data-su-drop]");
      if (!b || busy || !caller.manage) return;
      if (!window.confirm(`Remove ${b.dataset.suName} from the sheet?`)) return;
      act(b, "…", () => removeSignup(b.dataset.suDrop), () => `${b.dataset.suName} was removed.`);
    });
  }

  el.callerMoves.addEventListener("click", e => {
    const b = e.target.closest("[data-su-status]");
    if (!b || busy || !sheet) return;
    const to = b.dataset.suStatus;
    if (!caller.moves.includes(to)) return;
    if (to === "completed" && !window.confirm("Mark the CTA completed? The sheet is kept as it is and cannot change again.")) return;
    act(b, "Changing…", () => setEventStatus(sheet.event.id, to), r => `${sheet.event.name}: ${EVENT_STATUS_NAMES[r.status] || r.status}.`);
  });

  el.addForm.addEventListener("submit", e => {
    e.preventDefault();
    if (busy || !sheet || !caller.manage) return;
    const name = el.addName.value.trim();
    if (!name) { acctFlagFields({ playerName: el.addName }, { playerName: "Name the player." }); el.addName.focus(); return; }
    if (nameLength(name) > ACCOUNT_NAME_MAX) { acctFlagFields({ playerName: el.addName }, { playerName: `Use at most ${ACCOUNT_NAME_MAX} characters.` }); return; }
    const position = el.addSlot.value;
    act(el.add, "Adding…", () => addPlayer(sheet.event.id, { playerName: name, position, weapons: [] }), r => {
      el.addName.value = "";
      return r.position != null ? `${r.player_name} holds slot ${r.position}.` : `${r.player_name} is a reserve.`;
    });
  });

  /* ---- the record (phase 8) ---- */

  function attendanceTag(status) {
    const tag = document.createElement("span");
    tag.className = "su-att";
    tag.dataset.status = status;
    tag.textContent = ATTENDANCE_NAMES[status] || status;
    return tag;
  }

  function markSelect(attendanceId, status) {
    const select = document.createElement("select");
    select.className = "su-mark";
    select.dataset.suMark = attendanceId;
    select.setAttribute("aria-label", "attendance");
    const options = ATTENDANCE_MARKS.includes(status) || !status ? ATTENDANCE_MARKS : [status].concat(ATTENDANCE_MARKS);
    for (const value of options) {
      const o = document.createElement("option");
      o.value = value;
      o.textContent = ATTENDANCE_NAMES[value] || value;
      select.append(o);
    }
    select.value = status || "signed_up";
    return select;
  }

  for (const list of [el.board, el.reserves, el.history]) {
    list.addEventListener("change", e => {
      const t = e.target;
      if (t.dataset.suMark === undefined) return;
      const id = t.dataset.suMark;
      const status = t.value;
      act(null, "", () => markAttendance(id, status), r => `Marked ${ATTENDANCE_NAMES[r.status] || r.status}.`);
    });
  }

  el.markAll.addEventListener("click", () => {
    if (busy || !sheet || !marks.all) return;
    if (!window.confirm("Mark everyone still signed up or confirmed in a slot as attended? You can change single marks after.")) return;
    act(el.markAll, "Marking…", () => markAllAttended(sheet.event.id), n => `${n} marked attended.`);
  });

  el.confirm.addEventListener("click", () => {
    if (busy || !sheet || !sheet.mine || !marks.confirm) return;
    const yes = el.confirm.dataset.confirmed !== "yes";
    act(el.confirm, "…", () => confirmSignUp(code, readToken(), yes), r => r.status === "confirmed" ? "You are confirmed." : "Your confirmation is withdrawn.");
  });


  /* the caller's role in the CTA's guild, read once per guild */
  async function readRole() {
    if (!sheet || !sheet.guild || isGuest()) { myRole = null; roleGuild = null; return; }
    if (roleGuild === sheet.guild.id) return;
    try {
      const mine = await loadMyGuilds();
      myRole = (mine.find(g => g.guild.id === sheet.guild.id) || {}).role || null;
    } catch (err) {
      myRole = null;
    }
    roleGuild = sheet.guild.id;
  }


  /* ---- loading ---- */

  /* keepForm: the player's typing stays; live: a change someone else
     made, so the form is never refilled from the server, and a move of
     the player's own row is said out loud */
  async function reload(keepForm, live) {
    const seq = ++openSeq;
    if (!keepForm) clearMessages();
    const wasAt = sheet && sheet.mine ? sheet.mine.position : undefined;
    const had = !!(sheet && sheet.mine);

    let next;
    try {
      next = await loadSheet(code, readToken());
    } catch (err) {
      if (seq !== openSeq) return;
      showError(signupErrorMessage(err));
      if (signupErrorKind(err) === "noEvent") {
        el.title.textContent = "No CTA";
        el.form.hidden = true;
        el.board.replaceChildren();
        stopWatching();
      }
      return;
    }
    if (seq !== openSeq) return;

    sheet = next;
    await readRole();
    if (seq !== openSeq) return;
    renderBoard();
    if (!live && (!keepForm || sheet.mine)) fillForm();
    renderForm();
    if (!keepForm) acctFlagFields(FIELDS, {});

    if (live && had) {
      const nowAt = sheet.mine ? sheet.mine.position : undefined;
      if (!sheet.mine) {
        showNotice("The caller removed your sign-up.");
      } else if (nowAt !== wasAt) {
        el.slot.value = nowAt != null ? String(nowAt) : "";
        showNotice(nowAt != null ? `The caller moved you to slot ${nowAt}.` : "The caller moved you to the reserves.");
      }
    }
  }


  /* ---- the live channel ---- */

  function setLive(status) {
    el.liveState.textContent = LIVE_STATE_MSG[status] || "";
    el.liveState.dataset.live = status === "SUBSCRIBED" ? "yes" : "no";
  }

  function onSheetChanged() {
    clearTimeout(liveTimer);
    liveTimer = setTimeout(() => {
      liveTimer = null;
      if (busy) { onSheetChanged(); return; }
      reload(true, true);
    }, LIVE_SETTLE_MS);
  }

  function startWatching() {
    stopWatching();
    try {
      leave = watchSheet(code, onSheetChanged, setLive);
    } catch (err) {
      leave = null;
      setLive("CHANNEL_ERROR");
    }
  }

  function stopWatching() {
    clearTimeout(liveTimer);
    liveTimer = null;
    if (leave) {
      try { leave(); } catch (err) { /* the channel is gone either way */ }
      leave = null;
    }
    setLive("CLOSED");
  }

  async function openSheet(nextCode) {
    code = cleanJoinCode(nextCode);
    if (!JOIN_CODE_RE.test(code)) return;
    sheet = null;
    weapons = [];
    el.title.textContent = "Loading the sheet…";
    el.kicker.textContent = "CTA";
    el.when.textContent = "";
    el.status.textContent = "";
    el.notes.hidden = true;
    el.counts.textContent = "";
    el.board.replaceChildren();
    el.reservesWrap.hidden = true;
    el.historyWrap.hidden = true;
    el.form.hidden = true;
    el.closed.hidden = true;
    el.callerWrap.hidden = true;
    stopWatching();
    clearMessages();
    if (!dialog.open) dialog.showModal();

    await reload(false);
    if (sheet) startWatching();

    /* an account's profile weapons are the first declaration */
    if (sheet && !sheet.mine && !isGuest() && sheet.event.status === "open") {
      try {
        weapons = weaponsFromLists(weaponLists(await loadMyWeapons()));
        renderWeapons(true);
      } catch (err) { /* the list is optional */ }
    }
  }

  acctWireDialog(dialog, { canClose: () => !busy });
  $id("su-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", stopWatching);

  /* the CTAs dialog hands a code over */
  document.addEventListener("cta-sheet", e => {
    if (e.detail && e.detail.code) openSheet(e.detail.code);
  });


  /* ---- identity and the link ---- */

  window.Account.subscribe(state => {
    const was = account.user ? account.user.id : null;
    account = state;

    /* the link opens the sheet once the stored session has been read, so
       an account signs up as itself */
    if (state.ready && !booted) {
      booted = true;
      const fromLink = codeFromSearch(typeof location !== "undefined" ? location.search : "");
      if (fromLink) openSheet(fromLink);
      return;
    }

    if (dialog.open && code && (state.user ? state.user.id : null) !== was) {
      reload(false);
    }
  });
})();
