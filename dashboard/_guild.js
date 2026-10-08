"use strict";

/*
 * Guilds (platform phase 2): the guilds an account belongs to, each on
 * one Albion server, its members with a role (member / caller / officer /
 * admin), the join code a guild shares, and the members' characters and
 * weapon lists a caller reads to fill a comp.
 *
 * build.py inlines this file as its own <script> after _profile.js. Like
 * _profile.js it reads no planner state and never calls the engine;
 * identity comes from window.Account (_auth.js); weapons are read through
 * ACCOUNT_CATALOG and the profile module's pure functions (weaponInfo,
 * rolesCovered, ROLE_NAMES).
 *
 * Three parts, as in _profile.js:
 *   helpers - the only code that talks to window.DB (guilds,
 *             guild_members, guild_join_codes, profiles, player_weapons,
 *             create_guild, join_guild)
 *   pure    - validation, the member table, what a role may do, error
 *             wording (tests/test_guild.js)
 *   UI      - the guilds dialog the account menu opens
 *
 * Tables, policies, grants and bounds: supabase/migrations/ (guilds); the
 * rules every table follows: supabase/README.md. Who may do what is the
 * database's decision: the client only offers what the server would
 * allow, and reads the server's refusal as a sentence.
 */


/* ------------------------------------------------------------ helpers */

/* every guild the caller belongs to, with the caller's role, oldest first */
async function loadMyGuilds() {
  const id = await myUserId();
  const { data, error } = await window.DB
    .from("guild_members")
    .select("role, created_at, guild:guilds(id, name, albion_server, created_at)")
    .eq("user_id", id)
    .order("created_at", { ascending: true });

  if (error) {
    throw error;
  }

  return (data || []).filter(row => row.guild).map(row => ({ guild: row.guild, role: row.role }));
}


/* the members of one guild with their characters (the guild-scoped
   profile policy) */
async function loadGuildMembers(guildId) {
  const { data, error } = await window.DB
    .from("guild_members")
    .select("user_id, role, created_at, profile:profiles(albion_name, display_name, albion_server)")
    .eq("guild_id", guildId);

  if (error) {
    throw error;
  }

  return data || [];
}


/* the weapon lists of these players (the guild-scoped weapons policy) */
async function loadMembersWeapons(userIds) {
  if (!userIds.length) return [];

  const { data, error } = await window.DB
    .from("player_weapons")
    .select("user_id, weapon_id, preference, sort_order")
    .in("user_id", userIds)
    .order("sort_order", { ascending: true });

  if (error) {
    throw error;
  }

  return data || [];
}


/* the join code, or null when the caller is not an officer or admin (the
   view answers no row) */
async function loadJoinCode(guildId) {
  const { data, error } = await window.DB
    .from("guild_join_codes")
    .select("join_code")
    .eq("guild_id", guildId)
    .maybeSingle();

  if (error) {
    throw error;
  }

  return data ? data.join_code : null;
}


/* the guild and its first admin in one transaction; returns the guild */
async function createGuild({ name, albionServer }) {
  const { data, error } = await window.DB.rpc("create_guild", {
    name: String(name || "").trim(),
    albion_server: albionServer
  });

  if (error) {
    throw error;
  }

  return data;
}


/* the code holder becomes a member; returns the guild */
async function joinGuild(code) {
  const { data, error } = await window.DB.rpc("join_guild", { code: cleanJoinCode(code) });

  if (error) {
    throw error;
  }

  return data;
}


/* the one column a role change writes; the saved row comes back, or a
   refusal (no row) when the policy or the guard denied it */
async function setMemberRole(guildId, userId, role) {
  const { data, error } = await window.DB
    .from("guild_members")
    .update({ role })
    .eq("guild_id", guildId)
    .eq("user_id", userId)
    .select()
    .maybeSingle();

  if (error) {
    throw error;
  }

  if (!data) {
    throw guildRefusal();
  }

  return data;
}


/* remove a member, or leave (the caller's own row); the removed row
   comes back, or a refusal when the policy denied it */
async function removeMember(guildId, userId) {
  const { data, error } = await window.DB
    .from("guild_members")
    .delete()
    .eq("guild_id", guildId)
    .eq("user_id", userId)
    .select();

  if (error) {
    throw error;
  }

  if (!data || !data.length) {
    throw guildRefusal();
  }

  return data[0];
}


async function leaveGuild(guildId) {
  return removeMember(guildId, await myUserId());
}


async function renameGuild(guildId, name) {
  const { data, error } = await window.DB
    .from("guilds")
    .update({ name: String(name || "").trim() })
    .eq("id", guildId)
    .select()
    .maybeSingle();

  if (error) {
    throw error;
  }

  if (!data) {
    throw guildRefusal();
  }

  return data;
}


/* any written value becomes a fresh code (the guilds guard); the new code
   is read back through the view */
async function renewJoinCode(guildId) {
  const { data, error } = await window.DB
    .from("guilds")
    .update({ join_code: "RENEW" })
    .eq("id", guildId)
    .select("id");

  if (error) {
    throw error;
  }

  if (!data || !data.length) {
    throw guildRefusal();
  }

  return loadJoinCode(guildId);
}


async function deleteGuild(guildId) {
  const { data, error } = await window.DB
    .from("guilds")
    .delete()
    .eq("id", guildId)
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

/* The database's bounds and vocabulary (supabase/migrations guilds;
   tests/test_supabase_schema.py pins that they agree). The name bound is
   ACCOUNT_NAME_MAX and the servers ALBION_SERVERS (_auth.js). */
const GUILD_ROLES = ["member", "caller", "officer", "admin"];
const GUILDS_MAX = 20;
const GUILD_MEMBERS_MAX = 500;
const JOIN_CODE_RE = /^[A-Z0-9]{10}$/;

const GUILD_ROLE_NAMES = { member: "Member", caller: "Caller", officer: "Officer", admin: "Admin" };

/* what the server says when a policy or guard refused a write: no row
   comes back, and PostgREST reports no error */
function guildRefusal() {
  const err = new Error("the server refused the change");
  err.code = "refused";
  return err;
}


/* a code as the database compares it: trimmed, upper case */
function cleanJoinCode(value) {
  return String(value == null ? "" : value).trim().toUpperCase();
}


function validateGuild({ name, albionServer }) {
  const errors = {};

  if (!String(name || "").trim()) {
    errors.name = "Enter the guild's name.";
  } else if (nameLength(name) > ACCOUNT_NAME_MAX) {
    errors.name = `Use at most ${ACCOUNT_NAME_MAX} characters.`;
  }

  if (!Object.prototype.hasOwnProperty.call(ALBION_SERVERS, albionServer || "")) {
    errors.albionServer = "Choose the server the guild plays on.";
  }

  return errors;
}


function validateJoinCode(code) {
  const errors = {};
  const clean = cleanJoinCode(code);

  if (!clean) {
    errors.code = "Enter the join code.";
  } else if (!JOIN_CODE_RE.test(clean)) {
    errors.code = "A join code is 10 letters and digits.";
  }

  return errors;
}


/* a member as the roster names them: display name, else Albion name */
function memberLabel(profile) {
  const names = accountNames(profile || {}, null);
  return names.display || names.albion || "Unnamed";
}


/* Members and their weapon rows -> the table, admins first, then
   officers, callers, members, each group by name. Each row carries the
   member's lists and the roles they cover, read from the catalog (one
   role read). */
function memberRows(members, weaponRows, catalog) {
  const byUser = {};
  for (const row of weaponRows || []) {
    (byUser[row.user_id] = byUser[row.user_id] || []).push(row);
  }

  const rows = (members || []).map(m => {
    const lists = weaponLists(byUser[m.user_id] || []);
    return {
      userId: m.user_id,
      role: GUILD_ROLES.includes(m.role) ? m.role : "member",
      name: memberLabel(m.profile),
      albion: accountNames(m.profile || {}, null).albion,
      server: accountNames(m.profile || {}, null).server,
      since: m.created_at || null,
      lists,
      roles: rolesCovered(lists, catalog)
    };
  });

  return sortMemberRows(rows);
}


/* admins first, then officers, callers, members; each group by name */
function sortMemberRows(rows) {
  const rank = role => GUILD_ROLES.indexOf(role);
  return [...rows].sort((a, b) => rank(b.role) - rank(a.role) || a.name.localeCompare(b.name));
}


/* How many members bring each role as a main, and how many more could
   swap to it: what a caller asks before a CTA. */
function roleCoverage(rows) {
  const out = {};
  for (const role of ROLE_ORDER) {
    out[role] = { main: 0, also: 0 };
  }
  for (const row of rows || []) {
    for (const role of row.roles.main) out[role].main += 1;
    for (const role of row.roles.secondary) out[role].also += 1;
  }
  return out;
}


/* What the acting member may do to a target row, as the database decides
   it (the guard in supabase/migrations guilds): officers reach members and
   callers and set those two roles; admins reach everyone and set any role;
   an admin cannot leave or step down while the guild has no other admin.
   The client offers only these; the server still refuses the rest. */
function memberPowers(myRole, mine, target, adminCount) {
  const lastAdmin = target.role === "admin" && adminCount <= 1;

  if (mine) {
    return { roles: [], remove: !lastAdmin, removeLabel: "Leave" };
  }

  if (myRole === "admin") {
    return {
      roles: lastAdmin ? [] : GUILD_ROLES,
      remove: !lastAdmin,
      removeLabel: "Remove"
    };
  }

  if (myRole === "officer" && (target.role === "member" || target.role === "caller")) {
    return { roles: ["member", "caller"], remove: true, removeLabel: "Remove" };
  }

  return { roles: [], remove: false, removeLabel: "" };
}


const GUILD_MSG = {
  network: PROFILE_MSG.network,
  signedOut: "Log in to use guilds.",
  session: PROFILE_MSG.session,
  missing: "Guilds are not available yet: the account database has not been updated for this page. Try again later.",
  noCode: "No guild has this join code. Check it with whoever shared it.",
  taken: "A guild with this name already exists on that server.",
  lastAdmin: "A guild keeps at least one admin. Make another member an admin first.",
  officerReach: "An officer manages members and callers only.",
  tooManyGuilds: `An account belongs to at most ${GUILDS_MAX} guilds.`,
  guildFull: `A guild holds at most ${GUILD_MEMBERS_MAX} members.`,
  refused: "The server refused the change: your role in this guild does not allow it, or the guild has changed. Reload and try again.",
  invalid: "The server refused a value. Check the name and server, then try again.",
  unknown: PROFILE_MSG.unknown
};


function guildErrorKind(err) {
  const code = String((err && err.code) || "");
  const message = String((err && err.message) || "");

  if (authErrorKind(err) === "network") return "network";
  if (code === "not_signed_in" || (code === "42501" && /sign in/i.test(message))) return "signedOut";
  if (/^PGRST30\d$/.test(code) || /jwt expired/i.test(message)) return "session";
  if (code === "PGRST202" || code === "PGRST205" || code === "42883" || code === "42P01") return "missing";
  if (code === "P0002") return "noCode";
  if (code === "23505") return "taken";
  if (code === "23514" && /at least one admin/i.test(message)) return "lastAdmin";
  if (code === "23514" && /at most \d+ guilds/i.test(message)) return "tooManyGuilds";
  if (code === "23514" && /at most \d+ members/i.test(message)) return "guildFull";
  if (code === "42501" && /officer/i.test(message)) return "officerReach";
  if (code === "42501" || code === "refused") return "refused";
  if (code === "23514" || code === "22023" || code === "23502" || code === "22001") return "invalid";

  return "unknown";
}


function guildErrorMessage(err) {
  const kind = guildErrorKind(err);
  const message = String((err && err.message) || "").trim();

  if (kind === "unknown" && message) {
    return `Something went wrong: ${message}`;
  }

  return GUILD_MSG[kind];
}


/* ----------------------------------------------------------------- UI */

(function guildUI() {
  if (typeof document === "undefined") {
    return;
  }

  const $id = id => document.getElementById(id);
  const dialog = $id("guild-dialog");

  if (!dialog || typeof dialog.showModal !== "function" || !window.Account) {
    return;
  }

  const CATALOG = typeof ACCOUNT_CATALOG !== "undefined" ? ACCOUNT_CATALOG : {};

  const el = {
    error: $id("guild-error"),
    notice: $id("guild-notice"),
    list: $id("guild-list"),
    listNote: $id("guild-list-note"),
    newForm: $id("guild-new"),
    newName: $id("guild-new-name"),
    newServer: $id("guild-new-server"),
    newSubmit: $id("guild-new-submit"),
    joinForm: $id("guild-join"),
    joinCode: $id("guild-join-code"),
    joinSubmit: $id("guild-join-submit"),
    view: $id("guild-view"),
    empty: $id("guild-empty"),
    name: $id("guild-name"),
    meta: $id("guild-meta"),
    codeBox: $id("guild-code-box"),
    code: $id("guild-code"),
    copy: $id("guild-code-copy"),
    renew: $id("guild-code-renew"),
    coverage: $id("guild-coverage"),
    members: $id("guild-members"),
    membersNote: $id("guild-members-note"),
    renameForm: $id("guild-rename"),
    renameName: $id("guild-rename-name"),
    renameSubmit: $id("guild-rename-submit"),
    leave: $id("guild-leave"),
    remove: $id("guild-delete"),
    live: $id("guild-live")
  };

  let account = window.Account.current();
  let guilds = [];          /* [{guild, role}] */
  let current = null;       /* the selected guild's id */
  let rows = [];            /* memberRows of the selected guild */
  let busy = false;
  let openSeq = 0;
  /* bumped by every opening of the dialog: an action still waiting on the
     service from before neither changes the reopened dialog nor ends its
     busy state (a join code renewed for one guild never lands in another's
     panel) */
  let session = 0;
  let listState = "ready";  /* the list: "loading" until the service answers, "failed" when it did not */

  const showError = message => acctMessage(el.error, el.notice, "error", message);
  const showNotice = message => acctMessage(el.error, el.notice, "notice", message);
  const clearMessages = () => acctMessage(el.error, el.notice, null, "");
  const announce = text => { el.live.textContent = text; };
  const mine = () => guilds.find(g => g.guild.id === current) || null;


  /* ---- the guild list ---- */

  function renderList() {
    /* an unanswered list says so: "in no guild yet" is the service's
       answer, never the wait for it */
    if (listState !== "ready" || !guilds.length) {
      const li = document.createElement("li");
      li.className = "gd-none";
      li.textContent = listState === "loading" ? "Loading your guilds…"
        : listState === "failed" ? "Your guilds did not load. Close this dialog and open it again to retry."
        : "You are in no guild yet. Create one, or join with a code.";
      el.list.replaceChildren(li);
    } else {
      el.list.replaceChildren(...guilds.map(({ guild, role }) => {
        const li = document.createElement("li");
        const b = document.createElement("button");
        b.type = "button";
        b.className = "gd-item";
        b.dataset.guild = guild.id;
        b.setAttribute("aria-pressed", String(guild.id === current));
        const name = document.createElement("span");
        name.className = "gd-item-name";
        name.textContent = guild.name;
        const sub = document.createElement("span");
        sub.className = "gd-item-sub";
        sub.textContent = `${ALBION_SERVERS[guild.albion_server] || guild.albion_server} · ${GUILD_ROLE_NAMES[role] || role}`;
        b.append(name, sub);
        li.append(b);
        return li;
      }));
    }

    const full = guilds.length >= GUILDS_MAX;
    el.newSubmit.disabled = full;
    el.joinSubmit.disabled = full;
    el.listNote.textContent = full ? `An account belongs to at most ${GUILDS_MAX} guilds.` : "";
    el.listNote.hidden = !full;
  }

  el.list.addEventListener("click", e => {
    const b = e.target.closest("[data-guild]");
    if (!b || busy) return;
    select(b.dataset.guild);
  });


  /* ---- the selected guild ---- */

  function roleTag(role) {
    const tag = document.createElement("span");
    tag.className = `pw-role ${role}`;
    tag.textContent = ROLE_NAMES[role] || role;
    return tag;
  }

  function weaponChip(key) {
    const info = weaponInfo(CATALOG, key);
    const li = document.createElement("li");
    li.className = "gd-weapon" + (info.known ? "" : " unknown");
    li.title = info.known ? info.name : `${key} (unknown weapon)`;
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
      li.append(img);
    }
    const name = document.createElement("span");
    name.className = "gd-weapon-name";
    name.textContent = info.known ? info.name : key;
    li.append(name);
    return li;
  }

  function memberRow(row, myRole, adminCount) {
    const tr = document.createElement("tr");
    tr.dataset.user = row.userId;
    const isMe = account.user && row.userId === account.user.id;
    const powers = memberPowers(myRole, isMe, row, adminCount);

    const who = document.createElement("td");
    who.className = "gd-who";
    const name = document.createElement("span");
    name.className = "gd-name";
    name.textContent = row.name + (isMe ? " (you)" : "");
    who.append(name);
    const sub = [row.albion && row.albion !== row.name ? row.albion : "",
                 ALBION_SERVERS[row.server] || ""].filter(Boolean).join(" · ");
    if (sub) {
      const s = document.createElement("span");
      s.className = "gd-sub";
      s.textContent = sub;
      who.append(s);
    }

    const role = document.createElement("td");
    role.className = "gd-role";
    if (powers.roles.length) {
      const sel = document.createElement("select");
      sel.className = "gd-role-select";
      sel.dataset.gdRole = row.userId;
      sel.setAttribute("aria-label", `${row.name}: role`);
      for (const r of powers.roles) {
        const o = document.createElement("option");
        o.value = r;
        o.textContent = GUILD_ROLE_NAMES[r];
        o.selected = r === row.role;
        sel.append(o);
      }
      role.append(sel);
    } else {
      role.textContent = GUILD_ROLE_NAMES[row.role] || row.role;
    }

    const plays = document.createElement("td");
    plays.className = "gd-plays";
    const mains = document.createElement("ul");
    mains.className = "gd-weapons";
    mains.replaceChildren(...row.lists.main.map(weaponChip));
    if (row.lists.secondary.length) {
      const also = document.createElement("li");
      also.className = "gd-also";
      also.textContent = `+${row.lists.secondary.length} can also play`;
      also.title = row.lists.secondary.map(k => weaponInfo(CATALOG, k).name).join(", ");
      mains.append(also);
    }
    if (!row.lists.main.length && !row.lists.secondary.length) {
      const none = document.createElement("li");
      none.className = "gd-also";
      none.textContent = "no weapons listed";
      mains.append(none);
    }
    plays.append(mains);
    const covers = document.createElement("div");
    covers.className = "gd-covers";
    covers.replaceChildren(...row.roles.main.map(roleTag));
    plays.append(covers);

    const act = document.createElement("td");
    act.className = "gd-act";
    if (powers.remove) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "gd-btn" + (isMe ? "" : " danger");
      b.dataset.gdRemove = row.userId;
      b.textContent = powers.removeLabel;
      act.append(b);
    }

    tr.append(who, role, plays, act);
    return tr;
  }

  function renderGuild() {
    const g = mine();
    el.view.hidden = !g;
    el.empty.hidden = !!g;
    if (!g) return;

    const myRole = g.role;
    el.name.textContent = g.guild.name;
    el.meta.textContent = `${ALBION_SERVERS[g.guild.albion_server] || g.guild.albion_server} · you are ${GUILD_ROLE_NAMES[myRole] || myRole} · ${rows.length} member${rows.length === 1 ? "" : "s"}`;

    const adminCount = rows.filter(r => r.role === "admin").length;
    el.members.replaceChildren(...rows.map(r => memberRow(r, myRole, adminCount)));

    const cov = roleCoverage(rows);
    el.coverage.replaceChildren(...ROLE_ORDER.map(role => {
      const cell = document.createElement("span");
      cell.className = `gd-cov ${role}`;
      const n = document.createElement("b");
      n.textContent = String(cov[role].main);
      cell.append(n, ` ${ROLE_NAMES[role]}`);
      if (cov[role].also) {
        const also = document.createElement("small");
        also.textContent = ` +${cov[role].also}`;
        also.title = `${cov[role].also} more can also play ${ROLE_NAMES[role]}`;
        cell.append(also);
      }
      return cell;
    }));

    const officer = myRole === "officer" || myRole === "admin";
    el.codeBox.hidden = !officer;
    el.renew.hidden = myRole !== "admin";
    el.renameForm.hidden = myRole !== "admin";
    el.remove.hidden = myRole !== "admin";
    el.renameName.value = g.guild.name;
    const me = rows.find(r => account.user && r.userId === account.user.id);
    const lastAdmin = me && me.role === "admin" && adminCount <= 1;
    el.leave.hidden = !!lastAdmin;
  }

  async function select(guildId) {
    current = guildId;
    rows = [];
    renderList();
    renderGuild();
    clearMessages();
    if (!guildId) return;

    const seq = ++openSeq;
    el.membersNote.textContent = "Loading members…";
    el.membersNote.hidden = false;
    el.code.textContent = "";

    try {
      const members = await loadGuildMembers(guildId);
      if (seq !== openSeq) return;
      const weapons = await loadMembersWeapons(members.map(m => m.user_id));
      if (seq !== openSeq) return;
      rows = memberRows(members, weapons, CATALOG);
      el.membersNote.hidden = true;
      renderGuild();
    } catch (err) {
      if (seq !== openSeq) return;
      el.membersNote.textContent = `The members could not be loaded. ${guildErrorMessage(err)}`;
      return;
    }

    const g = mine();
    if (g && (g.role === "officer" || g.role === "admin")) {
      try {
        const code = await loadJoinCode(guildId);
        if (seq !== openSeq) return;
        el.code.textContent = code || "";
      } catch (err) {
        if (seq !== openSeq) return;
        el.code.textContent = "";
        showError(`The join code could not be read. ${guildErrorMessage(err)}`);
      }
    }
  }

  /* true once the list is read; false when the read failed (the panel then
     shows no guild rather than one just left or deleted) or another read
     took its place */
  async function reload(keep) {
    const seq = ++openSeq;
    try {
      guilds = await loadMyGuilds();
    } catch (err) {
      if (seq !== openSeq) return false;
      guilds = [];
      current = null;
      rows = [];
      listState = "failed";
      renderList();
      renderGuild();
      showError(guildErrorMessage(err));
      return false;
    }
    if (seq !== openSeq) return false;

    listState = "ready";
    const still = guilds.some(g => g.guild.id === keep);
    current = still ? keep : (guilds[0] ? guilds[0].guild.id : null);
    renderList();
    await select(current);
    return true;
  }


  /* ---- actions on the selected guild ---- */

  async function act(button, label, fn, done) {
    if (busy) return;
    busy = true;
    const ours = session;
    clearMessages();
    if (button) acctBusy(button, label);

    try {
      const result = await fn();
      if (ours === session) await done(result);
    } catch (err) {
      if (ours === session) showError(guildErrorMessage(err));
    } finally {
      if (button) acctIdle(button);
      if (ours === session) busy = false;
    }
  }

  el.members.addEventListener("change", e => {
    const sel = e.target.closest("[data-gd-role]");
    if (!sel) return;
    const g = mine();
    if (!g) return;
    const userId = sel.dataset.gdRole;
    const row = rows.find(r => r.userId === userId);
    const role = sel.value;
    if (!row || role === row.role) return;

    act(null, "", () => setMemberRole(g.guild.id, userId, role), () => {
      row.role = role;
      rows = sortMemberRows(rows);
      renderGuild();
      announce(`${row.name} is now ${GUILD_ROLE_NAMES[role]}.`);
      showNotice(`${row.name} is now ${GUILD_ROLE_NAMES[role]}.`);
    }).then(() => {
      /* a refused change: the select shows the role still in force */
      if (el.notice.hidden && sel.isConnected) sel.value = row.role;
    });
  });

  el.members.addEventListener("click", e => {
    const b = e.target.closest("[data-gd-remove]");
    if (!b) return;
    const g = mine();
    if (!g) return;
    const userId = b.dataset.gdRemove;
    const row = rows.find(r => r.userId === userId);
    const isMe = account.user && userId === account.user.id;
    if (!row) return;

    const question = isMe ? `Leave ${g.guild.name}?` : `Remove ${row.name} from ${g.guild.name}?`;
    if (!window.confirm(question)) return;

    act(b, isMe ? "Leaving…" : "Removing…", () => removeMember(g.guild.id, userId), async () => {
      if (isMe) {
        announce(`You left ${g.guild.name}.`);
        if (await reload(null)) showNotice(`You left ${g.guild.name}.`);
      } else {
        rows = rows.filter(r => r.userId !== userId);
        renderGuild();
        announce(`${row.name} removed.`);
        showNotice(`${row.name} was removed from the guild.`);
      }
    });
  });

  el.leave.addEventListener("click", () => {
    const g = mine();
    if (!g || !account.user) return;
    if (!window.confirm(`Leave ${g.guild.name}?`)) return;
    act(el.leave, "Leaving…", () => leaveGuild(g.guild.id), async () => {
      if (await reload(null)) showNotice(`You left ${g.guild.name}.`);
    });
  });

  el.remove.addEventListener("click", () => {
    const g = mine();
    if (!g) return;
    if (!window.confirm(`Delete ${g.guild.name}? Every membership goes with it. This cannot be undone.`)) return;
    act(el.remove, "Deleting…", () => deleteGuild(g.guild.id), async () => {
      if (await reload(null)) showNotice(`${g.guild.name} was deleted.`);
    });
  });

  el.copy.addEventListener("click", async () => {
    const code = el.code.textContent.trim();
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code);
      showNotice("Join code copied.");
    } catch (err) {
      showError("The code could not be copied. Select it and copy it by hand.");
    }
  });

  el.renew.addEventListener("click", () => {
    const g = mine();
    if (!g) return;
    if (!window.confirm("Renew the join code? The current code stops working.")) return;
    act(el.renew, "Renewing…", () => renewJoinCode(g.guild.id), code => {
      el.code.textContent = code || "";
      showNotice("A new join code is in force.");
    });
  });

  el.renameForm.addEventListener("submit", e => {
    e.preventDefault();
    const g = mine();
    if (!g) return;
    const first = acctFlagFields({ name: el.renameName }, validateGuild({ name: el.renameName.value, albionServer: g.guild.albion_server }));
    if (first) { first.focus(); return; }
    const name = el.renameName.value.trim();
    if (name === g.guild.name) { showNotice("Nothing to save: the name is unchanged."); return; }

    act(el.renameSubmit, "Saving…", () => renameGuild(g.guild.id, name), row => {
      g.guild.name = row.name;
      renderList();
      renderGuild();
      showNotice("Guild renamed.");
    });
  });


  /* ---- create and join ---- */

  el.newForm.addEventListener("submit", e => {
    e.preventDefault();
    const fields = { name: el.newName, albionServer: el.newServer };
    const first = acctFlagFields(fields, validateGuild({ name: el.newName.value, albionServer: el.newServer.value }));
    if (first) { first.focus(); return; }

    act(el.newSubmit, "Creating…",
        () => createGuild({ name: el.newName.value, albionServer: el.newServer.value }),
        async guild => {
          el.newName.value = "";
          if (await reload(guild.id)) showNotice(`${guild.name} created. Share its join code from the guild's panel.`);
        });
  });

  el.joinForm.addEventListener("submit", e => {
    e.preventDefault();
    const first = acctFlagFields({ code: el.joinCode }, validateJoinCode(el.joinCode.value));
    if (first) { first.focus(); return; }

    act(el.joinSubmit, "Joining…", () => joinGuild(el.joinCode.value), async guild => {
      el.joinCode.value = "";
      if (await reload(guild.id)) showNotice(`You joined ${guild.name}.`);
    });
  });


  /* ---- open, close ---- */

  async function openGuilds() {
    if (!account.user) return;

    /* a reopened dialog starts idle (session) */
    session++;
    busy = false;
    for (const b of [el.leave, el.remove, el.renew, el.renameSubmit, el.newSubmit, el.joinSubmit]) acctIdle(b);
    const names = accountNames(account.profile, account.user);
    el.newServer.value = names.server || "";
    clearMessages();
    acctFlagFields({ name: el.newName, albionServer: el.newServer, code: el.joinCode }, {});
    guilds = [];
    rows = [];
    current = null;
    listState = "loading";
    renderList();
    renderGuild();

    if (!dialog.open) dialog.showModal();
    await reload(null);
  }

  acctWireDialog(dialog, { canClose: () => !busy });
  $id("guild-close").addEventListener("click", () => dialog.close());


  /* ---- identity ---- */

  window.Account.subscribe(state => {
    const was = account.user ? account.user.id : null;
    account = state;

    if (dialog.open && (!state.user || state.user.id !== was)) {
      dialog.close();
    }
  });

  window.Account.registerView("guilds", openGuilds);
})();
