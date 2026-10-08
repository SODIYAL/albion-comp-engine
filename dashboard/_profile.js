"use strict";

/*
 * Player profile: the account's character (Albion name and server), its
 * display name, and the weapon lines its player plays - the first
 * user-owned data the site keeps, and the pattern the data after it
 * (guilds, sign-ups, attendance) follows.
 *
 * build.py inlines this file as its own <script> after _auth.js, beside
 * ACCOUNT_CATALOG: every weapon line's display name, role class and render
 * item, derived at build from the dataset and the engine's role_class (the
 * one role read). Like _auth.js it reads no planner state and never calls
 * the engine; identity comes from window.Account (_auth.js).
 *
 * Three parts, as in _auth.js, and the weapon picker the other dialogs
 * share:
 *   helpers - the only code that talks to window.DB (profiles,
 *             player_weapons, set_my_weapons)
 *   pure    - the weapon lists, search, roles, error wording
 *             (tests/test_profile.js)
 *   UI kit  - the weapon combobox (weaponCombo) with its art and role
 *             tag, the profile's lists' picker and the saved comps
 *             dialog's slot picker
 *   UI      - the profile dialog the account menu opens
 *
 * Tables, policies, grants and bounds: supabase/migrations/; the rules
 * every user-owned table follows: supabase/README.md.
 */


/* ------------------------------------------------------------ helpers */

async function myUserId() {
  const user = await getCurrentUser();

  if (!user) {
    const err = new Error("not signed in");
    err.code = "not_signed_in";
    throw err;
  }

  return user.id;
}


/* The character (name and server) and the display name. The column grants
   let a player write exactly these three columns of their own row. Returns
   the saved row. */
async function saveMyProfile({ albionName, albionServer, displayName }) {
  const id = await myUserId();
  const { data, error } = await window.DB
    .from("profiles")
    .update({ albion_name: albionName, albion_server: albionServer, display_name: displayName })
    .eq("id", id)
    .select()
    .single();

  if (error) {
    throw error;
  }

  return data;
}


/* The account's own row as the database holds it now: the profile form's
   baseline. Never the sign-up metadata, which no save updates, nor a copy
   read at page load, which a failed read leaves empty for the visit. */
async function loadMyProfile() {
  const id = await myUserId();
  const { data, error } = await window.DB
    .from("profiles")
    .select("*")
    .eq("id", id)
    .single();

  if (error) {
    throw error;
  }

  return data;
}


async function loadMyWeapons() {
  const id = await myUserId();
  const { data, error } = await window.DB
    .from("player_weapons")
    .select("weapon_id, preference, sort_order")
    .eq("user_id", id)
    .order("sort_order", { ascending: true });

  if (error) {
    throw error;
  }

  return data || [];
}


/* The whole list in one transaction (set_my_weapons): unlisted weapons
   go, listed ones are added or re-ordered. Returns the saved rows. */
async function saveMyWeapons(lists) {
  const { data, error } = await window.DB.rpc("set_my_weapons", {
    weapons: weaponPayload(lists)
  });

  if (error) {
    throw error;
  }

  return data || [];
}


/* --------------------------------------------------------------- pure */

/* The database's bounds (supabase/migrations; tests/test_supabase_schema.py
   pins that they agree). The name bound is ACCOUNT_NAME_MAX (_auth.js). */
const WEAPONS_MAX = 50;
const WEAPON_KEY_RE = /^[A-Z0-9_]{1,64}$/;
const WEAPON_PREFERENCES = ["main", "secondary"];

/* how many search hits the picker lists at once (display only) */
const WEAPON_SEARCH_LIMIT = 8;

const LIST_NAMES = { main: "Main weapons", secondary: "Can also play" };

/* The engine's role classes in a caller's words, in roster order (tanks,
   supports, damage, healers). */
const ROLE_NAMES = { frontline: "Tank", support: "Support", dps: "DPS", healer: "Healer" };
const ROLE_ORDER = ["frontline", "support", "dps", "healer"];


/* a name as the database stores it: trimmed, and empty as null */
function cleanName(value) {
  const text = String(value == null ? "" : value).trim();
  return text || null;
}


/* One weapon line as the profile shows it. A key the catalog no longer
   holds (a renamed line) stays, shown as unknown, until its player removes
   it: a stored choice is never dropped silently. */
function weaponInfo(catalog, key) {
  const entry = catalog && catalog[key];

  if (!entry) {
    return { key, name: key, role: null, item: "", known: false, removed: false };
  }

  return {
    key,
    name: entry.name || key,
    role: entry.role || null,
    item: entry.item || "",
    known: true,
    removed: !!entry.removed
  };
}


/* Saved rows -> { main: [keys], secondary: [keys] }, each in saved order.
   A repeated key keeps its first place; an unknown preference reads as
   secondary, the weaker claim. */
function weaponLists(rows) {
  const lists = { main: [], secondary: [] };
  const seen = new Set();
  const ordered = [...(rows || [])].sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));

  for (const row of ordered) {
    const key = row && row.weapon_id;
    if (!key || seen.has(key)) continue;
    seen.add(key);
    (row.preference === "main" ? lists.main : lists.secondary).push(key);
  }

  return lists;
}


/* The set_my_weapons payload: mains first, each list in its order. */
function weaponPayload(lists) {
  return [
    ...lists.main.map(weapon_id => ({ weapon_id, preference: "main" })),
    ...lists.secondary.map(weapon_id => ({ weapon_id, preference: "secondary" }))
  ];
}


function sameWeaponLists(a, b) {
  return JSON.stringify(weaponPayload(a)) === JSON.stringify(weaponPayload(b));
}


function copyWeaponLists(lists) {
  return { main: [...lists.main], secondary: [...lists.secondary] };
}


/* Search by name. A hit: every word of the query starts a word of the
   name, or the query sits inside the name. Ranked exact, prefix, word
   prefixes, inside; then by name. Listed weapons (exclude), removed lines
   and off-form keys never show. */
function weaponSearch(query, catalog, exclude, limit = WEAPON_SEARCH_LIMIT) {
  const q = String(query || "").trim().toLowerCase();
  if (!q) return [];

  const words = q.split(/\s+/);
  const hits = [];

  for (const [key, entry] of Object.entries(catalog || {})) {
    if (!entry || entry.removed || !WEAPON_KEY_RE.test(key) || (exclude && exclude.has(key))) continue;

    const name = String(entry.name || key).toLowerCase();
    const nameWords = name.split(/[\s'-]+/);
    let rank;

    if (name === q) rank = 0;
    else if (name.startsWith(q)) rank = 1;
    else if (words.every(w => nameWords.some(n => n.startsWith(w)))) rank = 2;
    else if (name.includes(q)) rank = 3;
    else continue;

    hits.push({ key, name: entry.name || key, role: entry.role || null, item: entry.item || "", rank });
  }

  hits.sort((a, b) => a.rank - b.rank || a.name.localeCompare(b.name));
  return hits.slice(0, limit);
}


/* The roles a player's lists cover, read from the catalog's role class:
   derived from the weapons, never stored beside them (one role read). A
   role both lists cover counts as main. */
function rolesCovered(lists, catalog) {
  const roleOf = key => ((catalog || {})[key] || {}).role;
  const cover = keys => ROLE_ORDER.filter(role => keys.some(key => roleOf(key) === role));
  const main = cover(lists.main);
  const secondary = cover(lists.secondary).filter(role => !main.includes(role));
  return { main, secondary };
}


const PROFILE_MSG = {
  network: "Could not reach the account service. Check your connection and try again.",
  signedOut: "Log in to edit your profile.",
  session: "Your session has expired. Log in again, then save.",
  missing: "Profiles cannot be saved yet: the account database has not been updated for this page. Try again later.",
  noRow: "Your profile record was not found. Log out and back in, then try again.",
  denied: "The server refused the change: an account edits only its own profile.",
  tooMany: `A profile lists at most ${WEAPONS_MAX} weapons.`,
  invalid: "The server refused a value. Check the names and weapons, then save again.",
  duplicate: "A weapon is listed twice. Remove the copy, then save.",
  unknown: "Something went wrong. Try again."
};


function profileErrorKind(err) {
  const code = String((err && err.code) || "");
  const message = String((err && err.message) || "");

  if (authErrorKind(err) === "network") return "network";
  if (code === "not_signed_in" || (code === "42501" && /sign in/i.test(message))) return "signedOut";
  if (/^PGRST30\d$/.test(code) || /jwt expired/i.test(message)) return "session";
  /* the page shipped before its migration: no table or function yet */
  if (code === "PGRST202" || code === "PGRST205" || code === "42883" || code === "42P01") return "missing";
  if (code === "PGRST116") return "noRow";
  if (code === "42501") return "denied";
  if (code === "23514") return /at most/i.test(message) ? "tooMany" : "invalid";
  if (code === "23505" || code === "21000") return "duplicate";
  if (code === "22023" || code === "23502" || code === "22001") return "invalid";

  return "unknown";
}


function profileErrorMessage(err) {
  const kind = profileErrorKind(err);
  const message = String((err && err.message) || "").trim();

  if (kind === "unknown" && message) {
    return `Something went wrong: ${message}`;
  }

  return PROFILE_MSG[kind];
}


/* ------------------------------------------------------------- UI kit */

/* a weapon's art: the page's icon, else the render service; a blank of
   the same size when there is none */
function pickerArt(info) {
  const src = (typeof ICONS !== "undefined" && ICONS[info.key])
    || (info.item ? `https://render.albiononline.com/v1/item/${encodeURIComponent(info.item)}.png?size=64` : "");

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
  img.width = 26;
  img.height = 26;
  img.loading = "lazy";
  return img;
}


function pickerRoleTag(role) {
  const tag = document.createElement("span");
  tag.className = `pw-role ${role}`;
  tag.textContent = ROLE_NAMES[role] || role;
  return tag;
}


/* The weapon combobox: the profile's picker, which the other dialogs
   share (the saved comps dialog's slots). A text input (role combobox)
   bound to its listbox, which opens in the flow under it, never over
   it. Typing lists opts.options(query) (each { key, name, role, item }:
   weaponSearch's hits, say) with their art and role tag; the first
   weapon is marked, an extra option (extra: true, the open slot) never
   is, and with no weapon the list says so above the extras; the arrows
   move, Enter or a click picks (opts.onPick(option), after the list
   closes), Enter never submits the form, the first Escape closes the
   list and not the dialog, and a blur closes it. opts.idPrefix names
   the options for aria-activedescendant. Returns { show, close }. */
function weaponCombo(input, results, opts) {
  const catalog = typeof ACCOUNT_CATALOG !== "undefined" ? ACCOUNT_CATALOG : {};
  let hits = [];
  let active = -1;

  function close() {
    hits = [];
    active = -1;
    results.hidden = true;
    results.replaceChildren();
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }

  function mark() {
    [...results.querySelectorAll("[role=option]")].forEach((li, i) => {
      li.setAttribute("aria-selected", String(i === active));
      if (i === active) li.scrollIntoView({ block: "nearest" });
    });

    if (active >= 0) {
      input.setAttribute("aria-activedescendant", `${opts.idPrefix}-${active}`);
    } else {
      input.removeAttribute("aria-activedescendant");
    }
  }

  function show() {
    const query = input.value.trim();
    if (!query) { close(); return; }

    hits = opts.options(query) || [];
    /* Enter picks a weapon the caller typed for, never an extra */
    active = hits.findIndex(hit => !hit.extra);

    const items = hits.map((hit, i) => {
      const li = document.createElement("li");
      li.id = `${opts.idPrefix}-${i}`;
      li.className = "pw-opt";
      li.setAttribute("role", "option");
      li.dataset.index = String(i);
      const name = document.createElement("span");
      name.className = "pw-name";
      name.textContent = hit.name;
      li.append(pickerArt(hit.key ? weaponInfo(catalog, hit.key) : { key: "", item: "" }), name);
      if (hit.role) li.append(pickerRoleTag(hit.role));
      return li;
    });

    if (active < 0) {
      const none = document.createElement("li");
      none.className = "pw-none";
      none.textContent = `No weapon matches “${query}”.`;
      items.unshift(none);
    }

    results.replaceChildren(...items);
    results.hidden = false;
    input.setAttribute("aria-expanded", "true");
    mark();
  }

  function choose(i) {
    const hit = hits[i];
    if (!hit) return;
    close();
    opts.onPick(hit);
  }

  input.addEventListener("input", show);
  input.addEventListener("blur", close);

  input.addEventListener("keydown", e => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (results.hidden) { show(); return; }
      if (!hits.length) return;
      const step = e.key === "ArrowDown" ? 1 : -1;
      active = (active + step + hits.length) % hits.length;
      mark();
    } else if (e.key === "Enter") {
      /* Enter picks; it never submits the form */
      e.preventDefault();
      if (active >= 0) choose(active);
    } else if (e.key === "Escape" && !results.hidden) {
      /* the first Escape closes the list, not the dialog */
      e.preventDefault();
      close();
    }
  });

  /* a press on a result must not blur the input before the click lands */
  results.addEventListener("pointerdown", e => e.preventDefault());
  results.addEventListener("click", e => {
    const li = e.target.closest("[data-index]");
    if (li) choose(Number(li.dataset.index));
  });

  return { show, close };
}


/* ----------------------------------------------------------------- UI */

(function profileUI() {
  if (typeof document === "undefined") {
    return;
  }

  const $id = id => document.getElementById(id);
  const dialog = $id("profile-dialog");

  if (!dialog || typeof dialog.showModal !== "function" || !window.Account) {
    return;
  }

  const CATALOG = typeof ACCOUNT_CATALOG !== "undefined" ? ACCOUNT_CATALOG : {};

  const el = {
    form: $id("profile-form"),
    error: $id("profile-error"),
    notice: $id("profile-notice"),
    display: $id("profile-display"),
    albion: $id("profile-albion"),
    server: $id("profile-server"),
    email: $id("profile-email"),
    save: $id("profile-save"),
    dirty: $id("profile-dirty"),
    note: $id("pw-note"),
    roles: $id("pw-roles"),
    live: $id("pw-live"),
    lists: { main: $id("pw-main"), secondary: $id("pw-secondary") }
  };

  const FIELDS = { albionName: el.albion, albionServer: el.server, displayName: el.display };
  const IDENTITY = Object.keys(FIELDS);

  const PICKERS = {
    main: { input: $id("pw-add-main"), results: $id("pw-results-main") },
    secondary: { input: $id("pw-add-secondary"), results: $id("pw-results-secondary") }
  };

  let account = window.Account.current();
  let lists = { main: [], secondary: [] };
  /* what the database holds, as last read or saved */
  let saved = { albionName: null, albionServer: null, displayName: null, lists: { main: [], secondary: [] } };
  /* the list loaded: a list never shown can never be saved over */
  let weaponsReady = false;
  /* the same for the names: read from the database when the dialog opens,
     and editable only once read */
  let identityReady = false;
  let busy = false;
  let openSeq = 0;
  /* bumped by every opening of the dialog: a save still waiting on the
     service from before neither changes the reopened dialog nor ends its
     busy state */
  let session = 0;


  /* ---- state -> the form ---- */

  const listed = () => new Set([...lists.main, ...lists.secondary]);

  /* the character and display name as typed, stored the database's way */
  const typedIdentity = () => ({
    albionName: cleanName(el.albion.value),
    albionServer: el.server.value || null,
    displayName: cleanName(el.display.value)
  });

  const identityChanged = typed => IDENTITY.some(key => typed[key] !== saved[key]);

  function dirty() {
    return (identityReady && identityChanged(typedIdentity()))
      || (weaponsReady && !sameWeaponLists(lists, saved.lists));
  }

  function setIdentityEnabled(on) {
    for (const input of Object.values(FIELDS)) input.disabled = !on;
  }

  /* the saved row back into the form and the baseline */
  function takeRow(row) {
    saved.albionName = cleanName(row.albion_name);
    saved.albionServer = row.albion_server || null;
    saved.displayName = cleanName(row.display_name);
    el.albion.value = row.albion_name || "";
    el.server.value = row.albion_server || "";
    el.display.value = row.display_name || "";
  }

  function markDirty() {
    el.dirty.hidden = !dirty();
  }

  const art = pickerArt;
  const roleTag = pickerRoleTag;

  function chipButton(kind, glyph, label, key, where) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = `pw-btn pw-${kind}`;
    b.dataset.pwAct = kind;
    b.dataset.pwKey = key;
    b.dataset.pwFrom = where;
    b.setAttribute("aria-label", label);
    b.title = label;
    b.textContent = glyph;
    return b;
  }

  function chip(key, where) {
    const info = weaponInfo(CATALOG, key);
    const other = where === "main" ? "secondary" : "main";
    const li = document.createElement("li");
    li.className = "pw-chip" + (info.known ? "" : " unknown");
    li.dataset.weapon = key;

    const name = document.createElement("span");
    name.className = "pw-name";
    name.textContent = info.known ? info.name : `${key} (unknown weapon)`;

    li.append(art(info), name);
    if (info.role) li.append(roleTag(info.role));
    li.append(
      chipButton("move", where === "main" ? "↓" : "↑",
                 `Move ${info.name} to ${LIST_NAMES[other]}`, key, where),
      chipButton("remove", "×", `Remove ${info.name}`, key, where)
    );
    return li;
  }

  function renderLists() {
    for (const where of ["main", "secondary"]) {
      const ul = el.lists[where];

      if (lists[where].length) {
        ul.replaceChildren(...lists[where].map(key => chip(key, where)));
      } else {
        const empty = document.createElement("li");
        empty.className = "pw-empty";
        empty.textContent = !weaponsReady ? "—"
          : where === "main" ? "No main weapons yet." : "Nothing listed yet.";
        ul.replaceChildren(empty);
      }
    }

    const full = listed().size >= WEAPONS_MAX;
    for (const picker of Object.values(PICKERS)) {
      picker.input.disabled = !weaponsReady || full;
      picker.input.placeholder = full ? `at most ${WEAPONS_MAX} weapons` : "type a weapon name";
    }

    const roles = rolesCovered(lists, CATALOG);
    const say = ids => ids.map(role => ROLE_NAMES[role]).join(" · ");
    el.roles.textContent = !roles.main.length && !roles.secondary.length ? ""
      : `Roles you cover: ${say(roles.main) || "none as a main"}`
        + (roles.secondary.length ? `; also ${say(roles.secondary)}` : "") + ".";

    markDirty();
  }

  function setNote(text) {
    el.note.textContent = text;
    el.note.hidden = !text;
  }

  const announce = text => { el.live.textContent = text; };
  const showError = message => acctMessage(el.error, el.notice, "error", message);
  const showNotice = message => acctMessage(el.error, el.notice, "notice", message);


  /* ---- editing the lists ---- */

  function add(key, where) {
    /* the list waits while a save runs: its answer replaces the list */
    if (busy || listed().has(key) || listed().size >= WEAPONS_MAX) return;
    lists[where].push(key);
    renderLists();
    announce(`${weaponInfo(CATALOG, key).name} added to ${LIST_NAMES[where]}.`);
  }

  el.form.addEventListener("click", e => {
    const b = e.target.closest("[data-pw-act]");
    if (!b || busy) return;

    const { pwAct: act, pwKey: key, pwFrom: from } = b.dataset;
    const at = lists[from].indexOf(key);
    if (at < 0) return;
    const name = weaponInfo(CATALOG, key).name;

    lists[from].splice(at, 1);

    if (act === "move") {
      const to = from === "main" ? "secondary" : "main";
      lists[to].push(key);
      renderLists();
      /* focus follows the weapon to its new list */
      const moved = el.lists[to].querySelector(`[data-pw-act="move"][data-pw-key="${key}"]`);
      if (moved) moved.focus();
      announce(`${name} moved to ${LIST_NAMES[to]}.`);
    } else {
      renderLists();
      /* focus goes to the next weapon's remove button, else the list's picker */
      const next = el.lists[from].querySelectorAll('[data-pw-act="remove"]')[Math.min(at, lists[from].length - 1)];
      (next || PICKERS[from].input).focus();
      announce(`${name} removed from ${LIST_NAMES[from]}.`);
    }
  });


  /* ---- the pickers: one combobox per list (weaponCombo) ---- */

  function wirePicker(where) {
    const { input, results } = PICKERS[where];
    weaponCombo(input, results, {
      idPrefix: `pw-opt-${where}`,
      options: query => weaponSearch(query, CATALOG, listed()),
      onPick: hit => {
        add(hit.key, where);
        input.value = "";
        input.focus();
      }
    });
  }

  wirePicker("main");
  wirePicker("secondary");


  /* ---- open, save, close ---- */

  async function openProfile() {
    if (!account.user) return;

    /* a reopened dialog starts idle (session) */
    session++;
    busy = false;
    acctIdle(el.save);
    const seq = ++openSeq;
    const names = accountNames(account.profile, account.user);

    /* the names the page holds show while the row is read; the row, once
       read, is the baseline a save compares against */
    el.display.value = names.display;
    el.albion.value = names.albion;
    el.server.value = names.server;
    el.email.textContent = account.user.email || "";
    saved = { albionName: cleanName(names.albion), albionServer: names.server || null,
              displayName: cleanName(names.display), lists: { main: [], secondary: [] } };
    lists = { main: [], secondary: [] };
    weaponsReady = false;
    identityReady = false;
    setIdentityEnabled(false);

    acctMessage(el.error, el.notice, null, "");
    acctFlagFields(FIELDS, {});
    setNote("Loading your profile…");
    renderLists();

    if (!dialog.open) dialog.showModal();

    const [p, w] = await Promise.all([
      loadMyProfile().then(row => ({ row }), err => ({ err })),
      loadMyWeapons().then(rows => ({ rows }), err => ({ err }))
    ]);
    if (seq !== openSeq) return;

    const notes = [];
    if (p.row) {
      takeRow(p.row);
      identityReady = true;
      window.Account.updateProfile(p.row);
    } else {
      notes.push(`Your name, server and display name could not be loaded, so they cannot be edited now. ${profileErrorMessage(p.err)}`);
    }
    setIdentityEnabled(identityReady);
    if (w.rows) {
      lists = weaponLists(w.rows);
      saved.lists = copyWeaponLists(lists);
      weaponsReady = true;
    } else {
      notes.push(`Your weapons could not be loaded, so they cannot be edited now. ${profileErrorMessage(w.err)}`);
    }
    setNote(notes.join(" "));
    renderLists();
    if (identityReady && !el.form.contains(document.activeElement)) el.albion.focus();
  }

  el.form.addEventListener("input", markDirty);

  el.form.addEventListener("submit", async e => {
    e.preventDefault();
    if (busy) return;

    acctMessage(el.error, el.notice, null, "");
    const first = identityReady ? acctFlagFields(FIELDS, validateIdentity({
      albionName: el.albion.value, albionServer: el.server.value, displayName: el.display.value
    })) : null;
    if (first) { first.focus(); return; }

    const identity = typedIdentity();
    const identityDirty = identityReady && identityChanged(identity);
    /* the lists as sent, taken now: the save never reads them after a wait
       (a reopened dialog empties them while it loads, and sending that
       would delete every row) */
    const sendLists = weaponsReady && !sameWeaponLists(lists, saved.lists) ? copyWeaponLists(lists) : null;

    if (!identityDirty && !sendLists) {
      showNotice("Nothing to save: your profile is up to date.");
      return;
    }

    busy = true;
    const mine = session;
    acctBusy(el.save, "Saving…");

    try {
      if (identityDirty) {
        try {
          const row = await saveMyProfile(identity);
          if (mine === session) takeRow(row);
          window.Account.updateProfile(row);
        } catch (err) {
          if (mine === session) showError(profileErrorMessage(err));
          return;
        }
      }

      if (sendLists) {
        try {
          const rows = await saveMyWeapons(sendLists);
          if (mine === session) {
            lists = weaponLists(rows);
            saved.lists = copyWeaponLists(lists);
            renderLists();
          }
        } catch (err) {
          if (mine === session) {
            showError((identityDirty ? "Your name, server and display name were saved; your weapons were not. " : "")
                      + profileErrorMessage(err));
          }
          return;
        }
      }

      if (mine === session) showNotice("Profile saved.");
    } finally {
      if (mine === session) {
        busy = false;
        acctIdle(el.save);
        markDirty();
      }
    }
  });

  /* unsaved edits survive a stray click on the backdrop; the close button
     and Escape still close */
  acctWireDialog(dialog, { canClose: () => !busy && !dirty() });

  $id("profile-close").addEventListener("click", () => dialog.close());


  /* ---- identity ---- */

  window.Account.subscribe(state => {
    const was = account.user ? account.user.id : null;
    account = state;

    /* a sign-out, here or in another tab, or another account, ends the edit */
    if (dialog.open && (!state.user || state.user.id !== was)) {
      dialog.close();
    }
  });

  window.Account.registerView("profile", openProfile);
})();
