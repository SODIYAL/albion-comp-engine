"use strict";

/*
 * Import (platform phase 10): a caller's spreadsheet as a saved comp.
 * Callers keep comps in Excel, Google Sheets and Discord tables: one
 * weapon per row with a player, a role, a party or a count beside it,
 * or one column per party. This module reads pasted cells, a CSV file
 * or an Excel workbook (one sheet of it, the caller's pick), finds what
 * each column holds, reads every weapon name through the catalog and
 * every gear name (helm, armor, boots, cape, off-hand, potion, food)
 * through the gear catalog, shows the uncertain ones for review, and
 * saves the result as a comp template through the comps module's
 * helper, each slot's kit in the template's share hash (the comps
 * module's kitHash, the planner's loadout codec). One way: the sheet
 * is read once; nothing syncs back.
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
 * How a gear name is read (matchGear): within its column's slot, the
 * key, the name, a short name (a city cape's initials), then the words,
 * a prefix, word prefixes, the initials, a text inside the name, a close
 * spelling. Items of one name that differ only in tier (a potion, a
 * meal) are one name: the tier the sheet writes picks one, else the
 * highest. Several names left are uncertain; the caller chooses one or
 * leaves the slot without a piece, which is also what an unread name
 * gives (a piece is never guessed). The guild's remembered names are
 * weapon names (weapon_aliases holds weapon lines): a gear choice is not
 * remembered.
 *
 * build.py inlines this file as its own <script> after _history.js. It
 * reads no planner state and never calls the engine: roles are read
 * through the catalog (one role read). The planner tables it reads are
 * the gear catalog (GEAR), the codec's slot rule (loSlotOpen: a
 * two-handed weapon holds no off-hand) and the art retry (loArtRetry).
 * Three parts, as in _profile.js:
 *   helpers - the only code that talks to window.DB (weapon_aliases,
 *             save_weapon_aliases; the comp itself is saved through the
 *             comps module's saveTemplate)
 *   pure    - the parser, the workbook reader, the column detection, the
 *             matchers, the slots and their kits, the learned names,
 *             error wording (tests/test_import.js, tests/test_xlsx.js)
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

/* what one file and one workbook may cost to read: the file itself
   (any kind), the entries of a workbook's zip, one part as inflated (a
   sheet past it is read up to it, its later rows cut; the workbook and
   its shared strings are refused past it), and the columns of a sheet
   (A to BL) */
const IMPORT_FILE_MAX = 20 * 1024 * 1024;
const XLSX_ENTRIES_MAX = 2000;
const XLSX_PART_MAX = 16 * 1024 * 1024;
const IMPORT_COLUMNS_MAX = 64;

/* a row's choice beyond a weapon key */
const IMPORT_OPEN = "_open";
const IMPORT_SKIP = "_skip";

/* the gear slots a sheet's columns may hold, in the loadout codec's
   order (LO_SLOTS in _loadout.js; test_dashboard_layout.py pins it) */
const GEAR_KINDS = ["head", "armor", "shoes", "cape", "offhand", "potion", "food"];

/* what a column holds, as the caller may set it */
const COLUMN_KINDS = ["ignore", "weapon", "player", "role", "party", "count", "note", "position"].concat(GEAR_KINDS);
const COLUMN_KIND_NAMES = {
  ignore: "ignored", weapon: "weapon", player: "player", role: "role", party: "party",
  count: "count", note: "note", position: "slot number",
  head: "helm", armor: "armor", shoes: "boots", cape: "cape", offhand: "off-hand", potion: "potion", food: "food"
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
  number: ["#", "no", "nr", "idx", "index", "slot", "seat", "pos", "position"],
  /* a gear column beside the weapon: its names are read through the
     gear catalog into the slot's kit */
  head: ["head", "helmet", "helm", "helmets", "hood", "cowl", "hat", "headgear"],
  armor: ["chest", "armor", "armour", "body", "jacket", "robe", "torso"],
  shoes: ["boots", "boot", "shoes", "feet", "foot", "sandals"],
  cape: ["cape", "capes", "cloak"],
  offhand: ["offhand", "off hand", "offhands", "oh"],
  potion: ["potion", "potions", "pot", "pots"],
  food: ["food", "foods", "meal", "meals"],
  ignore: ["mount", "bag", "ip", "item power", "tier"]
};

/* the words a gear name ends with, which the initials may leave out
   ("Fort Sterling Cape" is FS, "Eye of Secrets" EOS) */
const GEAR_SLOT_WORDS = new Set(["helmet", "hood", "cowl", "hat", "armor", "robe", "jacket", "boots", "shoes", "sandals",
                                 "workboots", "cape", "potion"]);

/* a sheet's spellings the gear names do not use (curation judgment) */
const GEAR_SYNONYMS = { pot: "potion", pots: "potion", potions: "potion", cleanse: "cleansing", heal: "healing",
                        heals: "healing", resist: "resistance", omelet: "omelette", omelets: "omelette" };

/* Gear names the derivations cannot read: a city cape by its city's
   short name (curation judgment; the community's usage). */
const GEAR_NICKNAMES = {
  cape: { "bw": "CAPEITEM_FW_BRIDGEWATCH", "fs": "CAPEITEM_FW_FORTSTERLING", "ml": "CAPEITEM_FW_MARTLOCK",
          "tf": "CAPEITEM_FW_THETFORD", "lh": "CAPEITEM_FW_LYMHURST", "cl": "CAPEITEM_FW_CAERLEON",
          "brec": "CAPEITEM_FW_BRECILIEN" }
};

/* the tier words an item's name may carry, as tiers */
const TIER_NAMES = { beginner: 1, novice: 2, journeyman: 3, adept: 4, expert: 5, master: 6, grandmaster: 7, elder: 8 };

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
   read ("Longbow x3", "3x Longbow", "Longbow (2)"), what follows a dash
   or a colon kept apart as the tail ("Longbow - Disc"), and a bracketed
   word beside the name kept apart as the label, the caller's word for
   the slot ("GA (Cleanse)", "Witchwork (DPS)", "[Support] Rotcaller"). */
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
  let label = "";
  const after = s.match(/^(.+?)\s*[(\[]\s*([^()\[\]]+?)\s*[)\]]$/);
  const before = after ? null : s.match(/^[(\[]\s*([^()\[\]]+?)\s*[)\]]\s*(.+)$/);
  if (after) { s = after[1].trim(); label = after[2].trim(); }
  else if (before) { s = before[2].trim(); label = before[1].trim(); }
  /* a label that is only a tier or an enchantment ("Longbow (8.3)") says nothing */
  if (label && !normalizeWeaponText(label)) label = "";
  const out = { name: s, count: Math.min(Math.max(count || 1, 1), COMP_SLOTS_MAX), tail };
  if (label) out.label = label;
  return out;
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


/* The cells as the paste box shows them: tab-separated rows, the text
   Excel puts on the clipboard. A cell is quoted where its text would
   split it (a tab, a line break, a quote; a comma, a semicolon or a
   pipe when no row has a second cell, which a paste would read as the
   delimiter), so parseSheet reads the text back to the same cells. */
function cellsText(cells) {
  const rows = (cells || []).map(r => {
    const out = r.map(c => String(c == null ? "" : c));
    while (out.length && out[out.length - 1] === "") out.pop();
    return out;
  });
  const single = rows.every(r => r.length <= 1);
  const special = single ? /[\t\r\n",;|]/ : /[\t\r\n"]/;
  const quote = c => (special.test(c) ? `"${c.replace(/"/g, '""')}"` : c);
  return rows.map(r => r.map(quote).join("\t")).join("\n");
}


/* ----------------------------------------------------------- workbook */

/* An Excel workbook (.xlsx, .xlsm) is a zip of XML parts, read here with
   no library: the zip's central directory, each part stored or deflated
   (DecompressionStream "deflate-raw") and checked against its CRC-32,
   the package's relationships for the workbook part, the workbook and
   its relationships for the worksheets in tab order, the shared strings
   and the chosen sheet's cells. A cell reads as Excel holds its value: a
   shared or inline string, a number in its shortest form, TRUE or FALSE,
   a formula's result as last saved; an error reads empty. A merged
   range reads its value in its top-left cell and empty in its other
   cells, as Excel copies a merge. The cells then take the paste's path:
   the same trimming, the same bounds and the same detection. Refused,
   with the way round: a workbook protected by a password and an Excel
   97-2003 .xls (both the older compound format), a zip that is no
   workbook (an .xlsb, an .ods), a zip64 or another compression, a
   damaged file, a file or a part past its bound. */

/* what a file's first bytes say it is: a zip (a workbook), an Office
   compound file (an encrypted workbook or an .xls) or text */
function fileKind(bytes) {
  const b = bytes || [];
  if (b.length >= 4 && b[0] === 0x50 && b[1] === 0x4b && ((b[2] === 3 && b[3] === 4) || (b[2] === 5 && b[3] === 6))) return "zip";
  const cfb = [0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1];
  if (b.length >= 8 && cfb.every((x, i) => b[i] === x)) return "cfb";
  return "text";
}


/* A compound file holds an encrypted workbook when one of its streams is
   the EncryptedPackage (its directory names streams in UTF-16LE);
   otherwise it is an Excel 97-2003 workbook. */
function compoundKind(bytes) {
  const want = [..."EncryptedPackage"].flatMap(ch => [ch.charCodeAt(0), 0]);
  const n = bytes.length - want.length;
  for (let i = 0; i <= n; i++) {
    if (bytes[i] !== want[0]) continue;
    let k = 1;
    while (k < want.length && bytes[i + k] === want[k]) k++;
    if (k === want.length) return "xlsxLocked";
  }
  return "xls";
}


/* a file's text: a byte-order mark names UTF-8 or UTF-16; without one,
   UTF-8 when it decodes, else Windows-1252 (Excel's "CSV (Comma
   delimited)" writes the system code page) */
function decodeText(bytes) {
  const b = bytes || new Uint8Array(0);
  if (b[0] === 0xff && b[1] === 0xfe) return new TextDecoder("utf-16le").decode(b.subarray(2));
  if (b[0] === 0xfe && b[1] === 0xff) return new TextDecoder("utf-16be").decode(b.subarray(2));
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(b);
  } catch (err) {
    return new TextDecoder("windows-1252").decode(b);
  }
}


const zip16 = (b, o) => b[o] | (b[o + 1] << 8);
const zip32 = (b, o) => (b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)) >>> 0;


/* The zip's central directory: each entry by its name in lower case
   (a package's part names ignore case), with its flags, method, CRC,
   sizes and where its local header sits. */
function zipEntries(bytes) {
  const n = bytes.length;
  if (n < 22) throw importError("xlsxCorrupt");
  /* the end record: the last 22 bytes, or before a comment of at most 65535 */
  let end = -1;
  for (let i = n - 22; i >= Math.max(0, n - 22 - 65535); i--) {
    if (bytes[i] === 0x50 && bytes[i + 1] === 0x4b && bytes[i + 2] === 5 && bytes[i + 3] === 6) { end = i; break; }
  }
  if (end < 0) throw importError("xlsxCorrupt");
  const count = zip16(bytes, end + 10);
  const size = zip32(bytes, end + 12);
  const start = zip32(bytes, end + 16);
  if (count === 0xffff || size === 0xffffffff || start === 0xffffffff) throw importError("xlsxUnsupported");
  if (count > XLSX_ENTRIES_MAX) throw importError("xlsxTooBig");
  if (start + size > end) throw importError("xlsxCorrupt");

  const names = new TextDecoder("utf-8");
  const entries = new Map();
  let at = start;
  for (let k = 0; k < count; k++) {
    if (at + 46 > end || zip32(bytes, at) !== 0x02014b50) throw importError("xlsxCorrupt");
    const nameLength = zip16(bytes, at + 28);
    const name = names.decode(bytes.subarray(at + 46, at + 46 + nameLength)).replace(/\\/g, "/");
    entries.set(name.toLowerCase(), {
      name, flags: zip16(bytes, at + 8), method: zip16(bytes, at + 10), crc: zip32(bytes, at + 16),
      csize: zip32(bytes, at + 20), usize: zip32(bytes, at + 24), offset: zip32(bytes, at + 42)
    });
    at += 46 + nameLength + zip16(bytes, at + 30) + zip16(bytes, at + 32);
  }
  return entries;
}


let CRC_TABLE = null;

function crc32(bytes) {
  if (!CRC_TABLE) {
    CRC_TABLE = new Uint32Array(256);
    for (let i = 0; i < 256; i++) {
      let c = i;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      CRC_TABLE[i] = c >>> 0;
    }
  }
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}


/* deflated bytes inflated, at most limit of them: past it the bytes are
   cut when the caller reads a prefix (cut), else refused */
async function inflateRaw(raw, limit, cut) {
  let stream;
  try {
    stream = new DecompressionStream("deflate-raw");
  } catch (err) {
    throw importError("noInflate");
  }
  const writer = stream.writable.getWriter();
  writer.write(raw).catch(() => {});
  writer.close().catch(() => {});
  const reader = stream.readable.getReader();
  const parts = [];
  let total = 0;
  let stopped = false;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      if (total + value.length > limit) {
        if (!cut) throw importError("xlsxTooBig");
        parts.push(value.subarray(0, limit - total));
        total = limit;
        stopped = true;
        break;
      }
      parts.push(value);
      total += value.length;
    }
  } catch (err) {
    reader.cancel().catch(() => {});
    /* the bound's refusal stands; any error of the stream is a damaged part */
    throw err && err.code === "xlsxTooBig" ? err : importError("xlsxCorrupt");
  }
  if (stopped) reader.cancel().catch(() => {});
  const out = new Uint8Array(total);
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.length; }
  return { bytes: out, cut: stopped };
}


/* One entry's bytes: stored as is or inflated, checked against its size
   and CRC-32 when read whole. cut: a part past XLSX_PART_MAX is read up
   to it (a sheet) instead of refused (the workbook, the strings). */
async function zipRead(bytes, entry, cut) {
  if (entry.flags & 1) throw importError("xlsxLocked");
  const at = entry.offset;
  if (at + 30 > bytes.length || zip32(bytes, at) !== 0x04034b50) throw importError("xlsxCorrupt");
  const from = at + 30 + zip16(bytes, at + 26) + zip16(bytes, at + 28);
  const to = from + entry.csize;
  if (to > bytes.length) throw importError("xlsxCorrupt");
  const raw = bytes.subarray(from, to);
  let read;
  if (entry.method === 0) {
    if (entry.csize !== entry.usize) throw importError("xlsxCorrupt");
    if (raw.length > XLSX_PART_MAX && !cut) throw importError("xlsxTooBig");
    read = raw.length > XLSX_PART_MAX ? { bytes: raw.subarray(0, XLSX_PART_MAX), cut: true } : { bytes: raw, cut: false };
  } else if (entry.method === 8) {
    if (entry.usize > XLSX_PART_MAX && !cut) throw importError("xlsxTooBig");
    read = await inflateRaw(raw, XLSX_PART_MAX, cut);
  } else {
    throw importError("xlsxUnsupported");
  }
  if (!read.cut && (read.bytes.length !== entry.usize || crc32(read.bytes) !== entry.crc)) throw importError("xlsxCorrupt");
  return read;
}


/* a part's text: UTF-8, or UTF-16 where a byte-order mark says so */
function partText(bytes) {
  if (bytes[0] === 0xff && bytes[1] === 0xfe) return new TextDecoder("utf-16le").decode(bytes.subarray(2));
  if (bytes[0] === 0xfe && bytes[1] === 0xff) return new TextDecoder("utf-16be").decode(bytes.subarray(2));
  return new TextDecoder("utf-8").decode(bytes);
}


const XML_ENTITIES = { lt: "<", gt: ">", amp: "&", quot: '"', apos: "'" };

/* the five entities XML defines and character references; any other
   text stays as written */
function xmlDecode(text) {
  const s = String(text);
  if (s.indexOf("&") < 0) return s;
  return s.replace(/&(?:#[xX]([0-9a-fA-F]{1,6})|#(\d{1,7})|(lt|gt|amp|quot|apos));/g, (m, hex, dec, name) => {
    if (name) return XML_ENTITIES[name];
    const code = hex ? parseInt(hex, 16) : parseInt(dec, 10);
    return code > 0 && code <= 0x10ffff && !(code >= 0xd800 && code <= 0xdfff) ? String.fromCodePoint(code) : "";
  });
}


/* a cell's text: the escapes a workbook writes for characters XML
   cannot carry (_x000D_ is a carriage return) */
function cellText(text) {
  return String(text).replace(/_x([0-9A-Fa-f]{4})_/g, (m, hex) => String.fromCharCode(parseInt(hex, 16)));
}


/* Walks an XML part: visit.open(name, attrs), visit.close(name) and
   visit.text(text) in document order, names without their namespace
   prefix, attribute values and text decoded (a CDATA section as
   written). A document type declaration is refused: a workbook part
   never carries one, and its entities are never expanded. Setting
   visit.stop ends the walk; a part cut short ends at its last whole
   tag. */
function xmlWalk(xml, visit) {
  const s = String(xml || "");
  const n = s.length;
  const local = q => { const k = q.indexOf(":"); return k >= 0 ? q.slice(k + 1) : q; };
  const attrRe = /([^\s=]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/g;
  let i = 0;
  while (i < n && !visit.stop) {
    const lt = s.indexOf("<", i);
    if (lt < 0) {
      if (visit.text) visit.text(xmlDecode(s.slice(i)));
      break;
    }
    if (lt > i && visit.text) visit.text(xmlDecode(s.slice(i, lt)));
    const next = s.charCodeAt(lt + 1);
    if (next === 33) {          /* <! */
      if (s.startsWith("<!--", lt)) {
        const e = s.indexOf("-->", lt + 4);
        if (e < 0) break;
        i = e + 3;
        continue;
      }
      if (s.startsWith("<![CDATA[", lt)) {
        const e = s.indexOf("]]>", lt + 9);
        if (e < 0) break;
        if (visit.text) visit.text(s.slice(lt + 9, e));
        i = e + 3;
        continue;
      }
      throw importError("xlsxUnsupported");
    }
    if (next === 63) {          /* <? */
      const e = s.indexOf("?>", lt + 2);
      if (e < 0) break;
      i = e + 2;
      continue;
    }
    /* the tag ends at the first > outside a quoted attribute value */
    let j = lt + 1;
    let quote = 0;
    for (; j < n; j++) {
      const ch = s.charCodeAt(j);
      if (quote) { if (ch === quote) quote = 0; }
      else if (ch === 34 || ch === 39) quote = ch;
      else if (ch === 62) break;
    }
    if (j >= n) break;
    const body = s.slice(lt + 1, j);
    i = j + 1;
    if (body.charCodeAt(0) === 47) {   /* </name> */
      if (visit.close) visit.close(local(body.slice(1).trim()));
      continue;
    }
    const empty = body.charCodeAt(body.length - 1) === 47;
    const inner = empty ? body.slice(0, -1) : body;
    const m = /^\s*([^\s/>]+)/.exec(inner);
    if (!m) continue;
    const name = local(m[1]);
    const attrs = {};
    attrRe.lastIndex = m[0].length;
    let a;
    while ((a = attrRe.exec(inner))) attrs[a[1]] = xmlDecode(a[2] != null ? a[2] : a[3]);
    if (visit.open) visit.open(name, attrs);
    if (empty && visit.close && !visit.stop) visit.close(name);
  }
}


/* a part's path from a relationship's target: relative to the folder of
   the part that names it, or from the package's root (a leading /) */
function partPath(dir, target) {
  const t = String(target || "").replace(/\\/g, "/");
  const out = [];
  for (const p of (t.startsWith("/") ? t.slice(1) : dir + t).split("/")) {
    if (p === "..") out.pop();
    else if (p && p !== ".") out.push(p);
  }
  return out.join("/");
}


/* a relationships part: each relationship's id, type and the part it
   names (an external target names none) */
function relationships(xml, dir) {
  const out = [];
  xmlWalk(xml, {
    open(name, a) {
      if (name !== "Relationship" || !a.Id || a.TargetMode === "External") return;
      out.push({ id: a.Id, type: a.Type || "", path: partPath(dir, a.Target) });
    }
  });
  return out;
}


/* The workbook's worksheets in tab order with their parts (a chart
   sheet holds no cells and is not listed; a hidden sheet is, marked),
   and the one that was open when the workbook was saved (else the first
   one shown). */
function workbookSheets(xml, rels) {
  const byId = new Map((rels || []).map(r => [r.id, r]));
  const listed = [];
  let active = 0;
  let view = false;
  let root = false;
  xmlWalk(xml, {
    open(name, a) {
      if (name === "workbook") root = true;
      else if (name === "workbookView" && !view) { view = true; active = parseInt(a.activeTab, 10) || 0; }
      else if (name === "sheet") {
        const idKey = Object.keys(a).find(k => /:id$/.test(k));
        const rel = idKey ? byId.get(a[idKey]) : null;
        listed.push({ name: String(a.name || `Sheet ${listed.length + 1}`), hidden: a.state === "hidden" || a.state === "veryHidden",
                      path: rel && /\/worksheet$/.test(rel.type) ? rel.path : null });
      }
    }
  });
  if (!root) throw importError("xlsxCorrupt");
  const sheets = listed.filter(s => s.path);
  const open = listed[active] && listed[active].path ? sheets.indexOf(listed[active]) : -1;
  const shown = sheets.findIndex(s => !s.hidden);
  return { sheets, active: open >= 0 ? open : Math.max(shown, 0) };
}


/* the shared strings: each string's text, a rich string's runs joined,
   its phonetic guide (rPh) left out */
function sharedStrings(xml) {
  const out = [];
  let root = false, inSi = false, inT = false, phonetic = 0, text = "";
  xmlWalk(xml, {
    open(name) {
      if (name === "sst") root = true;
      else if (name === "si") { inSi = true; text = ""; }
      else if (name === "rPh") phonetic += 1;
      else if (name === "t" && inSi && !phonetic) inT = true;
    },
    close(name) {
      if (name === "si" && inSi) { out.push(cellText(text)); inSi = false; }
      else if (name === "rPh") phonetic = Math.max(phonetic - 1, 0);
      else if (name === "t") inT = false;
    },
    text(t) { if (inT) text += t; }
  });
  if (!root) throw importError("xlsxCorrupt");
  return out;
}


/* a cell reference (B3) as its row and column from zero */
function cellRef(ref) {
  const m = /^([A-Za-z]{1,3})(\d{1,7})$/.exec(String(ref || ""));
  if (!m) return null;
  let col = 0;
  for (const ch of m[1].toUpperCase()) col = col * 26 + (ch.charCodeAt(0) - 64);
  const row = Number(m[2]);
  return row >= 1 ? { row: row - 1, col: col - 1 } : null;
}


/* one cell's value as text, by its type */
function cellValue(type, v, t, strings) {
  switch (type) {
    case "s": {
      const i = parseInt(v, 10);
      return Number.isInteger(i) && i >= 0 && i < strings.length ? strings[i] : "";
    }
    case "inlineStr": return cellText(t || v);
    case "str": return cellText(v);
    case "b": return v.trim() === "1" ? "TRUE" : v.trim() === "0" ? "FALSE" : "";
    case "e": return "";
    case "d": return v.trim();
    default: {
      const s = v.trim();
      const n = Number(s);
      return s && Number.isFinite(n) ? String(n) : s;
    }
  }
}


/* A worksheet's cells, row by row from A1 (a missing cell is an empty
   one, so the column letters stay the sheet's; a row with no value is
   no row, as a paste drops an empty line): every cell trimmed, a row
   ending at its last value, at most IMPORT_ROWS_MAX rows, IMPORT_TEXT_MAX
   characters and IMPORT_COLUMNS_MAX columns (cut says the bounds took
   something). merged counts the merged ranges, unvalued the formulas
   saved without a result. */
function sheetGrid(xml, strings) {
  const found = new Map();
  let root = false, r = -1, c = -1, type = "", v = "", t = "";
  let inV = false, inIs = false, inT = false, phonetic = 0, hasV = false, hasF = false;
  let chars = 0, cut = false, unvalued = 0;
  const visit = {
    open(name, a) {
      if (name === "worksheet") root = true;
      else if (name === "row") { const n = parseInt(a.r, 10); r = n >= 1 ? n - 1 : r + 1; c = -1; }
      else if (name === "c") {
        const ref = cellRef(a.r);
        if (ref) { r = ref.row; c = ref.col; } else { c += 1; if (r < 0) r = 0; }
        type = a.t || "n"; v = ""; t = ""; hasV = false; hasF = false;
      }
      else if (name === "v") { inV = true; hasV = true; }
      else if (name === "f") hasF = true;
      else if (name === "is") inIs = true;
      else if (name === "rPh") phonetic += 1;
      else if (name === "t" && inIs && !phonetic) inT = true;
    },
    close(name) {
      if (name === "v") inV = false;
      else if (name === "is") inIs = false;
      else if (name === "rPh") phonetic = Math.max(phonetic - 1, 0);
      else if (name === "t") inT = false;
      else if (name === "sheetData") visit.stop = true;
      else if (name === "c") {
        if (hasF && !hasV) unvalued += 1;
        const text = cellValue(type, v, t, strings).trim();
        if (!text || r < 0 || c < 0) return;
        if (c >= IMPORT_COLUMNS_MAX) { cut = true; return; }
        let row = found.get(r);
        if (!row) {
          if (found.size >= IMPORT_ROWS_MAX) { cut = true; visit.stop = true; return; }
          row = [];
          found.set(r, row);
        }
        chars += text.length;
        if (chars > IMPORT_TEXT_MAX) { cut = true; visit.stop = true; return; }
        row[c] = text;
      }
    },
    text(s) {
      if (inV) v += s;
      else if (inT) t += s;
    }
  };
  xmlWalk(xml, visit);
  if (!root) throw importError("xlsxCorrupt");

  /* a merged range keeps its top-left cell; its other cells read empty */
  let merged = 0;
  const mergeRe = /<(?:[\w.-]+:)?mergeCell\b[^>]*?\bref\s*=\s*["']([A-Za-z]{1,3}\d{1,7})(?::([A-Za-z]{1,3}\d{1,7}))?["']/g;
  let m;
  while ((m = mergeRe.exec(xml))) {
    const a = cellRef(m[1]);
    const b = cellRef(m[2] || m[1]);
    if (!a || !b) continue;
    merged += 1;
    for (const [ri, row] of found) {
      if (ri < Math.min(a.row, b.row) || ri > Math.max(a.row, b.row)) continue;
      for (let ci = Math.min(a.col, b.col); ci <= Math.max(a.col, b.col) && ci < row.length; ci++) {
        if (ri !== Math.min(a.row, b.row) || ci !== Math.min(a.col, b.col)) row[ci] = "";
      }
    }
  }

  const rows = [...found.keys()].sort((x, y) => x - y)
    .map(ri => {
      const row = Array.from(found.get(ri), x => x || "");
      while (row.length && !row[row.length - 1]) row.pop();
      return row;
    })
    .filter(row => row.length);
  return { cells: rows, cut, merged, unvalued };
}


/* A workbook's sheets, read once per file: the worksheets in tab order,
   the one open when it was saved, the shared strings, and a reader for
   one sheet's part. The workbook part is the one the package's own
   relationships name (xl/workbook.xml when they name none). */
async function readWorkbook(bytes) {
  const kind = fileKind(bytes);
  if (kind === "cfb") throw importError(compoundKind(bytes));
  if (kind !== "zip") throw importError("notWorkbook");
  if (bytes.length > IMPORT_FILE_MAX) throw importError("fileTooBig");
  const entries = zipEntries(bytes);
  const part = async (path, cut) => {
    const entry = entries.get(String(path).toLowerCase());
    if (!entry) return null;
    const read = await zipRead(bytes, entry, cut);
    return { text: partText(read.bytes), cut: read.cut };
  };

  let bookPath = "xl/workbook.xml";
  const pkg = await part("_rels/.rels", false);
  if (pkg) {
    const main = relationships(pkg.text, "").find(r => /\/officeDocument$/.test(r.type));
    if (main && main.path) bookPath = main.path;
  }
  const book = await part(bookPath, false);
  if (!book) throw importError("notWorkbook");
  const dir = bookPath.slice(0, bookPath.lastIndexOf("/") + 1);
  const relsPart = await part(`${dir}_rels/${bookPath.slice(dir.length)}.rels`, false);
  const rels = relsPart ? relationships(relsPart.text, dir) : [];
  const { sheets, active } = workbookSheets(book.text, rels);
  if (!sheets.length) throw importError("noSheet");
  const sst = rels.find(r => /\/sharedStrings$/.test(r.type));
  const strings = await part(sst ? sst.path : `${dir}sharedStrings.xml`, false);

  return {
    sheets, active,
    strings: strings ? sharedStrings(strings.text) : [],
    read: path => part(path, true)
  };
}


/* One sheet of an opened workbook as cells, the way parseSheet hands a
   paste over (cells, rows, cut), with the sheet's name, its merged
   ranges and the formulas saved without a result. */
async function readWorkbookSheet(book, index) {
  const sheet = book && book.sheets[index];
  if (!sheet) throw importError("noSheet");
  const part = await book.read(sheet.path);
  if (!part) throw importError("xlsxCorrupt");
  const grid = sheetGrid(part.text, book.strings);
  return { name: sheet.name, cells: grid.cells, rows: grid.cells.length, cut: grid.cut || part.cut,
           merged: grid.merged, unvalued: grid.unvalued };
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
    /* the words of the line's own E spells ("Runestone Golem
       Transformation"): a sheet often names a weapon by what its E does */
    const spellTokens = [];
    for (const spell of entry.e || []) {
      for (const t of normalizeWeaponText(spell).split(" ")) if (t && !spellTokens.includes(t)) spellTokens.push(t);
    }
    entries.push({
      key, name, norm, tokens, spellTokens,
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
   key, how, candidates }. The tiers, first hit wins: the key, the name,
   a remembered name, then the derivations (the words, a prefix, word
   prefixes, the initials, the key's words, the text inside a name, the
   words of one line's E spell, a close spelling). */
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
    ["spell", e => joined.length >= 4 && !ROLE_WORDS.has(joined) && tokens.every(t => e.spellTokens.includes(t))],
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


/* a gear text as the gear matcher reads it: the weapon text's form,
   then the gear spellings ("resist pot" -> "resistance potion") */
function normalizeGearText(text) {
  return normalizeWeaponText(text).split(" ").filter(Boolean).map(t => GEAR_SYNONYMS[t] || t).join(" ");
}


/* the tier a sheet writes beside an item, or null: T6, T8.2, 6.1, an
   item id's prefix (T8_), a tier word (Master's) */
function gearTier(text) {
  const s = String(text == null ? "" : text).toLowerCase();
  const m = /(?:^|[^a-z0-9])t([1-8])(?:[._@]|\b)/.exec(s) || /(?:^|\s)([1-8])\.[0-4](?:\s|$)/.exec(s);
  if (m) return Number(m[1]);
  for (const [word, tier] of Object.entries(TIER_NAMES)) {
    if (new RegExp(`\\b${word}(?:'s)?\\b`).test(s)) return tier;
  }
  return null;
}


/* The gear catalog as the matcher reads it, built once per import: per
   slot, each item with its normalized name, its words, its initials (a
   trailing slot word may be left out) and its tier (a potion's or a
   meal's key carries one: T6_POTION_HEAL), the items by name (a name
   several tiers share lists them all), and the short names. */
function gearIndex(gear) {
  const slots = {};
  for (const s of GEAR_KINDS) slots[s] = { entries: [], byKey: new Set(), byName: new Map(), aliases: new Map() };
  for (const [key, item] of Object.entries(gear || {})) {
    const slot = item && slots[item.slot];
    if (!slot || !WEAPON_KEY_RE.test(key)) continue;
    const name = String(item.name || key);
    const norm = normalizeWeaponText(name);
    const tokens = norm.split(" ").filter(Boolean);
    const initials = tokens.length >= 2 ? tokens.map(t => t[0]).join("") : "";
    const tier = /^T(\d)_/.exec(key);
    const entry = {
      key, name, norm, tokens, compact: norm.replace(/ /g, ""), initials,
      initialsShort: initials && GEAR_SLOT_WORDS.has(tokens[tokens.length - 1]) ? initials.slice(0, -1) : "",
      tier: tier ? Number(tier[1]) : null
    };
    slot.entries.push(entry);
    slot.byKey.add(key);
    if (!slot.byName.has(norm)) slot.byName.set(norm, []);
    slot.byName.get(norm).push(entry);
  }
  for (const [s, names] of Object.entries(GEAR_NICKNAMES)) {
    for (const [alias, key] of Object.entries(names)) {
      if (slots[s] && slots[s].byKey.has(key)) slots[s].aliases.set(alias, key);
    }
  }
  return slots;
}


/* among items of one name: the tier the sheet wrote where the catalog
   holds it, else the highest */
function pickTier(entries, tier) {
  const exact = tier ? entries.find(e => e.tier === tier) : null;
  if (exact) return exact;
  return entries.reduce((best, e) => ((e.tier || 0) > (best.tier || 0) ? e : best), entries[0]);
}


/* One sheet text in a gear column -> { status: exact | likely |
   uncertain | none, key, how, candidates }, read within the column's
   slot. The tiers, first hit wins: the key (an item id's tier and
   enchantment dropped), the name, a short name, then the words, a
   prefix, word prefixes, the initials, a text inside the name, a close
   spelling. Hits of one name are one hit at the tier pickTier reads;
   among several names the plainest (the fewest words) decides when it
   is alone, else the caller does. quick: no close spelling (the column
   detection's pass over every cell). */
function matchGear(text, slot, gearIdx, quick) {
  const raw = String(text == null ? "" : text).trim();
  const idx = gearIdx && gearIdx[slot];
  if (!raw || !idx || !idx.entries.length) return noMatch();
  const tier = gearTier(raw);

  const upper = raw.toUpperCase().replace(/\s+/g, "_").replace(/@\d$/, "");
  for (const key of [upper, upper.replace(/^T\d_/, "")]) {
    if (idx.byKey.has(key)) return { status: "exact", key, how: "key", candidates: [key] };
  }

  const norm = normalizeGearText(raw);
  if (!norm) return noMatch();
  const named = idx.byName.get(norm);
  if (named) {
    const e = pickTier(named, tier);
    return { status: "exact", key: e.key, how: "name", candidates: [e.key] };
  }
  const tokens = norm.split(" ");
  const short = GEAR_SLOT_WORDS.has(tokens[tokens.length - 1]) && tokens.length > 1 ? tokens.slice(0, -1).join(" ") : norm;
  const alias = idx.aliases.get(norm) || idx.aliases.get(short);
  if (alias) return { status: "likely", key: alias, how: "nickname", candidates: [alias] };

  const joined = norm;
  const compact = joined.replace(/ /g, "");
  const near = joined.length < 8 ? 1 : 2;
  const tiers = [
    ["words", e => tokens.every(t => e.tokens.includes(t))],
    ["prefix", e => joined.length >= 3 && (e.norm.startsWith(joined) || e.compact.startsWith(compact))],
    ["word-prefix", e => joined.length >= 3 && tokens.every(t => e.tokens.some(n => n.startsWith(t)))],
    ["initials", e => tokens.length === 1 && e.initials !== "" && (e.initials === joined || e.initialsShort === joined)],
    ["inside", e => joined.length >= 4 && e.norm.includes(joined)],
    ["close", e => editDistance(compact, e.compact) <= near]
  ];

  for (const [how, test] of tiers) {
    if (quick && how === "close") break;
    const hits = idx.entries.filter(test);
    if (!hits.length) continue;
    const groups = new Map();
    for (const e of hits) {
      if (!groups.has(e.norm)) groups.set(e.norm, []);
      groups.get(e.norm).push(e);
    }
    /* the plainest names decide when one is alone, and lead the list
       when several are */
    let names = [...groups.keys()];
    if (names.length > 1) {
      const fewest = Math.min(...names.map(n => n.split(" ").length));
      const plain = names.filter(n => n.split(" ").length === fewest);
      names = plain.length === 1 ? plain : plain.concat(names.filter(n => !plain.includes(n)));
    }
    const picks = names.map(n => pickTier(groups.get(n), tier));
    if (picks.length === 1) {
      const sure = how !== "close" || editDistance(compact, picks[0].compact) <= 1;
      return { status: sure ? "likely" : "uncertain", key: sure ? picks[0].key : null, how, candidates: [picks[0].key] };
    }
    return { status: "uncertain", key: null, how, candidates: picks.map(e => e.key).slice(0, IMPORT_CANDIDATES) };
  }

  return noMatch();
}


/* a slot holds a gear piece: a two-handed weapon holds no off-hand (the
   planner's rule, loSlotOpen in _loadout.js) */
function gearSlotOpen(weapon, slot) {
  if (typeof loSlotOpen === "function") return loSlotOpen(weapon, slot);
  return !(slot === "offhand" && String(weapon).startsWith("2H_"));
}


/* what a column's cells look like; gear: per slot, the cells read as
   one of its items (without the close spelling, a detection's pass) */
function columnStats(values, index, gearIdx) {
  const n = values.length;
  const s = { n, weapon: 0, integer: 0, party: 0, role: 0, sequential: false, words: 0, length: 0, gear: {} };
  if (!n) return s;
  let seq = true;
  values.forEach((v, i) => {
    const m = matchWeapon(parseSlotText(v).name, index);
    if (m.status === "exact" || m.status === "alias" || m.status === "likely") s.weapon += 1;
    else if (gearIdx) {
      for (const slot of GEAR_KINDS) {
        const g = matchGear(v, slot, gearIdx, true);
        if (g.status === "exact" || g.status === "likely") s.gear[slot] = (s.gear[slot] || 0) + 1;
      }
    }
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
  /* mostly one slot's items: that slot, unless another reads as many
     (a set's name alone, "Guardian", is a helm, an armor and boots) */
  const gear = GEAR_KINDS.filter(slot => ((s.gear || {})[slot] || 0) / s.n >= 0.5)
    .sort((a, b) => s.gear[b] - s.gear[a]);
  if (gear.length && (gear.length === 1 || s.gear[gear[0]] > s.gear[gear[1]])) return gear[0];
  if (s.integer / s.n >= 0.8) return s.sequential ? "position" : "count";
  if (s.party / s.n >= 0.6) return "party";
  if (s.role / s.n >= 0.6) return "role";
  return s.words <= 2 && s.length <= 20 ? "player" : "note";
}


/* What each column holds. A header row (one of the first three rows,
   naming a kind and holding no weapon) decides where it can; the cells
   decide the rest: mostly weapons -> weapon, mostly one gear slot's
   items -> that slot (gearIdx, the gear catalog as gearIndex reads it),
   integers -> a slot number (1, 2, 3 in order) or a count, party labels
   -> party, role words -> role, short texts -> player, long ones ->
   note. Two or more weapon columns are parties side by side (grid); one
   is a list. */
function detectColumns(cells, index, gearIdx) {
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
    const stats = columnStats(values, index, gearIdx);
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
   role, party and note beside it, how the text was read, and its gear
   (per slot the sheet's text and how matchGear read it within the
   slot). A list reads one weapon column (a row with one cell that is a
   party label or a role word opens a section for the rows below); a
   grid reads every weapon column in turn, each a party, its player,
   role, count, note and gear columns the ones to its right, a role,
   count or note column left of the first party shared by all. */
function sheetRows(cells, layout, index, gearIdx) {
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
    let label = parsed.label || "";
    let match = name ? matchWeapon(name, index) : noMatch();
    const read = m => ["exact", "alias", "likely"].includes(m.status);
    if (tail && (match.status === "none" || match.status === "uncertain")) {
      const swapped = matchWeapon(tail, index);
      if (read(swapped)) {
        [name, tail] = [tail, name];
        match = swapped;
      }
    }
    /* "Tank (Heavy Mace)": the weapon is the bracketed word */
    if (label && (match.status === "none" || match.status === "uncertain")) {
      const swapped = matchWeapon(label, index);
      if (read(swapped)) {
        [name, label] = [label, name];
        match = swapped;
      }
    }
    const player = extra.player || (tail && !isRoleWord(tail) ? tail : "");
    /* the bracketed word is the caller's label for the slot: its role
       where the sheet names none, else part of the note */
    const role = extra.role || (tail && isRoleWord(tail) ? tail : "") || label || extra.fallbackRole || "";
    const note = [extra.note || "", label && role !== label ? label : ""].filter(Boolean).join(" · ");
    const count = extra.count != null ? extra.count : parsed.count;
    const gear = {};
    for (const [slot, text] of Object.entries(extra.gear || {})) {
      if (text) gear[slot] = { text, match: matchGear(text, slot, gearIdx) };
    }
    return { row: rowIndex, col, text: name, count: clampCount(count), player, role,
             party: extra.party || "", note, match, gear };
  };
  /* a row's gear cells: the text in each gear column that serves it */
  const gearOf = (r, colOf) => {
    const out = {};
    for (const slot of GEAR_KINDS) {
      const text = at(r, colOf(slot));
      if (text) out[slot] = text;
    }
    return out;
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
        count: /^\d{1,2}$/.test(rawCount) ? Number(rawCount) : null, note: at(r, nc),
        gear: gearOf(r, colOf)
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
        count: /^\d{1,2}$/.test(rawCount) ? Number(rawCount) : null, note: at(r, nc),
        gear: gearOf(r, attached)
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


/* the piece a row's gear slot starts with: the item when its text was
   read, none otherwise (the caller may choose among uncertain ones) */
function defaultGear(row, slot) {
  const g = row && row.gear && row.gear[slot];
  const m = (g && g.match) || {};
  return m.status === "exact" || m.status === "likely" ? m.key : "";
}


/* the piece a row's gear slot holds: the caller's choice (a key, "" for
   none) where one was made, else as read */
function gearChoice(row, choice, slot) {
  return choice && choice[slot] != null ? choice[slot] : defaultGear(row, slot);
}


/* A row's kit for its weapon: each gear slot's piece, a slot the weapon
   does not take (a two-hander's off-hand) left without one. Null when
   no piece is left. */
function rowKit(row, weapon, choice) {
  const kit = {};
  for (const slot of GEAR_KINDS) {
    const key = gearChoice(row, choice, slot);
    if (key && gearSlotOpen(weapon, slot)) kit[slot] = key;
  }
  return Object.keys(kit).length ? kit : null;
}


/* The gear counts a review shows, over the rows that keep a kit (an
   open or skipped row keeps none): the pieces kept (a two-hander's
   off-hand is not), the read ones to glance at, the uncertain ones
   still without a piece, the unread ones. */
function gearSummary(rows, gearChoices, choices) {
  const s = { pieces: 0, likely: 0, uncertain: 0, none: 0 };
  (rows || []).forEach((row, i) => {
    const weapon = choices && choices[i] != null ? choices[i] : defaultChoice(row);
    if (weapon === IMPORT_OPEN || weapon === IMPORT_SKIP) return;
    for (const [slot, g] of Object.entries(row.gear || {})) {
      if (weapon && !gearSlotOpen(weapon, slot)) continue;
      const key = gearChoice(row, gearChoices && gearChoices[i], slot);
      const status = (g.match && g.match.status) || "none";
      if (key) s.pieces += 1;
      if (status === "likely" && key === g.match.key) s.likely += 1;
      else if (status === "uncertain" && !key) s.uncertain += 1;
      else if (status === "none" && !key) s.none += 1;
    }
  });
  return s;
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
   party); bounded by the roster cap. A slot with a weapon carries its
   row's kit (kit: { loadout }, the gear options.gear chose per row, else
   as read), which the comps module's kitHash writes into the share
   hash; an open slot carries none (a kit is a weapon's). */
function importSlots(rows, choices, options) {
  const opts = Object.assign({ players: false, parties: true }, options || {});
  const gearChoices = opts.gear || [];
  const slots = [];
  const parties = [];
  for (const row of rows || []) {
    if (row.party && !parties.includes(row.party)) parties.push(row.party);
  }
  const keepParty = opts.parties && parties.length > 1;
  let skipped = 0, unresolved = 0, open = 0, overflow = 0, kits = 0;
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
    const kit = weapon_id ? rowKit(row, weapon_id, gearChoices[i]) : null;
    for (let n = 0; n < row.count; n++) {
      if (slots.length >= COMP_SLOTS_MAX) { overflow += 1; continue; }
      if (!weapon_id) open += 1;
      const slot = { position: slots.length + 1, weapon_id, role: cut(role, COMP_ROLE_MAX), note };
      if (kit) { slot.kit = { loadout: Object.assign({}, kit) }; kits += 1; }
      slots.push(slot);
    }
  });

  return { slots, skipped, unresolved, open, overflow, parties, kits };
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


/* a chosen file's bytes, a file past IMPORT_FILE_MAX refused before it
   is read; what the bytes are (a workbook, an older Office file, text)
   is read from them, never from the file's name (fileKind) */
function readFileBytes(file) {
  return new Promise((resolve, reject) => {
    if (!file) { reject(importError("empty")); return; }
    if (Number(file.size) > IMPORT_FILE_MAX) { reject(importError("fileTooBig")); return; }
    const reader = new FileReader();
    reader.onload = () => resolve(new Uint8Array(reader.result));
    reader.onerror = () => reject(importError("unreadable"));
    reader.readAsArrayBuffer(file);
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
  xlsxCorrupt: "The workbook could not be read: the file may be damaged. Open it in Excel and save it again, or copy its cells and paste them.",
  xlsxLocked: "This workbook is protected with a password, so it cannot be read here. Remove the password in Excel (File, Info, Protect Workbook, Encrypt with Password), or copy its cells and paste them.",
  xls: "An Excel 97-2003 workbook (.xls) cannot be read here. Save it as .xlsx or CSV in Excel, or copy its cells and paste them.",
  notWorkbook: "This file is not an Excel workbook (.xlsx) this page reads. An .xlsb or .ods file: save it as .xlsx or CSV first, or copy its cells and paste them.",
  xlsxUnsupported: "This workbook is stored in a way this page does not read. Save it again from Excel as .xlsx, or copy its cells and paste them.",
  xlsxTooBig: `The workbook is too large to read here (more than ${XLSX_ENTRIES_MAX} parts, or a part past ${XLSX_PART_MAX / 1048576} MB). Copy the comp's cells and paste them.`,
  fileTooBig: `The file is larger than ${IMPORT_FILE_MAX / 1048576} MB. Copy the comp's cells and paste them instead.`,
  noInflate: "This browser cannot open an Excel workbook. Copy its cells and paste them, or save the sheet as CSV.",
  noSheet: "The workbook has no sheet with cells.",
  sheetEmpty: "This sheet holds no cells. Choose another sheet.",
  unreadable: "The file could not be read. Copy its cells and paste them instead.",
  empty: "Nothing to read: paste the sheet's cells or open a file.",
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
  /* the planner's gear catalog (the picker's: every item with its name,
     slot and render item), read as the gear matcher reads it, once */
  const GEAR_TABLE = typeof GEAR !== "undefined" ? GEAR : {};
  const gearIdx = gearIndex(GEAR_TABLE);

  const el = {
    error: $id("im-error"),
    notice: $id("im-notice"),
    live: $id("im-live"),
    form: $id("im-form"),
    guild: $id("im-guild"),
    text: $id("im-text"),
    file: $id("im-file"),
    sheetWrap: $id("im-sheet-wrap"),
    sheet: $id("im-sheet"),
    read: $id("im-read"),
    result: $id("im-result"),
    summary: $id("im-summary"),
    columns: $id("im-columns"),
    table: $id("im-table"),
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
  /* the caller's own choices by the row's cell: a re-read of the rows (a
     name forgotten, the guild's names arriving) keeps them, never resets a
     skipped row to imported */
  let chosen = {};
  let gearChoices = [];     /* per row, the caller's piece per gear slot (a key, "" for none) */
  let gearChosen = {};      /* the same by the row's cell and the slot, kept across a re-read */
  let sourceName = "";      /* the file's name, for the comp's name */
  let book = null;          /* the open workbook, while its sheets are offered */
  let fileSeq = 0;          /* bumped by every file and sheet read: a slower read never lands over a newer one */
  let busy = false;
  let openSeq = 0;
  /* bumped by every opening of the dialog: an import still waiting on the
     service from before neither closes the reopened dialog nor ends its
     busy state */
  let session = 0;
  let aliasState = "ready"; /* the remembered names: "loading" until read, "failed" when not */
  let shownGuild = null;    /* the guild whose names are shown */
  const rowKey = r => `${r.row}:${r.col}:${r.text}`;

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
      li.textContent = aliasState === "loading" ? "Loading the remembered names…"
        : aliasState === "failed" ? "The remembered names did not load: names are read without them. Close this dialog and open it again to retry."
        : "No remembered names yet. A name you choose during an import is kept here.";
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
    shownGuild = guildId();
    aliases = [];
    aliasState = guildId() ? "loading" : "ready";
    index = weaponIndex(CATALOG, aliases);
    paintAliases();
    if (!guildId()) return;
    try {
      aliases = await loadGuildAliases(guildId());
    } catch (err) {
      if (seq !== openSeq) return;
      aliasState = "failed";
      paintAliases();
      showError(importErrorMessage(err));
      return;
    }
    if (seq !== openSeq) return;
    aliasState = "ready";
    index = weaponIndex(CATALOG, aliases);
    paintAliases();
    if (cells.length) rereadRows();
  }

  /* while an import waits, the guild stays the one it imports into */
  el.guild.addEventListener("change", () => {
    if (busy) { el.guild.value = shownGuild || ""; return; }
    reloadAliases();
  });


  /* ---- reading the sheet ---- */

  const own = (map, key) => Object.prototype.hasOwnProperty.call(map, key);
  const gearKey = (r, slot) => `${rowKey(r)}|${slot}`;

  /* The cells read, from a paste, a CSV file or a workbook's sheet: one
     path from here. notes: what the read says beside it (a cut, merged
     ranges); emptyKind: the message for no cells. */
  function readCells(parsed, notes, emptyKind) {
    clearMessages();
    if (!parsed.cells.length) {
      cells = [];
      layout = null;
      rows = [];
      choices = [];
      gearChoices = [];
      paintResult();
      showError(IMPORT_MSG[emptyKind || "empty"]);
      return;
    }
    cells = parsed.cells;
    layout = detectColumns(cells, index, gearIdx);
    chosen = {};
    gearChosen = {};
    rereadRows();
    if (notes && notes.length) showNotice(notes.join(" "));
    const s = importSummary(rows);
    announce(`${s.rows} rows read, ${s.uncertain} to choose.`);
    if (!rows.length && !layout.kinds.includes("weapon")) showError(IMPORT_MSG.noWeapons);
  }

  function readText(text) {
    const parsed = parseSheet(text);
    readCells(parsed, parsed.cut ? [`The sheet was cut at ${IMPORT_ROWS_MAX} rows.`] : []);
  }

  function rereadRows() {
    rows = layout ? sheetRows(cells, layout, index, gearIdx) : [];
    choices = rows.map(r => own(chosen, rowKey(r)) ? chosen[rowKey(r)] : defaultChoice(r));
    gearChoices = rows.map(r => {
      const choice = {};
      for (const slot of Object.keys(r.gear || {})) {
        if (own(gearChosen, gearKey(r, slot))) choice[slot] = gearChosen[gearKey(r, slot)];
      }
      return choice;
    });
    if (!el.size.value || el.size.dataset.auto === "yes") {
      el.size.value = String(Math.min(Math.max(importSummary(rows).slots, COMP_SIZE_MIN), COMP_SLOTS_MAX));
      el.size.dataset.auto = "yes";
    }
    paintResult();
  }

  /* the comp's name follows the file (a workbook of several sheets: the
     sheet) until the caller types one */
  function nameFrom(text) {
    if (el.name.value && el.name.dataset.auto !== "yes") return;
    el.name.value = Array.from(String(text || "")).slice(0, ACCOUNT_NAME_MAX).join("").trim();
    el.name.dataset.auto = "yes";
  }
  el.name.addEventListener("input", () => { el.name.dataset.auto = "no"; });

  /* the open workbook's sheets, offered when it has more than one */
  function setBook(opened) {
    book = opened;
    el.sheet.replaceChildren(...(book ? book.sheets : []).map((s, i) => {
      const o = document.createElement("option");
      o.value = String(i);
      o.textContent = s.hidden ? `${s.name} (hidden)` : s.name;
      return o;
    }));
    el.sheetWrap.hidden = !book || book.sheets.length < 2;
  }

  /* one sheet of the open workbook, written into the paste box as the
     tab-separated cells Excel copies, and read */
  async function openSheet(i, seq) {
    const sheet = await readWorkbookSheet(book, i);
    if (seq !== fileSeq) return;
    el.sheet.value = String(i);
    el.text.value = cellsText(sheet.cells);
    nameFrom(book.sheets.length > 1 ? sheet.name : sourceName);
    const notes = [];
    if (sheet.cut) {
      notes.push(`The sheet was cut to what one import reads: ${IMPORT_ROWS_MAX} rows, ${IMPORT_COLUMNS_MAX} columns.`);
    }
    if (sheet.merged) {
      notes.push(`${sheet.merged} merged range${sheet.merged === 1 ? "" : "s"}: a merge reads its value in its top-left cell, its other cells empty.`);
    }
    if (sheet.unvalued) {
      notes.push(`${sheet.unvalued} formula${sheet.unvalued === 1 ? " was" : "s were"} saved without a value and read${sheet.unvalued === 1 ? "s" : ""} empty: open the workbook in Excel and save it again.`);
    }
    readCells(sheet, notes, "sheetEmpty");
  }

  el.read.addEventListener("click", () => { if (!busy) readText(el.text.value); });
  /* a paste is the sheet now: the workbook's sheets are no longer offered */
  el.text.addEventListener("paste", () => {
    setTimeout(() => {
      if (busy || !el.text.value.trim()) return;
      fileSeq++;
      setBook(null);
      readText(el.text.value);
    }, 0);
  });

  /* a file: its bytes say what it is (fileKind); a workbook offers its
     sheets, the one open when it was saved read first */
  el.file.addEventListener("change", async () => {
    const file = el.file.files && el.file.files[0];
    if (!file || busy) return;
    const seq = ++fileSeq;
    clearMessages();
    try {
      const bytes = await readFileBytes(file);
      if (seq !== fileSeq) return;
      const name = String(file.name || "").replace(/\.[^.]+$/, "");
      if (fileKind(bytes) === "text") {
        setBook(null);
        sourceName = name;
        const text = decodeText(bytes);
        el.text.value = text;
        nameFrom(sourceName);
        readText(text);
        return;
      }
      announce("Reading the workbook…");
      const opened = await readWorkbook(bytes);
      if (seq !== fileSeq) return;
      sourceName = name;
      setBook(opened);
      await openSheet(opened.active, seq);
    } catch (err) {
      if (seq === fileSeq) showError(importErrorMessage(err));
    } finally {
      el.file.value = "";
    }
  });

  el.sheet.addEventListener("change", async () => {
    if (busy || !book) return;
    const seq = ++fileSeq;
    try {
      await openSheet(Number(el.sheet.value), seq);
    } catch (err) {
      if (seq === fileSeq) showError(importErrorMessage(err));
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

  /* an item's name as the review shows it: a potion's or a meal's tier
     beside it (one name, several tiers) */
  function gearLabel(key) {
    const item = GEAR_TABLE[key] || {};
    const tier = /^T(\d)_/.exec(key);
    return `${item.name || key}${tier && (item.slot === "potion" || item.slot === "food") ? ` T${tier[1]}` : ""}`;
  }

  /* gear art is hotlinked (the planner's policy for the picker), retried */
  function gearArt(key) {
    const item = GEAR_TABLE[key] || {};
    if (!item.example_item) return null;
    const img = document.createElement("img");
    img.className = "pw-art im-gear-art";
    img.src = `https://render.albiononline.com/v1/item/${encodeURIComponent(item.example_item)}.png?size=64`;
    img.alt = "";
    img.width = 18;
    img.height = 18;
    img.loading = "lazy";
    if (typeof loArtRetry === "function") img.addEventListener("error", () => loArtRetry(img));
    return img;
  }

  /* A row's kit as read: a read piece with its art (a likely one marked
     to check), an uncertain one as a list of its candidates (no piece
     until one is chosen), an unread one by its text (no piece). Pieces
     of an open or skipped row, and a two-hander's off-hand, are not
     kept. */
  function kitCell(row, i) {
    const td = document.createElement("td");
    td.className = "im-kit";
    const weapon = choices[i];
    const armed = !!weapon && weapon !== IMPORT_OPEN && weapon !== IMPORT_SKIP;
    if (weapon === IMPORT_OPEN || weapon === IMPORT_SKIP) {
      td.dataset.kept = "no";
      td.title = "An open or skipped slot carries no kit.";
    }
    for (const slot of GEAR_KINDS) {
      const g = row.gear && row.gear[slot];
      if (!g) continue;
      const label = COLUMN_KIND_NAMES[slot];
      const m = g.match || {};
      const key = gearChoice(row, gearChoices[i], slot);
      if (m.status === "uncertain") {
        const select = document.createElement("select");
        select.className = "im-gear-pick";
        select.dataset.imGear = `${i}:${slot}`;
        select.setAttribute("aria-label", `row ${i + 1}: ${label}, read from ${g.text}`);
        select.title = `${label}: “${g.text}” names several items`;
        const none = document.createElement("option");
        none.value = "";
        none.textContent = `${label}: choose`;
        select.append(none);
        for (const c of m.candidates || []) {
          const o = document.createElement("option");
          o.value = c;
          o.textContent = gearLabel(c);
          select.append(o);
        }
        select.value = key || "";
        td.append(select);
        continue;
      }
      const piece = document.createElement("span");
      piece.className = "im-gear";
      if (key) {
        const closed = armed && !gearSlotOpen(weapon, slot);
        piece.dataset.status = closed ? "closed" : m.status;
        const art = gearArt(key);
        if (art) piece.append(art);
        piece.append(gearLabel(key));
        piece.title = closed ? `${label}: a two-handed weapon holds no off-hand, so it is left out`
          : `${label}: ${gearLabel(key)}` + (m.status === "likely" ? `, read from “${g.text}”: check it` : "");
      } else {
        piece.dataset.status = "none";
        piece.textContent = `${label}: ${g.text}`;
        piece.title = `${label}: “${g.text}” names no item, so the slot keeps no piece`;
      }
      td.append(piece);
    }
    return td;
  }

  function paintRows() {
    let position = 1;
    el.table.classList.toggle("im-nokit", !rows.some(r => Object.keys(r.gear || {}).length));
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
      tr.append(cell(pos, "cp-pos"), from, weapon, kitCell(row, i), cell(row.count > 1 ? `×${row.count}` : "", "im-count"),
                cell(row.player || "", "im-cell"), cell(row.role || "", "im-cell"), cell(row.party || "", "im-cell"), cell(row.note || "", "im-cell"));
      return tr;
    }));
  }

  el.rows.addEventListener("change", e => {
    if (busy) return;
    const gear = e.target.closest("[data-im-gear]");
    if (gear) {
      const [at, slot] = gear.dataset.imGear.split(":");
      const i = Number(at);
      if (!rows[i]) return;
      gearChoices[i] = Object.assign({}, gearChoices[i], { [slot]: gear.value });
      gearChosen[gearKey(rows[i], slot)] = gear.value;
      paintRows();
      paintSummary();
      return;
    }
    const select = e.target.closest("[data-im-row]");
    if (!select) return;
    const i = Number(select.dataset.imRow);
    choices[i] = select.value;
    if (rows[i]) chosen[rowKey(rows[i])] = select.value;
    paintRows();
    paintSummary();
  });

  function paintSummary() {
    const s = importSummary(rows);
    const built = importSlots(rows, choices, { players: el.players.checked, parties: el.parties.checked, gear: gearChoices });
    const g = gearSummary(rows, gearChoices, choices);
    const kit = rows.some(r => Object.keys(r.gear || {}).length)
      ? `kits: ${[`${g.pieces} piece${g.pieces === 1 ? "" : "s"}`, g.likely ? `${g.likely} to check` : "",
                  g.uncertain ? `${g.uncertain} to choose` : "", g.none ? `${g.none} unread` : ""].filter(Boolean).join(", ")}`
      : "";
    const parts = [`${s.rows} row${s.rows === 1 ? "" : "s"}`, `${layoutMode(layout ? layout.kinds : [])}`,
                   `${s.matched} matched`, s.likely ? `${s.likely} to check` : "", built.unresolved ? `${built.unresolved} to choose` : "",
                   built.open ? `${built.open} open` : "", built.skipped ? `${built.skipped} skipped` : "",
                   `${built.slots.length} slot${built.slots.length === 1 ? "" : "s"}`, kit];
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
    if (busy) return;
    clearMessages();
    if (!guildId()) {
      showError(guilds.length ? "Choose the guild to import into."
                              : "No guild to import into: the guild list did not load. Close this dialog and open it again to retry.");
      return;
    }
    if (!rows.length) { showError("Nothing to import yet: paste a sheet or choose a file, then read it."); return; }

    const built = importSlots(rows, choices, { players: el.players.checked, parties: el.parties.checked, gear: gearChoices });
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
    /* the slots' kits ride in the comp's share hash, the planner's own
       link (the comps module's kitHash, the loadout codec): "Open in
       planner" shows each slot in its kit. A link past the database's
       bound (COMP_HASH_MAX) is not built: the comp is saved without its
       kits, and says so. */
    const kept = built.kits ? kitHash(typed, built.slots) : "";
    typed.share_hash = kept;

    /* the guild and the names to remember, taken now: the import never
       reads the dialog after a wait */
    const gid = guildId();
    const pairs = el.remember.checked ? learnedAliases(rows, choices, index) : [];
    busy = true;
    const mine = session;
    acctBusy(el.save, "Importing…");
    try {
      const row = await saveTemplate(typed);
      let learned = 0;
      let namesError = "";
      if (pairs.length) {
        try {
          learned = await saveGuildAliases(gid, pairs);
        } catch (err) {
          namesError = importErrorMessage(err);
        }
      }
      if (mine !== session) return;
      announce(`${row.name} imported with ${built.slots.length} slots.`);
      /* a name save that failed rides along, and the kits kept or not
         kept: the comps dialog says so */
      const opened = { id: row.id, guildId: gid, slots: built.slots.length, learned, namesError,
                       kits: kept ? built.kits : 0, kitsDropped: built.kits > 0 && !kept };
      dialog.close();
      document.dispatchEvent(new CustomEvent("comp-imported", { detail: opened }));
    } catch (err) {
      if (mine === session) showError(compErrorMessage(err));
    } finally {
      if (mine === session) {
        busy = false;
        acctIdle(el.save);
      }
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
    chosen = {};
    gearChoices = [];
    gearChosen = {};
    sourceName = "";
    fileSeq++;
    setBook(null);
    el.text.value = "";
    el.file.value = "";
    el.name.value = "";
    el.name.dataset.auto = "yes";
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
    /* a reopened dialog starts idle (session) */
    session++;
    busy = false;
    acctIdle(el.save);
    reset();
    guilds = [];
    aliases = [];
    aliasState = "loading";
    index = weaponIndex(CATALOG, aliases);
    paintGuilds();
    paintAliases();
    if (!dialog.open) dialog.showModal();

    const seq = ++openSeq;
    try {
      guilds = (await loadMyGuilds()).filter(g => compPowers(g.role).write);
    } catch (err) {
      if (seq !== openSeq) return;
      aliasState = "failed";
      paintAliases();
      showError(guildErrorMessage(err));
      return;
    }
    if (seq !== openSeq) return;

    paintGuilds();
    if (!guilds.length) {
      aliasState = "ready";
      paintAliases();
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
