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
 * module's pure functions.
 *
 * Three parts, as in _profile.js:
 *   helpers - the only code that talks to window.DB (comp_templates,
 *             comp_template_slots, save_comp_template)
 *   pure    - the share hash, the slots, the summary, what a role may do,
 *             error wording (tests/test_comps.js)
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
   tests/test_supabase_schema.py pins that they agree). The slot cap is
   the planner's roster cap (HARD_CAP in _app.js, pinned by the layout
   test). The name bound is ACCOUNT_NAME_MAX (_auth.js). */
const COMP_SLOTS_MAX = 60;
const COMP_SIZE_MIN = 2;
const COMP_NOTES_MAX = 1000;
const COMP_ROLE_MAX = 40;
const COMP_NOTE_MAX = 200;
const COMP_TEMPLATES_MAX = 100;
const COMP_KEY_RE = /^[a-z0-9_]{1,40}$/;

/* the roles that write templates: the caller's first power */
const COMP_WRITER_ROLES = ["caller", "officer", "admin"];


/* The planner's share hash (c=, n=, st=, p=, then the loadout codec's
   g=, f=, k=) as a template reads it: the content, the planned size, the
   style ("" for balanced) and the weapon keys in roster order. Keys the
   catalog does not hold stay (the planner drops them; a template keeps
   what was saved). Null when the hash carries no comp. */
function parseShareHash(hash) {
  const h = String(hash || "").replace(/^#/, "");
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

  return {
    content: p.c || "",
    size: Number.isInteger(n) ? n : null,
    style: p.st || "",
    weapons,
    hash: h
  };
}


/* the weapon keys of a roster as slots, position 1 first */
function slotsFromWeapons(weapons) {
  return (weapons || []).slice(0, COMP_SLOTS_MAX).map((weapon_id, i) => ({
    position: i + 1, weapon_id: weapon_id || null, role: null, note: null
  }));
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
   its roster still matches the slots (the kits and picks ride along),
   else a plain c= / n= / st= / p= link built from the slots. */
function templateHash(template, slots) {
  const rows = normalizeSlots(slots);
  const weapons = rows.map(s => s.weapon_id).filter(Boolean);
  const saved = parseShareHash(template && template.share_hash);

  if (saved && saved.weapons.join(",") === weapons.join(",")
      && saved.content === (template.content || "") && (saved.style || "") === (template.style || "")
      && (saved.size === null || saved.size === template.planned_size)) {
    return saved.hash;
  }

  const parts = [`c=${encodeURIComponent(template.content || "")}`];
  if (template.planned_size) parts.push(`n=${template.planned_size}`);
  if (template.style) parts.push(`st=${encodeURIComponent(template.style)}`);
  if (weapons.length) parts.push(`p=${weapons.join(",")}`);
  return parts.join("&");
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
    dirty: $id("comp-dirty")
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
    if (full) el.fromPlanner.hidden = true;
  }

  el.guild.addEventListener("change", () => { if (!busy) reloadList(null); });

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

    el.meta.textContent = current.id
      ? `Saved ${current.updated_at ? new Date(current.updated_at).toLocaleString() : ""}`
        + (current.share_hash ? " · kits and picks kept from the planner" : "")
      : "Not saved yet: from the planner's current comp.";

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

  function typedTemplate() {
    return Object.assign({}, current, {
      name: el.name.value.trim(),
      content: el.content.value,
      style: el.style.value,
      planned_size: Number(el.size.value),
      notes: el.notes.value.trim(),
      slots
    });
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
    slots = slots.filter(s => s.position !== position).map((s, i) => Object.assign(s, { position: i + 1 }));
    renderTemplate();
    announce(`Slot ${position} removed.`);
  });

  async function openTemplate(id) {
    const seq = ++openSeq;
    clearMessages();
    acctFlagFields(FIELDS, {});
    el.slotsNote.textContent = "Loading the comp…";
    el.slotsNote.hidden = false;

    try {
      const t = await loadTemplate(id);
      if (seq !== openSeq) return;
      if (!t) { showError(COMP_MSG.refused); return; }
      t.slots = normalizeSlots(t.slots);
      current = t;
      slots = normalizeSlots(t.slots);
      el.slotsNote.textContent = "No slots: the comp is empty.";
    } catch (err) {
      if (seq !== openSeq) return;
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
    slots = slotsFromWeapons(parsed.weapons);
    clearMessages();
    acctFlagFields(FIELDS, {});
    el.slotsNote.textContent = "";
    renderList();
    renderTemplate();
    el.name.focus();
  }

  el.fromPlanner.addEventListener("click", () => { if (!busy) fromPlanner(); });

  el.replace.addEventListener("click", () => {
    if (busy || !current) return;
    const parsed = parseShareHash(typeof location !== "undefined" ? location.hash : "");
    if (!parsed || !parsed.weapons.length) {
      showError("The planner holds no comp: add weapons in the planner first.");
      return;
    }
    if (!window.confirm("Replace this comp's slots with the planner's current comp? Role labels and notes on the slots are cleared.")) return;
    slots = slotsFromWeapons(parsed.weapons);
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

    busy = true;
    acctBusy(el.save, "Saving…");

    try {
      const row = await saveTemplate(typed);
      row.slots = normalizeSlots(slots);
      current = row;
      slots = normalizeSlots(row.slots);
      await reloadList(row.id, true);
      renderTemplate();
      showNotice("Comp saved.");
      announce("Comp saved.");
    } catch (err) {
      showError(compErrorMessage(err));
    } finally {
      busy = false;
      acctIdle(el.save);
      markDirty();
    }
  });

  el.remove.addEventListener("click", async () => {
    if (busy || !current || !current.id) return;
    if (!window.confirm(`Delete ${current.name}? This cannot be undone.`)) return;

    busy = true;
    acctBusy(el.remove, "Deleting…");
    const name = current.name;

    try {
      await deleteTemplate(current.id);
      current = null;
      slots = [];
      await reloadList(null, true);
      renderTemplate();
      showNotice(`${name} was deleted.`);
    } catch (err) {
      showError(compErrorMessage(err));
    } finally {
      busy = false;
      acctIdle(el.remove);
    }
  });


  /* ---- loading ---- */

  async function reloadList(keepId, quiet) {
    const seq = ++openSeq;
    templates = [];
    if (!quiet) { current = null; slots = []; }
    renderList();
    renderTemplate();
    if (!guildId()) return;

    try {
      templates = await loadGuildTemplates(guildId());
    } catch (err) {
      if (seq !== openSeq) return;
      showError(compErrorMessage(err));
      return;
    }
    if (seq !== openSeq) return;

    renderList();
    if (keepId && !quiet) await openTemplate(keepId);
  }

  async function openComps() {
    if (!account.user) return;

    clearMessages();
    current = null;
    slots = [];
    templates = [];
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
      showError(guildErrorMessage(err));
      return;
    }
    if (seq !== openSeq) return;

    renderGuilds();
    await reloadList(null);
  }

  acctWireDialog(dialog, { canClose: () => !busy && !dirty() });
  $id("comp-close").addEventListener("click", () => dialog.close());


  /* ---- identity ---- */

  window.Account.subscribe(state => {
    const was = account.user ? account.user.id : null;
    account = state;

    if (dialog.open && (!state.user || state.user.id !== was)) {
      dialog.close();
    }
  });

  window.Account.registerView("comps", openComps);
})();
