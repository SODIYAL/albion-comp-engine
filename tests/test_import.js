/* Import tests - dashboard/_import.js.
 *
 * The account modules run together in a vm context with no document, as
 * the page loads them: the helpers and the pure functions load, and each
 * UI block returns before touching the DOM. The helpers run against a
 * stub client that records every call, so what the page sends to
 * Supabase is pinned without a network; tests/test_supabase_rls.mjs pins
 * what the database does with it. The matcher runs over the dataset's
 * own catalog (pipeline/out/dataset-latest.json), so a name a caller
 * writes is pinned against the lines the planner knows.
 *
 * Pinned: the text a sheet writes beside a weapon (tiers, counts, list
 * markers, a player after a dash), the parser (tabs, commas, semicolons,
 * pipes, quotes, one column), how a name is read (a key, the name, an
 * alias, the words, a prefix, the initials, the key's words, a close
 * spelling; one candidate likely, several uncertain, none open), the
 * columns (a header, the cells, a list or a grid), the rows (sections,
 * counts, a grid's parties), the slots, the names learned, error
 * wording, and what the helpers send.
 *
 * Run:  node tests/test_import.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const DASH = path.join(__dirname, "..", "dashboard");
const DATASET = path.join(__dirname, "..", "pipeline", "out", "dataset-latest.json");

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log(`PASS  ${name}`); }
  else { fail++; console.log(`FAIL  ${name}${detail !== undefined ? "\n      " + JSON.stringify(detail) : ""}`); }
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

const CALLS = [];
const REPLY = {};
function chain(record, answer) {
  const proxy = new Proxy(function () {}, {
    get(_t, prop) {
      if (prop === "then") return (res, rej) => Promise.resolve(answer()).then(res, rej);
      return (...args) => { record.push([prop, ...args]); return proxy; };
    },
  });
  return proxy;
}
const DB = {
  auth: {
    getSession: async () => ({ data: { session: null }, error: null }),
    onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
  },
  from(table) {
    const ops = [];
    CALLS.push({ table, ops });
    return chain(ops, () => REPLY[table] || { data: null, error: null });
  },
  rpc(fn, args) {
    CALLS.push({ rpc: fn, args });
    return Promise.resolve(REPLY[`rpc:${fn}`] || { data: null, error: null });
  },
  channel() { throw new Error("the import is not live"); },
};

const ctx = { console, URLSearchParams, setTimeout, Promise, Proxy, Date, decodeURIComponent, encodeURIComponent };
ctx.window = ctx;
ctx.window.DB = DB;
vm.createContext(ctx);
for (const f of ["_auth.js", "_profile.js", "_guild.js", "_comps.js", "_events.js", "_signup.js", "_history.js", "_import.js"]) {
  vm.runInContext(fs.readFileSync(path.join(DASH, f), "utf8"), ctx, { filename: f });
}
const run = expr => vm.runInContext(expr, ctx);

/* the catalog as build.py stamps it: every line's display name, the
   removed ones marked */
const weapons = JSON.parse(fs.readFileSync(DATASET, "utf8")).weapons;
const CATALOG = {};
for (const [key, w] of Object.entries(weapons)) {
  CATALOG[key] = { name: w.display_name || key, role: null, item: "" };
  if (w.removed) CATALOG[key].removed = true;
}
const index = run("weaponIndex")(CATALOG, []);

(async () => {

/* 1 - the text beside a weapon */
{
  const norm = run("normalizeWeaponText");
  check("a name normalizes to lower case, letters and digits, single spaces; tiers, enchantments, quality and possessives go",
        norm("  Great Arcane Staff ") === "great arcane staff" && norm("8.3 Elder's Hallowfall") === "hallowfall"
        && norm("T8 Longbow .3") === "longbow" && norm("Iron-clad Staff") === "iron clad staff" && norm("Hallöwfall") === "hallowfall"
        && norm("the Longbow") === "longbow" && norm("") === "" && norm(null) === "");
  check("one-handed and two-handed read as 1h and 2h; xbow as crossbow",
        norm("One-handed Arcane") === "1h arcane" && norm("two handed holy") === "2h holy" && norm("1-h fire") === "1h fire"
        && norm("1H xbow") === "1h crossbow" && norm("heavy xbow") === "heavy crossbow");
  const parse = run("parseSlotText");
  check("a count reads from x3, 3x, (2) and (x2); a list marker goes; what follows a dash or a colon is the tail",
        same(parse("Longbow x3"), { name: "Longbow", count: 3, tail: "" }) && same(parse("3x Longbow"), { name: "Longbow", count: 3, tail: "" })
        && same(parse("Longbow (2)"), { name: "Longbow", count: 2, tail: "" }) && same(parse("Longbow (x2)"), { name: "Longbow", count: 2, tail: "" })
        && same(parse("1. Longbow - Disc"), { name: "Longbow", count: 1, tail: "Disc" }) && same(parse("- Hallowfall: Eff"), { name: "Hallowfall", count: 1, tail: "Eff" })
        && same(parse("Heavy Crossbow"), { name: "Heavy Crossbow", count: 1, tail: "" }) && same(parse("8.3 Longbow"), { name: "8.3 Longbow", count: 1, tail: "" }));
  check("a count is bounded by the roster cap", parse("99x Longbow").count === run("COMP_SLOTS_MAX"));
  check("party labels and role words are known", run("isPartyLabel")("Party 1") && run("isPartyLabel")("P2") && run("isPartyLabel")("Group A")
        && !run("isPartyLabel")("Party") && !run("isPartyLabel")("Longbow") && run("isRoleWord")("Tanks:") && run("isRoleWord")("healer") && !run("isRoleWord")("Bow"));
  check("column letters run A..Z, AA", run("columnLetter")(0) === "A" && run("columnLetter")(25) === "Z" && run("columnLetter")(26) === "AA");
}

/* 2 - the parser */
{
  const parse = run("parseSheet");
  const tsv = parse("Weapon\tPlayer\r\nLongbow\tDisc\r\n\r\nHallowfall\t\r\n");
  check("cells copied from a spreadsheet are tab-separated; CRLF and empty rows are handled",
        tsv.delimiter === "\t" && same(tsv.cells, [["Weapon", "Player"], ["Longbow", "Disc"], ["Hallowfall", ""]]) && tsv.rows === 3 && !tsv.cut, tsv);
  const csv = parse('Weapon,Note\n"Longbow","engage, then ""kite"""\nWarbow,\n');
  check("CSV quoting: a comma and doubled quotes inside a quoted cell",
        csv.delimiter === "," && same(csv.cells, [["Weapon", "Note"], ["Longbow", 'engage, then "kite"'], ["Warbow", ""]]), csv);
  check("a semicolon CSV and a pipe table read too; a Markdown rule line and a code fence go",
        same(parse("Weapon;Player\nLongbow;Disc").cells, [["Weapon", "Player"], ["Longbow", "Disc"]])
        && same(parse("```\n| Weapon | Player |\n|---|---|\n| Longbow | Disc |\n```").cells, [["Weapon", "Player"], ["Longbow", "Disc"]]));
  check("lines without a delimiter are one column", same(parse("Longbow\nWarbow\n").cells, [["Longbow"], ["Warbow"]]) && parse("Longbow").delimiter === "");
  check("nothing reads as no cells", parse("").cells.length === 0 && parse("  \n\n").cells.length === 0);
  const big = parse(Array.from({ length: 600 }, (_, i) => `Row ${i}`).join("\n"));
  check("a sheet is cut at IMPORT_ROWS_MAX rows and says so", big.cells.length === run("IMPORT_ROWS_MAX") && big.rows === 600 && big.cut);
}

/* 3 - how a name is read, over the dataset's catalog */
{
  const match = run("matchWeapon");
  const cases = [
    ["Longbow", "exact", "2H_LONGBOW"], ["2H_LONGBOW", "exact", "2H_LONGBOW"], ["longbow", "exact", "2H_LONGBOW"],
    ["Great Arcane Staff", "exact", "2H_ARCANESTAFF"], ["8.3 Elder's Longbow", "exact", "2H_LONGBOW"],
    ["spirit hunter", "exact", "2H_HARPOON_HELL"], ["great axe", "exact", "2H_AXE"], ["Morningstar", "exact", "2H_FLAIL"],
    ["1h holy staff", "exact", "MAIN_HOLYSTAFF"],
    ["daggers", "alias", "2H_DAGGERPAIR"], ["Dual Maces", "alias", "2H_DUALMACE_AVALON"],
    ["great arcane", "likely", "2H_ARCANESTAFF"], ["arcane", "likely", "MAIN_ARCANESTAFF"], ["1h arcane", "likely", "MAIN_ARCANESTAFF"],
    ["2h holy", "likely", "2H_HOLYSTAFF"], ["holy", "likely", "MAIN_HOLYSTAFF"], ["one handed holy", "likely", "MAIN_HOLYSTAFF"],
    ["cursed", "likely", "MAIN_CURSEDSTAFF"], ["skull", "likely", "2H_SKULLORB_HELL"], ["infernal", "likely", "2H_INFERNOSTAFF"],
    ["hallow", "likely", "MAIN_HOLYSTAFF_AVALON"], ["perma", "likely", "2H_ICECRYSTAL_UNDEAD"], ["locus", "likely", "2H_ENIGMATICORB_MORGANA"],
    ["inc mace", "likely", "MAIN_MACE_HELL"], ["iron clad", "likely", "2H_IRONCLADEDSTAFF"], ["ironclad", "likely", "2H_IRONCLADEDSTAFF"],
    ["hoj", "likely", "2H_HAMMER_AVALON"], ["bob", "likely", "2H_BOW_KEEPER"], ["sob", "likely", "2H_ROCKSTAFF_KEEPER"], ["ga", "likely", "2H_ARCANESTAFF"],
    ["bp", "likely", "2H_DUALAXE_KEEPER"], ["wr", "likely", "2H_REPEATINGCROSSBOW_UNDEAD"],
    ["flail", "likely", "2H_FLAIL"], ["harpoon", "likely", "2H_HARPOON_HELL"],
    ["1h xbow", "likely", "MAIN_1HCROSSBOW"], ["heavy xbow", "exact", "2H_CROSSBOWLARGE"], ["repeater", "likely", "2H_REPEATINGCROSSBOW_UNDEAD"],
    ["Hallowfal", "likely", "MAIN_HOLYSTAFF_AVALON"], ["Halowfall", "likely", "MAIN_HOLYSTAFF_AVALON"], ["fall", "likely", "2H_HOLYSTAFF_HELL"],
    ["swords", "likely", "2H_DUALSWORD"], ["bear", "likely", "2H_DUALAXE_KEEPER"], ["monk", "likely", "2H_COMBATSTAFF_MORGANA"],
  ];
  for (const [text, status, key] of cases) {
    const m = match(text, index);
    check(`"${text}" reads as ${status} ${key}`, m.status === status && m.key === key, m);
  }
  const gh = match("gh", index);
  check('"gh" is uncertain between the Great Hammer and the Great Holy Staff',
        gh.status === "uncertain" && gh.key === null && same([...gh.candidates].sort(), ["2H_HAMMER", "2H_HOLYSTAFF"]), gh);
  const great = match("great", index);
  check('"great" is uncertain among the great staves, at most IMPORT_CANDIDATES listed',
        great.status === "uncertain" && great.candidates.length > 1 && great.candidates.length <= run("IMPORT_CANDIDATES") && great.candidates.includes("2H_FIRESTAFF"), great);
  const typo = match("Halowfal", index);
  check("a spelling two edits away is uncertain, the near line suggested", typo.status === "uncertain" && same(typo.candidates, ["MAIN_HOLYSTAFF_AVALON"]), typo);
  check("a role word, a removed line and nothing read as none",
        match("Tank", index).status === "none" && match("Black Hands", index).status === "none" && match("", index).status === "none" && match("1h", index).status === "none");
  check("the plain line decides among the great ones: fire, frost, nature",
        match("fire", index).key === "MAIN_FIRESTAFF" && match("frost", index).key === "MAIN_FROSTSTAFF" && match("nature", index).key === "MAIN_NATURESTAFF");
  const withAliases = run("weaponIndex")(CATALOG, [{ alias: "The Zaddy Bow", weapon_id: "2H_LONGBOW" }, { alias: "daggers", weapon_id: "2H_CLAWPAIR" }, { alias: "ghost", weapon_id: "NOT_A_LINE" }]);
  check("a guild's remembered name reads as alias, normalized both ways; it overrides a built-in nickname; a name for an unknown key is dropped",
        same(match("the zaddy bow", withAliases), { status: "alias", key: "2H_LONGBOW", how: "alias", candidates: ["2H_LONGBOW"] })
        && match("Daggers", withAliases).key === "2H_CLAWPAIR" && match("ghost", withAliases).status === "none");
  check("the index leaves removed lines out and keeps the rest", !index.byKey.has("2H_IRONGAUNTLETS_HELL") && index.byKey.has("2H_LONGBOW") && index.entries.length === Object.keys(CATALOG).length - 1);
}

/* 4 - the columns and the rows */
{
  const parse = run("parseSheet"), detect = run("detectColumns"), sheetRows = run("sheetRows"), mode = run("layoutMode");
  const read = text => { const cells = parse(text).cells; const layout = detect(cells, index); return { cells, layout, rows: sheetRows(cells, layout, index) }; };
  const brief = r => `${r.text}|${r.count}|${r.player}|${r.role}|${r.party}|${r.note}|${r.match.status}`;

  const a = read("Weapon\tPlayer\tRole\tParty\tNote\nHeavy Mace\tDisc\ttank\tParty 1\tengage first\nHallowfall\tEff\thealer\tParty 1\t\nLongbow x3\t\tdps\tParty 2\t");
  check("a header row names the columns: weapon, player, role, party, note", a.layout.header && same(a.layout.kinds, ["weapon", "player", "role", "party", "note"]) && mode(a.layout.kinds) === "list", a.layout);
  check("the rows carry what sits beside the weapon; an inline count repeats the slot",
        same(a.rows.map(brief), ["Heavy Mace|1|Disc|tank|Party 1|engage first|exact", "Hallowfall|1|Eff|healer|Party 1||exact", "Longbow|3||dps|Party 2||exact"]), a.rows.map(brief));

  const b = read("Disc\tLongbow\nGus\tHallowfall\nEff\tWarbow");
  check("without a header the cells decide: short texts are players, weapons are weapons", !b.layout.header && same(b.layout.kinds, ["player", "weapon"]) && same(b.rows.map(brief), ["Longbow|1|Disc||||exact", "Hallowfall|1|Gus||||exact", "Warbow|1|Eff||||exact"]), b.layout);

  const c = read("Party 1\tPlayer\tParty 2\tPlayer\nHeavy Mace\tDisc\tLongbow\tGus\nHallowfall\tEff\tLongbow\t");
  check("party labels over two weapon columns are a grid: each column a party, its player column the one beside it, parties in order",
        c.layout.header && mode(c.layout.kinds) === "grid" && same(c.layout.kinds, ["weapon", "player", "weapon", "player"])
        && same(c.rows.map(brief), ["Heavy Mace|1|Disc||Party 1||exact", "Hallowfall|1|Eff||Party 1||exact", "Longbow|1|Gus||Party 2||exact", "Longbow|1|||Party 2||exact"]), c.rows.map(brief));
  const d = read("Heavy Mace\tLongbow\nHallowfall\tWarbow");
  check("two weapon columns without a header are parties by order", mode(d.layout.kinds) === "grid" && same(d.rows.map(r => r.party), ["Party 1", "Party 1", "Party 2", "Party 2"]));
  const e = read("Role\tGroup A\tGroup B\ntank\tHeavy Mace\tBedrock\nhealer\tHallowfall\tHoly");
  check("a role column left of the first party is shared by every party; the header labels name the parties",
        same(e.layout.kinds, ["role", "weapon", "weapon"]) && same(e.rows.map(brief), ["Heavy Mace|1||tank|Group A||exact", "Hallowfall|1||healer|Group A||exact", "Bedrock|1||tank|Group B||likely", "Holy|1||healer|Group B||likely"]), e.rows.map(brief));

  const f = read("#\tWeapon\n1\tLongbow\n2\tWarbow");
  const g = read("#\tWeapon\n3\tLongbow\n2\tWarbow");
  check("a # column is the slot number when it counts 1, 2, 3 and a count otherwise",
        same(f.layout.kinds, ["position", "weapon"]) && same(f.rows.map(r => r.count), [1, 1]) && same(g.layout.kinds, ["count", "weapon"]) && same(g.rows.map(r => r.count), [3, 2]));
  const h = read("Position\tBuild\n1\tLongbow\ntank\tHeavy Mace");
  check("a header word the cells contradict yields to the cells", same(h.layout.kinds, ["player", "weapon"]) || same(h.layout.kinds, ["note", "weapon"]), h.layout.kinds);

  const s = read("Party 1\nTanks\nHeavy Mace - Disc\nBedrock\nHealers\nHallowfall\nParty 2\nLongbow x2");
  check("one column with sections: a party label or a role word alone opens a section for the rows below; a new party clears the role",
        !s.layout.header && same(s.layout.kinds, ["weapon"])
        && same(s.rows.map(brief), ["Heavy Mace|1|Disc|Tanks|Party 1||exact", "Bedrock|1||Tanks|Party 1||likely", "Hallowfall|1||Healers|Party 1||exact", "Longbow|2|||Party 2||exact"]), s.rows.map(brief));
  const t = read("1. Longbow - Disc\n2. Hallowfall - Eff\n3. Tank - Gus\n4. Disc - Warbow\n5. Warbow - dps");
  check("a Discord list: the weapon before the dash, the player after it (or the weapon after it, swapped); a role word after the dash is the role",
        same(t.rows.map(brief), ["Longbow|1|Disc||||exact", "Hallowfall|1|Eff||||exact", "Tank|1|Gus||||none", "Warbow|1|Disc||||exact", "Warbow|1||dps|||exact"]), t.rows.map(brief));
  const u = read("Comp for Tuesday\nWeapon\tPlayer\nLongbow\tDisc");
  check("a title row above the header is left out", u.layout.header && u.layout.headerAt === 1 && u.rows.length === 1 && u.rows[0].text === "Longbow");
  const v = read("Player\tRole\nDisc\ttank");
  check("no weapon column reads as no rows", v.rows.length === 0 && !v.layout.kinds.includes("weapon"));
  const w = read("Weapon\tPlayer\n\tDisc\nLongbow\t");
  check("an empty weapon cell beside a player is an open slot row", same(w.rows.map(brief), ["|1|Disc||||none", "Longbow|1|||||exact"]));
  const kinds = a.layout.kinds.slice();
  kinds[1] = "note";
  const relaid = sheetRows(a.cells, Object.assign({}, a.layout, { kinds }), index);
  check("the caller's column map is read as set", relaid[0].player === "" && relaid[0].note === "Disc");
}

/* 5 - the slots, the summary and the names learned */
{
  const parse = run("parseSheet"), detect = run("detectColumns"), sheetRows = run("sheetRows");
  const importSlots = run("importSlots"), summary = run("importSummary"), learned = run("learnedAliases"), choice = run("defaultChoice");
  const OPEN = run("IMPORT_OPEN"), SKIP = run("IMPORT_SKIP");
  const read = text => { const cells = parse(text).cells; return sheetRows(cells, detect(cells, index), index); };
  const rows = read("Weapon\tPlayer\tRole\tParty\tNote\nHeavy Mace\tDisc\ttank\tParty 1\tengage first\nHallowfall\tEff\thealer\tParty 1\t\nLongbow x3\t\tdps\tParty 2\t\nTank\tGus\t\tParty 2\t\ngh\t\t\tParty 2\t");
  check("the summary counts rows, slots and how each was read", same(summary(rows), { rows: 5, slots: 7, matched: 3, likely: 0, uncertain: 1, none: 1 }), summary(rows));
  check("a row starts with its key, nothing when uncertain, an open slot when unread",
        choice(rows[0]) === "2H_MACE" && choice(rows[4]) === "" && choice(rows[3]) === OPEN);
  const built = importSlots(rows, null, {});
  check("the slots: a count repeats, an uncertain row is unresolved, a role word is the open slot's role, party labels ride in the note",
        built.unresolved === 1 && built.open === 1 && built.skipped === 0 && built.overflow === 0 && same(built.parties, ["Party 1", "Party 2"])
        && same(built.slots.map(s => `${s.position}:${s.weapon_id}:${s.role}:${s.note}`),
                ["1:2H_MACE:tank:engage first · Party 1", "2:MAIN_HOLYSTAFF_AVALON:healer:Party 1", "3:2H_LONGBOW:dps:Party 2", "4:2H_LONGBOW:dps:Party 2", "5:2H_LONGBOW:dps:Party 2", "6:null:Tank:Party 2"]),
        built.slots);
  const choices = rows.map(choice);
  choices[4] = "2H_HAMMER";
  choices[2] = SKIP;
  const built2 = importSlots(rows, choices, { players: true, parties: false });
  check("a choice resolves a row, a skip drops it (its count too), player names ride in the note when asked and parties do not",
        built2.unresolved === 0 && built2.skipped === 3 && built2.slots.length === 4
        && same(built2.slots.map(s => `${s.weapon_id}:${s.note}`), ["2H_MACE:engage first · Disc", "MAIN_HOLYSTAFF_AVALON:Eff", "null:Gus", "2H_HAMMER:null"]), built2.slots);
  const open = importSlots(rows, Object.assign([], choices, { 0: OPEN }), {});
  check("a matched weapon the caller sets open keeps its role and note, not the weapon's name", open.slots[0].weapon_id === null && open.slots[0].role === "tank" && open.slots[0].note === "engage first · Party 1");
  const many = read(Array.from({ length: 62 }, () => "Longbow").join("\n"));
  check("the roster cap holds: 62 rows give 60 slots and 2 overflow", importSlots(many, null, {}).slots.length === run("COMP_SLOTS_MAX") && importSlots(many, null, {}).overflow === 2);
  check("a single party never rides in the note", importSlots(read("Weapon\tParty\nLongbow\tParty 1"), null, {}).slots[0].note === null);
  const unplaced = read("Mystery pick\nLongbow");
  check("an unread text that is no role word is kept as the open slot's note", importSlots(unplaced, null, {}).slots[0].note === "Mystery pick" && importSlots(unplaced, null, {}).slots[0].role === null);

  const l = learned(rows, choices, index);
  check("the names learned: the uncertain text the caller resolved; not a read name, an open slot or a skip",
        same(l, [{ alias: "gh", weapon_id: "2H_HAMMER" }]), l);
  const overrides = rows.map(choice);
  overrides[0] = "2H_MACE";
  overrides[3] = "MAIN_MACE";
  overrides[4] = OPEN;
  const l2 = learned(rows, overrides, index);
  check("a catalog name given another line is not learned; an unread text given a line is",
        same(l2, [{ alias: "tank", weapon_id: "MAIN_MACE" }]), l2);
  const likelyRows = read("hallow\nperma");
  const c3 = likelyRows.map(choice);
  c3[1] = "2H_FROSTSTAFF_CRYSTAL";
  check("a likely reading the caller keeps is not learned; one the caller changes is", same(learned(likelyRows, c3, index), [{ alias: "perma", weapon_id: "2H_FROSTSTAFF_CRYSTAL" }]));
  const payload = run("aliasPayload")([{ alias: " The Zaddy Bow ", weapon_id: "2H_LONGBOW" }, { alias: "!!!", weapon_id: "2H_BOW" }, { alias: "x", weapon_id: "not a key" }, { alias: "y".repeat(70), weapon_id: "2H_BOW" }]);
  check("the payload is normalized and on the form; a name with nothing left, a name too long and a key off the form are dropped", same(payload, [{ alias: "zaddy bow", weapon_id: "2H_LONGBOW" }]), payload);
  check("the bounds: ALIAS_MAX 64, ALIASES_MAX 500, ALIAS_SAVE_MAX 100, the form", run("ALIAS_MAX") === 64 && run("ALIASES_MAX") === 500 && run("ALIAS_SAVE_MAX") === 100 && run("ALIAS_RE").test("1h holy") && !run("ALIAS_RE").test("Holy"));
}

/* 6 - error wording and what the helpers send */
{
  const msg = run("importErrorMessage"), M = run("IMPORT_MSG"), importError = run("importError");
  const cases = [
    ["network", new TypeError("Failed to fetch"), M.network],
    ["not signed in", { code: "42501", message: "sign in to save aliases" }, M.signedOut],
    ["table missing", { code: "PGRST205", message: "Could not find the table" }, M.missing],
    ["too many names", { code: "23514", message: "a guild keeps at most 500 aliases" }, M.tooManyAliases],
    ["refused by the policy", { code: "42501", message: "new row violates row-level security policy" }, M.refused],
    ["no row came back", { code: "refused", message: "the server refused the change" }, M.refused],
    ["a value the checks refuse", { code: "23514", message: "violates check constraint" }, M.invalid],
    ["a workbook", importError("xlsx"), M.xlsx],
    ["nothing pasted", importError("empty"), M.empty],
    ["unknown with its message", { code: "XX000", message: "odd" }, "Something went wrong: odd"],
  ];
  for (const [name, err, want] of cases) check(`error wording: ${name}`, msg(err) === want, msg(err));
  check("error wording: the bound in the sentence is the bound in force", M.tooManyAliases.includes(String(run("ALIASES_MAX"))));

  const find = table => CALLS.find(c => c.table === table);
  const has = (ops, ...want) => ops.some(o => want.every((w, i) => same(o[i], w)));
  CALLS.length = 0;
  REPLY.weapon_aliases = { data: [{ alias: "perma", weapon_id: "2H_ICECRYSTAL_UNDEAD" }], error: null };
  const list = await run("loadGuildAliases")("g1");
  let q = find("weapon_aliases");
  check("loadGuildAliases reads one guild's names in order", has(q.ops, "eq", "guild_id", "g1") && has(q.ops, "order", "alias", { ascending: true }) && list.length === 1, q.ops);
  CALLS.length = 0;
  REPLY["rpc:save_weapon_aliases"] = { data: 2, error: null };
  const n = await run("saveGuildAliases")("g1", [{ alias: " Perma ", weapon_id: "2H_ICECRYSTAL_UNDEAD" }, { alias: "!!!", weapon_id: "2H_BOW" }, { alias: "1h holy", weapon_id: "MAIN_HOLYSTAFF" }]);
  const r = CALLS.find(c => c.rpc);
  check("saveGuildAliases sends one save_weapon_aliases payload, normalized and on the form, and returns the count",
        r.rpc === "save_weapon_aliases" && same(r.args, { guild: "g1", aliases: [{ alias: "perma", weapon_id: "2H_ICECRYSTAL_UNDEAD" }, { alias: "1h holy", weapon_id: "MAIN_HOLYSTAFF" }] }) && n === 2, r.args);
  CALLS.length = 0;
  REPLY.weapon_aliases = { data: [{ alias: "perma" }], error: null };
  await run("deleteGuildAlias")("g1", "perma");
  q = find("weapon_aliases");
  check("deleteGuildAlias deletes one name of one guild and reads the row back", q.ops.some(o => o[0] === "delete") && has(q.ops, "eq", "guild_id", "g1") && has(q.ops, "eq", "alias", "perma") && q.ops.some(o => o[0] === "select"), q.ops);
  CALLS.length = 0;
  REPLY.weapon_aliases = { data: [], error: null };
  let refused = null;
  try { await run("deleteGuildAlias")("g1", "perma"); } catch (e) { refused = e; }
  check("a deletion the policy refused (no row back) is reported", refused && refused.code === "refused");

  const src = fs.readFileSync(path.join(DASH, "_import.js"), "utf8");
  check("the module's one table is weapon_aliases; the comp goes through the comps module's helper; no planner state, no channel",
        same([...new Set(src.match(/\.from\("(\w+)"/g))], ['.from("weapon_aliases"']) && /saveTemplate\(/.test(src) && !/save_comp_template|\.channel\(/.test(src)
        && !/location\.hash|\bENG\b|CompEngine|DATASET|\brender\(|saveHash|loadHash/.test(src));
}

console.log(`\n${pass}/${pass + fail} import tests passed`);
process.exit(fail ? 1 : 0);
})();
