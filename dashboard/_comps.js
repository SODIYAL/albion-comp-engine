"use strict";

/*
 * Saved comps (platform phase 3): a guild's comp templates. A template is
 * a planner comp the guild keeps: the content, the planned size, the
 * style, the slots (a weapon line, a caller's role label, a note) and the
 * planner's share hash it was saved with, so the kits and spell picks come
 * back when it is opened. Members read; callers, officers and admins
 * write. A template is never a live roster.
 *
 * build.py inlines this file as its own <script> after _guild.js, beside
 * ACCOUNT_CONTENTS and ACCOUNT_STYLES (the dataset's content and style
 * names, stamped at build). Like the modules before it, it reads no
 * planner state and never calls the engine. Its one contact with the
 * planner is the address bar: a comp is saved from the planner's share
 * hash (location.hash, the link the planner already publishes) and opened
 * by setting it (the planner applies a hash change as it applies a pasted
 * link). Weapons are read through ACCOUNT_CATALOG and the profile
 * module's pure functions; a writer sets a slot's weapon in the dialog
 * through the profile's combobox (weaponCombo). Each slot carries the
 * kit its saved link holds for it (slotKits, read through the planner's
 * loadout codec, the functions alone: never the planner's state), so a
 * slot whose weapon changes opens without a kit and the others keep
 * theirs (kitHash).
 *
 * Three parts, as in _profile.js:
 *   helpers - the only code that talks to window.DB (comp_templates,
 *             comp_template_slots, save_comp_template)
 *   pure    - the share hash and the kits it carries, the slots and their
 *             edits, the summary, what a role may do, error wording
 *             (tests/test_comps.js)
 *   UI      - the comps dialog the account menu opens
 */


/* ------------------------------------------------------------ helpers */

/* a guild's templates, newest change first, with who changed them and
   how many slots they hold */
async function loadGuildTemplates(guildId) {
  const { data, error } = await window.DB
    .from("comp_templates")
    .select("id, guild_id, name, content, style, planned_size, notes, share_hash, updated_at, "
            + "editor:profiles!comp_templates_updated_by_fkey(albion_name, display_name), "
            + "slots:comp_template_slots(count)")
    .eq("guild_id", guildId)
    .order("updated_at", { ascending: false });

  if (error) {
    throw error;
  }

  return data || [];
}


/* one template with its slots in position order */
async function loadTemplate(templateId) {
  const { data, error } = await window.DB
    .from("comp_templates")
    .select("id, guild_id, name, content, style, planned_size, notes, share_hash, updated_at, "
            + "slots:comp_template_slots(position, weapon_id, role, note)")
    .eq("id", templateId)
    .maybeSingle();

  if (error) {
    throw error;
  }

  if (data && data.slots) {
    data.slots.sort((a, b) => a.position - b.position);
  }

  return data;
}


/* the template and its slots in one transaction (save_comp_template);
   returns the saved template row */
async function saveTemplate(template) {
  const { data, error } = await window.DB.rpc("save_comp_template", {
    template: templatePayload(template)
  });

  if (error) {
    throw error;
  }

  return data;
}


async function deleteTemplate(templateId) {
  const { data, error } = await window.DB
    .from("comp_templates")
    .delete()
    .eq("id", templateId)
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

/* The database's bounds (supabase/migrations comp_templates;
   tests/test_supabase_schema.py pins that they agree). The slot cap holds
   three full parties of the planner's party cap (HARD_CAP in _app.js).
   The name bound is ACCOUNT_NAME_MAX (_auth.js). */
const COMP_SLOTS_MAX = 60;
const COMP_SIZE_MIN = 2;
const COMP_NOTES_MAX = 1000;
const COMP_ROLE_MAX = 40;
const COMP_NOTE_MAX = 200;
const COMP_TEMPLATES_MAX = 100;
const COMP_KEY_RE = /^[a-z0-9_]{1,40}$/;
/* a saved share hash's bound (comp_templates_share_hash_form) */
const COMP_HASH_MAX = 8000;

/* the roles that write templates: the caller's first power */
const COMP_WRITER_ROLES = ["caller", "officer", "admin"];


/* The planner's share hash (c=, n=, st=, p=, then the loadout codec's
   g=, f=, k=) as a template reads it: the content, the planned size, the
   style ("" for balanced), the weapon keys in roster order, the members
   by position (members: p= as written, an empty entry an open slot of a
   link built from a comp's slots, kitHash) and every field (params).
   Keys the catalog does not hold stay (the planner drops them; a
   template keeps what was saved). Null when the hash carries no comp.
   A zerg's address carries every party: the open one on the plain fields,
   t naming its number and the others on suffixed fields (n2 p2 g2 f2 k2,
   _loadout.js partyEncode). A comp is one party, so the hash it keeps is
   the open party's alone; opening it never brings the other parties. */
function parseShareHash(hash) {
  const h = String(hash || "").replace(/^#/, "").split("&")
    .filter(kv => {
      const key = kv.slice(0, Math.max(kv.indexOf("="), 0));
      return key !== "t" && !/^[npgfk][1-9][0-9]?$/.test(key);
    }).join("&");
  if (!h) return null;

  const p = {};
  for (const kv of h.split("&")) {
    const i = kv.indexOf("=");
    if (i > 0) {
      try { p[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1)); }
      catch (err) { p[kv.slice(0, i)] = kv.slice(i + 1); }
    }
  }

  if (!("c" in p) && !("n" in p) && !("st" in p) && !("p" in p)) return null;

  const n = parseInt(p.n, 10);
  const weapons = p.p ? p.p.split(",").filter(Boolean) : [];
  const members = p.p ? p.p.split(",") : [];
  while (members.length && !members[members.length - 1]) members.pop();

  return {
    content: p.c || "",
    size: Number.isInteger(n) ? n : null,
    style: p.st || "",
    weapons,
    members,
    params: p,
    hash: h
  };
}


/* the weapon keys of a roster as slots, position 1 first */
function slotsFromWeapons(weapons) {
  return (weapons || []).slice(0, COMP_SLOTS_MAX).map((weapon_id, i) => ({
    position: i + 1, weapon_id: weapon_id || null, role: null, note: null
  }));
}


/* the slots as a link's members: one entry per position up to the last
   slot that holds a weapon, an open slot an empty entry */
function slotMembers(slots) {
  const rows = normalizeSlots(slots);
  let last = 0;
  for (const s of rows) if (s.weapon_id) last = Math.max(last, s.position);
  const out = Array.from({ length: last }, () => "");
  for (const s of rows) if (s.weapon_id && s.position <= last) out[s.position - 1] = s.weapon_id;
  return out;
}


/* The kit each slot holds in a saved link, by position: the link's
   member at the slot's position, while the slot still names that
   member's weapon (the sheet's rule, _build.js), decoded through the
   planner's codec (_loadout.js): { loadout } (the gear and the Q, W and
   passive picks), prov where the member was forged or locked, combo
   where it carries an explicit combo. Nothing without the codec. */
function slotKits(shareHash, slots) {
  const out = {};
  const saved = parseShareHash(shareHash);
  if (!saved || !saved.members.length || typeof loadoutDecode !== "function") return out;
  const n = saved.members.length;
  const loadouts = loadoutDecode(saved.params.g || "") || [];
  const provs = typeof provDecode === "function" ? provDecode(saved.params.f || "", n) : [];
  const combos = typeof comboDecode === "function" ? comboDecode(saved.params.k || "", n) : [];
  for (const s of normalizeSlots(slots)) {
    const i = s.position - 1;
    if (!s.weapon_id || saved.members[i] !== s.weapon_id) continue;
    const kit = {};
    if (loadouts[i]) kit.loadout = loadouts[i];
    if (provs[i] && provs[i] !== "m") kit.prov = provs[i];
    if (Number.isInteger(combos[i])) kit.combo = combos[i];
    if (Object.keys(kit).length) out[s.position] = kit;
  }
  return out;
}


/* the slots, each carrying the kit a saved link holds for it (slotKits) */
function slotsWithKits(slots, shareHash) {
  const kits = slotKits(shareHash, slots);
  return (slots || []).map(s => (kits[s.position] ? Object.assign({}, s, { kit: kits[s.position] }) : s));
}


/* A link built from the slots with each slot's kit (kit: { loadout,
   prov, combo }, as slotKits reads it or the import builds it), through
   the planner's codec (_loadout.js: loadoutEncode, provEncode,
   comboEncode). p= holds one entry per slot up to the last one with a
   weapon, an open slot an empty entry, so every slot keeps its position:
   the sheet reads a slot's build at it (_build.js, _roster.js), and the
   planner drops an empty entry with its fields, as it drops any key it
   does not hold. "" without the codec, or past COMP_HASH_MAX. */
function kitHash(template, slots) {
  if (typeof loadoutEncode !== "function") return "";
  const t = template || {};
  const members = slotMembers(slots);
  const kitAt = new Map();
  for (const s of slots || []) {
    const position = Number(s && s.position);
    if (s && s.kit && !kitAt.has(position)) kitAt.set(position, s.kit);
  }
  const kits = members.map((w, i) => (w ? kitAt.get(i + 1) || null : null));
  const g = loadoutEncode(members, kits.map(k => (k && k.loadout) || undefined));
  const f = typeof provEncode === "function" ? provEncode(kits.map(k => (k && k.prov) || "m"), members.length) : "";
  const c = typeof comboEncode === "function"
    ? comboEncode(kits.map(k => (k && Number.isInteger(k.combo) ? k.combo : null)), members.length) : "";
  const parts = [`c=${encodeURIComponent(t.content || "")}`];
  if (t.planned_size) parts.push(`n=${t.planned_size}`);
  if (t.style) parts.push(`st=${encodeURIComponent(t.style)}`);
  if (members.length) parts.push(`p=${members.join(",")}`);
  if (g) parts.push(`g=${g}`);
  if (f) parts.push(`f=${f}`);
  if (c) parts.push(`k=${c}`);
  const out = parts.join("&");
  return out.length <= COMP_HASH_MAX ? out : "";
}


/* the slots with one slot's weapon set (a key, or null for an open
   slot); a changed weapon drops the slot's kit, its old weapon's */
function withSlotWeapon(slots, position, key) {
  return (slots || []).map(s => {
    if (Number(s.position) !== Number(position)) return s;
    const weapon_id = key || null;
    if (weapon_id === (s.weapon_id || null)) return s;
    const next = Object.assign({}, s, { weapon_id });
    delete next.kit;
    return next;
  });
}


/* the slots without one, renumbered from 1; every other slot keeps its
   kit */
function dropSlot(slots, position) {
  return (slots || []).filter(s => Number(s.position) !== Number(position))
    .map((s, i) => Object.assign({}, s, { position: i + 1 }));
}


/* what a slot's weapon picker lists for a query: the profile's search
   (weaponSearch), then the open slot while the slot holds a weapon, an
   extra the combobox never marks for Enter (a name that matches nothing
   never clears the slot) */
function slotPickOptions(query, catalog, current) {
  const hits = weaponSearch(query, catalog, null).map(h => ({ key: h.key, name: h.name, role: h.role, item: h.item }));
  if (current) hits.push({ key: "", name: "Open slot (any weapon)", role: "any", item: "", extra: true });
  return hits;
}


/* Saved slots -> the rows the dialog shows and the payload sends: sorted
   by position, one per position, texts trimmed. */
function normalizeSlots(slots) {
  const byPos = new Map();

  for (const s of slots || []) {
    const position = Number(s && s.position);
    if (!Number.isInteger(position) || position < 1 || position > COMP_SLOTS_MAX || byPos.has(position)) continue;
    const clean = (value, max) => {
      const text = String(value == null ? "" : value).trim();
      return text ? Array.from(text).slice(0, max).join("") : null;
    };
    byPos.set(position, {
      position,
      weapon_id: s.weapon_id ? String(s.weapon_id) : null,
      role: clean(s.role, COMP_ROLE_MAX),
      note: clean(s.note, COMP_NOTE_MAX)
    });
  }

  return [...byPos.values()].sort((a, b) => a.position - b.position);
}


/* The hash the planner opens for a template: the saved share hash when
   its members still match the slots position by position (the kits and
   picks ride along); else, when a slot carries its kit (the comps
   dialog's slots, an import's), a link built from the slots with their
   kits (kitHash), so a changed slot opens without a kit and the others
   keep theirs; else a plain c= / n= / st= / p= link built from the
   slots. */
function templateHash(template, slots) {
  const rows = normalizeSlots(slots);
  const weapons = rows.map(s => s.weapon_id).filter(Boolean);
  const saved = parseShareHash(template && template.share_hash);

  if (saved && saved.members.join(",") === slotMembers(rows).join(",")
      && saved.content === (template.content || "") && (saved.style || "") === (template.style || "")
      && (saved.size === null || saved.size === template.planned_size)) {
    return saved.hash;
  }

  if ((slots || []).some(s => s && s.kit)) {
    const built = kitHash(template, slots);
    if (built) return built;
  }

  const parts = [`c=${encodeURIComponent(template.content || "")}`];
  if (template.planned_size) parts.push(`n=${template.planned_size}`);
  if (template.style) parts.push(`st=${encodeURIComponent(template.style)}`);
  if (weapons.length) parts.push(`p=${weapons.join(",")}`);
  return parts.join("&");
}


/* The share hash a template keeps when it is saved: the stored one while
   it still opens as saved (templateHash returns it); else, when a slot
   carries its kit, the link built from the slots with their kits, so the
   stored link matches the stored slots again; else the stored one as it
   was (no kit is left to keep, and the plain link is built on open). */
function keptHash(template, slots) {
  const stored = (template && template.share_hash) || "";
  const saved = parseShareHash(stored);
  if (saved && templateHash(template, slots) === saved.hash) return stored;
  if ((slots || []).some(s => s && s.kit)) return kitHash(template, slots) || stored;
  return stored;
}


/* How many slots bring each role (the catalog's role class: one role
   read) and how many are open. */
function templateSummary(slots, catalog) {
  const out = { open: 0, unknown: 0, total: 0 };
  for (const role of ROLE_ORDER) out[role] = 0;

  for (const s of normalizeSlots(slots)) {
    out.total += 1;
    if (!s.weapon_id) { out.open += 1; continue; }
    const info = weaponInfo(catalog, s.weapon_id);
    if (info.role) out[info.role] += 1;
    else out.unknown += 1;
  }

  return out;
}


function validateTemplate({ name, content, style, plannedSize }, contents, styles) {
  const errors = {};

  if (!String(name || "").trim()) {
    errors.name = "Name the comp.";
  } else if (nameLength(name) > ACCOUNT_NAME_MAX) {
    errors.name = `Use at most ${ACCOUNT_NAME_MAX} characters.`;
  }

  if (!Object.prototype.hasOwnProperty.call(contents || {}, content || "")) {
    errors.content = "Choose the content the comp is for.";
  }

  if (style && !Object.prototype.hasOwnProperty.call(styles || {}, style)) {
    errors.style = "Choose a style from the list, or leave it balanced.";
  }

  const n = Number(plannedSize);
  if (!Number.isInteger(n) || n < COMP_SIZE_MIN || n > COMP_SLOTS_MAX) {
    errors.plannedSize = `Plan between ${COMP_SIZE_MIN} and ${COMP_SLOTS_MAX} players.`;
  }

  return errors;
}


/* the save_comp_template payload */
function templatePayload(template) {
  return {
    id: template.id || null,
    guild_id: template.guild_id,
    name: String(template.name || "").trim(),
    content: template.content,
    style: template.style || "",
    planned_size: Number(template.planned_size),
    notes: String(template.notes || "").trim(),
    share_hash: template.share_hash || "",
    slots: normalizeSlots(template.slots)
  };
}


/* who writes templates: the guard's roles, as the client offers them */
function compPowers(myRole) {
  return { write: COMP_WRITER_ROLES.includes(myRole) };
}


/* The comp as a sheet (the export, platform phase 10): a header, then
   one row per slot with the weapon's catalog name (empty for an open
   slot), the role and the note. The import reads it back exactly. */
function compSheetRows(slots, catalog) {
  const rows = [["#", "Weapon", "Role", "Note"]];
  for (const s of normalizeSlots(slots)) {
    rows.push([s.position, s.weapon_id ? weaponInfo(catalog, s.weapon_id).name : "", s.role || "", s.note || ""]);
  }
  return rows;
}


/* the comp as lines for a Discord post: a title line, then
   "1. Heavy Mace - tank (note)" per slot */
function compText(template, slots, catalog, contents, styles) {
  const t = template || {};
  const head = [t.name || "Comp", (contents || {})[t.content] || t.content || "",
                t.planned_size ? `${t.planned_size} planned` : "", t.style ? ((styles || {})[t.style] || t.style) : ""]
    .filter(Boolean).join(" · ");
  const lines = normalizeSlots(slots).map(s => {
    const weapon = s.weapon_id ? weaponInfo(catalog, s.weapon_id).name : "open slot";
    return `${s.position}. ${weapon}${s.role ? ` - ${s.role}` : ""}${s.note ? ` (${s.note})` : ""}`;
  });
  return [head, ...lines].join("\n");
}


const COMP_MSG = {
  network: PROFILE_MSG.network,
  signedOut: "Log in to use saved comps.",
  session: PROFILE_MSG.session,
  missing: "Saved comps are not available yet: the account database has not been updated for this page. Try again later.",
  taken: "A comp with this name already exists in the guild.",
  tooManyTemplates: `A guild keeps at most ${COMP_TEMPLATES_MAX} comps.`,
  tooManySlots: `A comp holds at most ${COMP_SLOTS_MAX} slots.`,
  duplicate: "A slot position is listed twice. Reload and try again.",
  refused: "The server refused the change: your role in this guild does not edit comps, or the comp has changed. Reload and try again.",
  invalid: "The server refused a value. Check the name, content, size and notes, then try again.",
  unknown: PROFILE_MSG.unknown
};


function compErrorKind(err) {
  const code = String((err && err.code) || "");
  const message = String((err && err.message) || "");

  if (authErrorKind(err) === "network") return "network";
  if (code === "not_signed_in" || (code === "42501" && /sign in/i.test(message))) return "signedOut";
  if (/^PGRST30\d$/.test(code) || /jwt expired/i.test(message)) return "session";
  if (code === "PGRST202" || code === "PGRST205" || code === "42883" || code === "42P01") return "missing";
  if (code === "23505") return "taken";
  if (code === "23514" && /at most \d+ templates/i.test(message)) return "tooManyTemplates";
  if (code === "23514" && /at most \d+ slots/i.test(message)) return "tooManySlots";
  if (code === "21000") return "duplicate";
  if (code === "42501" || code === "refused") return "refused";
  if (code === "23514" || code === "22023" || code === "23502" || code === "22001" || code === "22P02" || code === "22003") return "invalid";

  return "unknown";
}


function compErrorMessage(err) {
  const kind = compErrorKind(err);
  const message = String((err && err.message) || "").trim();

  if (kind === "unknown" && message) {
    return `Something went wrong: ${message}`;
  }

  return COMP_MSG[kind];
}


/* ----------------------------------------------------------------- UI */

(function compsUI() {
  if (typeof document === "undefined") {
    return;
  }

  const $id = id => document.getElementById(id);
  const dialog = $id("comp-dialog");

  if (!dialog || typeof dialog.showModal !== "function" || !window.Account) {
    return;
  }

  const CATALOG = typeof ACCOUNT_CATALOG !== "undefined" ? ACCOUNT_CATALOG : {};
  const CONTENTS = typeof ACCOUNT_CONTENTS !== "undefined" ? ACCOUNT_CONTENTS : {};
  const STYLES = typeof ACCOUNT_STYLES !== "undefined" ? ACCOUNT_STYLES : {};

  const el = {
    error: $id("comp-error"),
    notice: $id("comp-notice"),
    live: $id("comp-live"),
    guild: $id("comp-guild"),
    list: $id("comp-list"),
    listNote: $id("comp-list-note"),
    fromPlanner: $id("comp-from-planner"),
    empty: $id("comp-empty"),
    view: $id("comp-view"),
    form: $id("comp-form"),
    name: $id("comp-name"),
    content: $id("comp-content"),
    style: $id("comp-style"),
    size: $id("comp-size"),
    notes: $id("comp-notes"),
    meta: $id("comp-meta"),
    summary: $id("comp-summary"),
    slots: $id("comp-slots"),
    slotsNote: $id("comp-slots-note"),
    replace: $id("comp-replace"),
    open: $id("comp-open"),
    save: $id("comp-save"),
    remove: $id("comp-delete"),
    dirty: $id("comp-dirty"),
    importBtn: $id("comp-import"),
    importHint: $id("comp-import-hint"),
    exportBtn: $id("comp-export"),
    copyBtn: $id("comp-copy"),
    railRow: $id("save-comp-row"),     /* the rail's save button: shown to an account, opens this dialog on the planner's comp */
    railSave: $id("save-comp"),
    dashSave: $id("pdash-save-comp")   /* the party board's save icon: the same button, in its action row */
  };

  const FIELDS = { name: el.name, content: el.content, style: el.style, plannedSize: el.size };

  let account = window.Account.current();
  let guilds = [];            /* [{guild, role}] the account belongs to */
  let templates = [];         /* the selected guild's list */
  let current = null;         /* the open template: {id, guild_id, ..., slots} or a new one */
  let slots = [];             /* the open template's slots as edited */
  let canWrite = false;
  let busy = false;
  let openSeq = 0;
  /* bumped by every opening of the dialog: an action still waiting on the
     service from before neither changes the reopened dialog nor ends its
     busy state */
  let session = 0;
  /* bumped by every change of the open comp: a comp read still on its way
     never replaces a comp taken from the planner or opened since */
  let tplSeq = 0;
  let listState = "ready";    /* the list: "loading" until the service answers, "failed" when it did not */
  let shownGuild = null;      /* the guild whose list is shown */

  const showError = message => acctMessage(el.error, el.notice, "error", message);
  const showNotice = message => acctMessage(el.error, el.notice, "notice", message);
  const clearMessages = () => acctMessage(el.error, el.notice, null, "");
  const announce = text => { el.live.textContent = text; };
  const guildId = () => el.guild.value || null;
  const myRole = () => (guilds.find(g => g.guild.id === guildId()) || {}).role || null;

  /* the select lists, once */
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

  function renderList() {
    canWrite = compPowers(myRole()).write;
    el.fromPlanner.hidden = !canWrite || !guildId();
    el.importBtn.hidden = el.fromPlanner.hidden;
    el.importHint.hidden = el.fromPlanner.hidden;

    /* an unanswered list says so: "No comps saved yet" is the service's
       answer, never the wait for it */
    if (listState !== "ready") {
      const li = document.createElement("li");
      li.className = "gd-none";
      li.textContent = listState === "loading" ? "Loading comps…"
                                               : "The comps did not load. Close this dialog and open it again to retry.";
      el.list.replaceChildren(li);
      el.listNote.hidden = true;
      return;
    }

    if (!guildId()) {
      const li = document.createElement("li");
      li.className = "gd-none";
      li.textContent = "Join or create a guild to keep comps.";
      el.list.replaceChildren(li);
      return;
    }

    if (!templates.length) {
      const li = document.createElement("li");
      li.className = "gd-none";
      li.textContent = canWrite ? "No comps saved yet. Build one in the planner, then save it here."
                                : "No comps saved yet. Callers, officers and admins save them.";
      el.list.replaceChildren(li);
    } else {
      el.list.replaceChildren(...templates.map(t => {
        const li = document.createElement("li");
        const b = document.createElement("button");
        b.type = "button";
        b.className = "gd-item";
        b.dataset.template = t.id;
        b.setAttribute("aria-pressed", String(!!current && current.id === t.id));
        const name = document.createElement("span");
        name.className = "gd-item-name";
        name.textContent = t.name;
        const sub = document.createElement("span");
        sub.className = "gd-item-sub";
        const count = Array.isArray(t.slots) && t.slots[0] ? t.slots[0].count : 0;
        sub.textContent = `${CONTENTS[t.content] || t.content} · ${t.planned_size} · ${count} slot${count === 1 ? "" : "s"}`;
        b.append(name, sub);
        li.append(b);
        return li;
      }));
    }

    const full = templates.length >= COMP_TEMPLATES_MAX;
    el.listNote.textContent = full ? `A guild keeps at most ${COMP_TEMPLATES_MAX} comps.` : "";
    el.listNote.hidden = !full;
    if (full) {
      el.fromPlanner.hidden = true;
      el.importBtn.hidden = true;
      el.importHint.hidden = true;
    }
  }

  /* while an action waits, the guild stays the one whose list is shown */
  el.guild.addEventListener("change", () => {
    if (busy) { el.guild.value = shownGuild || ""; return; }
    reloadList(null);
  });

  el.list.addEventListener("click", e => {
    const b = e.target.closest("[data-template]");
    if (!b || busy) return;
    openTemplate(b.dataset.template);
  });


  /* ---- the open template ---- */

  function roleTag(role) {
    const tag = document.createElement("span");
    tag.className = `pw-role ${role}`;
    tag.textContent = ROLE_NAMES[role] || role;
    return tag;
  }

  /* the slot's weapon art, or a blank of its size for an open slot */
  function slotArt(info) {
    const src = info && ((typeof ICONS !== "undefined" && ICONS[info.key])
      || (info.item ? `https://render.albiononline.com/v1/item/${encodeURIComponent(info.item)}.png?size=64` : ""));
    if (!src) {
      const blank = document.createElement("span");
      blank.className = "pw-art blank";
      blank.setAttribute("aria-hidden", "true");
      return blank;
    }
    const img = document.createElement("img");
    img.className = "pw-art";
    img.src = src;
    img.alt = "";
    img.width = 22;
    img.height = 22;
    img.loading = "lazy";
    return img;
  }

  /* the mark of a slot that keeps the kit it was saved with */
  function kitMark() {
    const tag = document.createElement("span");
    tag.className = "cp-kit";
    tag.textContent = "kit";
    tag.title = canWrite ? "This slot keeps the kit it was saved with; another weapon opens without it."
                         : "This slot keeps the kit it was saved with.";
    return tag;
  }

  /* A writer picks a slot's weapon in place: the profile's combobox
     (weaponCombo) on the slot's name, its search and an open slot. */
  function weaponPicker(cell, slot, info) {
    const label = info ? (info.known ? info.name : `${slot.weapon_id} (unknown weapon)`) : "";
    const input = document.createElement("input");
    input.type = "text";
    input.className = "text-input cp-in cp-weapon-in";
    input.value = label;
    input.placeholder = "open slot: type a weapon";
    input.autocomplete = "off";
    input.spellcheck = false;
    input.dataset.cpWeapon = String(slot.position);
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-controls", `cp-results-${slot.position}`);
    input.setAttribute("aria-label", `slot ${slot.position}: weapon`);
    const results = document.createElement("ul");
    results.className = "pw-results cp-results";
    results.id = `cp-results-${slot.position}`;
    results.setAttribute("role", "listbox");
    results.setAttribute("aria-label", `weapons for slot ${slot.position}`);
    results.hidden = true;
    weaponCombo(input, results, {
      idPrefix: `cp-opt-${slot.position}`,
      options: query => slotPickOptions(query, CATALOG, slot.weapon_id),
      onPick: hit => pickWeapon(slot.position, hit.key)
    });
    input.addEventListener("focus", () => input.select());
    /* text typed and left unpicked is not the slot's weapon */
    input.addEventListener("blur", () => { input.value = label; });
    cell.append(input);
    return results;
  }

  function slotRow(slot) {
    const tr = document.createElement("tr");
    tr.dataset.position = String(slot.position);

    const pos = document.createElement("td");
    pos.className = "cp-pos";
    pos.textContent = String(slot.position);

    const weapon = document.createElement("td");
    weapon.className = "cp-weapon";
    const info = slot.weapon_id ? weaponInfo(CATALOG, slot.weapon_id) : null;
    if (canWrite) {
      weapon.classList.add("cp-weapon-edit");
      weapon.append(slotArt(info));
      const results = weaponPicker(weapon, slot, info);
      if (info && info.role) weapon.append(roleTag(info.role));
      if (slot.kit) weapon.append(kitMark());
      weapon.append(results);
    } else if (info) {
      weapon.append(slotArt(info));
      const name = document.createElement("span");
      name.className = "gd-name";
      name.textContent = info.known ? info.name : `${slot.weapon_id} (unknown weapon)`;
      weapon.append(name);
      if (info.role) weapon.append(roleTag(info.role));
      if (slot.kit) weapon.append(kitMark());
    } else {
      const open = document.createElement("span");
      open.className = "cp-open";
      open.textContent = "open slot";
      weapon.append(open);
    }

    const role = document.createElement("td");
    const roleIn = document.createElement("input");
    roleIn.className = "text-input cp-in";
    roleIn.type = "text";
    roleIn.maxLength = COMP_ROLE_MAX;
    roleIn.placeholder = "role";
    roleIn.value = slot.role || "";
    roleIn.dataset.cpRole = String(slot.position);
    roleIn.setAttribute("aria-label", `slot ${slot.position}: role`);
    roleIn.readOnly = !canWrite;
    role.append(roleIn);

    const note = document.createElement("td");
    const noteIn = document.createElement("input");
    noteIn.className = "text-input cp-in";
    noteIn.type = "text";
    noteIn.maxLength = COMP_NOTE_MAX;
    noteIn.placeholder = "note";
    noteIn.value = slot.note || "";
    noteIn.dataset.cpNote = String(slot.position);
    noteIn.setAttribute("aria-label", `slot ${slot.position}: note`);
    noteIn.readOnly = !canWrite;
    note.append(noteIn);

    const act = document.createElement("td");
    act.className = "gd-act";
    if (canWrite) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "gd-btn";
      b.dataset.cpRemove = String(slot.position);
      b.setAttribute("aria-label", `remove slot ${slot.position}`);
      b.textContent = "×";
      act.append(b);
    }

    tr.append(pos, weapon, role, note, act);
    return tr;
  }

  function renderTemplate() {
    el.view.hidden = !current;
    el.empty.hidden = !!current;
    if (!current) return;

    el.name.value = current.name || "";
    el.content.value = current.content || "";
    el.style.value = current.style || "";
    el.size.value = current.planned_size || "";
    el.notes.value = current.notes || "";
    for (const input of [el.name, el.content, el.style, el.size, el.notes]) {
      input.disabled = !canWrite;
    }

    renderSlots();
  }

  /* the slots' part of the open comp: the meta line, the role summary,
     the table and the buttons that read the slots; a slot's edit
     repaints this alone, so the fields keep what the caller typed */
  function renderSlots() {
    if (!current) return;
    const kits = slots.filter(s => s.kit).length;
    const kept = kits ? ` · ${kits} of ${slots.length} slot${slots.length === 1 ? "" : "s"} keep${kits === 1 ? "s" : ""} a kit` : "";
    el.meta.textContent = current.id
      ? `Saved ${current.updated_at ? new Date(current.updated_at).toLocaleString() : ""}${kept}`
      : `Not saved yet: from the planner's current comp.${kept}`;

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
    el.slotsNote.hidden = slots.length > 0;
    el.replace.hidden = !canWrite;
    el.save.hidden = !canWrite;
    el.remove.hidden = !canWrite || !current.id;
    el.open.disabled = !slots.some(s => s.weapon_id) && !current.share_hash;
    markDirty();
  }

  /* the comp as typed, with the share hash a save keeps (keptHash: the
     stored link while it still opens as saved, else rebuilt from the
     slots and their kits) */
  function typedTemplate() {
    const t = Object.assign({}, current, {
      name: el.name.value.trim(),
      content: el.content.value,
      style: el.style.value,
      planned_size: Number(el.size.value),
      notes: el.notes.value.trim(),
      slots
    });
    t.share_hash = keptHash(t, slots);
    return t;
  }

  function dirty() {
    if (!current) return false;
    if (!current.id) return true;
    const a = templatePayload(typedTemplate());
    const b = templatePayload(Object.assign({}, current, { slots: current.slots }));
    return JSON.stringify(a) !== JSON.stringify(b);
  }

  function markDirty() {
    el.dirty.hidden = !dirty();
  }

  el.form.addEventListener("input", e => {
    const t = e.target;
    if (t.dataset.cpRole !== undefined || t.dataset.cpNote !== undefined) {
      const position = Number(t.dataset.cpRole || t.dataset.cpNote);
      const slot = slots.find(s => s.position === position);
      if (slot) {
        if (t.dataset.cpRole !== undefined) slot.role = t.value.trim() || null;
        else slot.note = t.value.trim() || null;
      }
    }
    markDirty();
  });

  el.slots.addEventListener("click", e => {
    const b = e.target.closest("[data-cp-remove]");
    if (!b || busy || !canWrite) return;
    const position = Number(b.dataset.cpRemove);
    slots = dropSlot(slots, position);
    renderSlots();
    announce(`Slot ${position} removed.`);
  });

  /* a slot's weapon picked in the dialog (a key, "" for an open slot):
     the slot drops the kit its old weapon wore */
  function pickWeapon(position, key) {
    if (busy || !canWrite) return;
    const before = slots.find(s => s.position === position);
    if (!before) return;
    const changed = (key || null) !== (before.weapon_id || null);
    slots = withSlotWeapon(slots, position, key);
    renderSlots();
    const input = el.slots.querySelector(`[data-cp-weapon="${position}"]`);
    if (input) input.focus();
    if (changed) {
      const name = key ? weaponInfo(CATALOG, key).name : "an open slot";
      announce(`Slot ${position}: ${name}${before.kit ? "; the old weapon's kit is dropped" : ""}.`);
    }
  }

  /* the note under the slots as the open comp reads it (a failed or
     dropped read leaves no "Loading the comp…" behind) */
  function slotsNoteNow() {
    el.slotsNote.textContent = current && current.id ? "No slots: the comp is empty." : "";
    el.slotsNote.hidden = !current || slots.length > 0;
  }

  async function openTemplate(id) {
    const seq = ++openSeq;
    const tpl = ++tplSeq;
    clearMessages();
    acctFlagFields(FIELDS, {});
    el.slotsNote.textContent = "Loading the comp…";
    el.slotsNote.hidden = false;

    try {
      const t = await loadTemplate(id);
      if (seq !== openSeq || tpl !== tplSeq) return;
      if (!t) { slotsNoteNow(); showError(COMP_MSG.refused); return; }
      t.slots = normalizeSlots(t.slots);
      current = t;
      /* each slot carries the kit its saved link holds for it */
      slots = slotsWithKits(normalizeSlots(t.slots), t.share_hash);
      el.slotsNote.textContent = "No slots: the comp is empty.";
    } catch (err) {
      if (seq !== openSeq || tpl !== tplSeq) return;
      slotsNoteNow();
      showError(compErrorMessage(err));
      return;
    }

    renderList();
    renderTemplate();
  }

  /* a new template from the planner's current comp (the address bar) */
  function fromPlanner() {
    const parsed = parseShareHash(typeof location !== "undefined" ? location.hash : "");
    if (!parsed || !parsed.weapons.length) {
      showError("The planner holds no comp to save: add weapons in the planner first.");
      return;
    }
    tplSeq++;

    current = {
      id: null,
      guild_id: guildId(),
      name: "",
      content: Object.prototype.hasOwnProperty.call(CONTENTS, parsed.content) ? parsed.content : "",
      style: Object.prototype.hasOwnProperty.call(STYLES, parsed.style) ? parsed.style : "",
      planned_size: parsed.size || parsed.weapons.length,
      notes: "",
      share_hash: parsed.hash,
      slots: []
    };
    slots = slotsWithKits(slotsFromWeapons(parsed.weapons), parsed.hash);
    clearMessages();
    acctFlagFields(FIELDS, {});
    el.slotsNote.textContent = "";
    renderList();
    renderTemplate();
    el.name.focus();
  }

  el.fromPlanner.addEventListener("click", () => { if (!busy) fromPlanner(); });

  /* the rail's button: the dialog opens on the planner's comp, ready to
     name and save; without a guild to save into, the list says so */
  el.railSave.addEventListener("click", () => { if (!busy) openComps({ fromPlanner: true }); });
  if (el.dashSave) el.dashSave.addEventListener("click", () => { if (!busy) openComps({ fromPlanner: true }); });

  /* the import dialog is the import module's: the guild is handed over
     as a DOM event, never a call between modules; the imported comp
     comes back the same way (comp-imported, below) */
  el.importBtn.addEventListener("click", () => {
    if (busy || !guildId()) return;
    if (dirty() && !window.confirm("Leave this comp's unsaved changes and import a sheet?")) return;
    const guild = guildId();
    dialog.close();
    document.dispatchEvent(new CustomEvent("comp-import", { detail: { guildId: guild } }));
  });

  /* the comp as a CSV file: what the import reads back exactly */
  el.exportBtn.addEventListener("click", () => {
    if (!current) return;
    const t = typedTemplate();
    acctDownloadText(acctFilename(t.name || "comp", "csv"), acctCsvText(compSheetRows(slots, CATALOG)), "text/csv");
    announce("Comp exported as CSV.");
  });

  /* the comp as lines for a Discord post */
  el.copyBtn.addEventListener("click", () => {
    if (!current) return;
    const text = compText(typedTemplate(), slots, CATALOG, CONTENTS, STYLES);
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => showNotice("Comp copied as text."), () => showNotice(text));
    } else {
      showNotice(text);
    }
  });

  el.replace.addEventListener("click", () => {
    if (busy || !current) return;
    const parsed = parseShareHash(typeof location !== "undefined" ? location.hash : "");
    if (!parsed || !parsed.weapons.length) {
      showError("The planner holds no comp: add weapons in the planner first.");
      return;
    }
    if (!window.confirm("Replace this comp's slots with the planner's current comp? Role labels and notes on the slots are cleared.")) return;
    slots = slotsWithKits(slotsFromWeapons(parsed.weapons), parsed.hash);
    current.share_hash = parsed.hash;
    if (Object.prototype.hasOwnProperty.call(CONTENTS, parsed.content)) el.content.value = parsed.content;
    if (parsed.size) el.size.value = parsed.size;
    el.style.value = Object.prototype.hasOwnProperty.call(STYLES, parsed.style) ? parsed.style : "";
    renderTemplate();
    showNotice("Slots replaced from the planner. Save to keep them.");
  });

  el.open.addEventListener("click", () => {
    if (!current) return;
    const hash = templateHash(typedTemplate(), slots);
    dialog.close();
    location.hash = hash;
    announce(`${current.name || "The comp"} opened in the planner.`);
  });

  el.form.addEventListener("submit", async e => {
    e.preventDefault();
    if (busy || !current || !canWrite) return;
    clearMessages();

    const typed = typedTemplate();
    const first = acctFlagFields(FIELDS, validateTemplate({
      name: typed.name, content: typed.content, style: typed.style, plannedSize: typed.planned_size
    }, CONTENTS, STYLES));
    if (first) { first.focus(); return; }

    if (current.id && !dirty()) {
      showNotice("Nothing to save: the comp is up to date.");
      return;
    }

    /* the slots as sent: a label typed while the save runs stays in the
       form as an unsaved change, never as saved */
    const sent = normalizeSlots(slots);
    typed.slots = sent;
    busy = true;
    const mine = session;
    acctBusy(el.save, "Saving…");

    try {
      const row = await saveTemplate(typed);
      if (mine !== session) return;
      row.slots = sent;
      current = row;
      const listed = await reloadList(row.id, true);
      if (mine !== session) return;
      renderTemplate();
      if (listed) {
        showNotice("Comp saved.");
        announce("Comp saved.");
      }
    } catch (err) {
      if (mine === session) showError(compErrorMessage(err));
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
      await deleteTemplate(current.id);
      if (mine !== session) return;
      current = null;
      slots = [];
      const listed = await reloadList(null, true);
      if (mine !== session) return;
      renderTemplate();
      if (listed) showNotice(`${name} was deleted.`);
    } catch (err) {
      if (mine === session) showError(compErrorMessage(err));
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
    /* a quiet reload (after a save or a delete) keeps the list on screen
       until the new one arrives */
    if (!quiet) {
      templates = [];
      listState = guildId() ? "loading" : "ready";
      current = null;
      slots = [];
      tplSeq++;
    }
    renderList();
    renderTemplate();
    if (!guildId()) return true;

    try {
      templates = await loadGuildTemplates(guildId());
    } catch (err) {
      if (seq !== openSeq) return false;
      if (!quiet) { listState = "failed"; renderList(); }
      showError(compErrorMessage(err));
      return false;
    }
    if (seq !== openSeq) return false;

    listState = "ready";
    renderList();
    if (keepId && !quiet) await openTemplate(keepId);
    return true;
  }

  async function openComps(opts) {
    if (!account.user) return;

    /* a reopened dialog starts idle (session) */
    session++;
    busy = false;
    acctIdle(el.save);
    acctIdle(el.remove);
    clearMessages();
    current = null;
    slots = [];
    tplSeq++;
    templates = [];
    listState = "loading";
    guilds = [];
    renderGuilds();
    renderList();
    renderTemplate();
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
    const want = opts || {};
    if (want.guildId && guilds.some(g => g.guild.id === want.guildId)) el.guild.value = want.guildId;
    const listed = await reloadList(want.templateId || null);
    /* still this opening: reloadList bumped the sequence once and nothing
       since, and the list answered (a failed read keeps its message) */
    if (want.fromPlanner && listed && seq === openSeq - 1 && dialog.open) {
      if (!el.fromPlanner.hidden) fromPlanner();
      else if (!guildId()) showNotice("Join or create a guild to save comps into.");
      else if (!canWrite) showNotice("Members read the guild's comps; callers, officers and admins save them.");
    }
  }

  /* an imported comp comes back from the import dialog as a DOM event:
     the list is re-read and the comp opened */
  document.addEventListener("comp-imported", e => {
    const d = e.detail || {};
    if (!d.id) return;
    openComps({ guildId: d.guildId, templateId: d.id }).then(() => {
      if (!dialog.open || !current || current.id !== d.id) return;
      const kits = d.kits ? `, ${d.kits} of them with a kit from the sheet's gear columns`
        : d.kitsDropped ? ", without the sheet's gear: the kits make a link longer than a comp keeps" : "";
      const done = `${current.name} imported with ${d.slots} slot${d.slots === 1 ? "" : "s"}${kits}`;
      if (d.namesError) showError(`${done}; the names were not remembered: ${d.namesError}`);
      else showNotice(done + (d.learned ? `; ${d.learned} name${d.learned === 1 ? "" : "s"} remembered for the next import` : "") + ".");
    });
  });

  acctWireDialog(dialog, { canClose: () => !busy && !dirty() });
  $id("comp-close").addEventListener("click", () => dialog.close());


  /* ---- identity ---- */

  window.Account.subscribe(state => {
    const was = account.user ? account.user.id : null;
    account = state;
    el.railRow.hidden = !state.user;
    if (el.dashSave) el.dashSave.hidden = !state.user;

    if (dialog.open && (!state.user || state.user.id !== was)) {
      dialog.close();
    }
  });

  window.Account.registerView("comps", openComps);
})();
