"use strict";

/*
 * Import (platform phase 10): a caller's spreadsheet as a saved comp.
 * Callers keep comps in Excel, Google Sheets and Discord tables: one
 * weapon per row with a player, a role, a party or a count beside it,
 * or one column per party. This module reads pasted cells or a CSV
 * file, finds what each column holds, reads every weapon name through
 * the catalog, shows the uncertain ones for review, and saves the result
 * as a comp template through the comps module's helper. One way: the
 * sheet is read once; nothing syncs back.
 *
 * How a name is read (matchWeapon): the dataset key itself, the
 * catalog's display name, an alias (the guild's remembered names, then
 * a short built-in list), then the derivations in order: all the words,
 * a prefix, word prefixes, the initials, the key's own words, a text
 * inside the name, a close spelling. A derivation that leaves one
 * candidate is "likely" (accepted, marked for a glance); several are
 * "uncertain" (the caller chooses); none is "none" (an open slot, the
 * text kept as its note). A name a caller chooses for an uncertain or
 * unread text is remembered for the guild (weapon_aliases), so the next
 * import reads it. "1h" and "2h" narrow the pool to one-handed or
 * two-handed lines. Tier and enchantment words are dropped.
 *
 * build.py inlines this file as its own <script> after _history.js. It
 * reads no planner state and never calls the engine: roles are read
 * through the catalog (one role read). Three parts, as in _profile.js:
 *   helpers - the only code that talks to window.DB (weapon_aliases,
 *             save_weapon_aliases; the comp itself is saved through the
 *             comps module's saveTemplate)
 *   pure    - the parser, the column detection, the matcher, the slots,
 *             the learned names, error wording (tests/test_import.js)
 *   UI      - the import dialog the comps dialog opens (a comp-import
 *             DOM event; comp-imported goes back with the new comp)
 */


/* ------------------------------------------------------------ helpers */

/* the guild's remembered names, alphabetical */
async function loadGuildAliases(guildId) {
  const { data, error } = await window.DB
    .from("weapon_aliases")
    .select("alias, weapon_id, created_at")
    .eq("guild_id", guildId)
    .order("alias", { ascending: true });

  if (error) {
    throw error;
  }

  return data || [];
}


/* the names one import matched, saved in one transaction; returns how
   many were added or changed */
async function saveGuildAliases(guildId, pairs) {
  const { data, error } = await window.DB.rpc("save_weapon_aliases", {
    guild: guildId, aliases: aliasPayload(pairs)
  });

  if (error) {
    throw error;
  }

  return Number(data) || 0;
}


async function deleteGuildAlias(guildId, alias) {
  const { data, error } = await window.DB
    .from("weapon_aliases")
    .delete()
    .eq("guild_id", guildId)
    .eq("alias", alias)
    .select("alias");

  if (error) {
    throw error;
  }

  if (!data || !data.length) {
    throw guildRefusal();
  }

  return data[0];
}


/* --------------------------------------------------------------- pure */

/* The database's bounds (supabase/migrations weapon_aliases;
   tests/test_supabase_schema.py pins that they agree). */
const ALIAS_MAX = 64;
const ALIASES_MAX = 500;
const ALIAS_SAVE_MAX = 100;
const ALIAS_RE = /^[a-z0-9]+( [a-z0-9]+)*$/;

/* what one import reads (display bounds, not the database's) */
const IMPORT_TEXT_MAX = 200000;
const IMPORT_ROWS_MAX = 500;
const IMPORT_CANDIDATES = 8;

/* a row's choice beyond a weapon key */
const IMPORT_OPEN = "_open";
const IMPORT_SKIP = "_skip";

/* what a column holds, as the caller may set it */
const COLUMN_KINDS = ["ignore", "weapon", "player", "role", "party", "count", "note", "position"];
const COLUMN_KIND_NAMES = {
  ignore: "ignored", weapon: "weapon", player: "player", role: "role", party: "party",
  count: "count", note: "note", position: "slot number"
};

/* header cells, lower-cased and stripped of punctuation, that name a
   column's kind; "number" is a slot number or a count, decided by the
   cells (1, 2, 3 in order is a slot number) */
const HEADER_WORDS = {
  weapon: ["weapon", "weapons", "build", "builds", "comp", "gear", "line", "weapon line", "wpn", "set", "kit", "class"],
  player: ["player", "players", "name", "names", "ign", "character", "char", "who", "member", "members", "nick", "nickname", "discord", "user"],
  role: ["role", "roles", "job", "duty", "type", "spot"],
  party: ["party", "parties", "group", "groups", "grp", "squad", "team", "pt"],
  count: ["count", "qty", "quantity", "amount", "number", "num", "n", "x", "copies", "slots", "how many"],
  note: ["note", "notes", "comment", "comments", "remark", "remarks", "info", "description", "desc", "extra"],
  number: ["#", "no", "nr", "idx", "index", "slot", "seat", "pos", "position"]
};

/* a party label: "Party 1", "P2", "Group A", "Squad 3", "Team B" */
const PARTY_LABEL_RE = /^(?:party|group|grp|squad|team|pt|p|g)\s*[-#:.]?\s*(?:\d{1,2}|[a-z])$/i;

/* a caller's role words: a section row or a role label, never a weapon */
const ROLE_WORDS = new Set([
  "tank", "tanks", "frontline", "front", "heal", "heals", "healer", "healers", "dps", "damage", "support", "supports", "supp",
  "ranged", "range", "melee", "bomb", "bombs", "bomb squad", "bombsquad", "caller", "callers", "shotcaller", "e caller", "ecaller",
  "engage caller", "scout", "scouts", "reserve", "reserves", "backline", "engage", "kite", "clap", "brawl", "def", "defense",
  "defence", "flank", "flanks", "flex", "fill", "utility", "cc", "debuff", "debuffs", "buff", "buffs", "purge", "roots"
]);

/* words a sheet writes beside a weapon that say nothing about the line:
   tiers, enchantments and quality */
const TIER_WORDS = new Set(["t4", "t5", "t6", "t7", "t8", "novice", "journeyman", "adept", "expert", "master", "grandmaster",
                            "elder", "elders", "flat", "the"]);

/* a sheet's spellings the catalog's names do not use */
const TEXT_SYNONYMS = { xbow: "crossbow", xbows: "crossbows", "1hand": "1h", "2hand": "2h", onehand: "1h", twohand: "2h",
                        onehanded: "1h", twohanded: "2h", "1handed": "1h", "2handed": "2h" };

/* the words a dataset key adds beyond the display name; a family marker
   alone (avalon, hell) names no line */
const KEY_FAMILY_TOKENS = new Set(["2h", "main", "avalon", "hell", "morgana", "undead", "keeper", "crystal", "set1", "set2", "set3"]);

/* Names the derivations cannot read: a dual line whose catalog name is
   its own word (curation judgment; the community's plural). A guild's
   remembered names override them. */
const WEAPON_NICKNAMES = {
  "daggers": "2H_DAGGERPAIR", "dual daggers": "2H_DAGGERPAIR", "dual dagger": "2H_DAGGERPAIR",
  "maces": "2H_DUALMACE_AVALON", "dual maces": "2H_DUALMACE_AVALON", "dual mace": "2H_DUALMACE_AVALON",
  "axes": "2H_DUALAXE_KEEPER", "dual axes": "2H_DUALAXE_KEEPER", "dual axe": "2H_DUALAXE_KEEPER"
};


/* A sheet's text as the matcher and the alias table read it: lower
   case, accents dropped, "one-handed" and "two-handed" as 1h and 2h,
   letters and digits only, single spaces; tier, enchantment and quality
   words gone ("8.3 Elder's Hallowfall" -> "hallowfall"). */
function normalizeWeaponText(text) {
  let s = String(text == null ? "" : text).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  s = s.replace(/&/g, " and ").replace(/'s\b/g, "");
  s = s.replace(/\b(one|two)[\s-]*(?:handed|hand|h)\b/g, (m, word) => (word === "one" ? "1h" : "2h"));
  s = s.replace(/\b([12])\s*-\s*h\b/g, "$1h");
  s = s.replace(/[^a-z0-9]+/g, " ");
  const tokens = s.trim().split(/\s+/).filter(Boolean)
    .map(t => TEXT_SYNONYMS[t] || t)
    .filter(t => !TIER_WORDS.has(t) && !/^\d{1,2}$/.test(t));
  return tokens.join(" ");
}


/* One cell's weapon text: a list marker dropped ("1. ", "- "), a count
   read ("Longbow x3", "3x Longbow", "Longbow (2)"), and what follows a
   dash or a colon kept apart as the tail ("Longbow - Disc"). */
function parseSlotText(text) {
  let s = String(text == null ? "" : text).trim().replace(/^(?:\d{1,2}[.):]|[-*•>]+)\s+/, "");
  let count = 1;
  let tail = "";
  let m = s.match(/^(\d{1,2})\s*[x×*]\s*(.+)$/i);
  if (m) {
    count = Number(m[1]);
    s = m[2].trim();
  } else if ((m = s.match(/^(.+?)\s*(?:[x×*]\s*(\d{1,2})|\(\s*x?\s*(\d{1,2})\s*\))$/i))) {
    count = Number(m[2] || m[3]);
    s = m[1].trim();
  }
  const split = s.split(/\s+[-–—]\s+|:\s+/);
  if (split.length > 1) {
    s = split[0].trim();
    tail = split.slice(1).join(" - ").trim();
    /* a tail that is only a tier or an enchantment ("Longbow: 8.3") names nobody */
    if (!normalizeWeaponText(tail)) tail = "";
  }
  return { name: s, count: Math.min(Math.max(count || 1, 1), COMP_SLOTS_MAX), tail };
}


function isPartyLabel(text) {
  return PARTY_LABEL_RE.test(String(text == null ? "" : text).trim());
}


function isRoleWord(text) {
  const t = String(text == null ? "" : text).trim().toLowerCase().replace(/[^a-z ]+/g, " ").replace(/\s+/g, " ").trim();
  return ROLE_WORDS.has(t);
}


/* the kind a header cell names, or null */
function headerKind(cell) {
  const t = String(cell == null ? "" : cell).trim().toLowerCase().replace(/[^a-z0-9# ]+/g, " ").replace(/\s+/g, " ").trim();
  if (!t) return null;
  if (isPartyLabel(t)) return "weapon";
  for (const [kind, words] of Object.entries(HEADER_WORDS)) {
    if (words.includes(t)) return kind;
  }
  return null;
}


/* the column letter a caller sees in a spreadsheet: A, B, ..., Z, AA */
function columnLetter(index) {
  let n = Number(index) || 0;
  let out = "";
  do {
    out = String.fromCharCode(65 + (n % 26)) + out;
    n = Math.floor(n / 26) - 1;
  } while (n >= 0);
  return out;
}


/* the delimiter a pasted sheet uses: a tab (Excel and Sheets copy cells
   as tab-separated), a pipe (a Discord or Markdown table), a semicolon
   or a comma (CSV); none for one column of lines */
function detectDelimiter(text) {
  const lines = String(text || "").split(/\r\n|\r|\n/).filter(l => l.trim()).slice(0, 20);
  if (!lines.length) return "";
  if (lines.some(l => l.includes("\t"))) return "\t";
  const pipes = lines.filter(l => (l.match(/\|/g) || []).length >= 2).length;
  if (pipes >= Math.ceil(lines.length / 2)) return "|";
  const count = ch => lines.filter(l => l.includes(ch)).length;
  const commas = count(",");
  const semis = count(";");
  if (!commas && !semis) return "";
  return semis > commas ? ";" : ",";
}


/* pasted or uploaded text -> cells (RFC 4180 quoting; CRLF, CR or LF
   line ends; a Markdown table's edge pipes and rule line dropped; a
   code fence dropped; empty rows dropped); bounded */
function parseSheet(text) {
  const src = String(text == null ? "" : text);
  const cut = src.length > IMPORT_TEXT_MAX;
  const body = cut ? src.slice(0, IMPORT_TEXT_MAX) : src;
  const delimiter = detectDelimiter(body);
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;

  for (let i = 0; i < body.length; i++) {
    const ch = body[i];
    if (quoted) {
      if (ch === '"') {
        if (body[i + 1] === '"') { cell += '"'; i++; }
        else quoted = false;
      } else {
        cell += ch;
      }
      continue;
    }
    if (ch === '"' && cell === "") { quoted = true; continue; }
    if (delimiter && ch === delimiter) { row.push(cell); cell = ""; continue; }
    if (ch === "\r" || ch === "\n") {
      if (ch === "\r" && body[i + 1] === "\n") i++;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
      continue;
    }
    cell += ch;
  }
  if (cell !== "" || row.length) { row.push(cell); rows.push(row); }

  let cells = rows.map(r => r.map(c => c.trim()));
  if (delimiter === "|") {
    cells = cells
      .map(r => { if (r.length && r[0] === "") r = r.slice(1); if (r.length && r[r.length - 1] === "") r = r.slice(0, -1); return r; })
      .filter(r => !r.every(c => /^:?-{2,}:?$/.test(c)));
  }
  cells = cells.filter(r => r.some(Boolean) && !(r.length === 1 && /^`{3}/.test(r[0])));
  const total = cells.length;
  return { delimiter, cells: cells.slice(0, IMPORT_ROWS_MAX), rows: total, cut: cut || total > IMPORT_ROWS_MAX };
}


/* the Levenshtein distance between two short strings */
function editDistance(a, b) {
  if (a === b) return 0;
  if (!a.length || !b.length) return a.length + b.length;
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    prev = cur;
  }
  return prev[b.length];
}


/* The catalog as the matcher reads it, built once per import: each line
   (removed lines left out) with its normalized name, its words, its
   initials, the words of its key and its hand; the alias table (the
   built-in nicknames, then the guild's names, which win). */
function weaponIndex(catalog, aliases) {
  const entries = [];
  const byKey = new Set();
  const byName = new Map();

  for (const [key, entry] of Object.entries(catalog || {})) {
    if (!entry || entry.removed || !WEAPON_KEY_RE.test(key)) continue;
    const name = String(entry.name || key);
    const norm = normalizeWeaponText(name);
    const tokens = norm.split(" ").filter(Boolean);
    entries.push({
      key, name, norm, tokens,
      compact: norm.replace(/ /g, ""),
      initials: tokens.length >= 2 ? tokens.map(t => t[0]).join("") : "",
      keyTokens: key.toLowerCase().split("_").filter(t => t && !KEY_FAMILY_TOKENS.has(t)),
      hand: key.startsWith("MAIN_") ? "1h" : key.startsWith("2H_") ? "2h" : null
    });
    byKey.add(key);
    byName.set(norm, key);
  }

  const aliasMap = new Map();
  for (const [alias, key] of Object.entries(WEAPON_NICKNAMES)) {
    if (byKey.has(key)) aliasMap.set(normalizeWeaponText(alias), key);
  }
  for (const a of aliases || []) {
    const norm = normalizeWeaponText(a && a.alias);
    const key = String((a && a.weapon_id) || "");
    if (norm && byKey.has(key)) aliasMap.set(norm, key);
  }

  return { entries, byKey, byName, aliases: aliasMap };
}


function noMatch() {
  return { status: "none", key: null, how: null, candidates: [] };
}


/* one sheet text -> { status: exact | alias | likely | uncertain | none,
   key, how, candidates } */
function matchWeapon(text, index) {
  const raw = String(text == null ? "" : text).trim();
  if (!raw || !index) return noMatch();

  const upper = raw.toUpperCase().replace(/\s+/g, "_");
  if (index.byKey.has(upper)) return { status: "exact", key: upper, how: "key", candidates: [upper] };

  const norm = normalizeWeaponText(raw);
  if (!norm) return noMatch();
  const named = index.byName.get(norm);
  if (named) return { status: "exact", key: named, how: "name", candidates: [named] };
  const alias = index.aliases.get(norm);
  if (alias) return { status: "alias", key: alias, how: "alias", candidates: [alias] };

  let tokens = norm.split(" ");
  const hand = tokens.includes("1h") ? "1h" : tokens.includes("2h") ? "2h" : null;
  tokens = tokens.filter(t => t !== "1h" && t !== "2h");
  if (!tokens.length) return noMatch();
  const joined = tokens.join(" ");
  const compact = joined.replace(/ /g, "");
  const pool = index.entries.filter(e => !hand || e.hand === hand);

  const exact = pool.filter(e => e.norm === joined || e.compact === compact);
  if (exact.length === 1) return { status: "exact", key: exact[0].key, how: "name", candidates: [exact[0].key] };

  const near = joined.length < 8 ? 1 : 2;
  const tiers = [
    ["words", e => tokens.every(t => e.tokens.includes(t))],
    ["prefix", e => joined.length >= 3 && (e.norm.startsWith(joined) || e.compact.startsWith(compact))],
    ["word-prefix", e => joined.length >= 3 && tokens.every(t => e.tokens.some(n => n.startsWith(t)))],
    ["initials", e => tokens.length === 1 && e.initials !== ""
                      && (e.initials === joined || (e.tokens[e.tokens.length - 1] === "staff" && e.initials.slice(0, -1) === joined))],
    ["key", e => tokens.every(t => e.keyTokens.includes(t))],
    ["inside", e => joined.length >= 4 && e.norm.includes(joined)],
    ["close", e => editDistance(compact, e.compact) <= near]
  ];

  for (const [how, test] of tiers) {
    const hits = pool.filter(test);
    if (!hits.length) continue;
    const keys = hits.map(e => e.key);
    if (hits.length === 1) {
      const sure = how !== "close" || editDistance(compact, hits[0].compact) <= 1;
      return { status: sure ? "likely" : "uncertain", key: sure ? hits[0].key : null, how, candidates: keys };
    }
    /* several: the plain line named "<text> Staff" decides (arcane ->
       Arcane Staff, not Great Arcane Staff); else the caller does */
    const plain = hits.filter(e => e.norm === `${joined} staff`);
    if (plain.length === 1) {
      return { status: "likely", key: plain[0].key, how,
               candidates: [plain[0].key, ...keys.filter(k => k !== plain[0].key)].slice(0, IMPORT_CANDIDATES) };
    }
    return { status: "uncertain", key: null, how, candidates: keys.slice(0, IMPORT_CANDIDATES) };
  }

  return noMatch();
}


/* what a column's cells look like */
function columnStats(values, index) {
  const n = values.length;
  const s = { n, weapon: 0, integer: 0, party: 0, role: 0, sequential: false, words: 0, length: 0 };
  if (!n) return s;
  let seq = true;
  values.forEach((v, i) => {
    const m = matchWeapon(parseSlotText(v).name, index);
    if (m.status === "exact" || m.status === "alias" || m.status === "likely") s.weapon += 1;
    if (/^\d{1,3}$/.test(v)) {
      s.integer += 1;
      if (Number(v) !== i + 1) seq = false;
    } else {
      seq = false;
    }
    if (isPartyLabel(v)) s.party += 1;
    if (isRoleWord(v)) s.role += 1;
    s.words += v.split(/\s+/).length;
    s.length += v.length;
  });
  s.sequential = seq && n >= 2;
  s.words /= n;
  s.length /= n;
  return s;
}


function kindFromStats(s) {
  if (!s.n) return "ignore";
  if (s.weapon / s.n >= 0.5) return "weapon";
  if (s.integer / s.n >= 0.8) return s.sequential ? "position" : "count";
  if (s.party / s.n >= 0.6) return "party";
  if (s.role / s.n >= 0.6) return "role";
  return s.words <= 2 && s.length <= 20 ? "player" : "note";
}


/* What each column holds. A header row (one of the first three rows,
   naming a kind and holding no weapon) decides where it can; the cells
   decide the rest: mostly weapons -> weapon, integers -> a slot number
   (1, 2, 3 in order) or a count, party labels -> party, role words ->
   role, short texts -> player, long ones -> note. Two or more weapon
   columns are parties side by side (grid); one is a list. */
function detectColumns(cells, index) {
  const width = (cells || []).reduce((w, r) => Math.max(w, r.length), 0);
  const nonEmpty = [];
  (cells || []).forEach((r, i) => { if (nonEmpty.length < 3 && r.some(Boolean)) nonEmpty.push(i); });
  if (!nonEmpty.length) return { header: false, headerAt: -1, bodyFrom: 0, kinds: [], labels: [] };

  const isWeapon = c => c && ["exact", "alias"].includes(matchWeapon(parseSlotText(c).name, index).status);
  let headerAt = -1;
  for (const i of nonEmpty) {
    const r = cells[i];
    const filled = r.filter(Boolean);
    if (filled.length === 1 && isPartyLabel(filled[0])) continue;
    if (r.map(headerKind).some(Boolean) && !r.some(isWeapon)) { headerAt = i; break; }
  }
  const bodyFrom = headerAt >= 0 ? headerAt + 1 : nonEmpty[0];
  const head = headerAt >= 0 ? cells[headerAt] : [];
  const body = cells.slice(bodyFrom);
  const kinds = [];

  for (let col = 0; col < width; col++) {
    const values = body.map(r => String(r[col] == null ? "" : r[col]).trim()).filter(Boolean);
    const stats = columnStats(values, index);
    let kind = headerAt >= 0 ? headerKind(head[col]) : null;
    if ((kind === "number" || kind === "count") && stats.n && stats.integer < stats.n) kind = null;
    if (kind === "number") kind = stats.sequential ? "position" : "count";
    if (!kind) kind = kindFromStats(stats);
    kinds.push(kind);
  }

  return { header: headerAt >= 0, headerAt, bodyFrom, kinds,
           labels: head.map(c => String(c == null ? "" : c).trim()) };
}


function layoutMode(kinds) {
  return (kinds || []).filter(k => k === "weapon").length > 1 ? "grid" : "list";
}


/* The sheet as slot rows: each with its text, its count, the player,
   role, party and note beside it, and how the text was read. A list
   reads one weapon column (a row with one cell that is a party label or
   a role word opens a section for the rows below); a grid reads every
   weapon column in turn, each a party, its player, role, count and note
   columns the ones to its right, a column left of the first party
   shared by all. */
function sheetRows(cells, layout, index) {
  const kinds = (layout && layout.kinds) || [];
  const labels = (layout && layout.labels) || [];
  const bodyFrom = (layout && layout.bodyFrom) || 0;
  const weaponCols = kinds.map((k, i) => (k === "weapon" ? i : -1)).filter(i => i >= 0);
  const out = [];
  if (!weaponCols.length) return out;

  const at = (r, i) => (i >= 0 && r[i] != null ? String(r[i]).trim() : "");
  const body = (cells || []).slice(bodyFrom);
  const clampCount = n => Math.min(Math.max(Number(n) || 1, 1), COMP_SLOTS_MAX);

  const make = (rowIndex, col, text, extra) => {
    const parsed = parseSlotText(text);
    let name = parsed.name;
    let tail = parsed.tail;
    let match = name ? matchWeapon(name, index) : noMatch();
    if (tail && (match.status === "none" || match.status === "uncertain")) {
      const swapped = matchWeapon(tail, index);
      if (["exact", "alias", "likely"].includes(swapped.status)) {
        [name, tail] = [tail, name];
        match = swapped;
      }
    }
    const player = extra.player || (tail && !isRoleWord(tail) ? tail : "");
    const role = extra.role || (tail && isRoleWord(tail) ? tail : "") || extra.fallbackRole || "";
    const count = extra.count != null ? extra.count : parsed.count;
    return { row: rowIndex, col, text: name, count: clampCount(count), player, role,
             party: extra.party || "", note: extra.note || "", match };
  };

  if (weaponCols.length === 1) {
    const wc = weaponCols[0];
    const colOf = kind => kinds.indexOf(kind);
    const pc = colOf("player"), rc = colOf("role"), yc = colOf("party"), cc = colOf("count"), nc = colOf("note");
    let party = "";
    let role = "";

    body.forEach((r, i) => {
      const filled = r.map((c, j) => (c ? j : -1)).filter(j => j >= 0);
      if (!filled.length) return;
      if (filled.length === 1) {
        const t = at(r, filled[0]);
        const [head, rest] = t.split(/\s*[:\-–—]\s*/, 2).map(x => (x || "").trim());
        if (yc < 0 && isPartyLabel(head)) {
          party = head;
          role = rest && isRoleWord(rest) ? rest : "";
          return;
        }
        if (rc < 0 && isRoleWord(t) && matchWeapon(t, index).status === "none") {
          role = t;
          return;
        }
      }
      const rawCount = cc >= 0 ? at(r, cc) : "";
      const row = make(bodyFrom + i, wc, at(r, wc), {
        player: at(r, pc), role: at(r, rc), fallbackRole: rc >= 0 ? "" : role,
        party: yc >= 0 ? at(r, yc) : party,
        count: /^\d{1,2}$/.test(rawCount) ? Number(rawCount) : null, note: at(r, nc)
      });
      if (!row.text && !row.player && !row.note) return;
      out.push(row);
    });
    return out;
  }

  const shared = kind => { for (let j = 0; j < weaponCols[0]; j++) if (kinds[j] === kind) return j; return -1; };
  const sharedRole = shared("role"), sharedCount = shared("count"), sharedNote = shared("note");
  weaponCols.forEach((wc, n) => {
    const next = weaponCols[n + 1] != null ? weaponCols[n + 1] : kinds.length;
    const attached = kind => { for (let j = wc + 1; j < next; j++) if (kinds[j] === kind) return j; return -1; };
    const pc = attached("player");
    const rc = attached("role") >= 0 ? attached("role") : sharedRole;
    const cc = attached("count") >= 0 ? attached("count") : sharedCount;
    const nc = attached("note") >= 0 ? attached("note") : sharedNote;
    const hdr = labels[wc] || "";
    const label = hdr && !HEADER_WORDS.weapon.includes(hdr.toLowerCase()) ? hdr : `Party ${n + 1}`;
    body.forEach((r, i) => {
      const rawCount = cc >= 0 ? at(r, cc) : "";
      const row = make(bodyFrom + i, wc, at(r, wc), {
        player: at(r, pc), role: at(r, rc), party: label,
        count: /^\d{1,2}$/.test(rawCount) ? Number(rawCount) : null, note: at(r, nc)
      });
      if (!row.text && !row.player) return;
      out.push(row);
    });
  });
  return out;
}


/* the choice a row starts with: its key when the text was read, nothing
   when the caller must choose, an open slot when nothing matched */
function defaultChoice(row) {
  const m = (row && row.match) || {};
  if (m.status === "exact" || m.status === "alias" || m.status === "likely") return m.key;
  if (m.status === "uncertain") return "";
  return IMPORT_OPEN;
}


/* the counts a review shows */
function importSummary(rows) {
  const s = { rows: 0, slots: 0, matched: 0, likely: 0, uncertain: 0, none: 0 };
  for (const row of rows || []) {
    s.rows += 1;
    s.slots += row.count || 1;
    const status = (row.match && row.match.status) || "none";
    if (status === "exact" || status === "alias") s.matched += 1;
    else if (status === "likely") s.likely += 1;
    else if (status === "uncertain") s.uncertain += 1;
    else s.none += 1;
  }
  return s;
}


/* The reviewed rows as a comp's slots: a key, an open slot (the text
   kept as the note unless it is a role word, which becomes the role) or
   a skipped row; a count repeats the slot; player names and party
   labels ride in the note when asked (a template has no player and no
   party); bounded by the roster cap. */
function importSlots(rows, choices, options) {
  const opts = Object.assign({ players: false, parties: true }, options || {});
  const slots = [];
  const parties = [];
  for (const row of rows || []) {
    if (row.party && !parties.includes(row.party)) parties.push(row.party);
  }
  const keepParty = opts.parties && parties.length > 1;
  let skipped = 0, unresolved = 0, open = 0, overflow = 0;
  const cut = (text, max) => (text ? Array.from(text).slice(0, max).join("") : null);

  (rows || []).forEach((row, i) => {
    const choice = choices && choices[i] != null ? choices[i] : defaultChoice(row);
    if (choice === IMPORT_SKIP) { skipped += row.count; return; }
    if (choice === "") { unresolved += 1; return; }
    const weapon_id = choice === IMPORT_OPEN ? null : choice;
    const role = row.role || (!weapon_id && isRoleWord(row.text) ? row.text : "");
    const status = (row.match && row.match.status) || "none";
    const unplaced = !weapon_id && row.text && !isRoleWord(row.text) && (status === "none" || status === "uncertain");
    const noteParts = [row.note, opts.players && row.player ? row.player : "", keepParty ? row.party : "",
                       unplaced ? row.text : ""].filter(Boolean);
    const note = noteParts.length ? cut(noteParts.join(" · "), COMP_NOTE_MAX) : null;
    for (let n = 0; n < row.count; n++) {
      if (slots.length >= COMP_SLOTS_MAX) { overflow += 1; continue; }
      if (!weapon_id) open += 1;
      slots.push({ position: slots.length + 1, weapon_id, role: cut(role, COMP_ROLE_MAX), note });
    }
  });

  return { slots, skipped, unresolved, open, overflow, parties };
}


/* The names to remember: a text the matcher could not read, or read
   differently, that the caller gave a weapon; never a catalog name, an
   open slot or a skipped row. Later rows win; bounded by the save. */
function learnedAliases(rows, choices, index) {
  const out = new Map();
  (rows || []).forEach((row, i) => {
    const choice = choices && choices[i] != null ? choices[i] : defaultChoice(row);
    if (!choice || choice === IMPORT_OPEN || choice === IMPORT_SKIP) return;
    const m = row.match || {};
    if (m.key === choice && m.status !== "uncertain") return;
    const alias = normalizeWeaponText(row.text);
    if (!alias || alias.length > ALIAS_MAX || !ALIAS_RE.test(alias)) return;
    if (index && index.byName.has(alias)) return;
    out.set(alias, choice);
  });
  return [...out].slice(0, ALIAS_SAVE_MAX).map(([alias, weapon_id]) => ({ alias, weapon_id }));
}


/* the save_weapon_aliases payload: normalized, on the form, keys only */
function aliasPayload(pairs) {
  return (pairs || [])
    .map(p => ({ alias: normalizeWeaponText(p && p.alias), weapon_id: String((p && p.weapon_id) || "") }))
    .filter(p => p.alias && p.alias.length <= ALIAS_MAX && ALIAS_RE.test(p.alias) && WEAPON_KEY_RE.test(p.weapon_id))
    .slice(0, ALIAS_SAVE_MAX);
}


/* a file as text; an Excel workbook is refused with the way round */
function readSheetFile(file) {
  return new Promise((resolve, reject) => {
    if (!file) { reject(importError("empty")); return; }
    if (/\.xlsx?$/i.test(String(file.name || "")) || /spreadsheetml|ms-excel/.test(String(file.type || ""))) {
      reject(importError("xlsx"));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(importError("unreadable"));
    reader.readAsText(file);
  });
}


const IMPORT_MSG = {
  network: PROFILE_MSG.network,
  signedOut: "Log in to import a comp.",
  session: PROFILE_MSG.session,
  missing: "Importing is not available yet: the account database has not been updated for this page. Try again later.",
  refused: "The server refused the change: your role in this guild does not import comps, or the guild has changed. Reload and try again.",
  tooManyAliases: `A guild remembers at most ${ALIASES_MAX} names. Remove some below, then import again.`,
  invalid: "The server refused a value. Check the names, then try again.",
  xlsx: "An Excel workbook cannot be read here. Copy its cells and paste them, or save the sheet as CSV first.",
  unreadable: "The file could not be read. Copy its cells and paste them instead.",
  empty: "Nothing to read: paste the sheet's cells or open a CSV file.",
  noWeapons: "No weapon column found. Set a column to weapon below, or check the sheet.",
  unresolved: "Choose a weapon for every row marked choose, or set it to an open slot or skip.",
  unknown: PROFILE_MSG.unknown
};


function importError(kind) {
  const err = new Error(IMPORT_MSG[kind] || String(kind));
  err.code = kind;
  return err;
}


function importErrorKind(err) {
  const code = String((err && err.code) || "");
  const message = String((err && err.message) || "");

  if (authErrorKind(err) === "network") return "network";
  if (Object.prototype.hasOwnProperty.call(IMPORT_MSG, code) && code !== "unknown") return code;
  if (code === "not_signed_in" || (code === "42501" && /sign in/i.test(message))) return "signedOut";
  if (/^PGRST30\d$/.test(code) || /jwt expired/i.test(message)) return "session";
  if (code === "PGRST202" || code === "PGRST205" || code === "42883" || code === "42P01") return "missing";
  if (code === "23514" && /at most \d+ aliases/i.test(message)) return "tooManyAliases";
  if (code === "42501" || code === "refused") return "refused";
  if (code === "23514" || code === "22023" || code === "23502" || code === "22001" || code === "22P02" || code === "21000") return "invalid";

  return "unknown";
}


function importErrorMessage(err) {
  const kind = importErrorKind(err);
  const message = String((err && err.message) || "").trim();

  if (kind === "unknown" && message) {
    return `Something went wrong: ${message}`;
  }

  return IMPORT_MSG[kind];
}


/* ----------------------------------------------------------------- UI */

(function importUI() {
  if (typeof document === "undefined") {
    return;
  }

  const $id = id => document.getElementById(id);
  const dialog = $id("import-dialog");

  if (!dialog || typeof dialog.showModal !== "function" || !window.Account) {
    return;
  }

  const CATALOG = typeof ACCOUNT_CATALOG !== "undefined" ? ACCOUNT_CATALOG : {};
  const CONTENTS = typeof ACCOUNT_CONTENTS !== "undefined" ? ACCOUNT_CONTENTS : {};
  const STYLES = typeof ACCOUNT_STYLES !== "undefined" ? ACCOUNT_STYLES : {};

  const el = {
    error: $id("im-error"),
    notice: $id("im-notice"),
    live: $id("im-live"),
    form: $id("im-form"),
    guild: $id("im-guild"),
    text: $id("im-text"),
    file: $id("im-file"),
    read: $id("im-read"),
    result: $id("im-result"),
    summary: $id("im-summary"),
    columns: $id("im-columns"),
    rows: $id("im-rows"),
    remember: $id("im-remember"),
    playersWrap: $id("im-players-wrap"),
    players: $id("im-players"),
    partiesWrap: $id("im-parties-wrap"),
    parties: $id("im-parties"),
    name: $id("im-name"),
    content: $id("im-content"),
    style: $id("im-style"),
    size: $id("im-size"),
    footNote: $id("im-foot-note"),
    save: $id("im-save"),
    aliasesWrap: $id("im-aliases-wrap"),
    aliasesCount: $id("im-aliases-count"),
    aliases: $id("im-aliases")
  };

  const FIELDS = { name: el.name, content: el.content, style: el.style, plannedSize: el.size };
  const STATUS_LABELS = { exact: "matched", alias: "remembered", likely: "check", uncertain: "choose", none: "no match" };

  let account = window.Account.current();
  let guilds = [];          /* [{guild, role}] the account writes comps in */
  let aliases = [];         /* the selected guild's remembered names */
  let index = null;         /* the catalog as the matcher reads it */
  let cells = [];           /* the sheet as read */
  let layout = null;        /* the columns' kinds */
  let rows = [];            /* the slot rows */
  let choices = [];         /* the caller's choice per row */
  let sourceName = "";      /* the file's name, for the comp's name */
  let busy = false;
  let openSeq = 0;

  const showError = message => acctMessage(el.error, el.notice, "error", message);
  const showNotice = message => acctMessage(el.error, el.notice, "notice", message);
  const clearMessages = () => acctMessage(el.error, el.notice, null, "");
  const announce = text => { el.live.textContent = text; };
  const guildId = () => el.guild.value || null;

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

  const WEAPON_GROUPS = weaponOptions(CATALOG);


  /* ---- the guild and its names ---- */

  function paintGuilds() {
    el.guild.replaceChildren(...guilds.map(({ guild, role }) => {
      const o = document.createElement("option");
      o.value = guild.id;
      o.textContent = `${guild.name} (${GUILD_ROLE_NAMES[role] || role})`;
      return o;
    }));
    el.guild.disabled = !guilds.length;
  }

  function paintAliases() {
    el.aliasesCount.textContent = aliases.length ? `(${aliases.length})` : "";
    el.aliases.replaceChildren(...aliases.map(a => {
      const li = document.createElement("li");
      li.className = "gd-weapon im-alias";
      const text = document.createElement("span");
      text.textContent = a.alias;
      const arrow = document.createElement("span");
      arrow.className = "gd-sub";
      arrow.textContent = weaponInfo(CATALOG, a.weapon_id).name;
      li.append(text, arrow);
      const b = document.createElement("button");
      b.type = "button";
      b.className = "gd-btn im-alias-drop";
      b.dataset.imAlias = a.alias;
      b.setAttribute("aria-label", `forget ${a.alias}`);
      b.textContent = "×";
      li.append(b);
      return li;
    }));
    if (!aliases.length) {
      const li = document.createElement("li");
      li.className = "gd-none";
      li.textContent = "No remembered names yet. A name you choose during an import is kept here.";
      el.aliases.append(li);
    }
  }

  el.aliases.addEventListener("click", async e => {
    const b = e.target.closest("[data-im-alias]");
    if (!b || busy || !guildId()) return;
    const alias = b.dataset.imAlias;
    busy = true;
    acctBusy(b, "…");
    try {
      await deleteGuildAlias(guildId(), alias);
      aliases = aliases.filter(a => a.alias !== alias);
      index = weaponIndex(CATALOG, aliases);
      paintAliases();
      if (cells.length) rereadRows();
      announce(`${alias} forgotten.`);
    } catch (err) {
      showError(importErrorMessage(err));
    } finally {
      busy = false;
      acctIdle(b);
    }
  });

  async function reloadAliases() {
    const seq = ++openSeq;
    aliases = [];
    index = weaponIndex(CATALOG, aliases);
    paintAliases();
    if (!guildId()) return;
    try {
      aliases = await loadGuildAliases(guildId());
    } catch (err) {
      if (seq !== openSeq) return;
      showError(importErrorMessage(err));
      return;
    }
    if (seq !== openSeq) return;
    index = weaponIndex(CATALOG, aliases);
    paintAliases();
    if (cells.length) rereadRows();
  }

  el.guild.addEventListener("change", () => { if (!busy) reloadAliases(); });


  /* ---- reading the sheet ---- */

  function readText(text) {
    clearMessages();
    const parsed = parseSheet(text);
    if (!parsed.cells.length) {
      cells = [];
      layout = null;
      rows = [];
      choices = [];
      paintResult();
      showError(IMPORT_MSG.empty);
      return;
    }
    cells = parsed.cells;
    layout = detectColumns(cells, index);
    rereadRows();
    if (parsed.cut) showNotice(`The sheet was cut at ${IMPORT_ROWS_MAX} rows.`);
    const s = importSummary(rows);
    announce(`${s.rows} rows read, ${s.uncertain} to choose.`);
    if (!rows.length && !layout.kinds.includes("weapon")) showError(IMPORT_MSG.noWeapons);
  }

  function rereadRows() {
    rows = layout ? sheetRows(cells, layout, index) : [];
    choices = rows.map(defaultChoice);
    if (!el.size.value || el.size.dataset.auto === "yes") {
      el.size.value = String(Math.min(Math.max(importSummary(rows).slots, COMP_SIZE_MIN), COMP_SLOTS_MAX));
      el.size.dataset.auto = "yes";
    }
    paintResult();
  }

  el.read.addEventListener("click", () => { if (!busy) readText(el.text.value); });
  el.text.addEventListener("paste", () => { setTimeout(() => { if (!busy && el.text.value.trim()) readText(el.text.value); }, 0); });

  el.file.addEventListener("change", async () => {
    const file = el.file.files && el.file.files[0];
    if (!file || busy) return;
    try {
      const text = await readSheetFile(file);
      sourceName = String(file.name || "").replace(/\.[^.]+$/, "");
      el.text.value = text;
      if (!el.name.value) el.name.value = sourceName.slice(0, ACCOUNT_NAME_MAX);
      readText(text);
    } catch (err) {
      showError(importErrorMessage(err));
    } finally {
      el.file.value = "";
    }
  });


  /* ---- the review ---- */

  function paintColumns() {
    const kinds = layout ? layout.kinds : [];
    el.columns.replaceChildren(...kinds.map((kind, i) => {
      const wrap = document.createElement("label");
      wrap.className = "im-column";
      const cap = document.createElement("span");
      cap.className = "im-column-cap";
      const header = layout.header && layout.labels[i] ? ` · ${layout.labels[i]}` : "";
      cap.textContent = `${columnLetter(i)}${header}`;
      const select = document.createElement("select");
      select.className = "im-column-kind";
      select.dataset.imColumn = String(i);
      select.setAttribute("aria-label", `column ${columnLetter(i)}: what it holds`);
      for (const k of COLUMN_KINDS) {
        const o = document.createElement("option");
        o.value = k;
        o.textContent = COLUMN_KIND_NAMES[k];
        select.append(o);
      }
      select.value = kind;
      wrap.append(cap, select);
      return wrap;
    }));
  }

  el.columns.addEventListener("change", e => {
    const select = e.target.closest("[data-im-column]");
    if (!select || !layout || busy) return;
    layout.kinds[Number(select.dataset.imColumn)] = select.value;
    rereadRows();
    announce(`Column ${columnLetter(Number(select.dataset.imColumn))} read as ${COLUMN_KIND_NAMES[select.value]}.`);
  });

  function weaponSelect(row, i) {
    const select = document.createElement("select");
    select.className = "im-weapon";
    select.dataset.imRow = String(i);
    select.setAttribute("aria-label", `row ${i + 1}: weapon`);
    const add = (parent, value, text) => {
      const o = document.createElement("option");
      o.value = value;
      o.textContent = text;
      parent.append(o);
      return o;
    };
    add(select, "", "choose…");
    add(select, IMPORT_OPEN, "open slot");
    add(select, IMPORT_SKIP, "skip this row");
    const m = row.match || {};
    if (m.candidates && m.candidates.length && m.status !== "exact") {
      const group = document.createElement("optgroup");
      group.label = "Suggested";
      for (const key of m.candidates) add(group, key, weaponInfo(CATALOG, key).name);
      select.append(group);
    }
    for (const g of WEAPON_GROUPS) {
      const group = document.createElement("optgroup");
      group.label = g.name;
      for (const w of g.weapons) add(group, w.key, w.name);
      select.append(group);
    }
    select.value = choices[i] == null ? defaultChoice(row) : choices[i];
    return select;
  }

  function cell(text, cls) {
    const td = document.createElement("td");
    if (cls) td.className = cls;
    td.textContent = text;
    return td;
  }

  function paintRows() {
    let position = 1;
    el.rows.replaceChildren(...rows.map((row, i) => {
      const tr = document.createElement("tr");
      const status = (row.match && row.match.status) || "none";
      const choice = choices[i];
      tr.dataset.status = choice === IMPORT_SKIP ? "skip" : choice === "" ? "uncertain" : status;
      const from = document.createElement("td");
      from.className = "im-from";
      const text = document.createElement("span");
      text.className = "gd-name";
      text.textContent = row.text || "(no weapon)";
      from.append(text);
      const tag = document.createElement("span");
      tag.className = "im-status";
      tag.textContent = choice === IMPORT_SKIP ? "skipped" : choice === "" ? STATUS_LABELS.uncertain : STATUS_LABELS[status];
      from.append(tag);
      const weapon = document.createElement("td");
      weapon.className = "im-pick";
      weapon.append(weaponSelect(row, i));
      const role = choices[i] !== IMPORT_SKIP && choices[i] !== "" && choices[i] !== IMPORT_OPEN && choices[i] ? weaponInfo(CATALOG, choices[i]).role : null;
      if (role) {
        const roleTag = document.createElement("span");
        roleTag.className = `pw-role ${role}`;
        roleTag.textContent = ROLE_NAMES[role] || role;
        weapon.append(roleTag);
      }
      const pos = choice === IMPORT_SKIP || choice === "" ? "—" : `${position}${row.count > 1 ? `–${position + row.count - 1}` : ""}`;
      if (choice !== IMPORT_SKIP && choice !== "") position += row.count;
      tr.append(cell(pos, "cp-pos"), from, weapon, cell(row.count > 1 ? `×${row.count}` : "", "im-count"),
                cell(row.player || "", "im-cell"), cell(row.role || "", "im-cell"), cell(row.party || "", "im-cell"), cell(row.note || "", "im-cell"));
      return tr;
    }));
  }

  el.rows.addEventListener("change", e => {
    const select = e.target.closest("[data-im-row]");
    if (!select || busy) return;
    choices[Number(select.dataset.imRow)] = select.value;
    paintRows();
    paintSummary();
  });

  function paintSummary() {
    const s = importSummary(rows);
    const built = importSlots(rows, choices, { players: el.players.checked, parties: el.parties.checked });
    const parts = [`${s.rows} row${s.rows === 1 ? "" : "s"}`, `${layoutMode(layout ? layout.kinds : [])}`,
                   `${s.matched} matched`, s.likely ? `${s.likely} to check` : "", built.unresolved ? `${built.unresolved} to choose` : "",
                   built.open ? `${built.open} open` : "", built.skipped ? `${built.skipped} skipped` : "",
                   `${built.slots.length} slot${built.slots.length === 1 ? "" : "s"}`];
    el.summary.textContent = parts.filter(Boolean).join(" · ");
    el.footNote.textContent = built.overflow ? `A comp holds at most ${COMP_SLOTS_MAX} slots: ${built.overflow} would be dropped. Skip rows first.`
                              : built.unresolved ? IMPORT_MSG.unresolved : "";
    el.footNote.hidden = !el.footNote.textContent;
    el.playersWrap.hidden = !rows.some(r => r.player);
    el.partiesWrap.hidden = built.parties.length < 2;
  }

  function paintResult() {
    el.result.hidden = !cells.length;
    if (!cells.length) return;
    paintColumns();
    paintRows();
    paintSummary();
  }

  el.players.addEventListener("change", paintSummary);
  el.parties.addEventListener("change", paintSummary);
  el.size.addEventListener("input", () => { el.size.dataset.auto = "no"; });


  /* ---- the import ---- */

  el.form.addEventListener("submit", async e => {
    e.preventDefault();
    if (busy || !rows.length || !guildId()) return;
    clearMessages();

    const built = importSlots(rows, choices, { players: el.players.checked, parties: el.parties.checked });
    if (built.unresolved) { showError(IMPORT_MSG.unresolved); return; }
    if (built.overflow) { showError(el.footNote.textContent); return; }
    if (!built.slots.length) { showError("Nothing to import: every row is skipped."); return; }

    const typed = {
      id: null, guild_id: guildId(), name: el.name.value.trim(), content: el.content.value, style: el.style.value,
      planned_size: Number(el.size.value), notes: "", share_hash: "", slots: built.slots
    };
    const first = acctFlagFields(FIELDS, validateTemplate({
      name: typed.name, content: typed.content, style: typed.style, plannedSize: typed.planned_size
    }, CONTENTS, STYLES));
    if (first) { first.focus(); return; }

    busy = true;
    acctBusy(el.save, "Importing…");
    try {
      const row = await saveTemplate(typed);
      let learned = 0;
      const pairs = el.remember.checked ? learnedAliases(rows, choices, index) : [];
      if (pairs.length) {
        try {
          learned = await saveGuildAliases(guildId(), pairs);
        } catch (err) {
          learned = -1;
          showNotice(`The comp was imported; the names were not remembered: ${importErrorMessage(err)}`);
        }
      }
      announce(`${row.name} imported with ${built.slots.length} slots.`);
      const opened = { id: row.id, guildId: guildId(), slots: built.slots.length, learned: Math.max(learned, 0) };
      dialog.close();
      document.dispatchEvent(new CustomEvent("comp-imported", { detail: opened }));
    } catch (err) {
      showError(compErrorMessage(err));
    } finally {
      busy = false;
      acctIdle(el.save);
    }
  });


  /* ---- opening ---- */

  function reset() {
    clearMessages();
    acctFlagFields(FIELDS, {});
    cells = [];
    layout = null;
    rows = [];
    choices = [];
    sourceName = "";
    el.text.value = "";
    el.file.value = "";
    el.name.value = "";
    el.content.value = "";
    el.style.value = "";
    el.size.value = "";
    el.size.dataset.auto = "yes";
    el.remember.checked = true;
    el.players.checked = false;
    el.parties.checked = true;
    el.aliasesWrap.open = false;
    paintResult();
  }

  async function openImport(preferredGuild) {
    if (!account.user) return;
    reset();
    guilds = [];
    aliases = [];
    index = weaponIndex(CATALOG, aliases);
    paintGuilds();
    paintAliases();
    if (!dialog.open) dialog.showModal();

    const seq = ++openSeq;
    try {
      guilds = (await loadMyGuilds()).filter(g => compPowers(g.role).write);
    } catch (err) {
      if (seq !== openSeq) return;
      showError(guildErrorMessage(err));
      return;
    }
    if (seq !== openSeq) return;

    paintGuilds();
    if (!guilds.length) {
      showError("Your role in no guild imports comps: callers, officers and admins do.");
      return;
    }
    if (preferredGuild && guilds.some(g => g.guild.id === preferredGuild)) el.guild.value = preferredGuild;
    await reloadAliases();
    el.text.focus();
  }

  acctWireDialog(dialog, { canClose: () => !busy });
  $id("im-close").addEventListener("click", () => dialog.close());

  /* the comps dialog hands the guild over as a DOM event, never a call
     between modules */
  document.addEventListener("comp-import", e => {
    openImport(e.detail && e.detail.guildId);
  });


  /* ---- identity ---- */

  window.Account.subscribe(state => {
    const was = account.user ? account.user.id : null;
    account = state;

    if (dialog.open && (!state.user || state.user.id !== was)) {
      dialog.close();
    }
  });
})();
