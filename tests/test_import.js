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
 * columns (a header, the cells, a list or a grid, the gear slots), how a
 * gear name is read within its slot (the gear catalog as build.py ships
 * it: a tier the sheet writes, the highest otherwise, a city cape's
 * short name), the rows (sections, counts, a grid's parties, the gear),
 * the slots and their kits (an open slot and a two-hander's off-hand
 * keep none), the share hash the kits ride in, read back by the
 * planner's own decoder (_loadout.js partyDecode) and the sheet's build
 * read (_build.js), the names learned, error wording, and what the
 * helpers send. The workbook reader: tests/test_xlsx.js.
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

/* the dataset, and the gear catalog as build.py ships it to the page
   (GEAR): gear_lines' items, named by the curated display name where
   the item is curated, else with the tier adjective stripped */
const DS = JSON.parse(fs.readFileSync(DATASET, "utf8"));
const weapons = DS.weapons;
const GEAR_LINES = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "pipeline", "out", "gear_lines.json"), "utf8"));
const TIER_ADJ = ["Beginner's ", "Novice's ", "Journeyman's ", "Adept's ", "Expert's ", "Master's ", "Grandmaster's ", "Elder's "];
const GEAR = {};
for (const [key, item] of Object.entries(GEAR_LINES)) {
  const g = Object.assign({}, item);
  const curated = (DS.gear || {})[key] || {};
  if (curated.display_name) g.name = curated.display_name;
  else for (const adj of TIER_ADJ) if (String(g.name || "").startsWith(adj)) { g.name = g.name.slice(adj.length); break; }
  GEAR[key] = g;
}

const ctx = { console, URLSearchParams, setTimeout, Promise, Proxy, Date, decodeURIComponent, encodeURIComponent };
ctx.window = ctx;
ctx.window.DB = DB;
/* the planner's tables the codec and the build read reads: the gear
   catalog, the weapons the planner holds, the spell pools */
ctx.GEAR = GEAR;
ctx.WEAPONS = weapons;
ctx.ICONS = {};
vm.createContext(ctx);
for (const f of ["_loadout.js", "_auth.js", "_profile.js", "_guild.js", "_comps.js", "_events.js", "_signup.js", "_history.js", "_import.js", "_build.js"]) {
  vm.runInContext(fs.readFileSync(path.join(DASH, f), "utf8"), ctx, { filename: f });
}
const run = expr => vm.runInContext(expr, ctx);

/* the catalog as build.py stamps it: every line's display name, the
   removed ones marked */
const SPELLS = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "pipeline", "out", "spell_index.json"), "utf8"));
const CATALOG = {};
for (const [key, w] of Object.entries(weapons)) {
  CATALOG[key] = { name: w.display_name || key, role: null, item: "" };
  const names = (w.loadout && w.loadout.slot_names) || [];
  if (names.includes("e")) {
    CATALOG[key].e = w.loadout.slot_spells[names.indexOf("e")].map(id => (SPELLS[id] || {}).name).filter(Boolean);
  }
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
        && same(parse("Heavy Crossbow"), { name: "Heavy Crossbow", count: 1, tail: "" }) && same(parse("8.3 Longbow"), { name: "8.3 Longbow", count: 1, tail: "" })
        && same(parse("Longbow: 8.3"), { name: "Longbow", count: 1, tail: "" }) && same(parse("Longbow - T8"), { name: "Longbow", count: 1, tail: "" }));
  check("a count is bounded by the roster cap", parse("99x Longbow").count === run("COMP_SLOTS_MAX"));
  check("a bracketed word beside the name is the label, before or after; a count and a tier in brackets are not",
        same(parse("GA (Cleanse)"), { name: "GA", count: 1, tail: "", label: "Cleanse" })
        && same(parse("Witchwork (DPS)"), { name: "Witchwork", count: 1, tail: "", label: "DPS" })
        && same(parse("[Support] Rotcaller"), { name: "Rotcaller", count: 1, tail: "", label: "Support" })
        && same(parse("Occult [Disengage]"), { name: "Occult", count: 1, tail: "", label: "Disengage" })
        && same(parse("Longbow (2)"), { name: "Longbow", count: 2, tail: "" })
        && same(parse("Longbow (8.3)"), { name: "Longbow", count: 1, tail: "" }), parse("GA (Cleanse)"));
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
  const withAliases = run("weaponIndex")(CATALOG, [{ alias: "The Zaddy Bow", weapon_id: "2H_LONGBOW" }, { alias: "daggers", weapon_id: "2H_CLAWPAIR" }, { alias: "gizmo", weapon_id: "NOT_A_LINE" }]);
  check("a guild's remembered name reads as alias, normalized both ways; it overrides a built-in nickname; a name for an unknown key is dropped",
        same(match("the zaddy bow", withAliases), { status: "alias", key: "2H_LONGBOW", how: "alias", candidates: ["2H_LONGBOW"] })
        && match("Daggers", withAliases).key === "2H_CLAWPAIR" && match("gizmo", withAliases).status === "none");
  check("the index leaves removed lines out and keeps the rest", !index.byKey.has("2H_IRONGAUNTLETS_HELL") && index.byKey.has("2H_LONGBOW") && index.entries.length === Object.keys(CATALOG).length - 1);
}

/* 3b - a caller's sheet: short names, a label in brackets, a weapon
   named by its E, gear columns beside the weapon */
{
  const match = run("matchWeapon");
  const want = { "GA": "2H_ARCANESTAFF", "Golem": "2H_SHAPESHIFTER_KEEPER", "Rotcaller": "MAIN_CURSEDSTAFF_CRYSTAL",
                 "Occult": "2H_ENIGMATICSTAFF", "Witchwork": "2H_SHAPESHIFTER_MORGANA", "Bedrock": "MAIN_ROCKMACE_KEEPER",
                 "Forge Bark": "MAIN_NATURESTAFF_CRYSTAL", "Permafrost": "2H_ICECRYSTAL_UNDEAD", "Spiked": "2H_KNUCKLES_SET3" };
  const got = Object.fromEntries(Object.keys(want).map(t => [t, match(t, index)]));
  const byName = n => Object.keys(CATALOG).find(k => CATALOG[k].name === n);
  check("short names read as one line: the initials, a prefix, a split word",
        ["GA", "Rotcaller", "Occult", "Witchwork", "Bedrock", "Forge Bark", "Permafrost", "Spiked"]
          .every(t => got[t].status === "likely")
        && got.GA.key === byName("Great Arcane Staff") && got.Rotcaller.key === byName("Rotcaller Staff")
        && got.Occult.key === byName("Occult Staff") && got.Witchwork.key === byName("Witchwork Staff")
        && got.Bedrock.key === byName("Bedrock Mace") && got["Forge Bark"].key === byName("Forgebark Staff")
        && got.Permafrost.key === byName("Permafrost Prism") && got.Spiked.key === byName("Spiked Gauntlets"),
        Object.fromEntries(Object.entries(got).map(([t, m]) => [t, `${m.status}:${m.key}:${m.how}`])));
  check("a weapon named by a word of its own E spell alone is read through the spell (Golem: the Earthrune Staff)",
        got.Golem.status === "likely" && got.Golem.how === "spell" && got.Golem.key === byName("Earthrune Staff"),
        `${got.Golem.status}:${got.Golem.key}:${got.Golem.how}`);
  check("a role word is never read as a spell word, and a word of no E is no weapon",
        match("Bomb", index).how !== "spell" && match("Purge", index).how !== "spell" && match("Mystery pick", index).status === "none");

  const cells = run("parseSheet")("Weapon\tPlayer\tHead\tChest\tBoots\nGolem\tAsh\tGuardian Helmet\tJudicator Armor\tKnight Boots\n"
    + "GA (Cleanse)\tBo\tCleric Cowl\tCleric Robe\tScholar Sandals\nHeavy Mace\tCy\tSoldier Helmet\tKnight Armor\tSoldier Boots\n"
    + "Witchwork (DPS)\tDee\tMage Cowl\tMage Robe\tMage Sandals\nHallowfall\tEff\tCleric Cowl\tPurity Robe\tCleric Sandals").cells;
  const layout = run("detectColumns")(cells, index);
  check("gear columns beside the weapon are read as their slots (helm, armor, boots), never as players",
        same(layout.kinds, ["weapon", "player", "head", "armor", "shoes"]), layout.kinds);
  const rows = run("sheetRows")(cells, layout, index);
  check("the bracketed word is the slot's role, the name without it is what is matched",
        same(rows.map(r => `${r.text}|${r.role}|${r.match.status}`),
             ["Golem||likely", "GA|Cleanse|likely", "Heavy Mace||exact", "Witchwork|DPS|likely", "Hallowfall||exact"]),
        rows.map(r => `${r.text}|${r.role}|${r.match.status}`));
  const built = run("importSlots")(rows, rows.map(r => run("defaultChoice")(r)), {});
  check("the slots carry the caller's label as the role: Witchwork as DPS, the Great Arcane as Cleanse",
        built.slots.length === 5 && built.slots[3].weapon_id === byName("Witchwork Staff") && built.slots[3].role === "DPS"
        && built.slots[1].role === "Cleanse" && built.slots[0].weapon_id === byName("Earthrune Staff"), built.slots);
  const withRole = run("parseSheet")("Weapon\tRole\nGA (Cleanse)\tsupport").cells;
  const rows2 = run("sheetRows")(withRole, run("detectColumns")(withRole, index), index);
  check("where the sheet has a role column the bracketed word rides in the note",
        rows2.length === 1 && rows2[0].role === "support" && rows2[0].note === "Cleanse", rows2[0]);
  const learned = run("learnedAliases")(rows, rows.map(r => run("defaultChoice")(r)), index);
  check("a name read without the caller choosing is not remembered; the label never enters a remembered name",
        same(learned, []), learned);
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

/* 5b - how a gear name is read, within its slot, over the gear catalog
   the page ships */
{
  const gearIdx = run("gearIndex")(GEAR);
  const read = (text, slot) => run("matchGear")(text, slot, gearIdx);
  const cases = [
    ["Guardian Helmet", "head", "exact", "HEAD_PLATE_SET3"], ["Elder's Guardian Helmet", "head", "exact", "HEAD_PLATE_SET3"],
    ["T8 Guardian Helmet", "head", "exact", "HEAD_PLATE_SET3"], ["HEAD_PLATE_SET3", "head", "exact", "HEAD_PLATE_SET3"],
    ["T8_HEAD_PLATE_SET3@3", "head", "exact", "HEAD_PLATE_SET3"], ["Guardian", "head", "likely", "HEAD_PLATE_SET3"],
    ["Guardian", "armor", "likely", "ARMOR_PLATE_SET3"], ["Judi helm", "head", "likely", "HEAD_PLATE_KEEPER"],
    ["Guardian Helment", "head", "likely", "HEAD_PLATE_SET3"], ["Robe of Purity", "armor", "exact", "ARMOR_CLOTH_AVALON"],
    ["Purity", "armor", "likely", "ARMOR_CLOTH_AVALON"], ["Hellion Jacket", "armor", "exact", "ARMOR_LEATHER_HELL"],
    ["Poison Potion", "potion", "exact", "T8_POTION_COOLDOWN"], ["T6 Poison Potion", "potion", "exact", "T6_POTION_COOLDOWN"],
    ["Poison", "potion", "likely", "T8_POTION_COOLDOWN"], ["resi pot", "potion", "likely", "T7_POTION_STONESKIN"],
    ["cleanse", "potion", "likely", "T7_POTION_CLEANSE2"], ["Gigantify", "potion", "likely", "T7_POTION_REVIVE"],
    ["Minor Healing Potion", "potion", "exact", "T2_POTION_HEAL"], ["Beef Stew", "food", "exact", "T8_MEAL_STEW"],
    ["Pork Omelette", "food", "exact", "T7_MEAL_OMELETTE"], ["BW", "cape", "likely", "CAPEITEM_FW_BRIDGEWATCH"],
    ["FS cape", "cape", "likely", "CAPEITEM_FW_FORTSTERLING"], ["Thetford", "cape", "likely", "CAPEITEM_FW_THETFORD"],
    ["EoS", "offhand", "likely", "OFF_ORB_MORGANA"], ["Muisak", "offhand", "exact", "OFF_DEMONSKULL_HELL"],
  ];
  for (const [text, slot, status, key] of cases) {
    const m = read(text, slot);
    check(`gear: "${text}" in a ${slot} column reads as ${status} ${key}`, m.status === status && m.key === key, m);
  }
  const royal = read("Royal", "head");
  check("gear: a name several items share is uncertain, one candidate per name (the Royal cowl, hood and helmet)",
        royal.status === "uncertain" && royal.key === null && same([...royal.candidates].sort(), ["HEAD_CLOTH_ROYAL", "HEAD_LEATHER_ROYAL", "HEAD_PLATE_ROYAL"]), royal);
  const omelette = read("Omelette", "food");
  check("gear: a meal named by its kind alone is uncertain among the meals of that kind",
        omelette.status === "uncertain" && omelette.candidates.includes("T7_MEAL_OMELETTE") && omelette.candidates.length <= run("IMPORT_CANDIDATES"), omelette);
  check("gear: a name is read within its column's slot alone, and an unknown name is none",
        read("Guardian Helmet", "armor").status !== "exact" && read("Shoes of Speed", "shoes").status === "none"
        && read("Guardian", "potion").status === "none" && read("", "head").status === "none");
  check("gear: the tier a sheet writes, else the highest: T6 and T8 Poison, a tier word, an enchantment",
        run("gearTier")("T6 Poison") === 6 && run("gearTier")("Poison 8.1") === 8 && run("gearTier")("Master's Poison") === 6
        && run("gearTier")("T8_MEAL_STEW") === 8 && run("gearTier")("Poison") === null);
  check("gear: the index carries every slot and every item the page ships",
        run("GEAR_KINDS").every(s => gearIdx[s].entries.length > 0)
        && run("GEAR_KINDS").reduce((n, s) => n + gearIdx[s].entries.length, 0) === Object.values(GEAR).filter(g => run("GEAR_KINDS").includes(g.slot)).length);
  check("gear: the gear kinds are the loadout codec's slots, in its order", same(run("GEAR_KINDS"), run("LO_SLOTS")));

  /* the columns: a header names each slot; without one, cells that are
     mostly one slot's items name it; a set's name alone names no slot */
  const parse = run("parseSheet"), detect = run("detectColumns"), sheetRows = run("sheetRows");
  const head = parse("Weapon\tPlayer\tHelm\tChest\tBoots\tCape\tOff-hand\tPotion\tFood\nHallowfall\tAsh\tCleric Cowl\tCleric Robe\tScholar Sandals\tBW\tMuisak\tPoison\tPork Omelette").cells;
  check("gear: header words name the seven slots", same(detect(head, index, gearIdx).kinds, ["weapon", "player", "head", "armor", "shoes", "cape", "offhand", "potion", "food"]),
        detect(head, index, gearIdx).kinds);
  const bare = parse("Golem\tGuardian Helmet\tJudicator Armor\tKnight Boots\nHallowfall\tCleric Cowl\tCleric Robe\tScholar Sandals\nLongbow\tHellion Hood\tHellion Jacket\tHellion Shoes").cells;
  check("gear: without a header the cells name the slot", same(detect(bare, index, gearIdx).kinds, ["weapon", "head", "armor", "shoes"]), detect(bare, index, gearIdx).kinds);
  const sets = parse("Golem\tGuardian\nHallowfall\tCleric\nLongbow\tHellion").cells;
  check("gear: a column of set names alone reads as no slot (a helm, an armor and boots equally)",
        !run("GEAR_KINDS").includes(detect(sets, index, gearIdx).kinds[1]), detect(sets, index, gearIdx).kinds);
  check("gear: without the gear catalog a gear header still names the slot",
        same(detect(head, index).kinds.slice(2, 5), ["head", "armor", "shoes"]));
  const grid = parse("Party 1\tHelm\tParty 2\tHelm\nGolem\tGuardian Helmet\tLongbow\tHellion Hood").cells;
  const gridRows = sheetRows(grid, detect(grid, index, gearIdx), index, gearIdx);
  check("gear: in a grid each party's gear columns are the ones to its right",
        same(gridRows.map(r => `${r.text}|${r.party}|${(r.gear.head || {}).text}|${((r.gear.head || {}).match || {}).key}`),
             ["Golem|Party 1|Guardian Helmet|HEAD_PLATE_SET3", "Longbow|Party 2|Hellion Hood|HEAD_LEATHER_HELL"]),
        gridRows.map(r => r.gear));
}

/* 5c - the kits, the share hash they ride in, and the link read back by
   the planner's own decoder and by the sheet's build read */
{
  const gearIdx = run("gearIndex")(GEAR);
  const parse = run("parseSheet"), detect = run("detectColumns"), sheetRows = run("sheetRows"), importSlots = run("importSlots");
  const text = "Weapon\tPlayer\tHelm\tChest\tBoots\tCape\tOff-hand\tPotion\tFood\n"
    + "Hallowfall\tAsh\tCleric Cowl\tCleric Robe\tScholar Sandals\tBW\tMuisak\tPoison\tPork Omelette\n"
    + "Mystery pick\tBo\tGuardian Helmet\t\t\t\t\t\t\n"
    + "Golem\tCy\tGuardian Helmet\tJudicator Armor\tKnight Boots\tThetford\tMuisak\tT6 Poison Potion\tBeef Stew\n"
    + "Longbow x2\tDee\tHellion Hood\tHellion Jacket\tRoyal\t\t\tGigantify\tOmelette\n"
    + "Bedrock\tEff\t\t\t\t\t\t\t";
  const cells = parse(text).cells;
  const rows = sheetRows(cells, detect(cells, index, gearIdx), index, gearIdx);
  const choices = rows.map(r => run("defaultChoice")(r));
  const built = importSlots(rows, choices, {});
  const kitOf = i => (built.slots[i].kit || {}).loadout || null;
  check("kits: a read row's pieces in the codec's slots",
        same(kitOf(0), { head: "HEAD_CLOTH_SET2", armor: "ARMOR_CLOTH_SET2", shoes: "SHOES_CLOTH_SET1", cape: "CAPEITEM_FW_BRIDGEWATCH",
                         offhand: "OFF_DEMONSKULL_HELL", potion: "T8_POTION_COOLDOWN", food: "T7_MEAL_OMELETTE" }), kitOf(0));
  check("kits: an open slot carries none, its row's gear notwithstanding", built.slots[1].weapon_id === null && !built.slots[1].kit);
  check("kits: a two-handed weapon holds no off-hand; the sheet's T6 is the potion's tier",
        built.slots[2].weapon_id === "2H_SHAPESHIFTER_KEEPER" && !("offhand" in kitOf(2)) && kitOf(2).potion === "T6_POTION_COOLDOWN"
        && kitOf(2).food === "T8_MEAL_STEW" && kitOf(2).cape === "CAPEITEM_FW_THETFORD", kitOf(2));
  check("kits: an uncertain piece is no piece until chosen; a count repeats the kit",
        same(kitOf(3), { head: "HEAD_LEATHER_HELL", armor: "ARMOR_LEATHER_HELL", potion: "T7_POTION_REVIVE" }) && same(kitOf(4), kitOf(3))
        && kitOf(3) !== kitOf(4), kitOf(3));
  check("kits: a row without gear carries none, and the count of kits is the slots that carry one",
        !built.slots[5].kit && built.kits === 4 && built.slots.length === 6);
  const chosen = rows.map(() => ({}));
  chosen[3] = { shoes: "SHOES_LEATHER_ROYAL", food: "" };
  const built2 = importSlots(rows, choices, { gear: chosen });
  check("kits: the caller's choice of an uncertain piece joins the kit", kitOf(3) && built2.slots[3].kit.loadout.shoes === "SHOES_LEATHER_ROYAL");
  const gs = run("gearSummary")(rows, chosen, choices);
  check("kits: the review counts the pieces kept (none of an open row, no two-hander's off-hand), the ones to check, to choose and unread",
        same(gs, { pieces: 17, likely: 4, uncertain: 1, none: 0 }), gs);

  const template = { content: "castle", style: "clap", planned_size: 20 };
  const hash = run("kitHash")(template, built.slots);
  const params = Object.fromEntries(hash.split("&").map(kv => [kv.slice(0, kv.indexOf("=")), kv.slice(kv.indexOf("=") + 1)]));
  check("the share hash: the planner's fields, one p= entry per slot up to the last weapon (an open slot an empty entry), the kits in g=",
        params.c === "castle" && params.n === "20" && params.st === "clap"
        && params.p === "MAIN_HOLYSTAFF_AVALON,,2H_SHAPESHIFTER_KEEPER,2H_LONGBOW,2H_LONGBOW,MAIN_ROCKMACE_KEEPER"
        && !!params.g && !("f" in params) && !("k" in params), params);
  check("the share hash is on the database's form and under its bound",
        /^[A-Za-z0-9_.,=&%:~!*()-]+$/.test(hash) && hash.length <= run("COMP_HASH_MAX"));
  const opened = run("partyDecode")(params, "");
  check("the planner reads the link as the comp: the open slot dropped with its fields, every member in its kit",
        same(opened.party, ["MAIN_HOLYSTAFF_AVALON", "2H_SHAPESHIFTER_KEEPER", "2H_LONGBOW", "2H_LONGBOW", "MAIN_ROCKMACE_KEEPER"])
        && same(opened.LOADOUT[0], kitOf(0)) && same(opened.LOADOUT[1], kitOf(2)) && same(opened.LOADOUT[2], kitOf(3))
        && same(opened.LOADOUT[3], kitOf(4)) && opened.LOADOUT[4] === undefined && opened.PLANNED === 20,
        { party: opened.party, LOADOUT: opened.LOADOUT });
  const saved = Object.assign({}, template, { share_hash: hash });
  check("a comp saved with the link opens with it whole (the kits ride along)", run("templateHash")(saved, built.slots) === hash);
  const builds = run("sheetBuilds")(hash, built.slots.map(s => ({ position: s.position, weapon_id: s.weapon_id })),
                                    { decode: run("loadoutDecode"), gear: GEAR, spells: {} });
  check("a CTA made from it shows every slot's build at its position, a slot after the open one included",
        builds[1].state === "set" && builds[2].state === "none" && builds[3].state === "set"
        && same(builds[3].gear.map(g => g.key), ["HEAD_PLATE_SET3", "ARMOR_PLATE_KEEPER", "SHOES_PLATE_SET2", "CAPEITEM_FW_THETFORD", "T6_POTION_COOLDOWN", "T8_MEAL_STEW"])
        && builds[5].state === "set" && builds[6].state === "unset", builds);
  const payload = run("templatePayload")(Object.assign({ guild_id: "g1", name: "Castle", notes: "" }, saved, { slots: built.slots }));
  check("the slots sent hold no kit: the kits live in the link", payload.slots.every(s => !("kit" in s)) && payload.share_hash === hash);
  check("a sheet without gear makes no link", run("importSlots")(sheetRows(parse("Weapon\nLongbow").cells, detect(parse("Weapon\nLongbow").cells, index, gearIdx), index, gearIdx), null, {}).kits === 0);
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
    ["a workbook protected by a password", importError("xlsxLocked"), M.xlsxLocked],
    ["an Excel 97-2003 workbook", importError("xls"), M.xls],
    ["a damaged workbook", importError("xlsxCorrupt"), M.xlsxCorrupt],
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
