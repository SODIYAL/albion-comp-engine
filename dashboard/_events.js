"use strict";

/*
 * CTAs (platform phase 4): a guild's events. An event is a CTA a caller
 * runs: the name, when it starts and when the guild masses, notes, a
 * status (draft, open, locked, completed), the share code of its sign-up
 * link (phase 5), the comp it was made from and its own slots, COPIED
 * from that template when the event is created: editing an event never
 * touches the template, and deleting the template leaves the event
 * whole. Members read; callers, officers and admins write.
 *
 * build.py inlines this file as its own <script> after _comps.js. It
 * reads no planner state and never calls the engine: as a saved comp, an
 * event meets the planner through the address bar alone (its share hash
 * opens in the planner; the planner's current comp becomes its roster).
 * Content and style names, weapons and slots are read through the comps
 * module's constants and pure functions.
 *
 * Three parts, as in _profile.js:
 *   helpers - the only code that talks to window.DB (events, event_slots,
 *             save_event)
 *   pure    - the statuses and their moves, the times, the grouping of a
 *             guild's calendar, validation, error wording
 *             (tests/test_events.js)
 *   UI      - the CTAs dialog the account menu opens
 */


/* ------------------------------------------------------------ helpers */

/* a guild's events, newest start first, with who runs them and how many
   slots they hold */
async function loadGuildEvents(guildId) {
  const { data, error } = await window.DB
    .from("events")
    .select("id, guild_id, template_id, name, content, style, planned_size, starts_at, mass_at, status, "
            + "share_code, updated_at, "
            + "caller:profiles!events_created_by_fkey(albion_name, display_name), "
            + "slots:event_slots(count), signups:signups(count)")
    .eq("guild_id", guildId)
    .order("starts_at", { ascending: false });

  if (error) {
    throw error;
  }

  return data || [];
}


/* one event with its slots in position order */
async function loadEvent(eventId) {
  const { data, error } = await window.DB
    .from("events")
    .select("id, guild_id, template_id, name, content, style, planned_size, starts_at, mass_at, notes, status, "
            + "share_code, share_hash, updated_at, "
            + "slots:event_slots(position, weapon_id, role, note)")
    .eq("id", eventId)
    .maybeSingle();

  if (error) {
    throw error;
  }

  if (data && data.slots) {
    data.slots.sort((a, b) => a.position - b.position);
  }

  return data;
}


/* the event and its slots in one transaction (save_event); returns the
   saved event row */
async function saveEvent(event) {
  const { data, error } = await window.DB.rpc("save_event", {
    event: eventPayload(event)
  });

  if (error) {
    throw error;
  }

  return data;
}


/* one status step (the guard refuses any other move) */
async function setEventStatus(eventId, status) {
  const { data, error } = await window.DB
    .from("events")
    .update({ status })
    .eq("id", eventId)
    .select("id, status, updated_at");

  if (error) {
    throw error;
  }

  if (!data || !data.length) {
    throw guildRefusal();
  }

  return data[0];
}


async function deleteEvent(eventId) {
  const { data, error } = await window.DB
    .from("events")
    .delete()
    .eq("id", eventId)
    .select("id");

  if (error) {
    throw error;
  }

  if (!data || !data.length) {
    throw guildRefusal();
  }

  return data[0];
}


/* --------------------------------------------------------------- pure */

/* The database's statuses and the moves its guard allows
   (supabase/migrations events; tests/test_supabase_schema.py pins that
   they agree). Completed is final. */
const EVENT_STATUSES = ["draft", "open", "locked", "completed"];
const EVENT_STATUS_NAMES = { draft: "Draft", open: "Sign-up open", locked: "Locked", completed: "Completed" };
const EVENT_MOVES = { draft: ["open"], open: ["draft", "locked"], locked: ["open", "completed"], completed: [] };
const EVENT_MOVE_LABELS = { open: "Open sign-up", draft: "Back to draft", locked: "Lock the roster", completed: "Mark completed" };

/* the database's bounds: events per guild; the slots, notes, role and
   note bounds are the comp's (COMP_* in _comps.js) */
const EVENTS_MAX = 200;

/* an event whose start is this long gone lists with the past ones */
const EVENT_PAST_AFTER_MS = 12 * 60 * 60 * 1000;


/* an ISO time as a datetime-local field shows it (local time, to the
   minute); "" when there is none */
function toLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = n => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}


/* a datetime-local value (local time) as the ISO instant the database
   stores; "" for an empty field, null for a value that is no time */
function fromLocalInput(value) {
  const v = String(value || "").trim();
  if (!v) return "";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}


/* a start as the list shows it: the viewer's local time, and the UTC
   time the game runs on; `zoned` names the viewer's zone beside the
   local time (the sheet, where players of several zones read it) */
function eventTimeLabel(iso, zoned) {
  const d = new Date(iso || "");
  if (Number.isNaN(d.getTime())) return "";
  const pad = n => String(n).padStart(2, "0");
  const how = { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" };
  if (zoned) how.timeZoneName = "short";
  const local = d.toLocaleString(undefined, how);
  return `${local} (${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} UTC)`;
}


/* The zone a caller types a CTA's times in: the game's clock (UTC, the
   default: a call time is announced in UTC) or the caller's own. The
   database stores the instant either way. */
const EVENT_ZONES = ["utc", "local"];
const EVENT_ZONE_KEY = "cta-time-zone";


/* an ISO time as a datetime-local field shows it in the zone */
function toZoneInput(iso, zone) {
  if (zone !== "utc") return toLocalInput(iso);
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = n => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}


/* a datetime-local value typed in the zone as the ISO instant; "" for an
   empty field, null for a value that is no time */
function fromZoneInput(value, zone) {
  if (zone !== "utc") return fromLocalInput(value);
  const v = String(value || "").trim();
  if (!v) return "";
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(v)) return null;
  const d = new Date(`${v}Z`);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}


/* the other reading of a field's value, shown under it: a UTC entry as
   the caller's own time, a local entry as UTC; "" for no time */
function zoneEcho(value, zone) {
  const iso = fromZoneInput(value, zone);
  if (!iso) return "";
  const d = new Date(iso);
  const pad = n => String(n).padStart(2, "0");
  if (zone === "utc") {
    return "your time: " + d.toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit",
                                                         minute: "2-digit", timeZoneName: "short" });
  }
  const day = d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
  return `game time: ${day}, ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} UTC`;
}


/* how far off a start is, to the minute: "in 2d 3h", "in 3h 12m",
   "in 12m", "starting now", "started 25m ago"; "" for no time and once
   the start is half a day gone */
function eventCountdown(iso, now) {
  const start = new Date(iso || "").getTime();
  if (!Number.isFinite(start)) return "";
  const t = now instanceof Date ? now.getTime() : (now ? new Date(now).getTime() : Date.now());
  const mins = Math.round((start - t) / 60000);
  const span = m => {
    const d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), r = m % 60;
    if (d) return `${d}d ${h}h`;
    if (h) return `${h}h ${r}m`;
    return `${r}m`;
  };
  if (mins === 0) return "starting now";
  if (mins > 0) return `in ${span(mins)}`;
  if (-mins * 60000 > EVENT_PAST_AFTER_MS) return "";
  return `started ${span(-mins)} ago`;
}


/* A guild's calendar: what is ahead (soonest first) and what is past
   (latest first). Completed events and events whose start is more than
   EVENT_PAST_AFTER_MS gone are past. */
function eventGroups(events, now) {
  const t = now instanceof Date ? now.getTime() : (now ? new Date(now).getTime() : Date.now());
  const upcoming = [];
  const past = [];

  for (const e of events || []) {
    const start = new Date(e.starts_at || "").getTime();
    const gone = e.status === "completed" || (Number.isFinite(start) && start < t - EVENT_PAST_AFTER_MS);
    (gone ? past : upcoming).push(e);
  }

  const at = e => new Date(e.starts_at || "").getTime() || 0;
  upcoming.sort((a, b) => at(a) - at(b));
  past.sort((a, b) => at(b) - at(a));
  return { upcoming, past };
}


/* a new event made from a template: the copy the database also makes,
   shown before the caller saves */
function eventFromTemplate(template, guildId) {
  const slots = normalizeSlots(template.slots);
  return {
    id: null,
    guild_id: guildId,
    template_id: template.id || null,
    name: template.name || "",
    content: template.content || "",
    style: template.style || "",
    planned_size: template.planned_size || slots.length || 0,
    starts_at: "",
    mass_at: "",
    notes: "",
    status: "draft",
    share_hash: template.share_hash || "",
    slots
  };
}


/* a new event from the planner's current comp (the share hash) */
function eventFromHash(hash, guildId, contents, styles) {
  const parsed = parseShareHash(hash);
  if (!parsed || !parsed.weapons.length) return null;
  const has = (map, key) => Object.prototype.hasOwnProperty.call(map || {}, key);
  return {
    id: null,
    guild_id: guildId,
    template_id: null,
    name: "",
    content: has(contents, parsed.content) ? parsed.content : "",
    style: has(styles, parsed.style) ? parsed.style : "",
    planned_size: parsed.size || parsed.weapons.length,
    starts_at: "",
    mass_at: "",
    notes: "",
    status: "draft",
    share_hash: parsed.hash,
    slots: slotsFromWeapons(parsed.weapons)
  };
}


/* the comp's rules (validateTemplate), then the times: a start is
   required, the mass time optional and never after the start */
function validateEvent({ name, content, style, plannedSize, startsAt, massAt }, contents, styles) {
  const errors = validateTemplate({ name, content, style, plannedSize }, contents, styles);
  if (errors.name === "Name the comp.") errors.name = "Name the CTA.";

  const start = startsAt ? new Date(startsAt).getTime() : NaN;
  if (!startsAt) {
    errors.startsAt = "Set when the CTA starts.";
  } else if (!Number.isFinite(start)) {
    errors.startsAt = "Enter a valid date and time.";
  }

  if (massAt) {
    const mass = new Date(massAt).getTime();
    if (!Number.isFinite(mass)) {
      errors.massAt = "Enter a valid date and time.";
    } else if (Number.isFinite(start) && mass > start) {
      errors.massAt = "The mass time must come before the start.";
    }
  }

  return errors;
}


/* the mass time offered once a start is typed: MASS_LEAD_MINUTES before
   it, as an ISO instant; "" for no start or one that is no time */
const MASS_LEAD_MINUTES = 30;
function massDefault(startsAt, minutes) {
  const start = new Date(startsAt || "").getTime();
  if (!Number.isFinite(start)) return "";
  const lead = Number.isFinite(minutes) ? minutes : MASS_LEAD_MINUTES;
  return new Date(start - lead * 60000).toISOString();
}


/* the save_event payload; a completed event's slots are frozen, so they
   are not sent */
function eventPayload(event) {
  const out = {
    id: event.id || null,
    guild_id: event.guild_id,
    template_id: event.template_id || null,
    name: String(event.name || "").trim(),
    content: event.content,
    style: event.style || "",
    planned_size: Number(event.planned_size),
    starts_at: event.starts_at || "",
    mass_at: event.mass_at || "",
    notes: String(event.notes || "").trim(),
    status: event.status || "draft",
    share_hash: event.share_hash || ""
  };
  if (event.status !== "completed") out.slots = normalizeSlots(event.slots);
  return out;
}


/* what the caller's role may do with an event: the policies' writer
   roles, the guard's moves, and no slot edits once completed */
function eventPowers(myRole, event) {
  const write = compPowers(myRole).write;
  const status = event && event.status;
  return {
    write,
    moves: write && status ? (EVENT_MOVES[status] || []) : [],
    editSlots: write && status !== "completed"
  };
}


const EVENT_MSG = {
  network: PROFILE_MSG.network,
  signedOut: "Log in to use CTAs.",
  session: PROFILE_MSG.session,
  missing: "CTAs are not available yet: the account database has not been updated for this page. Try again later.",
  tooManyEvents: `A guild keeps at most ${EVENTS_MAX} CTAs.`,
  tooManySlots: `A CTA holds at most ${COMP_SLOTS_MAX} slots.`,
  duplicate: "A slot position is listed twice. Reload and try again.",
  move: "The CTA cannot move to that status from where it is. Reload to see its current status.",
  frozen: "A completed CTA keeps its slots.",
  templateGone: "The comp was not found: it may have been deleted. Choose another.",
  collision: "The generated share code collided with another. Save again.",
  refused: "The server refused the change: your role in this guild does not edit CTAs, or the CTA has changed. Reload and try again.",
  invalid: "The server refused a value. Check the name, content, size, times and notes, then try again.",
  unknown: PROFILE_MSG.unknown
};


function eventErrorKind(err) {
  const code = String((err && err.code) || "");
  const message = String((err && err.message) || "");

  if (authErrorKind(err) === "network") return "network";
  if (code === "not_signed_in" || (code === "42501" && /sign in/i.test(message))) return "signedOut";
  if (/^PGRST30\d$/.test(code) || /jwt expired/i.test(message)) return "session";
  if (code === "PGRST202" || code === "PGRST205" || code === "42883" || code === "42P01") return "missing";
  if (code === "23514" && /at most \d+ events/i.test(message)) return "tooManyEvents";
  if (code === "23514" && /at most \d+ slots/i.test(message)) return "tooManySlots";
  if (code === "23514" && /moves from/i.test(message)) return "move";
  if (code === "23514" && /completed CTA keeps/i.test(message)) return "frozen";
  if (code === "P0002") return "templateGone";
  if (code === "23505") return "collision";
  if (code === "21000") return "duplicate";
  if (code === "42501" || code === "refused") return "refused";
  if (code === "23514" || code === "22023" || code === "23502" || code === "22001" || code === "22P02" || code === "22003" || code === "22007" || code === "22008") return "invalid";

  return "unknown";
}


function eventErrorMessage(err) {
  const kind = eventErrorKind(err);
  const message = String((err && err.message) || "").trim();

  if (kind === "unknown" && message) {
    return `Something went wrong: ${message}`;
  }

  return EVENT_MSG[kind];
}


/* ----------------------------------------------------------------- UI */

(function eventsUI() {
  if (typeof document === "undefined") {
    return;
  }

  const $id = id => document.getElementById(id);
  const dialog = $id("event-dialog");

  if (!dialog || typeof dialog.showModal !== "function" || !window.Account) {
    return;
  }

  const CATALOG = typeof ACCOUNT_CATALOG !== "undefined" ? ACCOUNT_CATALOG : {};
  const CONTENTS = typeof ACCOUNT_CONTENTS !== "undefined" ? ACCOUNT_CONTENTS : {};
  const STYLES = typeof ACCOUNT_STYLES !== "undefined" ? ACCOUNT_STYLES : {};

  const el = {
    error: $id("ev-error"),
    notice: $id("ev-notice"),
    live: $id("ev-live"),
    guild: $id("ev-guild"),
    list: $id("ev-list"),
    listNote: $id("ev-list-note"),
    create: $id("ev-new"),
    empty: $id("ev-empty"),
    view: $id("ev-view"),
    form: $id("ev-form"),
    sourceWrap: $id("ev-source-wrap"),
    sourceLabel: $id("ev-source-label"),
    source: $id("ev-source"),
    name: $id("ev-name"),
    content: $id("ev-content"),
    style: $id("ev-style"),
    size: $id("ev-size"),
    start: $id("ev-start"),
    mass: $id("ev-mass"),
    zone: $id("ev-zone"),
    startEcho: $id("ev-start-echo"),
    massEcho: $id("ev-mass-echo"),
    notes: $id("ev-notes"),
    status: $id("ev-status"),
    moves: $id("ev-moves"),
    share: $id("ev-share"),
    sheet: $id("ev-sheet"),
    link: $id("ev-link"),
    meta: $id("ev-meta"),
    summary: $id("ev-summary"),
    slots: $id("ev-slots"),
    slotsNote: $id("ev-slots-note"),
    open: $id("ev-open"),
    save: $id("ev-save"),
    remove: $id("ev-delete"),
    dirty: $id("ev-dirty")
  };

  const FIELDS = { name: el.name, content: el.content, style: el.style, plannedSize: el.size, startsAt: el.start, massAt: el.mass };

  let account = window.Account.current();
  let zone = storedZone();    /* the zone the time fields are typed in */
  let guilds = [];            /* [{guild, role}] the account belongs to */
  let events = [];            /* the selected guild's list */
  let listState = "ready";    /* the list: "loading" until the service answers, "failed" when it did not */
  let shownGuild = null;      /* the guild whose list is shown */
  let templates = [];         /* the selected guild's comps, for a new event */
  let current = null;         /* the open event: {id, guild_id, ..., slots} or a new one */
  let slots = [];             /* the open event's slots as edited */
  let powers = eventPowers(null, null);
  let massFollows = true;     /* the mass field follows the start until the caller types one of their own */
  let busy = false;
  let openSeq = 0;
  /* bumped by every opening of the dialog: an action still waiting on the
     service from before neither changes the reopened dialog nor ends its
     busy state */
  let session = 0;

  const showError = message => acctMessage(el.error, el.notice, "error", message);
  const showNotice = message => acctMessage(el.error, el.notice, "notice", message);
  const clearMessages = () => acctMessage(el.error, el.notice, null, "");
  const announce = text => { el.live.textContent = text; };
  const guildId = () => el.guild.value || null;
  const myRole = () => (guilds.find(g => g.guild.id === guildId()) || {}).role || null;

  const fill = (select, map, first) => {
    select.replaceChildren();
    if (first) {
      const o = document.createElement("option");
      o.value = "";
      o.textContent = first;
      select.append(o);
    }
    for (const [key, name] of Object.entries(map)) {
      const o = document.createElement("option");
      o.value = key;
      o.textContent = name;
      select.append(o);
    }
  };
  fill(el.content, CONTENTS, "Choose the content");
  fill(el.style, STYLES, "Balanced (no style)");


  /* ---- the list ---- */

  function renderGuilds() {
    el.guild.replaceChildren(...guilds.map(({ guild, role }) => {
      const o = document.createElement("option");
      o.value = guild.id;
      o.textContent = `${guild.name} (${GUILD_ROLE_NAMES[role] || role})`;
      return o;
    }));
    el.guild.disabled = !guilds.length;
  }

  function eventItem(e) {
    const li = document.createElement("li");
    const b = document.createElement("button");
    b.type = "button";
    b.className = "gd-item";
    b.dataset.event = e.id;
    b.setAttribute("aria-pressed", String(!!current && current.id === e.id));
    const name = document.createElement("span");
    name.className = "gd-item-name";
    name.textContent = e.name;
    const when = document.createElement("span");
    when.className = "ev-when";
    when.textContent = eventTimeLabel(e.starts_at);
    const sub = document.createElement("span");
    sub.className = "gd-item-sub";
    const count = Array.isArray(e.slots) && e.slots[0] ? e.slots[0].count : 0;
    const signed = Array.isArray(e.signups) && e.signups[0] ? e.signups[0].count : 0;
    sub.textContent = `${EVENT_STATUS_NAMES[e.status] || e.status} · ${CONTENTS[e.content] || e.content} · ${signed}/${count} slot${count === 1 ? "" : "s"}`;
    b.append(name, when, sub);
    li.append(b);
    return li;
  }

  function renderList() {
    powers = eventPowers(myRole(), current);
    el.create.hidden = !powers.write || !guildId();

    /* an unanswered list says so: "No CTAs yet" is the service's answer,
       never the wait for it */
    if (listState !== "ready") {
      const li = document.createElement("li");
      li.className = "gd-none";
      li.textContent = listState === "loading" ? "Loading CTAs…"
                                               : "The CTAs did not load. Close this dialog and open it again to retry.";
      el.list.replaceChildren(li);
      el.listNote.hidden = true;
      return;
    }

    if (!guildId()) {
      const li = document.createElement("li");
      li.className = "gd-none";
      li.textContent = "Join or create a guild to run CTAs.";
      el.list.replaceChildren(li);
      return;
    }

    if (!events.length) {
      const li = document.createElement("li");
      li.className = "gd-none";
      li.textContent = powers.write ? "No CTAs yet. Make one from a saved comp or the planner."
                                    : "No CTAs yet. Callers, officers and admins make them.";
      el.list.replaceChildren(li);
    } else {
      const groups = eventGroups(events);
      const items = [];
      for (const [label, list] of [["Ahead", groups.upcoming], ["Past", groups.past]]) {
        if (!list.length) continue;
        const h = document.createElement("li");
        h.className = "ev-group";
        h.textContent = label;
        items.push(h, ...list.map(eventItem));
      }
      el.list.replaceChildren(...items);
    }

    const full = events.length >= EVENTS_MAX;
    el.listNote.textContent = full ? `A guild keeps at most ${EVENTS_MAX} CTAs.` : "";
    el.listNote.hidden = !full;
    if (full) el.create.hidden = true;
  }

  /* while an action waits, the guild stays the one whose list is shown */
  el.guild.addEventListener("change", () => {
    if (busy) { el.guild.value = shownGuild || ""; return; }
    reloadList(null);
  });

  el.list.addEventListener("click", e => {
    const b = e.target.closest("[data-event]");
    if (!b || busy) return;
    openEvent(b.dataset.event);
  });


  /* ---- the open event ---- */

  function roleTag(role) {
    const tag = document.createElement("span");
    tag.className = `pw-role ${role}`;
    tag.textContent = ROLE_NAMES[role] || role;
    return tag;
  }

  function slotRow(slot) {
    const tr = document.createElement("tr");
    tr.dataset.position = String(slot.position);

    const pos = document.createElement("td");
    pos.className = "cp-pos";
    pos.textContent = String(slot.position);

    const weapon = document.createElement("td");
    weapon.className = "cp-weapon";
    if (slot.weapon_id) {
      const info = weaponInfo(CATALOG, slot.weapon_id);
      const src = (typeof ICONS !== "undefined" && ICONS[slot.weapon_id])
        || (info.item ? `https://render.albiononline.com/v1/item/${encodeURIComponent(info.item)}.png?size=64` : "");
      if (src) {
        const img = document.createElement("img");
        img.className = "pw-art";
        img.src = src;
        img.alt = "";
        img.width = 22;
        img.height = 22;
        img.loading = "lazy";
        weapon.append(img);
      }
      const name = document.createElement("span");
      name.className = "gd-name";
      name.textContent = info.known ? info.name : `${slot.weapon_id} (unknown weapon)`;
      weapon.append(name);
      if (info.role) weapon.append(roleTag(info.role));
    } else {
      const open = document.createElement("span");
      open.className = "cp-open";
      open.textContent = "open slot";
      weapon.append(open);
    }

    const text = (key, value, max, label) => {
      const td = document.createElement("td");
      const input = document.createElement("input");
      input.className = "text-input cp-in";
      input.type = "text";
      input.maxLength = max;
      input.placeholder = label;
      input.value = value || "";
      input.dataset[key] = String(slot.position);
      input.setAttribute("aria-label", `slot ${slot.position}: ${label}`);
      input.readOnly = !powers.editSlots;
      td.append(input);
      return td;
    };

    const act = document.createElement("td");
    act.className = "gd-act";
    if (powers.editSlots) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "gd-btn";
      b.dataset.evRemove = String(slot.position);
      b.setAttribute("aria-label", `remove slot ${slot.position}`);
      b.textContent = "×";
      act.append(b);
    }

    tr.append(pos, weapon, text("evRole", slot.role, COMP_ROLE_MAX, "role"), text("evNote", slot.note, COMP_NOTE_MAX, "note"), act);
    return tr;
  }

  function renderEvent() {
    powers = eventPowers(myRole(), current);
    el.view.hidden = !current;
    el.empty.hidden = !!current;
    if (!current) { handPlan(); return; }

    /* a new CTA takes its first roster from the picker; a saved one that
       may still change its slots replaces them from it */
    el.sourceWrap.hidden = !!current.id && !powers.editSlots;
    el.sourceLabel.textContent = current.id ? "Replace the roster from" : "Roster from";
    const source = el.source.value;
    renderSources(!!current.id);
    el.source.value = !current.id && Array.from(el.source.options).some(o => o.value === source) ? source : "";
    el.name.value = current.name || "";
    el.content.value = current.content || "";
    el.style.value = current.style || "";
    el.size.value = current.planned_size || "";
    el.zone.value = zone;
    el.start.value = toZoneInput(current.starts_at, zone);
    el.mass.value = toZoneInput(current.mass_at, zone);
    el.mass.max = el.start.value;
    massFollows = !el.mass.value || el.mass.value === toZoneInput(massDefault(current.starts_at), zone);
    paintEchoes();
    el.notes.value = current.notes || "";
    for (const input of [el.name, el.content, el.style, el.size, el.start, el.mass, el.notes]) {
      input.disabled = !powers.write;
    }

    el.status.textContent = EVENT_STATUS_NAMES[current.status] || current.status || "";
    el.status.dataset.status = current.status || "";
    el.share.textContent = current.share_code || "";
    el.share.parentElement.hidden = !current.share_code;
    el.sheet.hidden = !current.share_code;
    el.link.hidden = !current.share_code;
    el.moves.replaceChildren(...(current.id ? powers.moves : []).map(to => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "gd-btn";
      b.dataset.evMove = to;
      b.textContent = EVENT_MOVE_LABELS[to] || to;
      return b;
    }));

    el.meta.textContent = current.id
      ? `Saved ${current.updated_at ? new Date(current.updated_at).toLocaleString() : ""}`
        + (current.template_id ? " · copied from a saved comp" : "")
      : "Not saved yet.";

    el.save.hidden = !powers.write;
    el.remove.hidden = !powers.write || !current.id;
    renderSlots();
  }

  /* the roster part alone: the summary, the table, the note under an
     empty one, and the planner button; a slot change repaints this and
     leaves the typed fields as they are */
  function renderSlots() {
    const s = templateSummary(slots, CATALOG);
    el.summary.replaceChildren(...ROLE_ORDER.map(role => {
      const cell = document.createElement("span");
      cell.className = `gd-cov ${role}`;
      const n = document.createElement("b");
      n.textContent = String(s[role]);
      cell.append(n, ` ${ROLE_NAMES[role]}`);
      return cell;
    }), (() => {
      const cell = document.createElement("span");
      cell.className = "gd-cov";
      const n = document.createElement("b");
      n.textContent = String(s.total);
      cell.append(n, ` slot${s.total === 1 ? "" : "s"}`
        + (s.open ? `, ${s.open} open` : "") + (s.unknown ? `, ${s.unknown} unknown` : ""));
      return cell;
    })());

    el.slots.replaceChildren(...slots.map(slotRow));
    el.slotsNote.textContent = powers.editSlots
      ? "No slots yet: fill the roster from a saved comp or the planner's comp above."
      : "No slots: the roster is empty.";
    el.slotsNote.hidden = slots.length > 0;
    const openable = slots.some(s => s.weapon_id) || !!current.share_hash;
    el.open.disabled = !openable;
    el.open.title = openable ? "Closes this dialog and loads the roster into the planner" : "Nothing to open: the roster is empty";
    markDirty();
    handPlan();
  }

  /* The open CTA as designed, handed to the roster module's engine read
     as a DOM event (no call between modules): its slots' weapons and roles
     and its content, style and saved link, as the form holds them; an
     empty one when no CTA is open. Who signed up stays on the sheet. */
  function handPlan() {
    document.dispatchEvent(new CustomEvent("plan-read", { detail: current ? {
      surface: "cta",
      event: { content: el.content.value || current.content || "", style: el.style.value || current.style || "",
               share_hash: current.share_hash || "" },
      slots: slots.map(s => ({ position: s.position, weapon_id: s.weapon_id || null, role: s.role || null }))
    } : { surface: "cta", event: null } }));
  }

  /* the read follows a content or style the form changes */
  el.content.addEventListener("change", handPlan);
  el.style.addEventListener("change", handPlan);

  function typedEvent() {
    return Object.assign({}, current, {
      name: el.name.value.trim(),
      content: el.content.value,
      style: el.style.value,
      planned_size: Number(el.size.value),
      starts_at: fromZoneInput(el.start.value, zone),
      mass_at: fromZoneInput(el.mass.value, zone),
      notes: el.notes.value.trim(),
      slots
    });
  }

  function dirty() {
    if (!current) return false;
    if (!current.id) return true;
    const a = eventPayload(typedEvent());
    const b = eventPayload(Object.assign({}, current, { slots: current.slots,
      starts_at: fromZoneInput(toZoneInput(current.starts_at, zone), zone),
      mass_at: fromZoneInput(toZoneInput(current.mass_at, zone), zone) }));
    return JSON.stringify(a) !== JSON.stringify(b);
  }

  function markDirty() {
    el.dirty.hidden = !dirty();
  }

  /* ---- the zone the times are typed in ---- */

  function storedZone() {
    try {
      const z = window.localStorage.getItem(EVENT_ZONE_KEY);
      return EVENT_ZONES.includes(z) ? z : "utc";
    } catch (err) {
      return "utc";
    }
  }

  /* under each time field, its other reading: a UTC entry in the
     caller's own time, a local entry in UTC */
  function paintEchoes() {
    el.startEcho.textContent = zoneEcho(el.start.value, zone);
    el.massEcho.textContent = zoneEcho(el.mass.value, zone);
  }

  /* another zone shows the same instants: the fields are rewritten, the
     CTA is unchanged */
  el.zone.addEventListener("change", () => {
    const next = EVENT_ZONES.includes(el.zone.value) ? el.zone.value : "utc";
    const start = fromZoneInput(el.start.value, zone);
    const mass = fromZoneInput(el.mass.value, zone);
    zone = next;
    try { window.localStorage.setItem(EVENT_ZONE_KEY, zone); } catch (err) { /* the choice lasts the visit */ }
    el.start.value = toZoneInput(start || "", zone);
    el.mass.value = toZoneInput(mass || "", zone);
    el.mass.max = el.start.value;
    paintEchoes();
    markDirty();
  });

  /* the mass field is bounded by the start and follows it, MASS_LEAD_MINUTES
     before, until the caller types a mass time of their own; a mass time
     the start has moved before is pulled back to the lead */
  function followStart() {
    el.mass.max = el.start.value;
    const start = fromZoneInput(el.start.value, zone);
    if (!start) {
      if (massFollows) el.mass.value = "";
      return;
    }
    const mass = fromZoneInput(el.mass.value, zone);
    if (massFollows || (mass && new Date(mass).getTime() > new Date(start).getTime())) {
      el.mass.value = toZoneInput(massDefault(start), zone);
      massFollows = true;
    }
  }

  /* a typed mass time past the start is not kept: it goes back to the lead */
  el.mass.addEventListener("change", () => {
    const start = fromZoneInput(el.start.value, zone);
    const mass = fromZoneInput(el.mass.value, zone);
    if (!start || !mass || new Date(mass).getTime() <= new Date(start).getTime()) return;
    el.mass.value = toZoneInput(massDefault(start), zone);
    massFollows = true;
    paintEchoes();
    markDirty();
    showNotice(`The mass time cannot follow the start: set to ${MASS_LEAD_MINUTES} minutes before it.`);
    announce(`Mass time set to ${MASS_LEAD_MINUTES} minutes before the start.`);
  });

  el.form.addEventListener("input", e => {
    const t = e.target;
    if (t === el.mass) massFollows = false;
    if (t === el.start) followStart();
    if (t === el.start || t === el.mass) paintEchoes();
    if (t.dataset.evRole !== undefined || t.dataset.evNote !== undefined) {
      const position = Number(t.dataset.evRole || t.dataset.evNote);
      const slot = slots.find(s => s.position === position);
      if (slot) {
        if (t.dataset.evRole !== undefined) slot.role = t.value.trim() || null;
        else slot.note = t.value.trim() || null;
      }
    }
    markDirty();
  });

  el.slots.addEventListener("click", e => {
    const b = e.target.closest("[data-ev-remove]");
    if (!b || busy || !powers.editSlots) return;
    const position = Number(b.dataset.evRemove);
    slots = slots.filter(s => s.position !== position).map((s, i) => Object.assign(s, { position: i + 1 }));
    renderSlots();
    announce(`Slot ${position} removed.`);
  });

  async function openEvent(id) {
    const seq = ++openSeq;
    clearMessages();
    acctFlagFields(FIELDS, {});
    el.slotsNote.textContent = "Loading the CTA…";
    el.slotsNote.hidden = false;

    try {
      const e = await loadEvent(id);
      if (seq !== openSeq) return;
      if (!e) { showError(EVENT_MSG.refused); return; }
      e.slots = normalizeSlots(e.slots);
      current = e;
      slots = normalizeSlots(e.slots);
    } catch (err) {
      if (seq !== openSeq) return;
      showError(eventErrorMessage(err));
      return;
    }

    renderList();
    renderEvent();
  }

  /* ---- the roster's sources: a saved comp, the planner, or none ----
     a new event takes its first roster from one; a saved event that may
     still change its slots replaces them from one */

  function renderSources(saved) {
    const options = [["", saved ? "Keep these slots" : "No roster yet"], ["planner", "The planner's current comp"]]
      .concat(templates.map(t => [t.id, `Comp: ${t.name}`]));
    el.source.replaceChildren(...options.map(([value, label]) => {
      const o = document.createElement("option");
      o.value = value;
      o.textContent = label;
      return o;
    }));
  }

  function blankEvent() {
    return {
      id: null, guild_id: guildId(), template_id: null, name: "", content: "", style: "",
      planned_size: 20, starts_at: "", mass_at: "", notes: "", status: "draft", share_hash: "", slots: []
    };
  }

  function startNew() {
    current = blankEvent();
    slots = [];
    clearMessages();
    acctFlagFields(FIELDS, {});
    el.source.value = "";
    renderList();
    renderEvent();
    el.name.focus();
  }

  el.create.addEventListener("click", () => { if (!busy) startNew(); });

  /* the comp or the planner's comp the picker names, as a new event, with
     the error shown and null when there is none */
  async function sourceEvent(value) {
    if (value === "planner") {
      const next = eventFromHash(typeof location !== "undefined" ? location.hash : "", guildId(), CONTENTS, STYLES);
      if (!next) showError("The planner holds no comp: add weapons in the planner first.");
      return next;
    }
    const seq = ++openSeq;
    const mine = session;
    busy = true;
    try {
      const t = await loadTemplate(value);
      if (seq !== openSeq) return null;
      if (!t) { showError(EVENT_MSG.templateGone); return null; }
      return eventFromTemplate(t, guildId());
    } catch (err) {
      if (seq === openSeq) showError(eventErrorMessage(err));
      return null;
    } finally {
      if (mine === session) busy = false;
    }
  }

  /* a saved event's slots replaced from the picker: the slots, the share
     hash, and the source's content, style and size go into the form; Save
     keeps them; role labels and notes on the old slots are cleared */
  async function replaceRoster(value) {
    el.source.value = "";
    if (!value || !powers.editSlots) return;
    const next = await sourceEvent(value);
    if (!next) return;
    const from = value === "planner" ? "the planner's current comp" : `the comp ${next.name}`;
    if (slots.length && !window.confirm(`Replace this CTA's slots with ${from}? Role labels and notes on the slots are cleared.`)) return;
    slots = next.slots;
    current.share_hash = next.share_hash;
    current.template_id = next.template_id;
    if (next.content) el.content.value = next.content;
    if (next.planned_size) el.size.value = next.planned_size;
    el.style.value = next.style || "";
    renderSlots();
    showNotice(`Slots replaced from ${from}. Save to keep them.`);
    announce(`Slots replaced from ${from}.`);
  }

  el.source.addEventListener("change", async () => {
    if (busy || !current) return;
    if (current.id) { await replaceRoster(el.source.value); return; }
    const value = el.source.value;
    const keep = { name: el.name.value, starts_at: fromZoneInput(el.start.value, zone) || "",
                   mass_at: fromZoneInput(el.mass.value, zone) || "", notes: el.notes.value };
    clearMessages();

    if (!value) {
      current = Object.assign(blankEvent(), keep);
      slots = [];
    } else {
      const next = await sourceEvent(value);
      if (!next) { el.source.value = ""; return; }
      current = Object.assign(next, keep, keep.name ? {} : { name: next.name });
      slots = next.slots;
    }

    renderEvent();
    el.source.value = value;
  });

  el.open.addEventListener("click", () => {
    if (!current) return;
    const hash = templateHash(typedEvent(), slots);
    dialog.close();
    location.hash = hash;
    announce(`${current.name || "The CTA"} opened in the planner.`);
  });

  /* the sheet is its own page: the CTA's link, the share code as its one
     parameter (the sign-up module's link helper; no call between modules
     past the address) */
  el.sheet.addEventListener("click", () => {
    if (!current || !current.share_code || typeof signupLink !== "function") return;
    location.assign(signupLink(current.share_code, location.href));
  });

  el.link.addEventListener("click", () => {
    if (!current || !current.share_code || typeof signupLink !== "function") return;
    const link = signupLink(current.share_code, location.href);
    if (navigator.clipboard) {
      navigator.clipboard.writeText(link).then(() => showNotice("Sign-up link copied."), () => showNotice(link));
    } else {
      showNotice(link);
    }
  });

  /* ---- status moves ---- */

  el.moves.addEventListener("click", async e => {
    const b = e.target.closest("[data-ev-move]");
    if (!b || busy || !current || !current.id) return;
    const to = b.dataset.evMove;
    if (!powers.moves.includes(to)) return;
    if (dirty() && !window.confirm("Unsaved changes are kept in the form. Change the status now?")) return;
    if (to === "completed" && !window.confirm("Mark the CTA completed? Its slots are kept as they are and cannot change again.")) return;

    busy = true;
    const mine = session;
    acctBusy(b, "Changing…");

    try {
      const row = await setEventStatus(current.id, to);
      if (mine !== session) return;
      current.status = row.status;
      current.updated_at = row.updated_at;
      const listed = await reloadList(current.id, true);
      if (mine !== session) return;
      renderEvent();
      if (listed) {
        showNotice(`${current.name}: ${EVENT_STATUS_NAMES[to] || to}.`);
        announce(`Status: ${EVENT_STATUS_NAMES[to] || to}.`);
      }
    } catch (err) {
      if (mine === session) showError(eventErrorMessage(err));
    } finally {
      acctIdle(b);
      if (mine === session) busy = false;
    }
  });

  el.form.addEventListener("submit", async e => {
    e.preventDefault();
    if (busy || !current || !powers.write) return;
    clearMessages();

    const typed = typedEvent();
    const first = acctFlagFields(FIELDS, validateEvent({
      name: typed.name, content: typed.content, style: typed.style, plannedSize: typed.planned_size,
      startsAt: typed.starts_at === null ? "invalid" : typed.starts_at,
      massAt: typed.mass_at === null ? "invalid" : typed.mass_at
    }, CONTENTS, STYLES));
    if (first) { first.focus(); return; }

    if (current.id && !dirty()) {
      showNotice("Nothing to save: the CTA is up to date.");
      return;
    }

    busy = true;
    const mine = session;
    acctBusy(el.save, "Saving…");

    try {
      const row = await saveEvent(typed);
      if (mine !== session) return;
      row.slots = normalizeSlots(slots);
      current = row;
      slots = normalizeSlots(row.slots);
      const listed = await reloadList(row.id, true);
      if (mine !== session) return;
      renderEvent();
      if (listed) {
        showNotice("CTA saved.");
        announce("CTA saved.");
      }
    } catch (err) {
      if (mine === session) showError(eventErrorMessage(err));
    } finally {
      if (mine === session) {
        busy = false;
        acctIdle(el.save);
        markDirty();
      }
    }
  });

  el.remove.addEventListener("click", async () => {
    if (busy || !current || !current.id) return;
    if (!window.confirm(`Delete ${current.name}? This cannot be undone.`)) return;

    busy = true;
    const mine = session;
    acctBusy(el.remove, "Deleting…");
    const name = current.name;

    try {
      await deleteEvent(current.id);
      if (mine !== session) return;
      current = null;
      slots = [];
      const listed = await reloadList(null, true);
      if (mine !== session) return;
      renderEvent();
      if (listed) showNotice(`${name} was deleted.`);
    } catch (err) {
      if (mine === session) showError(eventErrorMessage(err));
    } finally {
      if (mine === session) {
        busy = false;
        acctIdle(el.remove);
      }
    }
  });


  /* ---- loading ---- */

  /* true once the guild's list is on screen; false when the read failed or
     another read took its place */
  async function reloadList(keepId, quiet) {
    const seq = ++openSeq;
    shownGuild = guildId();
    /* a quiet reload (after a save, a move or a delete) keeps the list on
       screen until the new one arrives */
    if (!quiet) {
      events = [];
      listState = guildId() ? "loading" : "ready";
      current = null;
      slots = [];
    }
    renderList();
    renderEvent();
    if (!guildId()) return true;

    try {
      [events, templates] = await Promise.all([loadGuildEvents(guildId()), loadGuildTemplates(guildId())]);
    } catch (err) {
      if (seq !== openSeq) return false;
      if (!quiet) { listState = "failed"; renderList(); }
      showError(eventErrorMessage(err));
      return false;
    }
    if (seq !== openSeq) return false;

    listState = "ready";
    renderList();
    if (keepId && !quiet) await openEvent(keepId);
    return true;
  }

  async function openEvents() {
    if (!account.user) return;

    /* a reopened dialog starts idle (session) */
    session++;
    busy = false;
    acctIdle(el.save);
    acctIdle(el.remove);
    clearMessages();
    current = null;
    slots = [];
    events = [];
    listState = "loading";
    templates = [];
    guilds = [];
    renderGuilds();
    renderList();
    renderEvent();
    if (!dialog.open) dialog.showModal();

    const seq = ++openSeq;
    try {
      guilds = await loadMyGuilds();
    } catch (err) {
      if (seq !== openSeq) return;
      listState = "failed";
      renderList();
      showError(guildErrorMessage(err));
      return;
    }
    if (seq !== openSeq) return;

    renderGuilds();
    await reloadList(null);
  }

  acctWireDialog(dialog, { canClose: () => !busy && !dirty() });
  $id("ev-close").addEventListener("click", () => dialog.close());


  /* ---- identity ---- */

  window.Account.subscribe(state => {
    const was = account.user ? account.user.id : null;
    account = state;

    if (dialog.open && (!state.user || state.user.id !== was)) {
      dialog.close();
    }
  });

  window.Account.registerView("events", openEvents);
})();
