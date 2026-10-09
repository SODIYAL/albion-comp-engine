/* History tests - dashboard/_history.js.
 *
 * The account modules run together in a vm context with no document, as
 * the page loads them: the helpers and the pure functions load, and each
 * UI block returns before touching the DOM. The helper runs against a
 * stub client that records the call, so what the page asks Supabase is
 * pinned without a network; tests/test_supabase_rls.mjs pins what the
 * database answers.
 *
 * Pinned: the show rate and its wording, the regular's definition, the
 * player rows (order, rate, roles and plays through the catalog), the
 * name filter, the weapons fielded, the completed CTAs with their fill,
 * the totals, error wording, the one call the helper makes, and the
 * period the facts cover (the last 30 days, the last 90 days, all time).
 *
 * Run:  node tests/test_history.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const DASH = path.join(__dirname, "..", "dashboard");

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log(`PASS  ${name}`); }
  else { fail++; console.log(`FAIL  ${name}${detail !== undefined ? "\n      " + JSON.stringify(detail) : ""}`); }
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

const CALLS = [];
const REPLY = {};
const DB = {
  auth: {
    getSession: async () => ({ data: { session: null }, error: null }),
    onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
  },
  from() { throw new Error("the history module reaches the database through its function alone"); },
  rpc(fn, args) {
    CALLS.push({ rpc: fn, args });
    return Promise.resolve(REPLY[`rpc:${fn}`] || { data: null, error: null });
  },
  channel() { throw new Error("history is not live"); },
};

const ctx = { console, URLSearchParams, setTimeout, Promise, Proxy, Date, decodeURIComponent, encodeURIComponent };
ctx.window = ctx;
ctx.window.DB = DB;
vm.createContext(ctx);
for (const f of ["_auth.js", "_profile.js", "_guild.js", "_comps.js", "_events.js", "_signup.js", "_history.js"]) {
  vm.runInContext(fs.readFileSync(path.join(DASH, f), "utf8"), ctx, { filename: f });
}
const run = expr => vm.runInContext(expr, ctx);

const CATALOG = {
  "2H_LONGBOW": { name: "Longbow", role: "dps", item: "" },
  MAIN_MACE_HELL: { name: "Incubus Mace", role: "frontline", item: "" },
  MAIN_HOLYSTAFF_AVALON: { name: "Hallowfall", role: "healer", item: "" },
};

(async () => {

/* 1 - the measures */
{
  const rate = run("showRate"), pct = run("ratePct");
  check("show rate is attended over attended plus no-show; nothing marked is no rate",
        rate(4, 1) === 0.8 && rate(0, 3) === 0 && rate(0, 0) === null && rate(null, null) === null && rate("2", "2") === 0.5);
  check("a rate reads as a whole percent; none as a dash", pct(0.8) === "80%" && pct(0.333) === "33%" && pct(null) === "—" && pct("0.5") === "50%");
  const regular = run("isRegular");
  check("a regular attended REGULAR_MIN_ATTENDED or more at REGULAR_MIN_RATE or better",
        run("REGULAR_MIN_ATTENDED") === 3 && run("REGULAR_MIN_RATE") === 0.75
        && regular({ attended: 3, no_show: 1 }) && !regular({ attended: 2, no_show: 0 }) && !regular({ attended: 3, no_show: 2 })
        && regular({ attended: 5, no_show: 0, show_rate: 1 }) && !regular({ attended: 5, no_show: 0, show_rate: 0.5 }));
}

/* 2 - the rows */
{
  const players = [
    { who: "guest:disc", name: "Disc", account: false, ctas: 1, attended: 1, no_show: 0, cancelled: 0, reserve: 0, unmarked: 0, show_rate: 1, weapons: [{ weapon_id: "MAIN_HOLYSTAFF_AVALON", n: 1 }] },
    { who: "account:f", name: "Eff", account: true, ctas: 4, attended: 3, no_show: 1, cancelled: 0, reserve: 0, unmarked: 0, show_rate: 0.75, last_attended: "2026-10-06T18:00:00Z",
      weapons: [{ weapon_id: "MAIN_MACE_HELL", n: 2 }, { weapon_id: "2H_LONGBOW", n: 1 }, { weapon_id: "MYSTERY", n: 1 }, { weapon_id: "X", n: 1 }] },
    { who: "guest:gus", name: "Gus", account: false, ctas: 3, attended: 3, no_show: 0, cancelled: 0, reserve: 0, unmarked: 0, show_rate: 1, weapons: [{ weapon_id: "2H_LONGBOW", n: 3 }] },
    { who: "guest:res", name: "Res", account: false, ctas: 2, attended: 0, no_show: 0, cancelled: 1, reserve: 1, unmarked: 0, show_rate: null, weapons: [] },
  ];
  const rows = run("playerRows")(players, CATALOG);
  check("players sort by attended, then CTAs, then name", same(rows.map(r => r.name), ["Eff", "Gus", "Disc", "Res"]), rows.map(r => r.name));
  const eff = rows[0];
  check("a row carries its rate, its regular mark, its plays named through the catalog (at most HISTORY_PLAYS_SHOWN, unknown keys kept) and the roles they cover in order",
        eff.rate === 0.75 && eff.regular === true && eff.plays.length === run("HISTORY_PLAYS_SHOWN")
        && same(eff.plays.map(p => `${p.name}:${p.n}:${p.role}`), ["Incubus Mace:2:frontline", "Longbow:1:dps", "MYSTERY:1:null"])
        && same(eff.roles, ["frontline", "dps"]), eff);
  check("a player with nothing marked has no rate and is no regular", rows[3].rate === null && rows[3].regular === false && same(rows[3].plays, []));
  check("Gus is a regular; Disc, with one CTA, is not", rows[1].regular && !rows[2].regular);
  const filter = run("filterPlayers");
  check("the filter holds the name, any case; empty keeps all", same(filter(rows, " gU ").map(r => r.name), ["Gus"]) && filter(rows, "").length === 4 && filter(rows, "zzz").length === 0);

  const weapons = run("weaponRows")([{ weapon_id: "MAIN_MACE_HELL", n: 2, players: 1 }, { weapon_id: "2H_LONGBOW", n: 4, players: 2 }, { weapon_id: "NEW_THING", n: 1, players: 1 }], CATALOG);
  check("the weapons fielded sort by count, named through the catalog, an unknown key kept",
        same(weapons.map(w => `${w.name}:${w.n}:${w.players}:${w.role}`), ["Longbow:4:2:dps", "Incubus Mace:2:1:frontline", "NEW_THING:1:1:null"]), weapons);

  const ctas = run("ctaRows")([
    { id: "a", name: "First", starts_at: "2026-10-01T18:00:00Z", slots: 3, claimed: 3, attended: 2, no_show: 1, unmarked: 0 },
    { id: "b", name: "Second", starts_at: "2026-10-06T18:00:00Z", slots: 4, claimed: 2, attended: 2, no_show: 0, unmarked: 0 },
    { id: "c", name: "Empty", starts_at: "2026-10-03T18:00:00Z", slots: 0, claimed: 0, attended: 0, no_show: 0, unmarked: 0 },
  ]);
  check("the completed CTAs come latest first, each with its fill; a roster without slots has none",
        same(ctas.map(c => `${c.id}:${c.fill}`), ["b:0.5", "c:null", "a:1"]), ctas.map(c => `${c.id}:${c.fill}`));

  const totals = run("historyTotals")({ ctas: "2", records: 6, attended: 4, no_show: 1, unmarked: 0, cancelled: 0, reserve: 1, show_rate: 0.8, fill: 0.833 });
  check("the totals read as numbers, rates included", totals.ctas === 2 && totals.attended === 4 && totals.rate === 0.8 && totals.fill === 0.833);
  check("empty totals are zeros without a rate", run("historyTotals")(null).ctas === 0 && run("historyTotals")({}).rate === null && run("historyTotals")({ attended: 2, no_show: 2 }).rate === 0.5);
}

/* 3 - error wording and the helper */
{
  const msg = run("historyErrorMessage"), M = run("HISTORY_MSG");
  check("error wording: network, not signed in, the function missing, unknown with its message",
        msg(new TypeError("Failed to fetch")) === M.network && msg({ code: "not_signed_in" }) === M.signedOut
        && msg({ code: "PGRST202", message: "Could not find the function" }) === M.missing
        && msg({ code: "XX000", message: "odd" }) === "Something went wrong: odd");

  CALLS.length = 0;
  REPLY["rpc:guild_history"] = { data: { totals: { ctas: 1 }, ctas: [], players: [], weapons: [] }, error: null };
  const facts = await run("loadGuildHistory")("g1");
  check("loadGuildHistory asks guild_history for one guild", same(CALLS[0], { rpc: "guild_history", args: { guild_id: "g1" } }) && facts.totals.ctas === 1);
  CALLS.length = 0;
  await run("loadGuildHistory")("g1", "2026-09-08T12:00:00.000Z");
  await run("loadGuildHistory")("g1", null);
  check("a period rides the call as its start; all time is the call that names the guild alone",
        same(CALLS[0], { rpc: "guild_history", args: { guild_id: "g1", since: "2026-09-08T12:00:00.000Z" } })
        && same(CALLS[1], { rpc: "guild_history", args: { guild_id: "g1" } }), CALLS);
  REPLY["rpc:guild_history"] = { data: null, error: null };
  check("no answer reads as empty facts", same(await run("loadGuildHistory")("g1"), { totals: {}, ctas: [], players: [], weapons: [] }));

  const src = fs.readFileSync(path.join(DASH, "_history.js"), "utf8");
  check("the module reads through one function and touches neither the planner nor the sheet's channel",
        !/\.from\(/.test(src) && !/\.channel\(/.test(src) && !/location\.hash|\bENG\b|CompEngine|DATASET|\brender\(|saveHash|loadHash/.test(src));
  check("no skill rating: the module offers none", !/skill|rating/i.test(src.replace(/None of (this|these) is a skill rating[^\n]*/g, "")));
}

/* 4 - the export: the facts as a sheet */
{
  const facts = {
    players: [{ name: "Gus", account: false, ctas: 3, attended: 3, no_show: 0, cancelled: 0, reserve: 0, unmarked: 0, show_rate: 1, last_attended: "2026-10-08T18:00:00Z", first_seen: "2026-10-01T18:00:00Z",
                weapons: [{ weapon_id: "2H_LONGBOW", n: 3 }, { weapon_id: "MYSTERY", n: 1 }] },
              { name: "Res", account: true, ctas: 1, attended: 0, no_show: 0, cancelled: 0, reserve: 1, unmarked: 0, show_rate: null, weapons: [] }],
    ctas: [{ name: "First", content: "castle", planned_size: 20, starts_at: "2026-10-01T18:00:00Z", slots: 4, claimed: 3, attended: 2, no_show: 1, unmarked: 0, cancelled: 0, reserve: 1 }]
  };
  const players = run("historySheetRows")("players", facts, CATALOG);
  check("the players sheet: a header, one row per player in the table's order with the measures, the regular mark and the weapons played",
        same(players, [["Player", "Account", "CTAs", "Attended", "No-show", "Cancelled", "Reserve", "Unmarked", "Show rate", "Regular", "Last attended", "First seen", "Played"],
                       ["Gus", "guest", 3, 3, 0, 0, 0, 0, "100%", "yes", "2026-10-08T18:00:00Z", "2026-10-01T18:00:00Z", "Longbow ×3; MYSTERY ×1"],
                       ["Res", "yes", 1, 0, 0, 0, 1, 0, "", "", "", "", ""]]), players);
  const ctas = run("historySheetRows")("ctas", facts, CATALOG);
  check("the CTAs sheet: a header, one row per completed CTA with its fill and counts",
        same(ctas, [["CTA", "Content", "Planned", "Starts (UTC)", "Slots", "Claimed", "Fill", "Attended", "No-show", "Unmarked", "Cancelled", "Reserve"],
                    ["First", "castle", 20, "2026-10-01T18:00:00Z", 4, 3, "75%", 2, 1, 0, 0, 1]]), ctas);
  check("no facts is a header alone", run("historySheetRows")("players", null, CATALOG).length === 1 && run("historySheetRows")("ctas", {}, CATALOG).length === 1);
}

/* 5 - the period: the last 30 days, the last 90 days, all time */
{
  const W = run("HISTORY_WINDOWS"), pick = run("historyWindow"), since = run("historySince"), note = run("historyWindowNote");
  check("the periods are the last 30 days, the last 90 days and all time, each named; all time is the default",
        same(W.map(w => `${w.key}:${w.days}`), ["30d:30", "90d:90", "all:null"]) && W.every(w => w.label)
        && run("HISTORY_WINDOW_DEFAULT") === "all" && pick("all").days === null);
  check("a key the dialog does not know reads as the default", pick("season").key === "all" && pick(null).key === "all" && pick(undefined).key === "all");
  const now = new Date("2026-10-08T12:00:00.000Z");
  check("a period starts that many days before now, as the instant the database compares a CTA's start with; all time has no start",
        since("30d", now) === "2026-09-08T12:00:00.000Z" && since("90d", now) === "2026-07-10T12:00:00.000Z"
        && since("all", now) === null && since("season", now) === null, [since("30d", now), since("90d", now)]);
  const n30 = note("30d", since("30d", now), now), nAll = note("all", null, now);
  check("the dialog says which period it reads: the period and the day it starts, or every completed CTA",
        /last 30 days/.test(n30) && n30.includes(run("historyDateLabel")(since("30d", now), now)) && /Every completed CTA/.test(nAll), [n30, nAll]);
  const src = fs.readFileSync(path.join(DASH, "_history.js"), "utf8");
  check("the period is offered from the list, read again on a change, remembered per browser, named in the empty state, the totals and the export",
        /HISTORY_WINDOWS\.map\(w =>/.test(src) && /el\.window\.addEventListener\("change"/.test(src)
        && /localStorage\.setItem\(HISTORY_WINDOW_KEY, windowKey\)/.test(src) && /No completed CTA started in the \$\{period\.label\.toLowerCase\(\)\}/.test(src)
        && /el\.totals\.setAttribute\("aria-label"/.test(src) && /players\$\{periodName\(\)\}/.test(src)
        && /loadGuildHistory\(guildId\(\), since\)/.test(src));
}

/* ---- a table's date is the day alone; the time lives in the title ---- */
{
  const label = run("historyDateLabel");
  const now = new Date("2026-10-03T12:00:00Z");
  const day = label("2026-10-01T12:00:00Z", now);
  check("a date cell reads the day alone: no clock time, no UTC, no year inside the current year",
        day && !/\d{1,2}:\d{2}/.test(day) && !/UTC/.test(day) && !/2026/.test(day) && /1/.test(day), day);
  check("a date in another year carries the year", /2025/.test(label("2025-06-15T12:00:00Z", now)), label("2025-06-15T12:00:00Z", now));
  check("no date is an empty label", label("", now) === "" && label("not a date", now) === "");
}

console.log(`\n${pass}/${pass + fail} history tests passed`);
process.exit(fail ? 1 : 0);
})();
